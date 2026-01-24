"""
Data import module for importing historical transactions from CSV.

This module processes the transaction ledger CSV and creates:
- Season record
- Player records
- PlayerSeason assignments
- Ledger entries (contributions, bet_placed, winnings_share, payouts)
- Bet records
"""

import csv
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Season, Player, PlayerSeason, Week, WeekAssignment, Bet, LedgerEntry
from app import ledger


def parse_date(date_str: str) -> date:
    """Parse date from DD/MM/YYYY format."""
    return datetime.strptime(date_str, "%d/%m/%Y").date()


def import_season(
    db: Session,
    name: str,
    start_date: date,
    end_date: Optional[date] = None
) -> Season:
    """
    Create or get the season for import.

    Args:
        db: Database session
        name: Season name (e.g., "2025-2026")
        start_date: Season start date
        end_date: Optional end date

    Returns:
        Season object
    """
    # Check if season already exists
    existing = db.query(Season).filter(Season.name == name).first()
    if existing:
        return existing

    season = Season(
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    db.add(season)
    db.flush()  # Get the ID without committing
    print(f"Created season: {name}")
    return season


def import_players(db: Session, player_names: List[str]) -> Dict[str, Player]:
    """
    Create players from a list of names.

    Args:
        db: Database session
        player_names: List of unique player names

    Returns:
        Dict mapping player name to Player object
    """
    players = {}

    for name in player_names:
        # Check if player already exists
        existing = db.query(Player).filter(Player.name == name).first()
        if existing:
            players[name] = existing
        else:
            player = Player(name=name, is_active=True)
            db.add(player)
            db.flush()  # Get the ID without committing
            players[name] = player
            print(f"Created player: {name}")

    return players


def assign_players_to_season(
    db: Session,
    players: Dict[str, Player],
    season: Season,
    joined_date: date
) -> None:
    """
    Assign all players to a season.

    Args:
        db: Database session
        players: Dict of player name to Player object
        season: Season to assign to
        joined_date: Date players joined
    """
    for name, player in players.items():
        # Check if already assigned
        existing = db.query(PlayerSeason).filter(
            PlayerSeason.player_id == player.id,
            PlayerSeason.season_id == season.id
        ).first()

        if not existing:
            ps = PlayerSeason(
                player_id=player.id,
                season_id=season.id,
                joined_date=joined_date,
                is_active=True
            )
            db.add(ps)

    db.flush()  # Flush without committing
    print(f"Assigned {len(players)} players to season {season.name}")


def import_transactions_from_csv(
    db: Session,
    csv_path: str,
    season: Season,
    players: Dict[str, Player]
) -> Dict[str, int]:
    """
    Import transactions from CSV file.

    CSV format: Date,Player,Amount,Transaction
    Transaction types: "paid in", "placed", "won", "paid out"

    Args:
        db: Database session
        csv_path: Path to CSV file
        season: Season to import into
        players: Dict of player name to Player object

    Returns:
        Dict with counts of imported transactions by type
    """
    counts = {
        'contributions': 0,
        'bets_placed': 0,
        'winnings': 0,
        'payouts': 0,
        'errors': 0
    }

    # Read all transactions
    transactions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('Date') or not row.get('Player'):
                continue  # Skip empty rows
            transactions.append(row)

    # Sort by date to process chronologically
    transactions.sort(key=lambda x: parse_date(x['Date']))

    # Get active players for winnings distribution
    active_player_list = list(players.values())
    num_players = len(active_player_list)

    print(f"\nProcessing {len(transactions)} transactions...")
    print(f"Active players for winnings distribution: {num_players}")

    try:
        for row in transactions:
            entry_date = parse_date(row['Date'])
            player_name = row['Player'].strip()
            amount = Decimal(row['Amount'].strip())
            transaction_type = row['Transaction'].strip().lower()

            if player_name not in players:
                raise ValueError(f"Unknown player '{player_name}'")

            player = players[player_name]

            if transaction_type == 'paid in':
                # Create contribution ledger entry
                entry = LedgerEntry(
                    entry_date=entry_date,
                    entry_type='contribution',
                    player_id=player.id,
                    season_id=season.id,
                    week_id=None,
                    amount=amount,
                    description=f"Contribution",
                    bet_id=None,
                    created_by='import'
                )
                db.add(entry)
                counts['contributions'] += 1

            elif transaction_type == 'placed':
                # Create bet record and bet_placed ledger entry
                bet = Bet(
                    week_id=None,  # We don't have week data
                    placed_by_player_id=player.id,
                    stake=amount,
                    description=f"Bet placed on {entry_date}",
                    odds=None,
                    bet_date=entry_date,
                    status='pending',  # Will be updated if we see a win
                    notes='Imported from CSV',
                    sport_id=None
                )
                db.add(bet)
                db.flush()  # Get the bet ID

                entry = LedgerEntry(
                    entry_date=entry_date,
                    entry_type='bet_placed',
                    player_id=player.id,
                    season_id=season.id,
                    week_id=None,
                    amount=-amount,  # Negative for money out
                    description=f"Bet placed",
                    bet_id=bet.id,
                    created_by='import'
                )
                db.add(entry)
                counts['bets_placed'] += 1

            elif transaction_type == 'won':
                # Record single winnings entry credited to player who placed the bet
                # Equal share per player is calculated dynamically: total_winnings / num_players
                entry = LedgerEntry(
                    entry_date=entry_date,
                    entry_type='winnings',
                    player_id=player.id,
                    season_id=season.id,
                    week_id=None,
                    amount=amount,
                    description=f"Bet won",
                    bet_id=None,
                    created_by='import'
                )
                db.add(entry)
                counts['winnings'] += 1

            elif transaction_type == 'paid out':
                # Create payout ledger entry
                entry = LedgerEntry(
                    entry_date=entry_date,
                    entry_type='payout',
                    player_id=player.id,
                    season_id=season.id,
                    week_id=None,
                    amount=-amount,  # Negative for money out
                    description=f"Payout to player",
                    bet_id=None,
                    created_by='import'
                )
                db.add(entry)
                counts['payouts'] += 1

            else:
                raise ValueError(f"Unknown transaction type '{transaction_type}'")

        # Commit all transactions at once if no errors
        db.commit()
        print("All transactions committed successfully.")

    except Exception as e:
        # Rollback everything on any error to avoid duplicates
        db.rollback()
        counts['errors'] += 1
        print(f"\nERROR: {e}")
        print("Rolling back all transactions to avoid duplicates.")
        print("Please fix the CSV and re-import.")
        raise  # Re-raise to stop the import

    return counts


def import_week_assignments(
    db: Session,
    csv_path: str,
    season: Season,
    players: Dict[str, Player]
) -> int:
    """
    Import week assignments from calendar CSV.

    CSV format: start_date,player1_name,player2_name
    Date format: DD/MM/YYYY

    Args:
        db: Database session
        csv_path: Path to calendar CSV file
        season: Season to import into
        players: Dict of player name to Player object

    Returns:
        Number of weeks imported
    """
    weeks_imported = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for week_num, row in enumerate(reader, start=1):
            if len(row) < 3:
                continue

            start_date = parse_date(row[0].strip())
            player1_name = row[1].strip()
            player2_name = row[2].strip()

            # Calculate end date (6 days after start)
            end_date = start_date + timedelta(days=6)

            # Check if week already exists
            existing_week = db.query(Week).filter(
                Week.season_id == season.id,
                Week.week_number == week_num
            ).first()

            if existing_week:
                week = existing_week
            else:
                # Create week
                week = Week(
                    season_id=season.id,
                    week_number=week_num,
                    start_date=start_date,
                    end_date=end_date
                )
                db.add(week)
                db.flush()

            # Get players
            player1 = players.get(player1_name)
            player2 = players.get(player2_name)

            if not player1:
                print(f"Warning: Player '{player1_name}' not found for week {week_num}")
                continue
            if not player2:
                print(f"Warning: Player '{player2_name}' not found for week {week_num}")
                continue

            # Check if assignments already exist
            existing_assignments = db.query(WeekAssignment).filter(
                WeekAssignment.week_id == week.id
            ).count()

            if existing_assignments == 0:
                # Create assignments
                assignment1 = WeekAssignment(
                    week_id=week.id,
                    player_id=player1.id,
                    assignment_order=1
                )
                assignment2 = WeekAssignment(
                    week_id=week.id,
                    player_id=player2.id,
                    assignment_order=2
                )
                db.add(assignment1)
                db.add(assignment2)

            weeks_imported += 1

    db.flush()  # Flush without committing - let caller handle commit
    print(f"Imported {weeks_imported} weeks with assignments")
    return weeks_imported


def run_import(
    db: Session,
    csv_path: str,
    season_name: str = "2025-2026",
    season_start: date = date(2025, 8, 11)
) -> Dict[str, any]:
    """
    Run the full import process.

    All operations are atomic - if any step fails, everything is rolled back
    to prevent duplicate data on re-import.

    Args:
        db: Database session
        csv_path: Path to CSV file
        season_name: Name for the season
        season_start: Season start date

    Returns:
        Dict with import results

    Raises:
        Exception: If any step fails, rolls back and re-raises
    """
    print("=" * 60)
    print("BETTING SYNDICATE DATA IMPORT")
    print("=" * 60)

    try:
        # Step 1: Read CSV to get unique player names
        print("\n1. Reading CSV to extract player names...")
        player_names = set()
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Player'):
                    player_names.add(row['Player'].strip())

        player_names = sorted(player_names)
        print(f"   Found {len(player_names)} unique players: {', '.join(player_names)}")

        # Step 2: Create season
        print(f"\n2. Creating season '{season_name}'...")
        season = import_season(db, season_name, season_start)

        # Step 3: Create players
        print("\n3. Creating players...")
        players = import_players(db, player_names)

        # Step 4: Assign players to season
        print("\n4. Assigning players to season...")
        assign_players_to_season(db, players, season, season_start)

        # Step 5: Import transactions
        print("\n5. Importing transactions...")
        counts = import_transactions_from_csv(db, csv_path, season, players)

        # Summary
        print("\n" + "=" * 60)
        print("IMPORT COMPLETE")
        print("=" * 60)
        print(f"Season: {season_name} (ID: {season.id})")
        print(f"Players: {len(players)}")
        print(f"Contributions imported: {counts['contributions']}")
        print(f"Bets placed imported: {counts['bets_placed']}")
        print(f"Winnings distributed: {counts['winnings']}")
        print(f"Payouts imported: {counts['payouts']}")
        print(f"Errors: {counts['errors']}")

        return {
            'season': season,
            'players': players,
            'counts': counts
        }

    except Exception as e:
        print("\n" + "=" * 60)
        print("IMPORT FAILED - ROLLING BACK")
        print("=" * 60)
        print(f"Error: {e}")
        db.rollback()
        raise
