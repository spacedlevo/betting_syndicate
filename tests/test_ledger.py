"""
Tests for the ledger module.

These tests verify the core ledger-based accounting logic, especially:
1. Correct ledger entry creation
2. Amount sign validation (positive for IN, negative for OUT)
3. Winnings distribution to all active players
4. Transaction integrity
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from decimal import Decimal

from app.database import Base
from app.models import Season, Player, PlayerSeason, Week, Bet
from app import ledger


# Test database setup
@pytest.fixture(scope="function")
def db_session():
    """Create a fresh test database for each test function."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_season(db_session):
    """Create a sample season."""
    season = Season(
        name="2025-2026 Test Season",
        start_date=date(2025, 8, 11),
        is_active=True
    )
    db_session.add(season)
    db_session.commit()
    db_session.refresh(season)
    return season


@pytest.fixture
def sample_players(db_session, sample_season):
    """Create sample players and assign them to the season."""
    players = []
    for i in range(1, 6):  # Create 5 players
        player = Player(
            name=f"Player {i}",
            email=f"player{i}@example.com",
            is_active=True
        )
        db_session.add(player)
        players.append(player)

    db_session.commit()

    # Assign all players to the season
    for player in players:
        db_session.refresh(player)
        ps = PlayerSeason(
            player_id=player.id,
            season_id=sample_season.id,
            joined_date=sample_season.start_date,
            is_active=True
        )
        db_session.add(ps)

    db_session.commit()
    return players


@pytest.fixture
def sample_week(db_session, sample_season):
    """Create a sample week."""
    week = Week(
        season_id=sample_season.id,
        week_number=1,
        start_date=date(2025, 8, 11),
        end_date=date(2025, 8, 17)
    )
    db_session.add(week)
    db_session.commit()
    db_session.refresh(week)
    return week


@pytest.fixture
def sample_bet(db_session, sample_week, sample_players):
    """Create a sample bet."""
    bet = Bet(
        week_id=sample_week.id,
        placed_by_player_id=sample_players[0].id,
        stake=Decimal('10.00'),
        description="Test bet",
        odds="5/1",
        bet_date=date(2025, 8, 12),
        status='pending'
    )
    db_session.add(bet)
    db_session.commit()
    db_session.refresh(bet)
    return bet


class TestAddContribution:
    """Tests for adding player contributions."""

    def test_add_contribution_creates_ledger_entry(self, db_session, sample_season, sample_players):
        """Test that adding a contribution creates a ledger entry with correct values."""
        player = sample_players[0]

        entry = ledger.add_contribution(
            db_session,
            player_id=player.id,
            season_id=sample_season.id,
            amount=Decimal('5.00'),
            entry_date=date(2025, 8, 11)
        )

        assert entry.id is not None
        assert entry.entry_type == 'contribution'
        assert entry.player_id == player.id
        assert entry.season_id == sample_season.id
        assert entry.amount == Decimal('5.00')
        assert entry.entry_date == date(2025, 8, 11)

    def test_add_contribution_positive_amount(self, db_session, sample_season, sample_players):
        """Test that contributions have positive amounts (money IN)."""
        player = sample_players[0]

        entry = ledger.add_contribution(
            db_session,
            player_id=player.id,
            season_id=sample_season.id,
            amount=Decimal('5.00'),
            entry_date=date(2025, 8, 11)
        )

        assert entry.amount > 0

    def test_add_contribution_negative_amount_raises_error(self, db_session, sample_season, sample_players):
        """Test that negative contributions raise an error."""
        player = sample_players[0]

        with pytest.raises(ValueError, match="Contribution amount must be positive"):
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('-5.00'),
                entry_date=date(2025, 8, 11)
            )


