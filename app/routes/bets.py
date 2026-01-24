"""
Bet management routes.
"""

import os
import uuid
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from decimal import Decimal

from app.database import get_db
from app.models import Bet, Player, PlayerSeason, Season, Week, LedgerEntry, Sport
from app import ledger


def is_season_frozen(season: Season) -> bool:
    """Check if a season is frozen (end date has passed)."""
    if not season or not season.end_date:
        return False
    return date.today() > season.end_date

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# Upload directory for screenshots
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "screenshots"


async def save_screenshot(file: UploadFile) -> str:
    """Save uploaded screenshot and return the filename."""
    if not file or not file.filename:
        return None

    # Generate unique filename
    ext = Path(file.filename).suffix.lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return None

    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename

    # Save file
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    return filename


@router.get("/", response_class=HTMLResponse)
async def list_bets(
    request: Request,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all bets with optional status filter."""
    season = db.query(Season).filter(Season.is_active == True).first()

    query = db.query(Bet).order_by(Bet.bet_date.desc())

    if status:
        query = query.filter(Bet.status == status)

    bets = query.limit(100).all()

    return templates.TemplateResponse("bets/list.html", {
        "request": request,
        "bets": bets,
        "season": season,
        "current_status": status
    })


@router.get("/new", response_class=HTMLResponse)
async def new_bet_form(request: Request, db: Session = Depends(get_db)):
    """Show form to place a new bet."""
    season = db.query(Season).filter(Season.is_active == True).first()

    # Check if season is frozen
    if season and is_season_frozen(season):
        return templates.TemplateResponse("bets/frozen.html", {
            "request": request,
            "season": season
        })

    # Get active players in season
    players = []
    if season:
        player_seasons = db.query(PlayerSeason).filter(
            PlayerSeason.season_id == season.id,
            PlayerSeason.is_active == True
        ).all()
        players = [ps.player for ps in player_seasons]

    # Get all sports
    sports = db.query(Sport).order_by(Sport.name).all()

    return templates.TemplateResponse("bets/form.html", {
        "request": request,
        "bet": None,
        "players": players,
        "season": season,
        "sports": sports
    })


@router.post("/")
async def create_bet(
    request: Request,
    placed_by_player_id: int = Form(...),
    stake: Decimal = Form(...),
    description: str = Form(...),
    odds: str = Form(None),
    sport_id: int = Form(None),
    bet_date: date = Form(...),
    screenshot: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Create a new bet and record it in the ledger."""
    season = db.query(Season).filter(Season.is_active == True).first()
    if not season:
        return RedirectResponse(url="/bets", status_code=303)

    # Save screenshot if provided
    screenshot_filename = None
    if screenshot and screenshot.filename:
        screenshot_filename = await save_screenshot(screenshot)

    # Create bet record
    bet = Bet(
        week_id=None,
        placed_by_player_id=placed_by_player_id,
        stake=stake,
        description=description,
        odds=odds if odds else None,
        sport_id=sport_id if sport_id else None,
        bet_date=bet_date,
        status='pending',
        screenshot=screenshot_filename
    )
    db.add(bet)
    db.flush()

    # Create ledger entry for bet placed
    ledger.record_bet_placed(
        db,
        bet_id=bet.id,
        player_id=placed_by_player_id,
        season_id=season.id,
        week_id=None,
        stake=stake,
        entry_date=bet_date
    )

    return RedirectResponse(url="/bets", status_code=303)


@router.get("/{bet_id}", response_class=HTMLResponse)
async def bet_detail(bet_id: int, request: Request, db: Session = Depends(get_db)):
    """Show bet details."""
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        return RedirectResponse(url="/bets", status_code=303)

    # Get related ledger entries
    ledger_entries = db.query(LedgerEntry).filter(
        LedgerEntry.bet_id == bet_id
    ).order_by(LedgerEntry.entry_date).all()

    return templates.TemplateResponse("bets/detail.html", {
        "request": request,
        "bet": bet,
        "ledger_entries": ledger_entries
    })


@router.get("/{bet_id}/result", response_class=HTMLResponse)
async def update_result_form(bet_id: int, request: Request, db: Session = Depends(get_db)):
    """Show form to update bet result."""
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        return RedirectResponse(url="/bets", status_code=303)

    return templates.TemplateResponse("bets/update_result.html", {
        "request": request,
        "bet": bet
    })


@router.post("/{bet_id}/result")
async def update_result(
    bet_id: int,
    status: str = Form(...),
    result_date: date = Form(...),
    winnings: Decimal = Form(None),
    db: Session = Depends(get_db)
):
    """Update bet result and create appropriate ledger entries."""
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        return RedirectResponse(url="/bets", status_code=303)

    season = db.query(Season).filter(Season.is_active == True).first()
    if not season:
        return RedirectResponse(url="/bets", status_code=303)

    # Update bet record
    bet.status = status
    bet.result_date = result_date

    if status == 'won':
        bet.winnings = winnings
        # Record winnings for the player who placed the bet
        ledger.record_bet_won(
            db,
            bet_id=bet.id,
            player_id=bet.placed_by_player_id,
            season_id=season.id,
            winnings=winnings,
            entry_date=result_date,
            week_id=None
        )
    elif status == 'void':
        # Return stake to syndicate
        ledger.record_bet_void(
            db,
            bet_id=bet.id,
            player_id=bet.placed_by_player_id,
            season_id=season.id,
            week_id=None,
            stake=bet.stake,
            entry_date=result_date
        )
    # For 'lost', no ledger entry needed - money already left via bet_placed

    db.commit()
    return RedirectResponse(url="/bets", status_code=303)


@router.post("/{bet_id}/screenshot")
async def upload_screenshot(
    bet_id: int,
    screenshot: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a screenshot for an existing bet."""
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        return RedirectResponse(url="/bets", status_code=303)

    # Delete old screenshot if exists
    if bet.screenshot:
        old_path = UPLOAD_DIR / bet.screenshot
        if old_path.exists():
            old_path.unlink()

    # Save new screenshot
    if screenshot and screenshot.filename:
        filename = await save_screenshot(screenshot)
        bet.screenshot = filename
        db.commit()

    return RedirectResponse(url=f"/bets/{bet_id}", status_code=303)
