"""
Calculations module - derive ALL values from the ledger.

All balances, totals, and statistics are calculated from the ledger table
using SQL aggregations. NO stored balances.

This ensures complete auditability and traceability.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any

from app.models import LedgerEntry, Player, PlayerSeason, Season, Bet, Week


def get_syndicate_balance(db: Session, season_id: Optional[int] = None) -> Decimal:
    """
    Calculate current syndicate bank balance.

    Formula: (Paid In + Bets Won) - Bets Placed - Paid Out

    Args:
        db: Database session
        season_id: Optional season filter (if None, calculates across all seasons)

    Returns:
        Current balance as Decimal
    """
    # Get contributions (paid in)
    contributions_query = db.query(func.sum(LedgerEntry.amount)).filter(
        LedgerEntry.entry_type == 'contribution'
    )
    if season_id is not None:
        contributions_query = contributions_query.filter(LedgerEntry.season_id == season_id)
    paid_in = contributions_query.scalar() or Decimal('0.00')

    # Get winnings (bets won)
    winnings_query = db.query(func.sum(LedgerEntry.amount)).filter(
        LedgerEntry.entry_type == 'winnings'
    )
    if season_id is not None:
        winnings_query = winnings_query.filter(LedgerEntry.season_id == season_id)
    bets_won = winnings_query.scalar() or Decimal('0.00')

    # Get bets placed (stored as negative, so use abs)
    bets_query = db.query(func.sum(func.abs(LedgerEntry.amount))).filter(
        LedgerEntry.entry_type == 'bet_placed'
    )
    if season_id is not None:
        bets_query = bets_query.filter(LedgerEntry.season_id == season_id)
    bets_placed = bets_query.scalar() or Decimal('0.00')

    # Get payouts (stored as negative, so use abs)
    payouts_query = db.query(func.sum(func.abs(LedgerEntry.amount))).filter(
        LedgerEntry.entry_type == 'payout'
    )
    if season_id is not None:
        payouts_query = payouts_query.filter(LedgerEntry.season_id == season_id)
    paid_out = payouts_query.scalar() or Decimal('0.00')

    # Bank Balance = (Paid In + Bets Won) - Bets Placed - Paid Out
    balance = (Decimal(str(paid_in)) + Decimal(str(bets_won))) - Decimal(str(bets_placed)) - Decimal(str(paid_out))
    return balance


def get_player_total_contributions(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate total contributions by a player.

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Total contributions as Decimal
    """
    query = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.player_id == player_id,
            LedgerEntry.entry_type == 'contribution'
        )
    )

    if season_id is not None:
        query = query.filter(LedgerEntry.season_id == season_id)

    result = query.scalar()
    return Decimal(result) if result else Decimal('0.00')


def get_player_total_bets(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate total amount bet by a player, excluding voided bets.

    This is the absolute value of all bet_placed entries minus any
    bet_void entries (voided stakes are returned and can be reused).

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Total bets placed as Decimal (excluding voided bets)
    """
    # Sum of bet_placed entries (stored as negative, so use abs)
    placed_query = db.query(func.sum(func.abs(LedgerEntry.amount))).filter(
        and_(
            LedgerEntry.player_id == player_id,
            LedgerEntry.entry_type == 'bet_placed'
        )
    )

    # Sum of bet_void entries (stored as positive)
    void_query = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.player_id == player_id,
            LedgerEntry.entry_type == 'bet_void'
        )
    )

    if season_id is not None:
        placed_query = placed_query.filter(LedgerEntry.season_id == season_id)
        void_query = void_query.filter(LedgerEntry.season_id == season_id)

    placed = placed_query.scalar()
    voided = void_query.scalar()

    total_placed = Decimal(placed) if placed else Decimal('0.00')
    total_voided = Decimal(voided) if voided else Decimal('0.00')

    return total_placed - total_voided


def get_player_total_winnings(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate total winnings from bets placed by a player.

    This is the sum of all 'winnings' entries for this player.

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Total winnings as Decimal
    """
    query = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.player_id == player_id,
            LedgerEntry.entry_type == 'winnings'
        )
    )

    if season_id is not None:
        query = query.filter(LedgerEntry.season_id == season_id)

    result = query.scalar()
    return Decimal(result) if result else Decimal('0.00')


def get_player_net_position(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate player's net position (contributions - payouts).

    This shows how much the player has "in" the syndicate.

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Net position as Decimal
    """
    query = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.player_id == player_id,
            LedgerEntry.entry_type.in_(['contribution', 'payout'])
        )
    )

    if season_id is not None:
        query = query.filter(LedgerEntry.season_id == season_id)

    result = query.scalar()
    return Decimal(result) if result else Decimal('0.00')


def get_player_profit_loss(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate player's profit/loss.

    This is winnings minus contributions.

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Profit/loss as Decimal (negative means player has lost)
    """
    winnings = get_player_total_winnings(db, player_id, season_id)
    contributions = get_player_total_contributions(db, player_id, season_id)
    return winnings - contributions


def get_season_total_contributions(db: Session, season_id: int) -> Decimal:
    """
    Calculate total contributions from all players for a season.

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Total contributions as Decimal
    """
    result = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.season_id == season_id,
            LedgerEntry.entry_type == 'contribution'
        )
    ).scalar()

    return Decimal(result) if result else Decimal('0.00')


