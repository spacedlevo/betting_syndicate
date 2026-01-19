"""
Script to run the data import from CSV.

Usage:
    python run_import.py
"""

from datetime import date
from decimal import Decimal

from app.database import SessionLocal, init_db
from app.import_data import run_import
from app import calculations


def main():
    # Initialize database
    print("Initializing database...")
    init_db()

    # Create session
    db = SessionLocal()

    try:
        # Run import
        csv_path = "/home/levo/Documents/projects/betting_syndicate/Data/Betting Syndicate 25_26 - Transactions.csv"
        result = run_import(
            db,
            csv_path=csv_path,
            season_name="2025-2026",
            season_start=date(2025, 8, 11)
        )

        # Verify calculations
        season = result['season']
        print("\n" + "=" * 60)
        print("VERIFICATION - Calculated from Ledger")
        print("=" * 60)

        balance = calculations.get_syndicate_balance(db, season.id)
        total_contributions = calculations.get_season_total_contributions(db, season.id)
        total_bets = calculations.get_season_total_bets_placed(db, season.id)
        total_winnings = calculations.get_season_total_winnings(db, season.id)
        profit_loss = calculations.get_season_profit_loss(db, season.id)
        profit_pct = calculations.get_season_profit_percentage(db, season.id)
        share_per_player = calculations.get_share_per_player(db, season.id)

        print(f"\nSyndicate Bank Balance: £{balance:.2f}")
        print(f"Total Paid In: £{total_contributions:.2f}")
        print(f"Total Bets Placed: £{total_bets:.2f}")
        print(f"Total Winnings: £{total_winnings:.2f}")
        print(f"Profit/Loss: £{profit_loss:.2f}")
        print(f"Profit Percentage: {profit_pct:.2f}%")
        print(f"Share Per Player: £{share_per_player:.2f}")

        # Player breakdown
        print("\n" + "-" * 60)
        print("PLAYER BREAKDOWN")
        print("-" * 60)
        print(f"{'Player':<20} {'Balance':>10} {'Bets':>10} {'Won':>12} {'P/L':>12}")
        print("-" * 60)

        stats = calculations.get_player_performance_stats(db, season.id)
        for stat in stats:
            print(f"{stat['player_name']:<20} £{stat['balance']:>8.2f} £{stat['bets_placed']:>8.2f} £{stat['won']:>10.2f} £{stat['profit_loss']:>10.2f}")

        print("-" * 60)

        # Expected values from Excel for comparison
        print("\n" + "=" * 60)
        print("EXPECTED VALUES (from Excel)")
        print("=" * 60)
        print("Bank: £1,789.88")
        print("Paid In: £1,460.00")
        print("Bets Placed: £1,260.00")
        print("Winnings: £1,589.88")
        print("Profit/Loss: £329.88")
        print("Percentage: 26.18%")
        print("Share Per Player: £132.49")

    finally:
        db.close()


if __name__ == "__main__":
    main()
