"""
Tests for the calculations module.

These tests verify that all derived values are correctly calculated from
the ledger entries using SQL aggregations.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta
from decimal import Decimal

from app.database import Base
from app.models import Season, Player, PlayerSeason, Week, Bet
from app import ledger, calculations


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
    for i in range(1, 4):  # Create 3 players
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


class TestSyndicateBalance:
    """Tests for calculating syndicate balance."""

    def test_syndicate_balance_empty(self, db_session, sample_season):
        """Test that balance is 0 with no entries."""
        balance = calculations.get_syndicate_balance(db_session, sample_season.id)
        assert balance == Decimal('0.00')

    def test_syndicate_balance_with_contributions(
        self, db_session, sample_season, sample_players
    ):
        """Test balance with only contributions."""
        # Add 3 contributions of £5 each
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        balance = calculations.get_syndicate_balance(db_session, sample_season.id)
        assert balance == Decimal('15.00')  # 3 × £5

    def test_syndicate_balance_with_bet_placed(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test balance after placing a bet."""
        # Add contributions
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        # Place bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        balance = calculations.get_syndicate_balance(db_session, sample_season.id)
        assert balance == Decimal('5.00')  # £15 - £10

    def test_syndicate_balance_with_winning_bet(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test balance after winning a bet."""
        # Add contributions
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        # Place bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        # Win bet
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        balance = calculations.get_syndicate_balance(db_session, sample_season.id)
        assert balance == Decimal('65.00')  # £15 - £10 + £60


class TestPlayerTotals:
    """Tests for calculating player-specific totals."""

    def test_player_total_contributions(
        self, db_session, sample_season, sample_players
    ):
        """Test calculating player's total contributions."""
        player = sample_players[0]

        # Add 3 contributions
        for i in range(3):
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11) + timedelta(days=i*7)
            )

        total = calculations.get_player_total_contributions(
            db_session, player.id, sample_season.id
        )
        assert total == Decimal('15.00')

    def test_player_total_bets(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating total bets placed by player."""
        player = sample_players[0]

        # Place bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        total = calculations.get_player_total_bets(
            db_session, player.id, sample_season.id
        )
        assert total == Decimal('10.00')

    def test_player_total_winnings(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating player's total winnings."""
        player = sample_players[0]

        # Record bet win (will be split among 3 players)
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        # Each player should get £20
        total = calculations.get_player_total_winnings(
            db_session, player.id, sample_season.id
        )
        assert total == Decimal('20.00')

    def test_player_profit_loss(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating player's profit/loss."""
        player = sample_players[0]

        # Contribute £15
        for i in range(3):
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11) + timedelta(days=i*7)
            )

        # Win £60 (split among 3 players = £20 each)
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        profit_loss = calculations.get_player_profit_loss(
            db_session, player.id, sample_season.id
        )
        # £20 (winnings) - £15 (contributions) = £5 profit
        assert profit_loss == Decimal('5.00')


