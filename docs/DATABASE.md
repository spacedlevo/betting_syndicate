# Betting Syndicate Database Documentation

## Overview

The betting syndicate database uses a **ledger-based accounting model**. All financial values are calculated from an immutable ledger of transactions - no stored balances.

## Core Principle

**The `ledger` table is the single source of truth for all financial activity.**

Every balance, total, and financial statistic is derived by querying the ledger table. Entries are never updated or deleted - only inserted.

---

## Database Schema

### Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   seasons    │       │  player_seasons  │       │   players    │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id (PK)      │◄──────│ season_id (FK)   │───────│ id (PK)      │
│ name         │       │ player_id (FK)   │──────►│ name         │
│ start_date   │       │ joined_date      │       │ email        │
│ end_date     │       │ is_active        │       │ is_active    │
│ is_active    │       └──────────────────┘       │ created_at   │
│ created_at   │                                  └──────────────┘
└──────────────┘                                         │
       │                                                 │
       │         ┌──────────────┐                        │
       │         │    weeks     │                        │
       │         ├──────────────┤                        │
       └────────►│ id (PK)      │                        │
                 │ season_id(FK)│                        │
                 │ week_number  │                        │
                 │ start_date   │                        │
                 │ end_date     │                        │
                 │ created_at   │                        │
                 └──────────────┘                        │
                        │                               │
                        │      ┌────────────────────┐   │
                        │      │ week_assignments   │   │
                        │      ├────────────────────┤   │
                        └─────►│ id (PK)            │   │
                               │ week_id (FK)       │   │
                               │ player_id (FK)     │◄──┘
                               │ assignment_order   │
                               └────────────────────┘

