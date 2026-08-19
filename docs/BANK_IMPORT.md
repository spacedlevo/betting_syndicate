# Bank import and audit

## What this is for

The bank import lets you cross-check what's actually arrived in your bank account against what's recorded in the ledger. The typical workflow is:

1. Export CSVs from your bank accounts (Monzo, TSB, PayPal)
2. Drop them in the `bank statements/` folder
3. Run the import from `/import`
4. Go to `/audit` to match bank transactions against ledger contributions

This is how you spot if someone forgot to pay their weekly contribution, or if a payment came in that you haven't recorded in the ledger yet.

---

## Supported banks

| Bank | Format | Player matching |
|------|--------|----------------|
| Monzo | CSV export with "Name" column | Exact match against a hardcoded name map in `bank_import.py` |
| TSB | CSV export with "Transaction description" column | Substring match against a name map |
| PayPal | CSV export with "Name" column | Exact match against a name map |

Only transactions matching a known syndicate member name are imported. Everything else is filtered out — you never see non-syndicate transactions in the audit page.

### Adding a new player to the import

Edit `app/bank_import.py` and add their bank name to the relevant dictionary:

```python
# Monzo: the "Name" field from the CSV → your player's name in the database
MONZO_PLAYERS = {
    "SURNAME F": "Full Name As In Database",
    ...
}

# TSB: substring of the "Transaction description" field
TSB_PLAYERS = {
    "SURNAME F": "Full Name As In Database",
}

# PayPal: the "Name" field from the CSV
PAYPAL_PLAYERS = {
    "Full Name As On PayPal": "Full Name As In Database",
}
```

The player name on the right must exactly match the player's name in the database (case-insensitive lookup is used, so capitalisation doesn't matter).

---

## File structure

Put your CSV exports in subfolders of the `bank statements/` directory at the project root:

```
bank statements/
├── monzo/
│   └── monzo-export-aug-2025.csv
├── tsb/
│   └── tsb-statement.csv
└── paypal/
    └── paypal-export.CSV
```

The importer scans for `.csv` and `.CSV` files in each subfolder automatically.

---

## Running the import

Go to `/import` and click Import. The system will:

1. Parse all CSV files in the `bank statements/` subfolders
2. Match each row to a player using the name maps
3. Insert new transactions into the `bank_transactions` table
4. Skip any transaction it's already seen (deduplication by source + external ID)

The import page shows a count of how many transactions were matched and how many were new.

**TSB note:** TSB's CSV format has no transaction ID, so the system generates a synthetic dedup key from `date + description + amount`. If a transaction's description or amount changes between exports, it could be imported twice — check the audit page if you see duplicates.

---

## The audit page

Go to `/audit` to see all imported bank transactions alongside ledger contributions for the active season, grouped by player.

### Match statuses

Each bank transaction has one of these statuses:

| Status | Meaning |
|--------|---------|
| Matched | A ledger entry has been linked to this bank transaction |
| Unmatched | Bank transaction exists but no corresponding ledger contribution found |
| Disregarded | Deliberately ignored (e.g. a payment that isn't a syndicate contribution) |

The page also auto-matches transactions by finding a ledger contribution for the same player within ±3 days and the same amount.

### What to do with unmatched transactions

**Bank transaction but no ledger entry:** Someone paid but you haven't recorded their contribution. Go to `/ledger/contribute` and add it.

**Ledger entry but no bank transaction:** You've recorded a contribution but no corresponding payment came through. Chase the player.

### Disregarding a transaction

If a transaction is genuinely not a syndicate contribution (e.g. a personal transfer that happens to match a player name), click Disregard on the audit page. It will be hidden from the unmatched view.

---

## Database tables involved

- `bank_transactions` — the raw imported rows
- `player_bank_transactions` — links a bank transaction to a player
- `ledger` — the contributions being reconciled against

See [DATABASE.md](DATABASE.md) for the full column reference.

---

## Related docs

- [DATABASE.md](DATABASE.md) — bank_transactions and player_bank_transactions tables
- [BETS.md](BETS.md) — ledger contributions and how money flows
