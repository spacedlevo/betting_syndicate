"""
Core ledger service - single point of entry for ALL financial operations.

This module implements the ledger-based accounting model where all financial
activity is recorded as immutable ledger entries.

CRITICAL RULES:
1. Ledger entries are IMMUTABLE - never update, only insert
2. All operations must use database transactions
3. Validate amount signs (positive for money IN, negative for money OUT)

Note: Equal share of winnings per player is calculated dynamically as:
      Total Winnings / Number of Active Players
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from app.models import LedgerEntry, PlayerSeason, Player, Bet
from app import models


def get_active_players_in_season(db: Session, season_id: int) -> List[models.Player]:
    """
    Get all active players in a season.

    Args:
        db: Database session
        season_id: Season ID

    Returns:
        List of active Player objects
    """
    active_player_seasons = db.query(PlayerSeason).filter(
        and_(
            PlayerSeason.season_id == season_id,
            PlayerSeason.is_active == True
        )
    ).all()

    player_ids = [ps.player_id for ps in active_player_seasons]

    players = db.query(Player).filter(
        and_(
            Player.id.in_(player_ids),
            Player.is_active == True
        )
    ).all()

    return players


def add_contribution(
    db: Session,
    player_id: int,
    season_id: int,
    amount: Decimal,
    entry_date: date,
    week_id: Optional[int] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> LedgerEntry:
    """
    Record a player's contribution to the syndicate.

    Creates a ledger entry with positive amount (money IN).

    Args:
        db: Database session
        player_id: Player making the contribution
        season_id: Current season
        amount: Contribution amount (should be positive, e.g., 5.00)
        entry_date: Date of contribution
        week_id: Optional week ID
        description: Optional description
        created_by: Optional user who created the entry

    Returns:
        Created LedgerEntry

    Raises:
        ValueError: If amount is negative or zero
    """
    if amount <= 0:
        raise ValueError("Contribution amount must be positive")

    entry = LedgerEntry(
        entry_date=entry_date,
        entry_type='contribution',
        player_id=player_id,
        season_id=season_id,
        week_id=week_id,
        amount=amount,
        description=description or f"Weekly contribution",
        bet_id=None,
        created_by=created_by
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


def record_bet_placed(
    db: Session,
    bet_id: int,
    player_id: int,
    season_id: int,
    week_id: int,
    stake: Decimal,
    entry_date: date,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> LedgerEntry:
    """
    Record a bet being placed.

    Creates a ledger entry with negative amount (money OUT to bookmaker).

    Args:
        db: Database session
        bet_id: Bet ID
        player_id: Player who placed the bet
        season_id: Current season
        week_id: Week ID
        stake: Bet stake (positive value, will be negated)
        entry_date: Date bet was placed
        description: Optional description
        created_by: Optional user who created the entry

    Returns:
        Created LedgerEntry

    Raises:
        ValueError: If stake is negative or zero
    """
    if stake <= 0:
        raise ValueError("Bet stake must be positive")

    entry = LedgerEntry(
        entry_date=entry_date,
        entry_type='bet_placed',
        player_id=player_id,
        season_id=season_id,
        week_id=week_id,
        amount=-stake,  # Negative because money is going OUT
        description=description or f"Bet placed",
        bet_id=bet_id,
        created_by=created_by
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


def record_bet_won(
    db: Session,
    bet_id: int,
    player_id: int,
    season_id: int,
    winnings: Decimal,
    entry_date: date,
    week_id: Optional[int] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> LedgerEntry:
    """
    Record a bet win.

    Creates a single ledger entry crediting the player who placed the winning bet.
    Equal share per player is calculated dynamically as: total_winnings / num_players

    Args:
        db: Database session
        bet_id: Bet ID that won
        player_id: Player who placed the winning bet
        season_id: Current season
        winnings: Total winnings (stake + profit)
        entry_date: Date bet was settled
        week_id: Optional week ID
        description: Optional description
        created_by: Optional user who created the entry

    Returns:
        Created LedgerEntry

    Raises:
        ValueError: If winnings is negative or zero
    """
    if winnings <= 0:
        raise ValueError("Winnings must be positive")

    entry = LedgerEntry(
        entry_date=entry_date,
        entry_type='winnings',
        player_id=player_id,
        season_id=season_id,
        week_id=week_id,
        amount=winnings,  # Positive because money is coming IN
        description=description or f"Bet won",
        bet_id=bet_id,
        created_by=created_by
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


def record_bet_void(
    db: Session,
    bet_id: int,
    player_id: int,
    season_id: int,
    week_id: int,
    stake: Decimal,
    entry_date: date,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> LedgerEntry:
    """
    Record a void bet and return the stake to the syndicate.

    Creates a ledger entry with positive amount (money returns).

    Args:
        db: Database session
        bet_id: Bet ID that was voided
        player_id: Player who placed the bet
        season_id: Current season
        week_id: Week ID
        stake: Bet stake being returned (positive value)
        entry_date: Date bet was voided
        description: Optional description
        created_by: Optional user who created the entry

    Returns:
        Created LedgerEntry

    Raises:
        ValueError: If stake is negative or zero
    """
    if stake <= 0:
        raise ValueError("Bet stake must be positive")

    entry = LedgerEntry(
        entry_date=entry_date,
        entry_type='bet_void',
        player_id=player_id,
        season_id=season_id,
        week_id=week_id,
        amount=stake,  # Positive because money is returning
        description=description or f"Bet voided, stake returned",
        bet_id=bet_id,
        created_by=created_by
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


def record_payout(
    db: Session,
    player_id: int,
    season_id: int,
    amount: Decimal,
    entry_date: date,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> LedgerEntry:
    """
    Record a payout to a player (withdrawal from syndicate).

    Creates a ledger entry with negative amount (money OUT).

    Args:
        db: Database session
        player_id: Player receiving the payout
        season_id: Current season
        amount: Payout amount (positive value, will be negated)
        entry_date: Date of payout
        description: Optional description
        created_by: Optional user who created the entry

    Returns:
        Created LedgerEntry

    Raises:
        ValueError: If amount is negative or zero
    """
    if amount <= 0:
        raise ValueError("Payout amount must be positive")

    entry = LedgerEntry(
        entry_date=entry_date,
        entry_type='payout',
        player_id=player_id,
        season_id=season_id,
        week_id=None,
        amount=-amount,  # Negative because money is going OUT
        description=description or f"Payout to player",
        bet_id=None,
        created_by=created_by
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return entry


def get_ledger_entries(
    db: Session,
    season_id: Optional[int] = None,
    player_id: Optional[int] = None,
    entry_type: Optional[str] = None,
    bet_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0
) -> List[LedgerEntry]:
    """
    Query ledger entries with optional filters.

    Args:
        db: Database session
        season_id: Filter by season
        player_id: Filter by player
        entry_type: Filter by entry type
        bet_id: Filter by bet
        limit: Maximum number of entries to return
        offset: Number of entries to skip

    Returns:
        List of LedgerEntry objects ordered by entry_date desc
    """
    query = db.query(LedgerEntry)

    if season_id is not None:
        query = query.filter(LedgerEntry.season_id == season_id)

    if player_id is not None:
        query = query.filter(LedgerEntry.player_id == player_id)

    if entry_type is not None:
        query = query.filter(LedgerEntry.entry_type == entry_type)

    if bet_id is not None:
        query = query.filter(LedgerEntry.bet_id == bet_id)

    query = query.order_by(LedgerEntry.entry_date.desc(), LedgerEntry.created_at.desc())

    if offset:
        query = query.offset(offset)

    if limit:
        query = query.limit(limit)

    return query.all()
