from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import BankTransaction, LedgerEntry, Player, PlayerBankTransaction, Season

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    player_id: Optional[int] = None,
    source: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    season = db.query(Season).filter(Season.is_active == True).first()

    players = (
        db.query(Player)
        .filter(Player.is_active == True, Player.name != "Free Bets")
        .order_by(Player.name)
        .all()
    )

    # Bank transactions (all directions), scoped to current season dates
    bank_q = (
        db.query(BankTransaction, Player)
        .join(PlayerBankTransaction, BankTransaction.id == PlayerBankTransaction.bank_transaction_id)
        .join(Player, PlayerBankTransaction.player_id == Player.id)
    )
    if season:
        bank_q = bank_q.filter(BankTransaction.date >= season.start_date)
        if season.end_date:
            bank_q = bank_q.filter(BankTransaction.date <= season.end_date)
    if player_id:
        bank_q = bank_q.filter(Player.id == player_id)
    if source:
        bank_q = bank_q.filter(BankTransaction.source == source)
    bank_rows = bank_q.order_by(BankTransaction.date.desc()).all()

    # Ledger contributions scoped to current season
    contrib_q = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.player), joinedload(LedgerEntry.week))
        .filter(LedgerEntry.entry_type == "contribution", LedgerEntry.amount > 0)
    )
    if season:
        contrib_q = contrib_q.filter(LedgerEntry.season_id == season.id)
    if player_id:
        contrib_q = contrib_q.filter(LedgerEntry.player_id == player_id)
    all_contributions = contrib_q.order_by(LedgerEntry.entry_date).all()

    # All manually linked ledger_entry_ids across the entire DB
    linked_ids_global = {
        row[0]
        for row in db.query(BankTransaction.ledger_entry_id)
        .filter(BankTransaction.ledger_entry_id.isnot(None))
        .all()
    }

    # Fetch payouts for linking pool (contributions already fetched above)
    payout_link_q = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.player), joinedload(LedgerEntry.week))
        .filter(LedgerEntry.entry_type == "payout")
    )
    if season:
        payout_link_q = payout_link_q.filter(LedgerEntry.season_id == season.id)
    if player_id:
        payout_link_q = payout_link_q.filter(LedgerEntry.player_id == player_id)
    all_payouts_for_linking = payout_link_q.order_by(LedgerEntry.entry_date).all()

    # Build per-player pool of linkable entries (contributions + payouts, not yet linked)
    available_entries: dict = defaultdict(list)
    for entry in all_contributions + all_payouts_for_linking:
        if entry.id not in linked_ids_global:
            available_entries[entry.player_id].append(entry)
    # Sort each player's pool by date
    for pid in available_entries:
        available_entries[pid].sort(key=lambda e: e.entry_date)

    # Build audit rows
    audit_rows = []
    for txn, player in bank_rows:
        if txn.is_disregarded:
            status = "disregarded"
            ledger_entry = None
            auto_entry = None
        elif txn.ledger_entry_id:
            status = "matched"
            ledger_entry = (
                db.query(LedgerEntry)
                .options(joinedload(LedgerEntry.week))
                .filter(LedgerEntry.id == txn.ledger_entry_id)
                .first()
            )
            auto_entry = None
        else:
            window_start = txn.date - timedelta(days=7)
            window_end = txn.date + timedelta(days=7)
            target_type = "contribution" if txn.amount >= 0 else "payout"
            txn_amount = float(txn.amount)
            pool = available_entries[player.id]
            # Among candidates in window, pick closest date; prefer exact amount match
            exact_candidates = [
                e for e in pool
                if window_start <= e.entry_date <= window_end
                and e.entry_type == target_type
                and abs(float(e.amount) - txn_amount) < 0.01
            ]
            if exact_candidates:
                auto_entry = min(exact_candidates, key=lambda e: abs((e.entry_date - txn.date).days))
            else:
                approx_candidates = [
                    e for e in pool
                    if window_start <= e.entry_date <= window_end
                    and e.entry_type == target_type
                ]
                auto_entry = min(approx_candidates, key=lambda e: abs((e.entry_date - txn.date).days)) if approx_candidates else None
            if auto_entry:
                pool.remove(auto_entry)
            status = "auto" if auto_entry else "unmatched"
            ledger_entry = None

        audit_rows.append(
            {
                "txn": txn,
                "player": player,
                "ledger_entry": ledger_entry,
                "auto_entry": auto_entry,
                "status": status,
            }
        )

    # Ledger payouts for the same scope
    payout_q = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.entry_type == "payout")
    )
    if season:
        payout_q = payout_q.filter(LedgerEntry.season_id == season.id)
    if player_id:
        payout_q = payout_q.filter(LedgerEntry.player_id == player_id)
    all_payouts = payout_q.all()

    ledger_contributions = sum((e.amount for e in all_contributions), 0)
    ledger_payouts = sum((e.amount for e in all_payouts), 0)  # already negative
    bank_in = sum((r["txn"].amount for r in audit_rows if r["txn"].amount > 0 and r["status"] != "disregarded"), 0)
    bank_out = sum((r["txn"].amount for r in audit_rows if r["txn"].amount < 0 and r["status"] != "disregarded"), 0)

    # Stats computed before status filter
    stats = {
        "ledger_contributions": ledger_contributions,
        "ledger_payouts": ledger_payouts,
        "ledger_net": ledger_contributions + ledger_payouts,
        "bank_in": bank_in,
        "bank_out": bank_out,
        "bank_net": bank_in + bank_out,
        "matched": sum(1 for r in audit_rows if r["status"] == "matched"),
        "auto": sum(1 for r in audit_rows if r["status"] == "auto"),
        "unmatched": sum(1 for r in audit_rows if r["status"] == "unmatched"),
        "disregarded": sum(1 for r in audit_rows if r["status"] == "disregarded"),
    }

    if status_filter:
        display_rows = [r for r in audit_rows if r["status"] == status_filter]
    else:
        display_rows = audit_rows

    unmatched_contribs = sorted(
        [e for e in all_contributions + all_payouts_for_linking if e.id not in linked_ids_global],
        key=lambda e: e.entry_date,
    )

    return templates.TemplateResponse(
        "audit/index.html",
        {
            "request": request,
            "players": players,
            "audit_rows": display_rows,
            "available_entries": dict(available_entries),
            "stats": stats,
            "unmatched_contribs": unmatched_contribs,
            "selected_player_id": player_id,
            "selected_source": source,
            "selected_status": status_filter,
        },
    )


