"""Bank statement parsers and import logic for the betting syndicate."""

import csv
import glob
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BankTransaction, Player, PlayerBankTransaction

# Maps bank name field → canonical player name
MONZO_PLAYERS = {
    "THACKER C":              "Chris Thacker",
    "Andrew Thacker":         "Andy Thacker",
    "THOMAS S":               "Shane Thomas",
    "S Thomas":               "Shane Thomas",
    "BATES D":                "David Bates",
    "STEPHEN BUCKLEY-MELLOR": "Ste Mellor",
    "GARY BENYON":            "Gary Benyon",
}

# Substring match against TSB transaction description
TSB_PLAYERS = {
    "C TURNER": "Colin Turner",
}

PAYPAL_PLAYERS = {
    "James McNamee":   "James McNamee",
    "Ben Alston":      "Ben Alston",
    "David Ashcroft":  "David Ashcroft",
    "Craig Pemberton": "Craig Pemberton",
}


def _parse_dmy(s: str):
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()


def _parse_ymd(s: str):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _to_decimal(s: str) -> Decimal:
    s = s.strip().replace(",", "")
    if not s:
        return Decimal("0")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def parse_monzo(filepath: str) -> list[dict]:
    rows = []
    filename = os.path.basename(filepath)
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            if name not in MONZO_PLAYERS:
                continue
            rows.append({
                "source": "monzo",
                "external_id": row["Transaction ID"].strip(),
                "date": _parse_dmy(row["Date"]),
                "name": name,
                "amount": _to_decimal(row["Amount"]),
                "currency": row.get("Currency", "GBP").strip(),
                "transaction_type": row.get("Type", "").strip(),
                "source_file": filename,
                "player_name": MONZO_PLAYERS[name],
            })
    return rows


def parse_tsb(filepath: str) -> list[dict]:
    rows = []
    filename = os.path.basename(filepath)
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            description = row.get("Transaction description", "").strip()
            matched_player = None
            for key, player_name in TSB_PLAYERS.items():
                if key in description:
                    matched_player = player_name
                    break
            if matched_player is None:
                continue

            credit = _to_decimal(row.get("Credit amount", ""))
            debit = _to_decimal(row.get("Debit Amount", ""))
            if credit:
                amount = credit
            elif debit:
                amount = -debit
            else:
                amount = Decimal("0")

            date = _parse_ymd(row["Transaction date"])
            # Synthetic key for dedup since TSB has no transaction ID
            external_id = f"{row['Transaction date'].strip()}|{description}|{amount}"

            rows.append({
                "source": "tsb",
                "external_id": external_id,
                "date": date,
                "name": description,
                "amount": amount,
                "currency": "GBP",
                "transaction_type": row.get("Transaction Type", "").strip(),
                "source_file": filename,
                "player_name": matched_player,
            })
    return rows


def parse_paypal(filepath: str) -> list[dict]:
    rows = []
    filename = os.path.basename(filepath)
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            currency = row.get("Currency", "").strip()
            if name not in PAYPAL_PLAYERS or currency != "GBP":
                continue
            rows.append({
                "source": "paypal",
                "external_id": row["Transaction ID"].strip(),
                "date": _parse_dmy(row["Date"]),
                "name": name,
                "amount": _to_decimal(row["Amount"]),
                "currency": currency,
                "transaction_type": row.get("Type", "").strip(),
                "source_file": filename,
                "player_name": PAYPAL_PLAYERS[name],
            })
    return rows


def import_bank_statements(bank_statements_dir: str, session: Session) -> None:
    # Build player lookup: lowercase name → Player
    players = session.query(Player).all()
    player_map = {p.name.lower(): p for p in players}

    stats = {"monzo": (0, 0), "tsb": (0, 0), "paypal": (0, 0)}  # (parsed, inserted)

    parsers = [
        ("monzo",  parse_monzo,  "monzo/**/*.csv",  "monzo/*.csv"),
        ("tsb",    parse_tsb,    "tsb/**/*.csv",    "tsb/*.csv"),
        ("paypal", parse_paypal, "paypal/**/*.CSV", "paypal/*.csv"),
    ]

    for source, parser_fn, glob_pattern, glob_pattern2 in parsers:
        base = os.path.join(bank_statements_dir, source)
        files = glob.glob(os.path.join(base, "*.csv")) + glob.glob(os.path.join(base, "*.CSV"))
        files = list(set(files))

        parsed_total = 0
        inserted_total = 0

        for filepath in files:
            rows = parser_fn(filepath)
            parsed_total += len(rows)

            for row in rows:
                player = player_map.get(row["player_name"].lower())
                if player is None:
                    print(f"  WARNING: No player found for '{row['player_name']}' — skipping")
                    continue

                try:
                    txn = BankTransaction(
                        source=row["source"],
                        external_id=row["external_id"],
                        date=row["date"],
                        name=row["name"],
                        amount=row["amount"],
                        currency=row["currency"],
                        transaction_type=row["transaction_type"],
                        source_file=row["source_file"],
                    )
                    session.add(txn)
                    session.flush()
                    link = PlayerBankTransaction(bank_transaction=txn, player=player)
                    session.add(link)
                    session.commit()
                    inserted_total += 1
                except IntegrityError:
                    session.rollback()  # duplicate — skip

        stats[source] = (parsed_total, inserted_total)

    print("\nBank statement import complete:")
    for source, (parsed, inserted) in stats.items():
        print(f"  {source.capitalize():8s}  matched: {parsed:3d}  new: {inserted:3d}")