def get_season_total_bets_placed(db: Session, season_id: int) -> Decimal:
    """
    Calculate total amount bet for a season, excluding voided bets.

    This is the absolute value of all bet_placed entries minus any
    bet_void entries (voided stakes are returned and can be reused).

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Total bets placed as Decimal (excluding voided bets)
    """
    # Sum of bet_placed entries (stored as negative, so use abs)
    placed = db.query(func.sum(func.abs(LedgerEntry.amount))).filter(
        and_(
            LedgerEntry.season_id == season_id,
            LedgerEntry.entry_type == 'bet_placed'
        )
    ).scalar()

    # Sum of bet_void entries (stored as positive)
    voided = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.season_id == season_id,
            LedgerEntry.entry_type == 'bet_void'
        )
    ).scalar()

    total_placed = Decimal(placed) if placed else Decimal('0.00')
    total_voided = Decimal(voided) if voided else Decimal('0.00')

    return total_placed - total_voided


def get_season_total_winnings(db: Session, season_id: int) -> Decimal:
    """
    Calculate total winnings for a season.

    This is the sum of all 'winnings' entries.

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Total winnings as Decimal
    """
    result = db.query(func.sum(LedgerEntry.amount)).filter(
        and_(
            LedgerEntry.season_id == season_id,
            LedgerEntry.entry_type == 'winnings'
        )
    ).scalar()

    return Decimal(result) if result else Decimal('0.00')


def get_season_profit_loss(db: Session, season_id: int) -> Decimal:
    """
    Calculate season profit/loss.

    This is total winnings minus total bets placed.

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Profit/loss as Decimal
    """
    winnings = get_season_total_winnings(db, season_id)
    bets_placed = get_season_total_bets_placed(db, season_id)
    return winnings - bets_placed


def get_season_profit_percentage(db: Session, season_id: int) -> Decimal:
    """
    Calculate season profit/loss percentage.

    Formula: (Profit/Loss ÷ Bets Placed) × 100

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Profit/loss percentage as Decimal
    """
    profit_loss = get_season_profit_loss(db, season_id)
    bets_placed = get_season_total_bets_placed(db, season_id)

    if bets_placed == 0:
        return Decimal('0.00')

    percentage = (profit_loss / bets_placed) * 100
    return Decimal(percentage).quantize(Decimal('0.01'))


def get_expected_contributions(db: Session, season_id: int, weekly_amount: Decimal = Decimal('5.00')) -> Decimal:
    """
    Calculate expected total contributions based on Mondays elapsed.

    Formula: mondays_elapsed × weekly_amount × number_of_active_players

    Args:
        db: Database session
        season_id: Season ID
        weekly_amount: Weekly contribution amount (default £5)

    Returns:
        Expected total contributions as Decimal
    """
    season = db.query(Season).filter(Season.id == season_id).first()
    if not season:
        return Decimal('0.00')

    # Count Mondays since season start
    weeks_elapsed = count_mondays_since(season.start_date, date.today())

    # Get number of active players
    active_players_count = db.query(PlayerSeason).filter(
        and_(
            PlayerSeason.season_id == season_id,
            PlayerSeason.is_active == True
        )
    ).count()

    expected = weeks_elapsed * weekly_amount * active_players_count
    return Decimal(expected).quantize(Decimal('0.01'))


