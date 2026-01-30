"""
Dashboard route - main overview page.
"""

from datetime import date, timedelta
from decimal import Decimal

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


def _calc_potential_return(stake: float, odds: str, is_free_bet: bool) -> float | None:
    """Parse odds string and calculate potential return.

    Supports fractional (5/1), decimal (6.0), and 'evens'.
    For free bets the stake is not returned, only the profit.
    Returns None if odds cannot be parsed.
    """
    if not odds:
        return None
    odds = odds.strip().lower()
    try:
        if odds == "evens":
            decimal_odds = 2.0
        elif "/" in odds:
            num, den = odds.split("/", 1)
            decimal_odds = float(num) / float(den) + 1
        else:
            decimal_odds = float(odds)
            # If someone entered fractional value without slash (e.g. "5")
            # treat values >= 2 as already decimal, < 2 ambiguous but keep as-is
    except (ValueError, ZeroDivisionError):
        return None
    if is_free_bet:
        return round(stake * (decimal_odds - 1), 2)
    return round(stake * decimal_odds, 2)


@router.get("/weekly-bets", response_class=HTMLResponse)
async def weekly_bets(request: Request, db: Session = Depends(get_db)):
    """
    Screenshot-friendly page showing bets placed in the last 7 days.
    Optimized for WhatsApp sharing.
    """
    season = db.query(Season).filter(Season.is_active).first()

    if not season:
        return templates.TemplateResponse("weekly_bets.html", {
            "request": request,
            "season": None,
        })

    today = date.today()
    week_ago = today - timedelta(days=7)

    # Get bets from last 7 days
    bets = db.query(Bet).filter(
        Bet.bet_date >= week_ago
    ).order_by(Bet.bet_date.desc(), Bet.created_at.desc()).all()

    # Calculate summary stats
    total_staked = sum(float(b.stake) for b in bets)
    total_returned = sum(float(b.winnings or 0) for b in bets if b.status == 'won')
    won_count = sum(1 for b in bets if b.status == 'won')
    lost_count = sum(1 for b in bets if b.status == 'lost')
    pending_count = sum(1 for b in bets if b.status == 'pending')
    void_count = sum(1 for b in bets if b.status == 'void')
    net_pl = total_returned - total_staked

    # Build bet data with player names
    bet_data = []
    for b in bets:
        potential_return = _calc_potential_return(float(b.stake), b.odds, b.is_free_bet)
        bet_data.append({
            "description": b.description,
            "player_name": b.placed_by_player.name,
            "stake": float(b.stake),
            "odds": b.odds or "-",
            "status": b.status,
            "bet_date": b.bet_date,
            "winnings": float(b.winnings) if b.winnings else None,
            "is_free_bet": b.is_free_bet,
            "sport": b.sport.name if b.sport else None,
            "potential_return": potential_return,
        })

    # Total potential return from pending bets
    pending_potential = sum(
        b["potential_return"] for b in bet_data
        if b["status"] == "pending" and b["potential_return"] is not None
    )

    return templates.TemplateResponse("weekly_bets.html", {
        "request": request,
        "season": season,
        "bets": bet_data,
        "total_staked": total_staked,
        "total_returned": total_returned,
        "net_pl": net_pl,
        "pending_potential": pending_potential,
        "won_count": won_count,
        "lost_count": lost_count,
        "pending_count": pending_count,
        "void_count": void_count,
        "today": today,
        "week_ago": week_ago,
    })


@router.get("/schedule", response_class=HTMLResponse)
async def schedule(request: Request, db: Session = Depends(get_db)):
    """
    Screenshot-friendly page showing when each player's next betting week starts.
    Optimized for WhatsApp sharing.
    """
    season = db.query(Season).filter(Season.is_active).first()

    if not season:
        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "season": None,
        })

    today = date.today()

    # Get all active players in the season
    player_seasons = db.query(PlayerSeason).filter(
        PlayerSeason.season_id == season.id,
        PlayerSeason.is_active == True
    ).all()

    # Get all upcoming assignments (current week + future), ordered by date
    upcoming_assignments = db.query(WeekAssignment).join(Week).filter(
        Week.season_id == season.id,
        Week.end_date >= today,
    ).order_by(Week.start_date, WeekAssignment.assignment_order).all()

    # For each player, find their next assignment (first occurrence)
    player_next = {}
    for assignment in upcoming_assignments:
        if assignment.player_id not in player_next:
            player_next[assignment.player_id] = assignment

    # Build a mapping of week_id -> list of assigned player names (for partner lookup)
    week_players = {}
    for assignment in upcoming_assignments:
        wid = assignment.week_id
        if wid not in week_players:
            week_players[wid] = []
        week_players[wid].append({
            "player_id": assignment.player_id,
            "player_name": assignment.player.name,
        })

    # Build schedule data
    schedule_data = []
    for ps in player_seasons:
        player = ps.player
        next_assignment = player_next.get(player.id)

        if next_assignment:
            week = next_assignment.week
            is_current = week.start_date <= today <= week.end_date

            # Find partner name
            partners = week_players.get(week.id, [])
            partner_name = None
            for p in partners:
                if p["player_id"] != player.id:
                    partner_name = p["player_name"]
                    break

            schedule_data.append({
                "player_name": player.name,
                "week_start": week.start_date,
                "week_end": week.end_date,
                "week_number": week.week_number,
                "is_current": is_current,
                "partner_name": partner_name,
            })
        else:
            schedule_data.append({
                "player_name": player.name,
                "week_start": None,
                "week_end": None,
                "week_number": None,
                "is_current": False,
                "partner_name": None,
            })

    # Sort: current week first, then by start date, unassigned last
    schedule_data.sort(key=lambda x: (
        x["week_start"] is None,
        not x["is_current"],
        x["week_start"] or date.max,
    ))

    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "season": season,
        "schedule": schedule_data,
        "today": today,
    })