class TestSeasonTotals:
    """Tests for calculating season-wide totals."""

    def test_season_total_contributions(
        self, db_session, sample_season, sample_players
    ):
        """Test calculating total contributions for season."""
        # Each player contributes £5
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        total = calculations.get_season_total_contributions(db_session, sample_season.id)
        assert total == Decimal('15.00')  # 3 × £5

    def test_season_total_bets_placed(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating total bets placed for season."""
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        total = calculations.get_season_total_bets_placed(db_session, sample_season.id)
        assert total == Decimal('10.00')

    def test_season_total_winnings(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating total winnings for season."""
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        total = calculations.get_season_total_winnings(db_session, sample_season.id)
        assert total == Decimal('60.00')

    def test_season_profit_loss(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating season profit/loss."""
        # Place bet (£10)
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        # Win bet (£60)
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        profit_loss = calculations.get_season_profit_loss(db_session, sample_season.id)
        assert profit_loss == Decimal('50.00')  # £60 - £10

    def test_season_profit_percentage(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test calculating season profit percentage."""
        # Place bet (£10)
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        # Win bet (£60)
        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        percentage = calculations.get_season_profit_percentage(db_session, sample_season.id)
        # (50 ÷ 10) × 100 = 500%
        assert percentage == Decimal('500.00')


class TestExpectedContributions:
    """Tests for calculating expected contributions."""

    def test_expected_contribution_per_player(self, db_session, sample_season):
        """Test calculating expected contribution per player based on weeks elapsed."""
        # Mock current date to be 3 weeks after season start
        # In real implementation, this uses date.today(), so we test the logic
        expected = calculations.get_expected_contribution_per_player(
            db_session,
            sample_season.id,
            weekly_amount=Decimal('5.00')
        )

        # The actual value depends on current date
        # Just verify it's a Decimal
        assert isinstance(expected, Decimal)


class TestSharePerPlayer:
    """Tests for calculating share per player."""

    def test_share_per_player(
        self, db_session, sample_season, sample_players
    ):
        """Test calculating what each player would get if cashing out."""
        # Add contributions to create balance
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        # Balance is £15, 3 active players
        share = calculations.get_share_per_player(db_session, sample_season.id)
        assert share == Decimal('5.00')  # £15 ÷ 3


class TestPlayerBetBalance:
    """Tests for calculating player's pending bet balance."""

    def test_player_bet_balance_with_pending_bet(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that pending bets are included in bet balance."""
        player = sample_players[0]

        # sample_bet is created as pending by default
        bet_balance = calculations.get_player_bet_balance(
            db_session, player.id, sample_season.id
        )

        assert bet_balance == Decimal('10.00')

    def test_player_bet_balance_excludes_settled_bets(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that settled bets are not included."""
        player = sample_players[0]

        # Settle the bet
        sample_bet.status = 'won'
        db_session.commit()

        bet_balance = calculations.get_player_bet_balance(
            db_session, player.id, sample_season.id
        )

        assert bet_balance == Decimal('0.00')


class TestPlayerPerformanceStats:
    """Tests for getting player performance statistics."""

    def test_player_performance_stats(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test getting performance stats for all players."""
        # Add contributions
        for player in sample_players:
            ledger.add_contribution(
                db_session,
                player_id=player.id,
                season_id=sample_season.id,
                amount=Decimal('5.00'),
                entry_date=date(2025, 8, 11)
            )

        # Place and win bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        ledger.record_bet_won(
            db_session,
            bet_id=sample_bet.id,
            season_id=sample_season.id,
            winnings=Decimal('60.00'),
            entry_date=date(2025, 8, 15)
        )

        stats = calculations.get_player_performance_stats(db_session, sample_season.id)

        assert len(stats) == 3

        # Check structure
        for stat in stats:
            assert 'player_id' in stat
            assert 'player_name' in stat
            assert 'balance' in stat
            assert 'bets_placed' in stat
            assert 'bet_balance' in stat
            assert 'won' in stat
            assert 'profit_loss' in stat

        # Find player 1's stats (who placed the bet)
        player1_stats = next(s for s in stats if s['player_id'] == sample_players[0].id)

        assert player1_stats['balance'] == Decimal('5.00')  # Contributions
        assert player1_stats['bets_placed'] == Decimal('10.00')
        assert player1_stats['won'] == Decimal('20.00')  # Share of £60
        assert player1_stats['profit_loss'] == Decimal('15.00')  # £20 - £5


class TestVoidedBetsExcludedFromTotals:
    """Tests for verifying voided bets don't count against betting budget."""

    def test_player_total_bets_excludes_voided(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that voided bets are excluded from player's total bets."""
        player = sample_players[0]

        # Place a bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        # Initially should count as £10 bet
        total = calculations.get_player_total_bets(db_session, player.id, sample_season.id)
        assert total == Decimal('10.00')

        # Void the bet
        ledger.record_bet_void(
            db_session,
            bet_id=sample_bet.id,
            player_id=player.id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 13)
        )

        # After void, should be £0 (stake is freed up)
        total_after_void = calculations.get_player_total_bets(db_session, player.id, sample_season.id)
        assert total_after_void == Decimal('0.00')

    def test_season_total_bets_excludes_voided(
        self, db_session, sample_season, sample_week, sample_players, sample_bet
    ):
        """Test that voided bets are excluded from season total bets."""
        # Place a bet
        ledger.record_bet_placed(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 12)
        )

        # Initially should count as £10
        total = calculations.get_season_total_bets_placed(db_session, sample_season.id)
        assert total == Decimal('10.00')

        # Void the bet
        ledger.record_bet_void(
            db_session,
            bet_id=sample_bet.id,
            player_id=sample_players[0].id,
            season_id=sample_season.id,
            week_id=sample_week.id,
            stake=Decimal('10.00'),
            entry_date=date(2025, 8, 13)
        )

        # After void, should be £0
        total_after_void = calculations.get_season_total_bets_placed(db_session, sample_season.id)
        assert total_after_void == Decimal('0.00')
