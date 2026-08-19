# Seasons and schedules

## What a season is

A season represents a defined time period — typically a football season like "2025-2026". It's the top-level grouping for everything: contributions, bets, player assignments, and statistics.

Only one season is active at a time. The dashboard always shows data for the active season.

Each season has its own configurable **weekly contribution** (default £5.00 per player) and **weekly betting budget** (default £27.50 per week across the syndicate).

---

## Season states

| State | Condition | What you can do |
| ----- | --------- | --------------- |
| Active | `is_active = true`, end date not passed | Everything: place bets, record contributions, manage players |
| Frozen | `is_active = true`, end date has passed | View data and record payouts. No new bets or contributions. |
| Inactive | `is_active = false` | View historical data only |

A season freezes automatically when its end date passes — you don't need to do anything manually. To unfreeze it, clear or extend the end date.

---

## Creating a new season

1. Go to `/seasons/new`
2. Fill in:
   - **Name** — e.g. "2025-2026"
   - **Start date** — use the first Monday of the season (contributions are calculated by counting Mondays from this date)
   - **Weekly contribution** — how much each player pays per week (default £5.00)
   - **Weekly betting budget** — the total staking limit per week (default £27.50)
   - **Players** — tick everyone who is playing this season
3. Click Create

Creating a new season automatically deactivates all other seasons.

**Note:** Players are linked to the season at creation time. If you need to add someone later, go to `/players` and use the "Add to season" action.

---

## Contributions and the Monday count

Contributions are tracked against expected amounts using a simple Monday count:

```text
Expected per player = number of Mondays elapsed since season start × weekly_contribution
```

The system counts actual calendar Mondays from the season start date up to today. This stays accurate even if the season started mid-week — it finds the first Monday on or after the start date and counts from there.

Example: season starts 11 Aug 2025 (a Monday), checked on 19 Jan 2026 = 24 Mondays = £120 expected per player.

---

## The round-robin schedule

### What it does

Each week, two players are assigned to place bets. The schedule auto-generates a fair rotation so everyone gets paired with everyone else before the cycle repeats. This is the classic "circle method" round-robin.

### Generating a schedule

1. Go to `/seasons/{id}/schedule/generate`
2. Set the **schedule start date** (the Monday of week 1)
3. Set the **number of weeks** to cover
4. Click Generate

This deletes any existing weeks and assignments for the season and replaces them completely.

### How the algorithm works

The algorithm lives in `app/round_robin.py`. Here's what it does:

1. **Shuffle the player list** randomly so the rotation order is different each season.
2. **Build one full cycle** using the circle method:
   - One player is fixed (player 0). The rest rotate around them.
   - In each round, player 0 is paired with the last rotating player; the others pair up across from each other in the rotating list.
   - After each round, the rotating list shifts by one position.
   - This continues for N-1 rounds (where N is the number of players), producing one pairing of every possible pair.
3. **Handle odd player counts** by adding a dummy "bye" slot. When a player is paired with the bye, they get a solo week — they place the bets alone. Pairs where the dummy appears are sorted to the end of each round.
4. **Extend to the full season length** by cycling through the generated pairs. Once all pairs have been used, the cycle starts again from the top.

Each week slot has a start date (Monday) and end date (Sunday), calculated from the schedule start date and the week's index.

### Solo weeks (odd player count)

If there's an odd number of players, one player per round gets a solo week — no partner. This is handled cleanly: `player2_id` in the week assignment is null, and the schedule view labels these weeks accordingly.

### Example (5 players)

With 5 players (A, B, C, D, E), the algorithm adds a dummy to make 6, producing 5 rounds of 2 pairs + 1 solo per round = 15 weeks per full cycle. Players cycle through all possible pairings before any pair is repeated.

### Viewing the schedule

Go to `/seasons/{id}/schedule` to see all weeks, who's assigned to each, and which is the current week (highlighted).

---

## Freezing a season

Set an end date in the past or present on the season's edit page (`/seasons/{id}/edit`). From that point:

- No new bets can be placed
- No new contributions can be added
- Payouts can still be recorded (so you can distribute the final pot)
- All history is preserved

To **unfreeze**: edit the season and clear or extend the end date.

You can set an end date in the future to pre-schedule a freeze — activity continues as normal until the date arrives.

---

## Switching between seasons

Go to `/seasons`, find the season you want, and click Activate. The dashboard will immediately switch to showing that season's data.

---

## What gets scoped to a season

| Data | Scoped to season? |
| ---- | ----------------- |
| Ledger entries (contributions, bets, winnings, payouts) | Yes |
| Weeks and week assignments | Yes |
| Player stats (balance, P/L, payout calculation) | Yes |
| Players themselves | No — players exist globally and are linked to seasons via player_seasons |

Old season data is always preserved. Switching seasons just changes the filter applied to every view.

---

## Routes

| Route | Method | What it does |
| ----- | ------ | ------------ |
| `/seasons` | GET | List all seasons |
| `/seasons/new` | GET | Create season form |
| `/seasons` | POST | Create a season |
| `/seasons/{id}/edit` | GET/POST | Edit end date |
| `/seasons/{id}/activate` | POST | Make this the active season |
| `/seasons/{id}/schedule` | GET | View the full week schedule |
| `/seasons/{id}/schedule/generate` | GET/POST | Generate round-robin schedule |

---

## Troubleshooting

**"No active season found"** — go to `/seasons` and activate one, or create a new one.

**Contributions showing wrong expected amount** — check the season's start date is a Monday. The Monday count starts from there.

**Schedule looks wrong** — regenerating the schedule deletes all existing weeks and assignments and starts fresh. Do this before any bets have been linked to weeks, or you'll lose those links.

---

## Related docs

- [DATABASE.md](DATABASE.md) — full table reference including the weeks and ledger tables
- [BETS.md](BETS.md) — how bets and winnings work
