"""
Ledger routes for viewing transactions and adding contributions.
"""

from typing import Optional
import io
import csv

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from decimal import Decimal

from app.database import get_db
from app.models import LedgerEntry, Player, PlayerSeason, Season
from app import ledger
from app.flash import set_flash

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def is_season_frozen(season: Season) -> bool:
    """Check if a season is frozen (end date has passed)."""
    if not season or not season.end_date:
        return False
    return date.today() > season.end_date


@router.get("/", response_class=HTMLResponse)
async def list_ledger(
    request: Request,
    player_id: Optional[str] = None,
    entry_type: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """List ledger entries with optional filters."""
    season = db.query(Season).filter(Season.is_active == True).first()

    query = db.query(LedgerEntry)

    if season:
        query = query.filter(LedgerEntry.season_id == season.id)

    # Handle empty string from form (when "All players" is selected)
    if player_id and player_id.strip():
        query = query.filter(LedgerEntry.player_id == int(player_id))

    if entry_type and entry_type.strip():
        query = query.filter(LedgerEntry.entry_type == entry_type)

    # Pagination
    per_page = 50
    offset = (page - 1) * per_page

    total = query.count()
    entries = query.order_by(
        LedgerEntry.entry_date.desc(),
        LedgerEntry.created_at.desc()
    ).offset(offset).limit(per_page).all()

    # Get players for filter dropdown
    players = db.query(Player).filter(Player.is_active == True).order_by(Player.name).all()

    # Get all seasons for download dropdown
    all_seasons = db.query(Season).order_by(Season.start_date.desc()).all()

    # Entry types for filter
    entry_types = ['contribution', 'bet_placed', 'winnings', 'bet_void', 'payout']

    # Convert player_id to int for template comparison, or None if empty
    current_player_id = int(player_id) if player_id and player_id.strip() else None
    current_entry_type = entry_type if entry_type and entry_type.strip() else None

    return templates.TemplateResponse("ledger/list.html", {
        "request": request,
        "entries": entries,
        "players": players,
        "entry_types": entry_types,
        "current_player_id": current_player_id,
        "current_entry_type": current_entry_type,
        "page": page,
        "total": total,
        "per_page": per_page,
        "season": season,
        "all_seasons": all_seasons
    })


@router.get("/contribute", response_class=HTMLResponse)
async def contribution_form(request: Request, db: Session = Depends(get_db)):
    """Show form to add contributions."""
    season = db.query(Season).filter(Season.is_active == True).first()

    # Check if season is frozen
    if season and is_season_frozen(season):
        return templates.TemplateResponse("ledger/frozen.html", {
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

    return templates.TemplateResponse("ledger/add_contribution.html", {
        "request": request,
        "players": players,
        "season": season,
        "default_amount": Decimal('5.00')
    })


@router.post("/contribute")
async def add_contribution(
    request: Request,
    player_id: int = Form(...),
    amount: Decimal = Form(...),
    entry_date: date = Form(...),
    db: Session = Depends(get_db)
):
    """Add a contribution for a single player."""
    season = db.query(Season).filter(Season.is_active == True).first()
    if not season:
        return RedirectResponse(url="/ledger/contribute", status_code=303)

    ledger.add_contribution(
        db,
        player_id=player_id,
        season_id=season.id,
        amount=amount,
        entry_date=entry_date
    )

    set_flash(request, "Contribution added.")
    return RedirectResponse(url="/", status_code=303)


@router.get("/payout", response_class=HTMLResponse)
async def payout_form(request: Request, db: Session = Depends(get_db)):
    """Show form to record a payout."""
    season = db.query(Season).filter(Season.is_active == True).first()

    # Get active players in season
    players = []
    if season:
        player_seasons = db.query(PlayerSeason).filter(
            PlayerSeason.season_id == season.id,
            PlayerSeason.is_active == True
        ).all()
        players = [ps.player for ps in player_seasons]

    return templates.TemplateResponse("ledger/payout.html", {
        "request": request,
        "players": players,
        "season": season
    })


@router.post("/payout")
async def add_payout(
    request: Request,
    player_id: int = Form(...),
    amount: Decimal = Form(...),
    entry_date: date = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    """Record a payout to a player."""
    season = db.query(Season).filter(Season.is_active == True).first()
    if not season:
        return RedirectResponse(url="/ledger/payout", status_code=303)

    ledger.record_payout(
        db,
        player_id=player_id,
        season_id=season.id,
        amount=amount,
        entry_date=entry_date,
        description=description
    )

    set_flash(request, f"Payout of £{amount:.2f} recorded.")
    return RedirectResponse(url="/", status_code=303)


@router.get("/download-csv")
async def download_ledger_csv(
    season_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Download ledger entries for a season as CSV."""
    
    # If no season specified, use active season
    if season_id:
        season = db.query(Season).filter(Season.id == season_id).first()
    else:
        season = db.query(Season).filter(Season.is_active == True).first()
    
    if not season:
        # Return empty CSV if no season found
        season_name = "No_Season"
        entries = []
    else:
        season_name = season.name.replace(" ", "_").replace("/", "-")
        # Get all ledger entries for the season
        entries = db.query(LedgerEntry).filter(
            LedgerEntry.season_id == season.id
        ).order_by(
            LedgerEntry.entry_date.asc(),
            LedgerEntry.created_at.asc()
        ).all()
    
    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date',
        'Entry Type',
        'Player',
        'Amount',
        'Description',
        'Bet ID',
        'Week',
        'Created At',
        'Created By'
    ])
    
    # Write data rows
    for entry in entries:
        writer.writerow([
            entry.entry_date.strftime('%Y-%m-%d'),
            entry.entry_type,
            entry.player.name if entry.player else '',
            str(entry.amount),
            entry.description or '',
            entry.bet_id or '',
            f"Week {entry.week.week_number}" if entry.week else '',
            entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            entry.created_by or ''
        ])
    
    # Get the CSV content
    csv_content = output.getvalue()
    output.close()
    
    # Create filename with season name and date
    filename = f"ledger_{season_name}_{date.today().strftime('%Y%m%d')}.csv"
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