@router.post("/confirm-all")
async def confirm_all(
    player_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """Confirm all auto-suggested matches for a player (or all players)."""
    season = db.query(Season).filter(Season.is_active == True).first()

    bank_q = (
        db.query(BankTransaction, Player)
        .join(PlayerBankTransaction, BankTransaction.id == PlayerBankTransaction.bank_transaction_id)
        .join(Player, PlayerBankTransaction.player_id == Player.id)
        .filter(
            BankTransaction.is_disregarded == False,
            BankTransaction.ledger_entry_id.is_(None),
        )
    )
    if season:
        bank_q = bank_q.filter(BankTransaction.date >= season.start_date)
        if season.end_date:
            bank_q = bank_q.filter(BankTransaction.date <= season.end_date)
    if player_id:
        bank_q = bank_q.filter(Player.id == player_id)
    bank_rows = bank_q.all()

    linked_ids = {
        row[0]
        for row in db.query(BankTransaction.ledger_entry_id)
        .filter(BankTransaction.ledger_entry_id.isnot(None))
        .all()
    }

    # Build available entries per player (contributions + payouts, not yet linked)
    contrib_q = db.query(LedgerEntry).filter(
        LedgerEntry.entry_type == "contribution", LedgerEntry.amount > 0
    )
    if season:
        contrib_q = contrib_q.filter(LedgerEntry.season_id == season.id)
    if player_id:
        contrib_q = contrib_q.filter(LedgerEntry.player_id == player_id)

    payout_q2 = db.query(LedgerEntry).filter(LedgerEntry.entry_type == "payout")
    if season:
        payout_q2 = payout_q2.filter(LedgerEntry.season_id == season.id)
    if player_id:
        payout_q2 = payout_q2.filter(LedgerEntry.player_id == player_id)

    all_linkable = contrib_q.all() + payout_q2.all()

    available: dict = defaultdict(list)
    for entry in all_linkable:
        if entry.id not in linked_ids:
            available[entry.player_id].append(entry)
    for pid in available:
        available[pid].sort(key=lambda e: e.entry_date)

    confirmed = 0
    for txn, player in bank_rows:
        window_start = txn.date - timedelta(days=7)
        window_end = txn.date + timedelta(days=7)
        target_type = "contribution" if txn.amount >= 0 else "payout"
        txn_amount = float(txn.amount)
        pool = available[player.id]
        exact_candidates = [
            e for e in pool
            if window_start <= e.entry_date <= window_end
            and e.entry_type == target_type
            and abs(float(e.amount) - txn_amount) < 0.01
        ]
        if exact_candidates:
            auto_entry = min(exact_candidates, key=lambda e: abs((e.entry_date - txn.date).days))
        else:
            approx_candidates = [
                e for e in pool
                if window_start <= e.entry_date <= window_end
                and e.entry_type == target_type
            ]
            auto_entry = min(approx_candidates, key=lambda e: abs((e.entry_date - txn.date).days)) if approx_candidates else None
        if auto_entry:
            txn.ledger_entry_id = auto_entry.id
            # Remove from pool so the same entry isn't matched twice
            available[player.id].remove(auto_entry)
            linked_ids.add(auto_entry.id)
            confirmed += 1

    db.commit()

    redirect = "/audit"
    if player_id:
        redirect += f"?player_id={player_id}"
    return RedirectResponse(url=redirect, status_code=303)


def _audit_redirect(player_id, source, status_filter):
    params = []
    if player_id:
        params.append(f"player_id={player_id}")
    if source:
        params.append(f"source={source}")
    if status_filter:
        params.append(f"status_filter={status_filter}")
    return "/audit?" + "&".join(params) if params else "/audit"


@router.post("/link/{txn_id}")
async def link_transaction(
    txn_id: int,
    ledger_entry_id: int = Form(...),
    player_id: Optional[int] = Form(None),
    source: Optional[str] = Form(None),
    status_filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    txn = db.query(BankTransaction).filter(BankTransaction.id == txn_id).first()
    if txn:
        txn.ledger_entry_id = ledger_entry_id
        txn.is_disregarded = False
        db.commit()
    return RedirectResponse(url=_audit_redirect(player_id, source, status_filter), status_code=303)


@router.post("/disregard/{txn_id}")
async def disregard_transaction(
    txn_id: int,
    player_id: Optional[int] = Form(None),
    source: Optional[str] = Form(None),
    status_filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    txn = db.query(BankTransaction).filter(BankTransaction.id == txn_id).first()
    if txn:
        txn.is_disregarded = True
        txn.ledger_entry_id = None
        db.commit()
    return RedirectResponse(url=_audit_redirect(player_id, source, status_filter), status_code=303)


@router.post("/restore/{txn_id}")
async def restore_transaction(
    txn_id: int,
    player_id: Optional[int] = Form(None),
    source: Optional[str] = Form(None),
    status_filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    txn = db.query(BankTransaction).filter(BankTransaction.id == txn_id).first()
    if txn:
        txn.is_disregarded = False
        txn.ledger_entry_id = None
        db.commit()
    return RedirectResponse(url=_audit_redirect(player_id, source, status_filter), status_code=303)
