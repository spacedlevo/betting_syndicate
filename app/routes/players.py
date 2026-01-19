"""
Player management routes.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date

from app.database import get_db
from app.models import Player, PlayerSeason, Season
from app import calculations

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def list_players(request: Request, db: Session = Depends(get_db)):
    """List all players with their stats."""
    # Get active season
    season = db.query(Season).filter(Season.is_active == True).first()

    players = db.query(Player).order_by(Player.name).all()

    # Get season-level values needed for payout calculation
    expected_per_player = calculations.get_expected_contribution_per_player(db, season.id) if season else 0
    share_per_player = calculations.get_share_per_player(db, season.id) if season else 0

    # Get stats for each player
    player_data = []
    for player in players:
        # Check if player is in active season
        in_season = False
        if season:
            ps = db.query(PlayerSeason).filter(
                PlayerSeason.player_id == player.id,
                PlayerSeason.season_id == season.id
            ).first()
            in_season = ps is not None and ps.is_active

        balance = calculations.get_player_net_position(db, player.id, season.id if season else None)
        # Calculate payout: balance - amount_owed + share_per_player
        payout = (balance - expected_per_player) + share_per_player

        stats = {
            'player': player,
            'in_season': in_season,
            'balance': balance,
            'bets_placed': calculations.get_player_total_bets(db, player.id, season.id if season else None),
            'bet_balance': calculations.get_player_bet_balance(db, player.id, season.id if season else None),
            'won': calculations.get_player_total_winnings(db, player.id, season.id if season else None),
            'profit_loss': calculations.get_player_profit_loss(db, player.id, season.id if season else None),
            'payout': payout
        }
        player_data.append(stats)

    return templates.TemplateResponse("players/list.html", {
        "request": request,
        "player_data": player_data,
        "season": season
    })


@router.get("/new", response_class=HTMLResponse)
async def new_player_form(request: Request, db: Session = Depends(get_db)):
    """Show form to create a new player."""
    season = db.query(Season).filter(Season.is_active == True).first()
    return templates.TemplateResponse("players/form.html", {
        "request": request,
        "player": None,
        "season": season
    })


@router.post("/")
async def create_player(
    request: Request,
    name: str = Form(...),
    email: str = Form(None),
    add_to_season: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Create a new player."""
    player = Player(
        name=name,
        email=email if email else None,
        is_active=True
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    # Add to active season if requested
    if add_to_season:
        season = db.query(Season).filter(Season.is_active == True).first()
        if season:
            ps = PlayerSeason(
                player_id=player.id,
                season_id=season.id,
                joined_date=date.today(),
                is_active=True
            )
            db.add(ps)
            db.commit()

    return RedirectResponse(url="/players", status_code=303)


@router.get("/{player_id}", response_class=HTMLResponse)
async def player_detail(player_id: int, request: Request, db: Session = Depends(get_db)):
    """Show player detail with full history."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return RedirectResponse(url="/players", status_code=303)

    season = db.query(Season).filter(Season.is_active == True).first()

    # Get player's ledger entries
    from app.models import LedgerEntry
    ledger_entries = db.query(LedgerEntry).filter(
        LedgerEntry.player_id == player_id
    ).order_by(LedgerEntry.entry_date.desc()).limit(50).all()

    # Get stats
    stats = {
        'balance': calculations.get_player_total_contributions(db, player_id, season.id if season else None),
        'bets_placed': calculations.get_player_total_bets(db, player_id, season.id if season else None),
        'bet_balance': calculations.get_player_bet_balance(db, player_id, season.id if season else None),
        'won': calculations.get_player_total_winnings(db, player_id, season.id if season else None),
        'profit_loss': calculations.get_player_profit_loss(db, player_id, season.id if season else None),
        'payout_amount': calculations.get_player_payout_amount(db, player_id, season.id) if season else 0
    }

    return templates.TemplateResponse("players/detail.html", {
        "request": request,
        "player": player,
        "stats": stats,
        "ledger_entries": ledger_entries,
        "season": season
    })


@router.post("/{player_id}/toggle")
async def toggle_player_season(player_id: int, db: Session = Depends(get_db)):
    """Toggle player's active status in current season."""
    season = db.query(Season).filter(Season.is_active == True).first()
    if not season:
        return RedirectResponse(url="/players", status_code=303)

    ps = db.query(PlayerSeason).filter(
        PlayerSeason.player_id == player_id,
        PlayerSeason.season_id == season.id
    ).first()

    if ps:
        ps.is_active = not ps.is_active
    else:
        # Add player to season
        ps = PlayerSeason(
            player_id=player_id,
            season_id=season.id,
            joined_date=date.today(),
            is_active=True
        )
        db.add(ps)

    db.commit()
    return RedirectResponse(url="/players", status_code=303)
