"""
Dashboard route - main overview page.
"""

from datetime import date

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pathlib import Path

from app.database import get_db
from app.models import Season, WeekAssignment, Week, Bet, PlayerSeason
from app import calculations


def is_season_frozen(season: Season) -> bool:
    """Check if a season is frozen (end date has passed)."""
    if not season or not season.end_date:
        return False
    return date.today() > season.end_date

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Main dashboard showing syndicate overview.
    """
    # Get active season
    season = db.query(Season).filter(Season.is_active == True).first()

    if not season:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "season": None,
            "error": "No active season found. Please create a season first."
        })

    # Calculate all metrics from ledger
    bank_balance = calculations.get_syndicate_balance(db, season.id)
    total_contributions = calculations.get_season_total_contributions(db, season.id)
    total_bets_placed = calculations.get_season_total_bets_placed(db, season.id)
    total_winnings = calculations.get_season_total_winnings(db, season.id)
    profit_loss = calculations.get_season_profit_loss(db, season.id)
    profit_percentage = calculations.get_season_profit_percentage(db, season.id)
    expected_per_player = calculations.get_expected_contribution_per_player(db, season.id)
    share_per_player = calculations.get_share_per_player(db, season.id)

    # Get player performance stats
    player_stats = calculations.get_player_performance_stats(db, season.id)

    # Get current week's assigned players (based on today's date)
    today = date.today()
    current_week = db.query(Week).filter(
        and_(
            Week.season_id == season.id,
            Week.start_date <= today,
            Week.end_date >= today
        )
    ).first()

    assigned_players = []
    if current_week:
        assignments = db.query(WeekAssignment).filter(
            WeekAssignment.week_id == current_week.id
        ).order_by(WeekAssignment.assignment_order).all()
        for assignment in assignments:
            assigned_players.append(assignment.player.name)

    # Get recent bets
    recent_bets = db.query(Bet).order_by(
        Bet.bet_date.desc()
    ).limit(10).all()

    # Calculate number of active players
    num_active_players = db.query(PlayerSeason).filter(
        PlayerSeason.season_id == season.id,
        PlayerSeason.is_active == True
    ).count()

    # Bet amount per person
    bet_amount_per_person = total_bets_placed / num_active_players if num_active_players > 0 else 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "season": season,
        "is_frozen": is_season_frozen(season),
        "bank_balance": bank_balance,
        "total_contributions": total_contributions,
        "total_bets_placed": total_bets_placed,
        "total_winnings": total_winnings,
        "profit_loss": profit_loss,
        "profit_percentage": profit_percentage,
        "expected_per_player": expected_per_player,
        "share_per_player": share_per_player,
        "bet_amount_per_person": bet_amount_per_person,
        "player_stats": player_stats,
        "assigned_players": assigned_players,
        "current_week": current_week,
        "recent_bets": recent_bets,
        "num_active_players": num_active_players
    })


@router.get("/summary", response_class=HTMLResponse)
async def screenshot_summary(request: Request, db: Session = Depends(get_db)):
    """
    Compact summary page optimized for WhatsApp screenshot sharing.
    Shows: payout per player, winnings ranking, bet balances, week assignments, who owes money.
    """
    # Get active season
    season = db.query(Season).filter(Season.is_active).first()

    if not season:
        return templates.TemplateResponse("summary.html", {
            "request": request,
            "season": None,
            "error": "No active season found."
        })

    # Calculate metrics
    bank_balance = calculations.get_syndicate_balance(db, season.id)
    share_per_player = calculations.get_share_per_player(db, season.id)
    expected_per_player = calculations.get_expected_contribution_per_player(db, season.id)
    profit_loss = calculations.get_season_profit_loss(db, season.id)
    profit_percentage = calculations.get_season_profit_percentage(db, season.id)

    # Get player stats with additional info for who owes money
    player_stats = calculations.get_player_performance_stats(db, season.id)

    # Add "owes" calculation and convert Decimals to floats for JSON serialization
    for stat in player_stats:
        # Convert Decimals to floats
        stat['balance'] = float(stat['balance'])
        stat['bets_placed'] = float(stat['bets_placed'])
        stat['bet_balance'] = float(stat['bet_balance'])
        stat['won'] = float(stat['won'])
        stat['profit_loss'] = float(stat['profit_loss'])

        # How much they've actually paid
        paid = stat['balance']
        # How much they should have paid
        expected = float(expected_per_player)
        # Difference (positive = owes money)
        stat['owes'] = expected - paid if expected > paid else 0
        stat['expected'] = expected

    # Sort by profit_loss for ranking (already sorted)
    # Players with bet_balance > 0 have money to spend

    # Get current week's assigned players
    today = date.today()
    current_week = db.query(Week).filter(
        Week.season_id == season.id,
        Week.start_date <= today,
        Week.end_date >= today
    ).first()

    assigned_players = []
    if current_week:
        assignments = db.query(WeekAssignment).filter(
            WeekAssignment.week_id == current_week.id
        ).order_by(WeekAssignment.assignment_order).all()
        for assignment in assignments:
            assigned_players.append(assignment.player.name)

    # Count weeks elapsed
    weeks_elapsed = calculations.count_mondays_since(season.start_date, today)

    return templates.TemplateResponse("summary.html", {
        "request": request,
        "season": season,
        "bank_balance": float(bank_balance),
        "share_per_player": float(share_per_player),
        "expected_per_player": float(expected_per_player),
        "profit_loss": float(profit_loss),
        "profit_percentage": float(profit_percentage),
        "player_stats": player_stats,
        "assigned_players": assigned_players,
        "current_week": current_week,
        "weeks_elapsed": weeks_elapsed,
        "today": today
    })