def count_mondays_since(start_date: date, end_date: date) -> int:
    """
    Count the number of Mondays from start_date up to and including end_date.

    Each Monday represents a week where £5 is owed.

    Args:
        start_date: Season start date
        end_date: Current date

    Returns:
        Number of Mondays (weeks owed)
    """
    if end_date < start_date:
        return 0

    # Find the first Monday on or after start_date
    days_until_monday = (7 - start_date.weekday()) % 7  # weekday() returns 0 for Monday
    if start_date.weekday() == 0:  # If start_date is already Monday
        first_monday = start_date
    else:
        first_monday = start_date + timedelta(days=days_until_monday)

    # If first Monday is after end_date, no weeks owed yet
    if first_monday > end_date:
        return 0

    # Count Mondays from first_monday to end_date
    days_between = (end_date - first_monday).days
    mondays = (days_between // 7) + 1  # +1 to include the first Monday

    return mondays


def get_expected_contribution_per_player(
    db: Session,
    season_id: int,
    weekly_amount: Decimal = Decimal('5.00')
) -> Decimal:
    """
    Calculate expected contribution per player based on Mondays elapsed.

    Each Monday from the season start represents one week of £5 owed.

    Args:
        db: Database session
        season_id: Season ID
        weekly_amount: Weekly contribution amount (default £5)

    Returns:
        Expected contribution per player as Decimal
    """
    season = db.query(Season).filter(Season.id == season_id).first()
    if not season:
        return Decimal('0.00')

    # Count Mondays since season start
    weeks_elapsed = count_mondays_since(season.start_date, date.today())

    expected = weeks_elapsed * weekly_amount
    return Decimal(expected).quantize(Decimal('0.01'))


def get_share_per_player(db: Session, season_id: int) -> Decimal:
    """
    Calculate each player's share of the winnings.

    Formula: total_winnings ÷ number_of_active_players

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        Share per player as Decimal
    """
    total_winnings = get_season_total_winnings(db, season_id)

    active_players_count = db.query(PlayerSeason).filter(
        and_(
            PlayerSeason.season_id == season_id,
            PlayerSeason.is_active == True
        )
    ).count()

    if active_players_count == 0:
        return Decimal('0.00')

    share = total_winnings / active_players_count
    return Decimal(share).quantize(Decimal('0.01'))


def get_player_bet_balance(
    db: Session,
    player_id: int,
    season_id: Optional[int] = None
) -> Decimal:
    """
    Calculate the betting budget available for a player.

    Formula: ROUNDUP(weeks_since_start / 6) * 30 - bets_placed

    Every 6 weeks, each player gets £30 of betting budget.
    The available balance is this budget minus what they've already bet.

    Args:
        db: Database session
        player_id: Player ID
        season_id: Optional season filter

    Returns:
        Available betting balance as Decimal
    """
    import math

    # Get season start date
    if season_id is None:
        season = db.query(Season).filter(Season.is_active == True).first()
    else:
        season = db.query(Season).filter(Season.id == season_id).first()

    if not season:
        return Decimal('0.00')

    # Calculate weeks since start
    today = date.today()
    days_elapsed = (today - season.start_date).days
    weeks_elapsed = days_elapsed // 7

    # Calculate budget: ROUNDUP(weeks / 6) * 30
    budget = Decimal(math.ceil(weeks_elapsed / 6) * 30)

    # Get bets placed by this player
    bets_placed = get_player_total_bets(db, player_id, season_id)

    # Available balance = budget - bets placed
    return budget - bets_placed


def get_player_payout_amount(
    db: Session,
    player_id: int,
    season_id: int
) -> Decimal:
    """
    Calculate what a player would receive if cashing out now.

    Formula: player_contributions + share_of_current_profit

    Args:
        db: Database session
        player_id: Player ID
        season_id: Season ID

    Returns:
        Payout amount as Decimal
    """
    contributions = get_player_net_position(db, player_id, season_id)
    share = get_share_per_player(db, season_id)
    expected_per_player = get_expected_contribution_per_player(db, season_id)
    return (contributions - expected_per_player) + share


def get_player_performance_stats(
    db: Session,
    season_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get performance statistics for all players.

    Used for dashboard player table and bar chart.

    Args:
        db: Database session
        season_id: Optional season filter

    Returns:
        List of dicts with player stats:
        {
            'player_id': int,
            'player_name': str,
            'balance': Decimal,         # Net contributions (contributions - payouts)
            'bets_placed': Decimal,     # Total bets placed by this player
            'bet_balance': Decimal,     # Available betting budget
            'won': Decimal,             # Total winnings from bets this player placed
            'profit_loss': Decimal      # Won - Bets placed
        }
    """
    # Get all players
    query = db.query(Player).filter(Player.is_active == True)

    # Filter by season if provided
    if season_id is not None:
        active_player_ids = db.query(PlayerSeason.player_id).filter(
            and_(
                PlayerSeason.season_id == season_id,
                PlayerSeason.is_active == True
            )
        ).all()
        active_player_ids = [pid[0] for pid in active_player_ids]
        query = query.filter(Player.id.in_(active_player_ids))

    players = query.all()

    stats = []
    for player in players:
        # Balance = contributions - payouts (net amount player has "in" the syndicate)
        balance = get_player_net_position(db, player.id, season_id)
        bets_placed = get_player_total_bets(db, player.id, season_id)
        bet_balance = get_player_bet_balance(db, player.id, season_id)
        won = get_player_total_winnings(db, player.id, season_id)
        profit_loss = won - bets_placed

        stats.append({
            'player_id': player.id,
            'player_name': player.name,
            'balance': balance,
            'bets_placed': bets_placed,
            'bet_balance': bet_balance,
            'won': won,
            'profit_loss': profit_loss
        })

    # Sort by profit_loss descending (winners first)
    stats.sort(key=lambda x: x['profit_loss'], reverse=True)

    return stats
