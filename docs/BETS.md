# Bets and winnings

## How a bet moves through the system

```
Place bet → status: pending
                │
      ┌─────────┼──────────┐
      ↓         ↓          ↓
   Won        Lost       Void
   (record   (no action) (return
   winnings)             stake)
```

### 1. Placing a bet

Go to `/bets/new`. You'll need to pick:
- Who placed the bet
- Stake amount
- Description (what you bet on)
- Odds (free-text — decimal, fraction, or words like "evens")
- Sport (optional, for categorisation)
- Date the bet was placed
- Whether it's a free bet or a pot bet (see below)
- A screenshot of the bet slip (optional but recommended)

When a regular bet is placed, a `bet_placed` ledger entry is created for the staking amount (stored as a negative number — money leaving the syndicate).

### 2. Settling a bet

Go to the bet, click Update Result, and choose Won / Lost / Void.

- **Won**: Enter the total return (stake + profit). A `winnings` ledger entry is created, credited to the player who placed the bet.
- **Lost**: Nothing extra happens. The money already left when the bet was placed.
- **Void**: A `bet_void` ledger entry is created to return the stake to the syndicate.

### 3. Editing a bet

You can edit a bet after the fact:
- If it's **pending**: you can change the player, stake, odds, sport, and date. The `bet_placed` ledger entry is updated in place (this is an exception to the immutability rule — only for pending bets that haven't settled yet).
- If it's **won**: you can correct the winnings amount and result date.
- If it's **lost or void**: you can correct the result date.

---

## Free bets

A free bet is one where the bookmaker provides the stake (e.g. a sign-up offer). Tick **Free bet** when placing it.

- No `bet_placed` ledger entry is created — the syndicate didn't put any money in.
- If the free bet wins, winnings are recorded normally.
- If it's voided, there's nothing to return.

Free bets show up in the bet list with a "FREE" badge.

---

## Pot bets

A pot bet is funded from the shared winnings pool rather than from weekly contributions. Use this when the syndicate decides to reinvest some winnings in a new bet rather than distributing them.

Tick **Pot bet** when placing it.

Accounting:
- A `bet_placed` ledger entry is created as normal (money out).
- If it wins, the winnings go back into the shared pool.
- The stake is deducted from the shared winnings pool calculation rather than from individual player balances.

This means pot bets don't affect individual players' bet balances or the "bets placed" stat — only the shared pot is affected.

---

## How winnings are shared

Winnings from regular bets are tracked against the player who placed the bet, but they're **shared equally** across all active players for payout purposes.

The share calculation:
```
Share Per Player = (regular_winnings + pot_bet_winnings - pot_bet_stakes) ÷ active_player_count
```

Individual player profit/loss stats show only the bets they personally placed (useful for seeing who's picking winners), but the actual payout calculation uses the equal share.

---

## The bet balance

Each player has a "bet balance" — how much of their season budget they have left to stake. It's calculated as:

```
Budget = weekly_contribution × total_scheduled_weeks
Bet Balance = Budget - total_staked_by_this_player
```

This is based on the total number of weeks in the schedule, not weeks elapsed. If you haven't generated a schedule yet, the balance will show £0.

---

## Payout calculation

If a player wants to cash out, their payout is:

```
Payout = (actual_contributions - expected_contributions) + share_per_player
```

- If they've paid more than expected (ahead on contributions): they get that surplus back.
- If they've paid less than expected (behind): it's deducted.
- Plus their equal share of the total winnings pool.

Payouts are recorded as `payout` ledger entries (negative — money leaving the syndicate).

---

## Screenshots

When placing a bet you can upload a photo of the bet slip. Files are stored in `uploads/screenshots/` with a UUID filename. You can also upload or replace a screenshot later from the bet detail page.

Supported formats: JPG, JPEG, PNG, GIF, WebP.

---

## Pages

| Route | What it does |
|-------|-------------|
| `/bets` | List all bets for the active season. Filterable by status. Paginated (50 per page). |
| `/bets/new` | Place a new bet |
| `/bets/{id}` | Bet detail — shows the bet plus its ledger entries |
| `/bets/{id}/result` | Update the result (won/lost/void) |
| `/bets/{id}/edit` | Edit bet metadata |
| `/bets/{id}/screenshot` | Upload or replace a bet slip screenshot |

---

## Related docs

- [DATABASE.md](DATABASE.md) — ledger table and entry types
- [SEASONS.md](SEASONS.md) — how seasons and the schedule work