class TestRecordBetPlaced:
    """Tests for recording bet placements."""

    def test_record_bet_placed_creates_ledger_entry(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that recording a bet creates a ledger entry."""
        player = sample_players[0]

        entry = ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        assert entry.id is not None
        assert entry.entry_type == 'bet_placed'
        assert entry.player_id == player.id
        assert entry.bet_id == sample_bet.id
        assert entry.amount == Decimal('-10.00')  # Negative (money OUT)

    def test_record_bet_placed_negative_amount(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that bet placements have negative amounts (money OUT)."""
        player = sample_players[0]

        entry = ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        assert entry.amount < 0


class TestRecordBetWon:
    """Tests for recording bet wins and distributing winnings."""

    def test_record_bet_won_creates_multiple_entries(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that winning a bet creates one entry per active player."""
        winnings = Decimal('60.00')

        entries = ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=winnings,
            entry_date=date(2025, 8, 15)
        )

        # Should create 5 entries (one per player)
        assert len(entries) == 5

        # All entries should be winnings_share type
        assert all(e.entry_type == 'winnings_share' for e in entries)

        # All entries should have positive amounts
        assert all(e.amount > 0 for e in entries)

    def test_record_bet_won_splits_equally(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that winnings are split equally among all active players."""
        winnings = Decimal('100.00')

        entries = ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=winnings,
            entry_date=date(2025, 8, 15)
        )

        # Each player should get £20 (100 ÷ 5)
        expected_share = Decimal('20.00')
        assert all(e.amount == expected_share for e in entries)

    def test_record_bet_won_includes_all_active_players(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that all active players receive a share."""
        winnings = Decimal('60.00')

        entries = ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=winnings,
            entry_date=date(2025, 8, 15)
        )

        entry_player_ids = {e.player_id for e in entries}
        expected_player_ids = {p.id for p in sample_players}

        assert entry_player_ids == expected_player_ids

    def test_record_bet_won_no_active_players_raises_error(
        self, db_session, sample_season, sample_bet
    ):
        """Test that winning with no active players raises an error."""
        # Deactivate all players
        player_seasons = db_session.query(PlayerSeason).all()
        for ps in player_seasons:
            ps.is_active = False
        db_session.commit()

        with pytest.raises(ValueError, match="No active players found"):
            ledger.record_bet_won(
                db_session,
                bet_id=sample_bet.id,
                season_id=sample_season.id,
                winnings=Decimal('60.00'),
                entry_date=date(2025, 8, 15)
            )

    def test_record_bet_won_rounding(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that winnings are correctly rounded to 2 decimal places."""
        # 10.00 ÷ 3 = 3.333... should round to 3.33
        winnings = Decimal('10.00')

        # Create scenario with 3 active players
        player_seasons = db_session.query(PlayerSeason).all()
        for i, ps in enumerate(player_seasons):
            if i >= 3:
                ps.is_active = False
        db_session.commit()

        entries = ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=winnings,
            entry_date=date(2025, 8, 15)
        )

        assert len(entries) == 3
        expected_share = Decimal('3.33')
        assert all(e.amount == expected_share for e in entries)


class TestRecordBetVoid:
    """Tests for recording void bets."""

    def test_record_bet_void_creates_ledger_entry(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that voiding a bet creates a ledger entry."""
        player = sample_players[0]

        entry = ledger.record_bet_void(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 15)
        )

        assert entry.id is not None
        assert entry.entry_type == 'bet_void'
        assert entry.bet_id == sample_bet.id
        assert entry.amount == Decimal('10.00')  # Positive (money returns)

    def test_record_bet_void_positive_amount(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that void bets have positive amounts (money returns)."""
        player = sample_players[0]

        entry = ledger.record_bet_void(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 15)
        )

        assert entry.amount > 0


class TestRecordPayout:
    """Tests for recording payouts."""

    def test_record_payout_creates_ledger_entry(
        self, db_session, sample_season, sample_players
    ):
        """Test that recording a payout creates a ledger entry."""
        player = sample_players[0]

        entry = ledger.record_payout(
            db_session,
            player_id=player.id,
            season_id=sample_season.id,
            amount=Decimal('50.00'),
            entry_date=date(2025, 8, 20)
        )

        assert entry.id is not None
        assert entry.entry_type == 'payout'
        assert entry.player_id == player.id
        assert entry.amount == Decimal('-50.00')  # Negative (money OUT)

    def test_record_payout_negative_amount(
        self, db_session, sample_season, sample_players
    ):
        """Test that payouts have negative amounts (money OUT)."""
        player = sample_players[0]

        entry = ledger.record_payout(
            db_session,
            player_id=player.id,
            season_id=sample_season.id,
            amount=Decimal('50.00'),
            entry_date=date(2025, 8, 20)
        )

        assert entry.amount < 0


class TestGetActivePlayersInSeason:
    """Tests for getting active players."""

    def test_get_active_players_returns_all_active(
        self, db_session, sample_season, sample_players
    ):
        """Test that function returns all active players."""
        active_players = ledger.get_active_players_in_season(db_session, sample_season.id)

        assert len(active_players) == 5
        assert all(p.is_active for p in active_players)

    def test_get_active_players_excludes_inactive(
        self, db_session, sample_season, sample_players
    ):
        """Test that function excludes inactive players."""
        # Deactivate one player
        player_season = db_session.query(PlayerSeason).filter(
            PlayerSeason.player_id == sample_players[0].id
        ).first()
        player_season.is_active = False
        db_session.commit()

        active_players = ledger.get_active_players_in_season(db_session, sample_season.id)

        assert len(active_players) == 4
        assert sample_players[0].id not in [p.id for p in active_players]
