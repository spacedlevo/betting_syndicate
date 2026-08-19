# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — 2026-08-19

### Added
- `docs/BETS.md` — new doc covering the full bet lifecycle (placing, settling, editing), free bets, pot bets, how winnings are shared, and the payout calculation.
- `docs/BANK_IMPORT.md` — new doc covering the bank statement import workflow (Monzo, TSB, PayPal CSVs), how to add a new player to the import name maps, and how to use the audit page to reconcile transactions against ledger contributions.

### Changed
- `docs/DATABASE.md` — updated to reflect the current schema. Added the `sports`, `bank_transactions`, and `player_bank_transactions` tables which were missing. Added the `weekly_contribution` and `weekly_betting_budget` columns to the `seasons` table. Added `is_free_bet`, `is_pot_bet`, and `sport_id` columns to the `bets` table. Rewrote in a more readable style with "why it exists" notes per table.
- `docs/SEASONS.md` — added a full section on the round-robin schedule generator: how the circle method works, how solo weeks are handled for odd player counts, and how the cycle is extended to cover a full season. Also clarified per-season contribution and betting budget config, which was missing.

---

## Earlier history

The project did not maintain a changelog before 2026-08-19. See `git log` for historical changes.
