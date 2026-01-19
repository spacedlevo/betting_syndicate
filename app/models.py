"""
SQLAlchemy ORM models for the betting syndicate database.

This module defines all database tables using SQLAlchemy's declarative base.
The ledger table is the single source of truth for all financial activity.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Numeric,
    ForeignKey, UniqueConstraint, CheckConstraint, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Season(Base):
    """
    Represents a betting season/year.

    A season groups all activity for a given time period (e.g., "2025-2026 Season").
    Only one season should be active at a time.
    """
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "2025-2026 Season"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    player_seasons = relationship("PlayerSeason", back_populates="season")
    weeks = relationship("Week", back_populates="season")
    ledger_entries = relationship("LedgerEntry", back_populates="season")


class Player(Base):
    """
    Represents a player in the betting syndicate.

    Players can participate in multiple seasons.
    """
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    player_seasons = relationship("PlayerSeason", back_populates="player")
    placed_bets = relationship("Bet", back_populates="placed_by_player")
    ledger_entries = relationship("LedgerEntry", back_populates="player")
    week_assignments = relationship("WeekAssignment", back_populates="player")


class PlayerSeason(Base):
    """
    Many-to-many relationship between players and seasons.

    Tracks which players are active in which seasons.
    """
    __tablename__ = "player_seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    joined_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    player = relationship("Player", back_populates="player_seasons")
    season = relationship("Season", back_populates="player_seasons")

    # Constraints
    __table_args__ = (
        UniqueConstraint('player_id', 'season_id', name='uq_player_season'),
    )


class Week(Base):
    """
    Represents a weekly round within a season.

    Each week has a number (1, 2, 3, ...) and date range.
    """
    __tablename__ = "weeks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    season = relationship("Season", back_populates="weeks")
    assignments = relationship("WeekAssignment", back_populates="week")
    bets = relationship("Bet", back_populates="week")
    ledger_entries = relationship("LedgerEntry", back_populates="week")

    # Constraints
    __table_args__ = (
        UniqueConstraint('season_id', 'week_number', name='uq_season_week'),
    )


class WeekAssignment(Base):
    """
    Assigns two players to be responsible for betting each week.

    Each week should have exactly two players assigned (assignment_order 1 and 2).
    """
    __tablename__ = "week_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    assignment_order = Column(Integer, nullable=False)  # 1 or 2

    # Relationships
    week = relationship("Week", back_populates="assignments")
    player = relationship("Player", back_populates="week_assignments")

    # Constraints
    __table_args__ = (
        UniqueConstraint('week_id', 'player_id', name='uq_week_player'),
        UniqueConstraint('week_id', 'assignment_order', name='uq_week_order'),
        CheckConstraint('assignment_order IN (1, 2)', name='ck_assignment_order'),
    )


class LedgerEntry(Base):
    """
    The single source of truth for all financial activity.

    CRITICAL: This table is immutable - entries are never updated, only inserted.
    All balances and totals are calculated from this table.

    Entry Types:
        - 'contribution': Player pays weekly contribution (+£5)
        - 'bet_placed': Bet is placed (-stake), credited to player who placed it
        - 'winnings': Bet wins (+winnings), credited to player who placed it
        - 'bet_void': Bet is void, stake returned (+stake)
        - 'payout': Player withdraws from syndicate (-amount)

    Note: Equal share of winnings is calculated dynamically as:
          Total Winnings / Number of Active Players
    """
    __tablename__ = "ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_date = Column(Date, nullable=False)
    entry_type = Column(String(20), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)  # Positive for IN, negative for OUT
    description = Column(Text, nullable=True)
    bet_id = Column(Integer, ForeignKey("bets.id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)

    # Relationships
    player = relationship("Player", back_populates="ledger_entries")
    season = relationship("Season", back_populates="ledger_entries")
    week = relationship("Week", back_populates="ledger_entries")
    bet = relationship("Bet", back_populates="ledger_entries")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('contribution', 'bet_placed', 'winnings', 'bet_void', 'payout')",
            name='ck_entry_type'
        ),
    )


class Bet(Base):
    """
    Represents a bet placed by the syndicate.

    Financial impact is tracked in the ledger table, not here.
    This table stores metadata about the bet.

    Status values:
        - 'pending': Bet not yet settled
        - 'won': Bet won
        - 'lost': Bet lost
        - 'void': Bet cancelled/void
    """
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=True)  # Nullable for imported historical data
    placed_by_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    stake = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=False)
    odds = Column(String(50), nullable=True)  # e.g., "5/1", "2.5", "evens"
    bet_date = Column(Date, nullable=False)
    status = Column(String(20), default='pending', nullable=False)
    result_date = Column(Date, nullable=True)
    winnings = Column(Numeric(10, 2), nullable=True)  # Total return if won (stake + profit)
    notes = Column(Text, nullable=True)
    screenshot = Column(String(255), nullable=True)  # Path to screenshot file
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    week = relationship("Week", back_populates="bets")
    placed_by_player = relationship("Player", back_populates="placed_bets")
    ledger_entries = relationship("LedgerEntry", back_populates="bet")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'won', 'lost', 'void')",
            name='ck_bet_status'
        ),
        CheckConstraint('stake > 0', name='ck_positive_stake'),
    )
