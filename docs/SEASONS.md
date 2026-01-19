# Season Management

## Overview

Seasons are the top-level organisational unit in the Betting Syndicate system. A season represents a defined time period (typically a football season like "2025-2026") during which the syndicate operates.

**Only one season can be active at a time.** All dashboard statistics, player contributions, bets, and calculations are scoped to the active season.

---

## Key Concepts

### Active Season

- The active season is the "current" season where all activity takes place
- When you view the dashboard, it shows data for the active season only
- Creating a new season automatically deactivates all other seasons
- You can switch between seasons by activating a different one

### Season Dates

| Field | Description |
|-------|-------------|
| **Start Date** | The first day of the season. Used to calculate weeks elapsed and expected contributions. Should be a Monday. |
| **End Date** | Optional. When set and the date passes, the season becomes "frozen". |

### Frozen Seasons

A season becomes **frozen** when its end date has passed. When frozen:

- No new bets can be placed
- No new contributions can be added
- Payouts can still be recorded (to distribute winnings)
- The season remains "active" but is locked for new activity
- All historical data is preserved and viewable

**Setting an End Date in Advance:**

You can set an end date before it arrives. The system will:
1. Show the scheduled end date in the seasons list
2. Continue allowing normal activity until the date passes
3. Automatically freeze the season when the end date is reached

### Weekly Contributions

Contributions are calculated based on Mondays since the season start date:

```
Expected Contribution = Number of Mondays × £5
```

For example, if a season started on 11/08/2025 and today is 19/01/2026:
- 24 Mondays have passed
- Expected contribution per player = 24 × £5 = £120

---

## Database Structure

### `seasons` Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | VARCHAR(100) | Season name, e.g., "2025-2026" (must be unique) |
| start_date | DATE | Season start date (should be a Monday) |
| end_date | DATE | Season end date (null if ongoing) |
| is_active | BOOLEAN | Whether this is the current active season |
| created_at | DATETIME | When the record was created |

### `player_seasons` Table

Links players to seasons they participate in:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| player_id | INTEGER | Foreign key to players |
| season_id | INTEGER | Foreign key to seasons |
| joined_date | DATE | When the player joined this season |
| is_active | BOOLEAN | Whether player is currently active in this season |

**Constraint:** A player can only be linked to a season once (unique player_id + season_id).

---

## Managing Seasons

### Creating a New Season

1. Navigate to `/seasons`
2. Click **"New Season"**
3. Enter:
   - **Name**: e.g., "2025-2026 Season"
   - **Start Date**: The first Monday of the season
4. Click **"Create Season"**

**Note:** Creating a new season automatically:
- Deactivates all existing seasons
- Sets the new season as active
- Does NOT automatically add players (you must add them separately)

### Switching Between Seasons

1. Navigate to `/seasons`
2. Find the season you want to activate
3. Click **"Activate"**

This will:
- Deactivate the current season
- Activate the selected season
- Update all dashboard views to show data from the newly active season

### Adding Players to a Season

After creating a season, you need to add players:

1. Navigate to `/players`
2. For each player, click **"Add"** to include them in the active season
3. Or when creating a new player, tick **"Add to current season"**

---

## Season-Scoped Data

The following data is scoped to a specific season:

| Data | Description |
|------|-------------|
| **Ledger Entries** | All contributions, bets placed, winnings, and payouts are linked to a season |
| **Weeks** | Weekly rounds belong to a specific season |
| **Week Assignments** | Player betting responsibilities are per-week, per-season |
| **Player Stats** | Balance, bets placed, winnings, P/L are calculated per-season |

### What Happens to Old Season Data?

- Old season data is **preserved** in the database
- You can switch back to view historical seasons
- Ledger entries are never deleted (immutable audit trail)
- Players can be active in multiple seasons over time

---

## Best Practices

### Starting a New Season

1. **End the current season** (optional): Set an end date on the current season
2. **Create the new season**: Use the first Monday as the start date
3. **Add players**: Add all participating players to the new season
4. **Import week assignments**: If you have a schedule, import it via `/import`

### Season Naming Convention

Use a consistent naming format:
- `2025-2026` or `2025-2026 Season`
- `Season 1`, `Season 2`, etc.

### Start Date Selection

- **Always use a Monday** as the start date
- Contributions are calculated based on Mondays elapsed
- Example: If your season starts on 11 August 2025 (a Monday), the first £5 is due on that day

---

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/seasons` | GET | List all seasons |
| `/seasons/new` | GET | Show create season form |
| `/seasons` | POST | Create a new season |
| `/seasons/{id}/edit` | GET | Show edit season form |
| `/seasons/{id}/edit` | POST | Update season (set end date) |
| `/seasons/{id}/activate` | POST | Activate a specific season |

---

## Freezing and Unfreezing Seasons

### To Freeze a Season

1. Go to `/seasons`
2. Click **"Edit"** next to the season
3. Set an **End Date** (can be today or a future date)
4. Click **"Save Changes"**

The season will freeze when the end date passes.

### To Unfreeze a Season

1. Go to `/seasons`
2. Click **"Edit"** next to the frozen season
3. Either:
   - **Remove** the end date (clear the field), or
   - **Extend** the end date to a future date
4. Click **"Save Changes"**

The season will immediately become active again.

---

## Troubleshooting

### "No active season found"

This error appears when there's no active season. Solution:
1. Go to `/seasons`
2. Either create a new season or activate an existing one

### Players not appearing in dashboard

Players must be added to the active season:
1. Go to `/players`
2. Click **"Add"** next to each player to include them in the current season

### Wrong contribution amounts

Check that the season start date is correct:
1. Go to `/seasons`
2. Verify the start date is a Monday
3. Contributions are calculated from that date

---

## Related Documentation

- [DATABASE.md](DATABASE.md) - Full database schema and ledger system
- [DEPLOYMENT.md](DEPLOYMENT.md) - Proxmox deployment guide