┌──────────────┐       ┌──────────────────────────────────┐
│    bets      │       │             ledger               │
├──────────────┤       ├──────────────────────────────────┤
│ id (PK)      │◄──────│ id (PK)                          │
│ week_id (FK) │       │ entry_date                       │
│ placed_by_   │       │ entry_type                       │
│  player_id   │       │ player_id (FK)                   │
│ stake        │       │ season_id (FK)                   │
│ description  │       │ week_id (FK)                     │
│ odds         │       │ amount                           │
│ bet_date     │       │ description                      │
│ status       │       │ bet_id (FK)                      │
│ result_date  │       │ created_at                       │
│ winnings     │       │ created_by                       │
│ notes        │       └──────────────────────────────────┘
│ screenshot   │
│ created_at   │
└──────────────┘
```

---

## Tables

### `seasons`

Represents a betting season/year (e.g., "2025-2026"). Only one season should be active at a time.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| name | VARCHAR(100) | No | Season name, e.g., "2025-2026" (unique) |
| start_date | DATE | No | Season start date |
| end_date | DATE | Yes | Season end date (null if ongoing) |
| is_active | BOOLEAN | No | Whether this is the current active season |
| created_at | DATETIME | No | Record creation timestamp |

### `players`

All players who have participated in the syndicate across any season.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| name | VARCHAR(100) | No | Player's full name |
| email | VARCHAR(255) | Yes | Email address (unique if provided) |
| is_active | BOOLEAN | No | Whether player is generally active |
| created_at | DATETIME | No | Record creation timestamp |

### `player_seasons`

Many-to-many relationship tracking which players participate in which seasons.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| player_id | INTEGER | No | Foreign key to players |
| season_id | INTEGER | No | Foreign key to seasons |
| joined_date | DATE | No | Date player joined this season |
| is_active | BOOLEAN | No | Whether player is active in this season |

**Constraints:**
- Unique: (player_id, season_id)

### `weeks`

Weekly rounds within each season. Each week has a number and date range.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| season_id | INTEGER | No | Foreign key to seasons |
| week_number | INTEGER | No | Week number (1, 2, 3, ...) |
| start_date | DATE | No | Week start date (typically Monday) |
| end_date | DATE | No | Week end date (typically Sunday) |
| created_at | DATETIME | No | Record creation timestamp |

**Constraints:**
- Unique: (season_id, week_number)

### `week_assignments`

Assigns two players to be responsible for placing bets each week.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| week_id | INTEGER | No | Foreign key to weeks |
| player_id | INTEGER | No | Foreign key to players |
| assignment_order | INTEGER | No | 1 or 2 (first or second assigned player) |

**Constraints:**
- Unique: (week_id, player_id)
- Unique: (week_id, assignment_order)
- Check: assignment_order IN (1, 2)

### `bets`

Metadata about bets placed by the syndicate. Financial impact is tracked in the ledger.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| week_id | INTEGER | Yes | Foreign key to weeks (nullable for imports) |
| placed_by_player_id | INTEGER | No | Foreign key to players - who placed the bet |
| stake | NUMERIC(10,2) | No | Amount staked |
| description | TEXT | No | Bet description |
| odds | VARCHAR(50) | Yes | Odds, e.g., "5/1", "2.5", "evens" |
| bet_date | DATE | No | Date bet was placed |
| status | VARCHAR(20) | No | 'pending', 'won', 'lost', or 'void' |
| result_date | DATE | Yes | Date bet was settled |
| winnings | NUMERIC(10,2) | Yes | Total return if won (stake + profit) |
| notes | TEXT | Yes | Additional notes |
| screenshot | VARCHAR(255) | Yes | Filename of uploaded bet slip screenshot |
| created_at | DATETIME | No | Record creation timestamp |

**Constraints:**
- Check: status IN ('pending', 'won', 'lost', 'void')
- Check: stake > 0

### `ledger`

**THE SINGLE SOURCE OF TRUTH** for all financial activity. This table is immutable.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| entry_date | DATE | No | Date of the transaction |
| entry_type | VARCHAR(20) | No | Type of entry (see below) |
| player_id | INTEGER | No | Foreign key to players |
| season_id | INTEGER | No | Foreign key to seasons |
| week_id | INTEGER | Yes | Foreign key to weeks (if applicable) |
| amount | NUMERIC(10,2) | No | Amount (+ve for money IN, -ve for money OUT) |
| description | TEXT | Yes | Description of the entry |
| bet_id | INTEGER | Yes | Foreign key to bets (if related to a bet) |
| created_at | DATETIME | No | Record creation timestamp |
| created_by | VARCHAR(100) | Yes | Who/what created this entry |

**Constraints:**
- Check: entry_type IN ('contribution', 'bet_placed', 'winnings', 'bet_void', 'payout')

---

## Ledger Entry Types

| Entry Type | Amount Sign | Description |
|------------|-------------|-------------|
| `contribution` | **+** (positive) | Player pays weekly contribution |
| `bet_placed` | **-** (negative) | Bet placed, money to bookmaker |
| `winnings` | **+** (positive) | Bet won, credited to player who placed it |
| `bet_void` | **+** (positive) | Bet cancelled, stake returned |
| `payout` | **-** (negative) | Player withdraws from syndicate |

---

## Calculated Values

All financial values are derived from the ledger. No balances are stored.

### Bank Balance
```
Bank Balance = (Paid In + Bets Won) - Bets Placed - Paid Out
```

### Player's Net Position (Balance)
Contributions minus payouts - what the player has "in" the syndicate.
```sql
SELECT SUM(amount) FROM ledger
WHERE player_id = ? AND season_id = ?
AND entry_type IN ('contribution', 'payout')
```

### Total Bets Placed
```sql
SELECT SUM(ABS(amount)) FROM ledger
WHERE season_id = ? AND entry_type = 'bet_placed'
```

### Total Winnings
```sql
SELECT SUM(amount) FROM ledger
WHERE season_id = ? AND entry_type = 'winnings'
```

### Player's Winnings (Won)
Total winnings from bets the player placed.
```sql
SELECT SUM(amount) FROM ledger
WHERE player_id = ? AND season_id = ?
AND entry_type = 'winnings'
```

### Player Profit/Loss
```
Profit/Loss = Won - Bets Placed
```

### Share Per Player (Equal Distribution)
Calculated dynamically - not stored in the database.
```
Share Per Player = Total Winnings / Number of Active Players
```

### Expected Contribution Per Player
Based on Mondays elapsed since season start (£5 per week).
```
Expected = Number of Mondays since season start × £5
```
*Note: Contributions are due every Monday. The system counts Mondays, not calendar weeks.*

### Bet Balance (Available Budget)
```
Budget = ROUNDUP(weeks_since_start / 6) * 30
Bet Balance = Budget - Bets Placed
```

### Player Payout
What each player would receive if cashing out now.
```
Payout = (Balance - Expected Contribution) + Share Per Player
```

---

## Screenshot Storage

Bet screenshots are stored in `/uploads/screenshots/` with UUID-based filenames.

**Supported formats:** JPG, JPEG, PNG, GIF, WebP

**Access URL:** `/uploads/screenshots/{filename}`

---

## Season States

A season can be in one of three states:

| State | Condition | Behaviour |
|-------|-----------|-----------|
| **Active** | `is_active = true` AND (`end_date` is null OR `end_date >= today`) | Normal operation - all actions allowed |
| **Frozen** | `is_active = true` AND `end_date < today` | Read-only - no new bets or contributions allowed, payouts still permitted |
| **Inactive** | `is_active = false` | Not the current season - view only |

To freeze a season, set an `end_date` in the past or present. To unfreeze, remove or extend the `end_date`.

---

## Data Integrity Rules

1. **Immutability**: Ledger entries are never updated or deleted
2. **Atomic transactions**: All related entries created in the same transaction
3. **Foreign keys**: All relationships enforced at database level
4. **Positive stakes**: Bet stakes must be greater than 0
5. **Valid entry types**: Ledger entry types are constrained to valid values
6. **Single active season**: Only one season should have `is_active = true` at a time

---

## File Locations

- **Database:** `betting_syndicate.db` (SQLite, in project root)
- **Screenshots:** `uploads/screenshots/`

---

## Related Documentation

- [SEASONS.md](SEASONS.md) - Season management and freezing guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Proxmox deployment guide
