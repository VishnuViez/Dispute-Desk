"""
generate_data.py – Create data/disputedesk.db and data/cases.csv.

Run from the repo root:
    python data/generate_data.py

Rules:
- Standard library only (sqlite3, csv, random, datetime, pathlib).
- random.seed(42) and REFERENCE_DATE = 2026-10-15 → identical every run.
- Each run deletes and recreates the database.
- Synthetic data only; no real names, emails, phone numbers, or addresses.
"""

import csv
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REFERENCE_DATE = date(2026, 10, 15)
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "disputedesk.db"
CSV_PATH = REPO_ROOT / "data" / "cases.csv"

random.seed(42)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def next_5th(d: date) -> date:
    """Return the next 5th-of-the-month on or after d (statement close date)."""
    if d.day <= 5:
        return date(d.year, d.month, 5)
    # advance to the 5th of the following month
    if d.month == 12:
        return date(d.year + 1, 1, 5)
    return date(d.year, d.month + 1, 5)


def days_before(n: int) -> date:
    return REFERENCE_DATE - timedelta(days=n)


def fmt(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def rand_last4() -> str:
    return f"{random.randint(1000, 9999)}"


def rand_amount(lo: float, hi: float) -> float:
    return round(random.uniform(lo, hi), 2)


def rand_date_between(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE customers (
    customer_id       TEXT PRIMARY KEY,
    account_open_date TEXT NOT NULL
);

CREATE TABLE cards (
    card_id     TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers,
    network     TEXT NOT NULL DEFAULT 'visa',
    card_type   TEXT NOT NULL,
    last4       TEXT NOT NULL
);

CREATE TABLE merchants (
    merchant_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    is_online     INTEGER NOT NULL,
    refund_policy TEXT NOT NULL
);

CREATE TABLE subscriptions (
    subscription_id   TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL REFERENCES customers,
    card_id           TEXT NOT NULL REFERENCES cards,
    merchant_id       TEXT NOT NULL REFERENCES merchants,
    monthly_amount_usd REAL NOT NULL,
    start_date        TEXT NOT NULL,
    cancelled_date    TEXT
);

CREATE TABLE transactions (
    transaction_id      TEXT PRIMARY KEY,
    card_id             TEXT NOT NULL REFERENCES cards,
    customer_id         TEXT NOT NULL REFERENCES customers,
    merchant_id         TEXT NOT NULL REFERENCES merchants,
    txn_datetime        TEXT NOT NULL,
    amount_usd          REAL NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'USD',
    channel             TEXT NOT NULL,
    device_id           TEXT,
    shipping_address_id TEXT,
    subscription_id     TEXT REFERENCES subscriptions,
    statement_date      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'posted'
);

CREATE TABLE shipments (
    shipment_id           TEXT PRIMARY KEY,
    transaction_id        TEXT NOT NULL REFERENCES transactions,
    carrier               TEXT NOT NULL,
    shipped_date          TEXT,
    expected_delivery_date TEXT NOT NULL,
    delivered_date        TEXT,
    delivery_status       TEXT NOT NULL,
    proof_of_delivery     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE refunds (
    refund_id      TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL REFERENCES transactions,
    refund_date    TEXT NOT NULL,
    amount_usd     REAL NOT NULL
);

CREATE TABLE disputes (
    dispute_id     TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL REFERENCES transactions,
    customer_id    TEXT NOT NULL REFERENCES customers,
    filed_date     TEXT NOT NULL,
    complaint_text TEXT NOT NULL,
    status         TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Merchant catalogue (25 merchants, fictional names only)
# ---------------------------------------------------------------------------

MERCHANT_DEFS = [
    # (name, category, is_online, refund_policy)
    ("Bramble & Bean Coffee", "coffee_shop", 0, "No refunds on prepared drinks; unopened bags refunded within 7 days."),
    ("The Roasted Crow", "coffee_shop", 0, "Refunds on merchandise within 14 days with receipt."),
    ("Patio Verde Café", "coffee_shop", 0, "All sales final on food and beverages."),
    ("Saltwood Kitchen", "restaurant", 0, "Contact us within 24 hours of your visit for any billing concerns."),
    ("The Amber Fork", "restaurant", 0, "No refunds; please raise concerns with your server before leaving."),
    ("Mossfern Market", "grocery", 0, "Full refund or exchange within 30 days with original packaging."),
    ("Daybreak Foods", "grocery", 0, "Perishables are non-refundable; shelf-stable items refunded within 14 days."),
    ("Veldt Supply Co.", "online_retail", 1, "Returns accepted within 30 days; customer pays return shipping."),
    ("Thornwick Goods", "online_retail", 1, "Full refund within 45 days if item is returned unused in original box."),
    ("Cascade Outfitters", "online_retail", 1, "Exchange or store credit within 60 days; no cash refunds after 30 days."),
    ("NovaSpark Electronics", "electronics", 1, "Defective items replaced within 90 days; no refunds after 30 days."),
    ("Circuit Hollow", "electronics", 0, "In-store returns within 15 days; online orders refunded within 30 days."),
    ("Pixel & Wire", "electronics", 1, "All sales final on opened software; hardware returns within 14 days."),
    ("StreamFlick Plus", "streaming", 1, "Cancel any time; partial-month fees are non-refundable."),
    ("SoundLoop", "streaming", 1, "Refunds issued only for duplicate charges; contact billing within 48 hours."),
    ("ZenCast", "streaming", 1, "Pro-rated refund if cancelled in the first 7 days of a billing cycle."),
    ("IronPath Fitness", "fitness", 0, "Monthly memberships non-refundable; annual plans prorated after 30 days."),
    ("HarborLight Gym", "fitness", 0, "No refunds after the first 3 days; freeze available for up to 3 months."),
    ("Cloudstep Fitness", "fitness", 1, "Digital plans refundable within 14 days if fewer than 3 sessions used."),
    ("Wanderlux Travel", "travel", 1, "Full refund if cancelled 14+ days before departure; 50% within 7 days."),
    ("Skybridge Flights", "travel", 1, "Non-refundable fares; change fees apply."),
    ("Crestline Stays", "travel", 1, "Free cancellation up to 48 hours before check-in."),
    ("Ridgeline Outfitters", "online_retail", 1, "Items returned within 30 days for full refund; clearance items final sale."),
    ("Harbor Eats", "restaurant", 0, "Concerns addressed at the time of service only."),
    ("Northwall Supply", "online_retail", 1, "Refunds processed within 5 business days of receiving the returned item."),
]

CARRIERS = ["FedEx", "UPS", "USPS", "DHL"]
PHYSICAL_CATEGORIES = {"online_retail", "electronics"}

# ---------------------------------------------------------------------------
# Counters for IDs (global, so case-planting functions can continue the seq)
# ---------------------------------------------------------------------------

_counters = {
    "txn": 0,
    "ship": 0,
    "refund": 0,
    "dispute": 0,
    "sub": 0,
    "case": 0,
}


def next_id(kind: str) -> str:
    _counters[kind] += 1
    fmt_map = {
        "txn":     f"TXN-{_counters['txn']:06d}",
        "ship":    f"SHIP-{_counters['ship']:04d}",
        "refund":  f"REF-{_counters['refund']:04d}",
        "dispute": f"DSP-{_counters['dispute']:04d}",
        "sub":     f"SUB-{_counters['sub']:04d}",
        "case":    f"CASE-{_counters['case']:04d}",
    }
    return fmt_map[kind]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def build_database():
    # Remove old DB
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    conn.row_factory = sqlite3.Row

    # -----------------------------------------------------------------------
    # 1. Customers (60)
    # -----------------------------------------------------------------------
    customers = []
    for i in range(1, 61):
        cid = f"CUST-{i:04d}"
        open_date = fmt(days_before(random.randint(365, 1825)))
        customers.append((cid, open_date))
    conn.executemany("INSERT INTO customers VALUES (?,?)", customers)

    # -----------------------------------------------------------------------
    # 2. Cards (1–2 per customer, ~70% credit / 30% debit)
    # -----------------------------------------------------------------------
    # card_id → (customer_id, card_type)
    customer_cards: dict[str, list[str]] = {c[0]: [] for c in customers}
    cards = []
    card_type_map: dict[str, str] = {}
    card_counter = 0
    for cid, _ in customers:
        n_cards = 1 if random.random() < 0.5 else 2
        for _ in range(n_cards):
            card_counter += 1
            card_id = f"CARD-{card_counter:04d}"
            ctype = "credit" if random.random() < 0.70 else "debit"
            cards.append((card_id, cid, "visa", ctype, rand_last4()))
            customer_cards[cid].append(card_id)
            card_type_map[card_id] = ctype
    conn.executemany("INSERT INTO cards VALUES (?,?,?,?,?)", cards)

    # -----------------------------------------------------------------------
    # 3. Merchants (25)
    # -----------------------------------------------------------------------
    merchants = []
    merchant_ids: list[str] = []
    for i, (name, cat, is_online, policy) in enumerate(MERCHANT_DEFS, 1):
        mid = f"MERCH-{i:03d}"
        merchants.append((mid, name, cat, is_online, policy))
        merchant_ids.append(mid)
    conn.executemany("INSERT INTO merchants VALUES (?,?,?,?,?)", merchants)

    # Convenience lookups
    merchant_by_id: dict[str, tuple] = {m[0]: m for m in merchants}
    online_merchants = [m[0] for m in merchants if m[3] == 1]
    instore_merchants = [m[0] for m in merchants if m[3] == 0]
    coffee_merchants = [m[0] for m in merchants if m[2] == "coffee_shop"]
    streaming_merchants = [m[0] for m in merchants if m[2] == "streaming"]
    subscription_merchants = streaming_merchants  # use streaming for subs

    # -----------------------------------------------------------------------
    # 4. Device IDs and shipping address IDs per customer
    # -----------------------------------------------------------------------
    customer_devices: dict[str, list[str]] = {}
    customer_addrs: dict[str, list[str]] = {}
    dev_counter = 0
    addr_counter = 0
    for cid, _ in customers:
        n_dev = random.choice([1, 1, 2])
        devs = []
        for _ in range(n_dev):
            dev_counter += 1
            devs.append(f"DEV-{dev_counter:04d}")
        customer_devices[cid] = devs

        n_addr = random.choice([1, 1, 2])
        addrs = []
        for _ in range(n_addr):
            addr_counter += 1
            addrs.append(f"ADDR-{addr_counter:04d}")
        customer_addrs[cid] = addrs

    # -----------------------------------------------------------------------
    # 5. Subscriptions (~8 background)
    # -----------------------------------------------------------------------
    subscriptions = []
    # Pick 8 distinct (customer, streaming_merchant) pairs
    sub_pairs = random.sample(
        [(c[0], m) for c in customers for m in subscription_merchants], 8
    )
    for cid, mid in sub_pairs:
        sub_id = next_id("sub")
        card_id = random.choice(customer_cards[cid])
        monthly = rand_amount(8, 30)
        start = fmt(days_before(random.randint(120, 700)))
        cancelled = None  # background subs stay active
        subscriptions.append((sub_id, cid, card_id, mid, monthly, start, cancelled))
    conn.executemany("INSERT INTO subscriptions VALUES (?,?,?,?,?,?,?)", subscriptions)
    # Build lookup: (customer_id, merchant_id) → subscription_id
    sub_lookup: dict[tuple, str] = {
        (s[1], s[3]): s[0] for s in subscriptions
    }

    # -----------------------------------------------------------------------
    # 6. Background transactions (~500)
    # -----------------------------------------------------------------------
    # Track (card_id, merchant_id, amount_usd, date) to prevent accidental
    # duplicates (same card + merchant + amount within 24 h).
    # key = (card_id, merchant_id, amount_cents, date_str)
    txn_signature_set: set[tuple] = set()

    # Also track per-customer merchant purchase history for 10.4 evidence.
    # cust_merchant_txns[cid][mid] = list of transaction dicts
    cust_merchant_txns: dict[str, dict[str, list[dict]]] = {
        c[0]: {} for c in customers
    }

    all_txn_rows = []  # accumulated for bulk insert

    def _make_txn(
        card_id: str,
        customer_id: str,
        merchant_id: str,
        txn_dt: datetime,
        amount: float,
        channel: str,
        device_id: str | None = None,
        shipping_address_id: str | None = None,
        subscription_id: str | None = None,
        status: str = "posted",
    ) -> str:
        txn_id = next_id("txn")
        stmt = fmt(next_5th(txn_dt.date()))
        all_txn_rows.append((
            txn_id, card_id, customer_id, merchant_id,
            fmt_dt(txn_dt), round(amount, 2), "USD",
            channel, device_id, shipping_address_id,
            subscription_id, stmt, status,
        ))
        if customer_id not in cust_merchant_txns:
            cust_merchant_txns[customer_id] = {}
        cust_merchant_txns[customer_id].setdefault(merchant_id, []).append({
            "txn_id": txn_id, "card_id": card_id, "txn_dt": txn_dt,
            "amount": amount, "device_id": device_id,
            "shipping_address_id": shipping_address_id,
        })
        return txn_id

    def _sig(card_id, merchant_id, amount, d: date):
        return (card_id, merchant_id, round(amount * 100), fmt(d))

    def _safe_amount(card_id, merchant_id, lo, hi):
        """Pick an amount that won't create an accidental duplicate signature."""
        for _ in range(50):
            amt = rand_amount(lo, hi)
            # check against today ± 1 day window doesn't matter for background;
            # the set is keyed by date, so collisions are per-day.
            return amt
        return rand_amount(lo, hi)

    # Merchants reserved for escalate cases (never used in background transactions)
    _ESCALATE_MERCHANTS = {
        f"MERCH-{i:03d}" for i in (23, 24, 25)  # Ridgeline Outfitters, Harbor Eats, Northwall Supply
    }
    bg_online_merchants = [m for m in online_merchants if m not in _ESCALATE_MERCHANTS]
    bg_instore_merchants = instore_merchants  # instore merchants are fine

    for _ in range(500):
        cid = random.choice(customers)[0]
        card_id = random.choice(customer_cards[cid])
        # prefer online merchants for online channel
        channel_roll = random.random()
        if channel_roll < 0.35:
            channel = "online"
            mid = random.choice(bg_online_merchants)
        elif channel_roll < 0.55:
            channel = "recurring"
            # use one of the customer's subscriptions if possible, else skip
            cust_subs = [(k[1], v) for k, v in sub_lookup.items() if k[0] == cid]
            if not cust_subs:
                channel = "in_store"
                mid = random.choice(instore_merchants)
            else:
                mid, sub_id_bg = random.choice(cust_subs)
        else:
            channel = "in_store"
            mid = random.choice(instore_merchants)

        days_ago = random.randint(1, 400)
        txn_date = days_before(days_ago)
        hour = random.randint(8, 21)
        minute = random.randint(0, 59)
        txn_dt = datetime(txn_date.year, txn_date.month, txn_date.day, hour, minute)

        merch = merchant_by_id[mid]
        cat = merch[2]
        is_online_merch = merch[3]

        # Amount ranges by category
        amt_range = {
            "coffee_shop": (4, 15), "restaurant": (12, 80),
            "grocery": (20, 120), "online_retail": (15, 200),
            "electronics": (30, 500), "streaming": (8, 30),
            "fitness": (20, 80), "travel": (50, 600),
        }.get(cat, (10, 100))

        # Avoid accidental duplicate: same card, merchant, amount, same day
        for _ in range(10):
            amt = rand_amount(*amt_range)
            sig = _sig(card_id, mid, amt, txn_date)
            if sig not in txn_signature_set:
                txn_signature_set.add(sig)
                break

        device_id = None
        addr_id = None
        sub_id_val = None

        if channel == "online" and is_online_merch:
            device_id = random.choice(customer_devices[cid])
            if cat in PHYSICAL_CATEGORIES:
                addr_id = random.choice(customer_addrs[cid])
        elif channel == "recurring":
            cust_subs = [(k[1], v) for k, v in sub_lookup.items() if k[0] == cid]
            if cust_subs:
                mid, sub_id_val = random.choice(cust_subs)
                merch = merchant_by_id[mid]
                # recurring uses subscription amount
                for s in subscriptions:
                    if s[0] == sub_id_val:
                        amt = s[4]
                        break

        _make_txn(card_id, cid, mid, txn_dt, amt, channel,
                  device_id, addr_id, sub_id_val)

    # -----------------------------------------------------------------------
    # 7. Shipments for background online physical-goods transactions
    # -----------------------------------------------------------------------
    ship_rows = []

    def _make_shipment(txn_id: str, txn_dt: datetime,
                       status: str = "delivered",
                       proof: int = 1,
                       expected_offset: int = 7,
                       shipped_offset: int | None = 2,
                       delivered_offset: int | None = None) -> str:
        ship_id = next_id("ship")
        carrier = random.choice(CARRIERS)
        shipped_date = fmt(txn_dt.date() + timedelta(days=shipped_offset)) if shipped_offset is not None else None
        expected = fmt(txn_dt.date() + timedelta(days=expected_offset))
        if delivered_offset is not None:
            delivered = fmt(txn_dt.date() + timedelta(days=delivered_offset))
        else:
            delivered = None
        ship_rows.append((ship_id, txn_id, carrier, shipped_date, expected,
                          delivered, status, proof))
        return ship_id

    for row in all_txn_rows:
        txn_id, card_id, cid, mid = row[0], row[1], row[2], row[3]
        txn_dt_str = row[4]
        txn_dt = datetime.strptime(txn_dt_str, "%Y-%m-%dT%H:%M:%S")
        channel = row[7]
        merch = merchant_by_id[mid]
        cat = merch[2]
        if channel == "online" and cat in PHYSICAL_CATEGORIES:
            _make_shipment(txn_id, txn_dt,
                           status="delivered",
                           proof=1,
                           expected_offset=random.randint(5, 10),
                           shipped_offset=random.randint(1, 3),
                           delivered_offset=random.randint(4, 12))

    # -----------------------------------------------------------------------
    # 8. Background refunds (~15)
    # -----------------------------------------------------------------------
    refund_rows = []
    refund_txn_set: set[str] = set()

    def _make_refund(txn_id: str, txn_date: date, amount: float) -> str:
        ref_id = next_id("refund")
        refund_date = fmt(txn_date + timedelta(days=random.randint(3, 14)))
        refund_rows.append((ref_id, txn_id, refund_date, round(amount, 2)))
        refund_txn_set.add(txn_id)
        return ref_id

    bg_txn_candidates = [r for r in all_txn_rows
                         if r[7] in ("online", "in_store")]
    for row in random.sample(bg_txn_candidates, min(15, len(bg_txn_candidates))):
        txn_id = row[0]
        txn_dt = datetime.strptime(row[4], "%Y-%m-%dT%H:%M:%S")
        _make_refund(txn_id, txn_dt.date(), row[5])

    # -----------------------------------------------------------------------
    # 9. Background disputes (~20, already resolved)
    # -----------------------------------------------------------------------
    dispute_rows = []
    bg_dispute_txns = random.sample(bg_txn_candidates, min(20, len(bg_txn_candidates)))
    past_statuses = ["resolved_customer", "resolved_merchant", "withdrawn"]

    for row in bg_dispute_txns:
        d_id = next_id("dispute")
        txn_id = row[0]
        cid = row[2]
        txn_date = datetime.strptime(row[4], "%Y-%m-%dT%H:%M:%S").date()
        filed = fmt(txn_date + timedelta(days=random.randint(5, 55)))
        text = random.choice([
            "I don't recognize this charge.",
            "This was charged to my card by mistake.",
            "I returned the item but never got my money back.",
            "The merchant charged me twice.",
            "I cancelled but they kept billing me.",
        ])
        status = random.choice(past_statuses)
        dispute_rows.append((d_id, txn_id, cid, filed, text, status))

    # -----------------------------------------------------------------------
    # Now flush background data (transactions, shipments, refunds, disputes)
    # Case planting will append more rows via the same lists.
    # -----------------------------------------------------------------------
    conn.executemany(
        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        all_txn_rows,
    )
    conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?)", ship_rows)
    conn.executemany("INSERT INTO refunds VALUES (?,?,?,?)", refund_rows)
    conn.executemany("INSERT INTO disputes VALUES (?,?,?,?,?,?)", dispute_rows)

    # -----------------------------------------------------------------------
    # CASE PLANTING HELPERS
    # -----------------------------------------------------------------------

    cases_csv: list[dict] = []

    def _add_txn_direct(row: tuple) -> None:
        """Insert a single transaction row immediately (for case planting)."""
        conn.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)

    def _add_shipment_direct(row: tuple) -> None:
        conn.execute("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?)", row)

    def _add_refund_direct(row: tuple) -> None:
        conn.execute("INSERT INTO refunds VALUES (?,?,?,?)", row)

    def _add_dispute_direct(row: tuple) -> None:
        conn.execute("INSERT INTO disputes VALUES (?,?,?,?,?,?)", row)

    def _add_sub_direct(row: tuple) -> None:
        conn.execute("INSERT INTO subscriptions VALUES (?,?,?,?,?,?,?)", row)

    def _plant_txn(
        card_id: str,
        customer_id: str,
        merchant_id: str,
        txn_dt: datetime,
        amount: float,
        channel: str,
        device_id: str | None = None,
        shipping_address_id: str | None = None,
        subscription_id: str | None = None,
        status: str = "posted",
    ) -> str:
        txn_id = next_id("txn")
        stmt = fmt(next_5th(txn_dt.date()))
        row = (
            txn_id, card_id, customer_id, merchant_id,
            fmt_dt(txn_dt), round(amount, 2), "USD",
            channel, device_id, shipping_address_id,
            subscription_id, stmt, status,
        )
        _add_txn_direct(row)
        return txn_id, stmt

    def _plant_shipment(txn_id, txn_date, status, proof,
                        expected_offset, shipped_offset=None,
                        delivered_offset=None):
        ship_id = next_id("ship")
        carrier = random.choice(CARRIERS)
        shipped = fmt(txn_date + timedelta(days=shipped_offset)) if shipped_offset else None
        expected = fmt(txn_date + timedelta(days=expected_offset))
        delivered = fmt(txn_date + timedelta(days=delivered_offset)) if delivered_offset else None
        _add_shipment_direct((ship_id, txn_id, carrier, shipped, expected,
                               delivered, status, proof))
        return ship_id, txn_date + timedelta(days=expected_offset)

    def _plant_dispute(txn_id, cid, filed_date, complaint, status="open"):
        d_id = next_id("dispute")
        _add_dispute_direct((d_id, txn_id, cid, fmt(filed_date), complaint, status))
        return d_id

    def _add_case(case_id, dispute_id, txn_id, cid, filed_date,
                  complaint, reason_code, outcome, demo, notes):
        cases_csv.append({
            "case_id": case_id,
            "dispute_id": dispute_id,
            "transaction_id": txn_id,
            "customer_id": cid,
            "filed_date": fmt(filed_date),
            "complaint_text": complaint,
            "expected_reason_code": reason_code,
            "expected_outcome": outcome,
            "demo_case": demo,
            "notes": notes,
        })

    # Reserve distinct customers for case planting (use customers 1–30)
    case_custs = [f"CUST-{i:04d}" for i in range(1, 31)]
    # Each case customer has cards already. Pick their first card.
    def _card(cid): return customer_cards[cid][0]
    def _dev(cid): return customer_devices[cid][0]
    def _addr(cid): return customer_addrs[cid][0]

    # Coffee shop merchant for demo A
    coffee_mid = coffee_merchants[0]  # MERCH-001 Bramble & Bean Coffee

    # An online_retail merchant for fraud/not-received cases
    online_retail_mids = [m[0] for m in merchants if m[2] == "online_retail"]
    electronics_mids = [m[0] for m in merchants if m[2] == "electronics"]

    # -----------------------------------------------------------------------
    # DEMO A – Duplicate charge 12.6.1 (file_chargeback)
    # Two identical $6.50 charges 2 minutes apart at the same coffee shop.
    # -----------------------------------------------------------------------
    cid_A = case_custs[0]
    card_A = _card(cid_A)
    base_dt_A = datetime(2026, 10, 1, 9, 14)
    txn_A1, stmt_A1 = _plant_txn(card_A, cid_A, coffee_mid, base_dt_A, 6.50, "in_store")
    txn_A2, _ = _plant_txn(card_A, cid_A, coffee_mid, base_dt_A + timedelta(minutes=2), 6.50, "in_store")
    filed_A = date(2026, 10, 10)
    complaint_A = "I was charged twice at a coffee shop. Both charges are $6.50 and I only bought one drink."
    did_A = _plant_dispute(txn_A2, cid_A, filed_A, complaint_A)
    case_A = next_id("case")
    _add_case(case_A, did_A, txn_A2, cid_A, filed_A, complaint_A, "12.6.1", "file_chargeback", "A",
              "Two identical charges 2 minutes apart on the same card at the same merchant; clear duplicate processing.")

    # -----------------------------------------------------------------------
    # Duplicate 12.6.1 – file_chargeback #2
    # -----------------------------------------------------------------------
    cid = case_custs[1]
    card = _card(cid)
    base_dt = datetime(2026, 9, 20, 14, 5)
    mid_dup = coffee_merchants[1]
    txn1, stmt1 = _plant_txn(card, cid, mid_dup, base_dt, 11.25, "in_store")
    txn2, _ = _plant_txn(card, cid, mid_dup, base_dt + timedelta(minutes=4), 11.25, "in_store")
    filed = date(2026, 10, 6)  # Oct 5 is the stmt date (next 5th after Sep 20)
    complaint = "They charged me twice for the same coffee order! Same amount, looked like right after each other."
    did = _plant_dispute(txn2, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn2, cid, filed, complaint, "12.6.1", "file_chargeback", "",
              "Same card, merchant, and amount charged twice within 4 minutes; duplicate processing.")

    # -----------------------------------------------------------------------
    # Duplicate 12.6.1 – file_chargeback #3
    # -----------------------------------------------------------------------
    cid = case_custs[2]
    card = _card(cid)
    base_dt = datetime(2026, 9, 28, 11, 30)
    mid_dup3 = coffee_merchants[2]
    txn1, _ = _plant_txn(card, cid, mid_dup3, base_dt, 8.75, "in_store")
    txn2, _ = _plant_txn(card, cid, mid_dup3, base_dt + timedelta(minutes=1), 8.75, "in_store")
    filed = date(2026, 10, 5)
    complaint = "My card was charged $8.75 twice in a minute. This is clearly an error."
    did = _plant_dispute(txn2, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn2, cid, filed, complaint, "12.6.1", "file_chargeback", "",
              "Identical amounts 1 minute apart on the same card and merchant; duplicate processing.")

    # -----------------------------------------------------------------------
    # Duplicate 12.6.1 – request_more_info (4+ hours apart)
    # -----------------------------------------------------------------------
    cid = case_custs[3]
    card = _card(cid)
    base_dt = datetime(2026, 9, 15, 8, 0)
    mid_dup4 = coffee_merchants[0]
    txn1, _ = _plant_txn(card, cid, mid_dup4, base_dt, 5.50, "in_store")
    txn2, _ = _plant_txn(card, cid, mid_dup4, base_dt + timedelta(hours=5), 5.50, "in_store")
    filed = date(2026, 10, 5)  # Oct 5 is the stmt date (next 5th after Sep 15)
    complaint = "I see two charges for $5.50 at the same coffee place on the same day. Not sure if I went twice."
    did = _plant_dispute(txn2, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn2, cid, filed, complaint, "12.6.1", "request_more_info", "",
              "Same amount at same merchant but 5 hours apart; could be two separate visits, need confirmation.")

    # -----------------------------------------------------------------------
    # 13.1 Item not received – file_chargeback #1
    # -----------------------------------------------------------------------
    cid = case_custs[4]
    card = _card(cid)
    mid_or = online_retail_mids[0]
    txn_dt = datetime(2026, 8, 10, 13, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or, txn_dt, 89.99, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, exp_date = _plant_shipment(txn_id, txn_dt.date(), "lost", 0,
                                  expected_offset=10, shipped_offset=2, delivered_offset=None)
    filed = date(2026, 10, 1)  # within 60 days of Sep 5 stmt; expected delivery Aug 20 long passed
    complaint = "I ordered something online over a month ago and it never showed up. The tracking just stopped updating."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.1", "file_chargeback", "",
              "Expected delivery date passed, shipment status is lost, no delivery recorded.")

    # -----------------------------------------------------------------------
    # 13.1 Item not received – file_chargeback #2
    # -----------------------------------------------------------------------
    cid = case_custs[5]
    card = _card(cid)
    mid_or2 = online_retail_mids[1]
    txn_dt = datetime(2026, 8, 20, 10, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or2, txn_dt, 142.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, exp_date = _plant_shipment(txn_id, txn_dt.date(), "in_transit", 0,
                                  expected_offset=7, shipped_offset=2, delivered_offset=None)
    filed = date(2026, 10, 2)  # within 60 days of Sep 5 stmt; expected delivery Aug 27 long passed
    complaint = "My package was supposed to arrive 3 weeks ago. It says 'in transit' but nothing has changed."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.1", "file_chargeback", "",
              "Shipment in transit past expected delivery date with no delivery confirmation.")

    # -----------------------------------------------------------------------
    # 13.1 Item not received – file_chargeback #3
    # -----------------------------------------------------------------------
    cid = case_custs[6]
    card = _card(cid)
    mid_el = electronics_mids[0]
    txn_dt = datetime(2026, 8, 25, 15, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_el, txn_dt, 230.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, exp_date = _plant_shipment(txn_id, txn_dt.date(), "not_shipped", 0,
                                  expected_offset=8, shipped_offset=None, delivered_offset=None)
    filed = date(2026, 10, 3)  # within 60 days of Sep 5 stmt; expected delivery Sep 2 long passed
    complaint = "I paid for an electronic item almost a month ago and it still hasn't shipped. This is ridiculous."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.1", "file_chargeback", "",
              "Item never shipped; expected delivery date passed; no delivery recorded.")

    # -----------------------------------------------------------------------
    # 13.1 Item not received – request_more_info
    # (proof_of_delivery=1 to customer's usual address)
    # -----------------------------------------------------------------------
    cid = case_custs[7]
    card = _card(cid)
    mid_or3 = online_retail_mids[2]
    txn_dt = datetime(2026, 9, 5, 11, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or3, txn_dt, 58.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, exp_date = _plant_shipment(txn_id, txn_dt.date(), "delivered", 1,
                                  expected_offset=7, shipped_offset=2, delivered_offset=9)
    filed = date(2026, 10, 1)
    complaint = "I never received my order even though it says delivered. Very frustrating."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.1", "request_more_info", "",
              "Shipment shows delivered with proof of delivery to customer's address; need customer to confirm non-receipt.")

    # -----------------------------------------------------------------------
    # 13.1 Item not received – deny (too early, expected_delivery_date not yet)
    # -----------------------------------------------------------------------
    cid = case_custs[8]
    card = _card(cid)
    mid_or4 = online_retail_mids[3] if len(online_retail_mids) > 3 else online_retail_mids[0]
    txn_dt = datetime(2026, 10, 8, 9, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or4, txn_dt, 74.50, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    # expected delivery is Oct 20, AFTER reference date Oct 15
    _, exp_date = _plant_shipment(txn_id, txn_dt.date(), "in_transit", 0,
                                  expected_offset=12, shipped_offset=2, delivered_offset=None)
    filed = date(2026, 10, 13)
    complaint = "I ordered something a few days ago and I'm worried it won't arrive. Can I dispute this already?"
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.1", "deny", "",
              "Expected delivery date has not yet passed; dispute filed too early.")

    # -----------------------------------------------------------------------
    # 13.2 Cancelled subscription – file_chargeback #1
    # -----------------------------------------------------------------------
    cid = case_custs[9]
    card = _card(cid)
    stream_mid = streaming_merchants[0]
    sub_id_13_2_a = next_id("sub")
    cancel_date = date(2026, 8, 1)
    _add_sub_direct((sub_id_13_2_a, cid, card, stream_mid,
                     14.99, fmt(days_before(300)), fmt(cancel_date)))
    # Charge AFTER cancel date
    txn_dt = datetime(2026, 9, 1, 0, 5)
    txn_id, stmt = _plant_txn(card, cid, stream_mid, txn_dt, 14.99, "recurring",
                               subscription_id=sub_id_13_2_a)
    filed = date(2026, 10, 6)  # stmt is Oct 5 (next 5th after Sep 1); Oct 6 is 1 day after stmt
    complaint = "I cancelled my subscription in August but they charged me again in September. I want my money back."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.2", "file_chargeback", "",
              "Charge posted after the subscription's cancelled_date; valid chargeback.")

    # -----------------------------------------------------------------------
    # 13.2 Cancelled subscription – file_chargeback #2
    # -----------------------------------------------------------------------
    cid = case_custs[10]
    card = _card(cid)
    stream_mid2 = streaming_merchants[1]
    sub_id_13_2_b = next_id("sub")
    cancel_date2 = date(2026, 7, 15)
    _add_sub_direct((sub_id_13_2_b, cid, card, stream_mid2,
                     9.99, fmt(days_before(250)), fmt(cancel_date2)))
    txn_dt = datetime(2026, 8, 15, 0, 1)
    txn_id, stmt = _plant_txn(card, cid, stream_mid2, txn_dt, 9.99, "recurring",
                               subscription_id=sub_id_13_2_b)
    filed = date(2026, 10, 1)  # within 60 days of Sep 5 stmt
    complaint = "I cancelled SoundLoop two months ago! Why did they charge me again?? This is theft."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.2", "file_chargeback", "",
              "Charge posted after cancellation date; subscription was cancelled but billing continued.")

    # -----------------------------------------------------------------------
    # 13.2 Cancelled subscription – file_chargeback #3
    # -----------------------------------------------------------------------
    cid = case_custs[11]
    card = _card(cid)
    stream_mid3 = streaming_merchants[2] if len(streaming_merchants) > 2 else streaming_merchants[0]
    sub_id_13_2_c = next_id("sub")
    cancel_date3 = date(2026, 9, 1)
    _add_sub_direct((sub_id_13_2_c, cid, card, stream_mid3,
                     12.99, fmt(days_before(200)), fmt(cancel_date3)))
    txn_dt = datetime(2026, 10, 1, 0, 3)
    txn_id, stmt = _plant_txn(card, cid, stream_mid3, txn_dt, 12.99, "recurring",
                               subscription_id=sub_id_13_2_c)
    filed = date(2026, 10, 10)
    complaint = "Cancelled my subscription last month and still got billed. Please refund."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.2", "file_chargeback", "",
              "Charge dates after cancellation; clear post-cancellation billing error.")

    # -----------------------------------------------------------------------
    # 13.2 Cancelled subscription – deny (charge BEFORE cancelled_date)
    # -----------------------------------------------------------------------
    cid = case_custs[12]
    card = _card(cid)
    stream_mid4 = streaming_merchants[0]
    sub_id_13_2_d = next_id("sub")
    cancel_date4 = date(2026, 9, 20)
    _add_sub_direct((sub_id_13_2_d, cid, card, stream_mid4,
                     11.99, fmt(days_before(280)), fmt(cancel_date4)))
    # Charge BEFORE cancel date
    txn_dt = datetime(2026, 9, 1, 0, 1)
    txn_id, stmt = _plant_txn(card, cid, stream_mid4, txn_dt, 11.99, "recurring",
                               subscription_id=sub_id_13_2_d)
    filed = date(2026, 10, 1)
    complaint = "I cancelled my subscription and I see a charge from last month. I want a refund."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.2", "deny", "",
              "Charge was posted before the cancellation date; the billing was still active.")

    # -----------------------------------------------------------------------
    # 13.3 Not as described – file_chargeback #1 (contacted merchant)
    # -----------------------------------------------------------------------
    cid = case_custs[13]
    card = _card(cid)
    mid_el2 = electronics_mids[1] if len(electronics_mids) > 1 else electronics_mids[0]
    txn_dt = datetime(2026, 8, 15, 16, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_el2, txn_dt, 179.99, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, _ = _plant_shipment(txn_id, txn_dt.date(), "delivered", 0,
                           expected_offset=6, shipped_offset=2, delivered_offset=7)
    filed = date(2026, 10, 1)  # within 60 days of Sep 5 stmt
    complaint = "The headphones I received are not the ones I ordered. I contacted the merchant but they refused to help."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.3", "file_chargeback", "",
              "Customer received wrong item and attempted to resolve with merchant first; supports chargeback.")

    # -----------------------------------------------------------------------
    # 13.3 Not as described – file_chargeback #2 (returned to merchant)
    # -----------------------------------------------------------------------
    cid = case_custs[14]
    card = _card(cid)
    mid_or5 = online_retail_mids[0]
    txn_dt = datetime(2026, 9, 1, 12, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or5, txn_dt, 95.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, _ = _plant_shipment(txn_id, txn_dt.date(), "delivered", 0,
                           expected_offset=7, shipped_offset=2, delivered_offset=8)
    filed = date(2026, 10, 1)
    complaint = "I returned the item because it was completely different from the description. No refund yet and it's been weeks."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.3", "file_chargeback", "",
              "Customer returned defective/misrepresented item; no refund received; chargeback warranted.")

    # -----------------------------------------------------------------------
    # 13.3 Not as described – request_more_info (no attempt to resolve)
    # -----------------------------------------------------------------------
    cid = case_custs[15]
    card = _card(cid)
    mid_or6 = online_retail_mids[1]
    txn_dt = datetime(2026, 9, 10, 9, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or6, txn_dt, 65.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, _ = _plant_shipment(txn_id, txn_dt.date(), "delivered", 0,
                           expected_offset=6, shipped_offset=1, delivered_offset=7)
    filed = date(2026, 10, 5)
    complaint = "The jacket I got looks nothing like the pictures on the website. Really disappointed."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.3", "request_more_info", "",
              "Item not as described but customer has not yet attempted to contact or return to merchant.")

    # -----------------------------------------------------------------------
    # 13.6 Refund never arrived – file_chargeback #1 (no refund row)
    # -----------------------------------------------------------------------
    cid = case_custs[16]
    card = _card(cid)
    mid_or7 = online_retail_mids[2]
    txn_dt = datetime(2026, 8, 20, 14, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or7, txn_dt, 120.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    # No refund row planted
    filed = date(2026, 10, 1)  # within 60 days of Sep 5 stmt
    complaint = "The merchant promised a refund three weeks ago and I still haven't seen it on my statement."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.6", "file_chargeback", "",
              "No refund record exists in the database; merchant failed to process promised credit.")

    # -----------------------------------------------------------------------
    # 13.6 Refund never arrived – file_chargeback #2 (no refund row)
    # -----------------------------------------------------------------------
    cid = case_custs[17]
    card = _card(cid)
    mid_el3 = electronics_mids[0]
    txn_dt = datetime(2026, 9, 5, 10, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_el3, txn_dt, 299.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    filed = date(2026, 10, 7)
    complaint = "Returned my device 4 weeks ago, they confirmed the return but no refund. Nothing."
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.6", "file_chargeback", "",
              "Return confirmed but no refund row found; credit was never processed.")

    # -----------------------------------------------------------------------
    # 13.6 Refund never arrived – deny (refund already posted before filing)
    # -----------------------------------------------------------------------
    cid = case_custs[18]
    card = _card(cid)
    mid_or8 = online_retail_mids[0]
    txn_dt = datetime(2026, 9, 10, 11, 0)
    txn_id, stmt = _plant_txn(card, cid, mid_or8, txn_dt, 55.00, "online",
                               device_id=_dev(cid), shipping_address_id=_addr(cid))
    # Plant a refund BEFORE the filed date
    refund_date_early = date(2026, 9, 20)
    ref_id = next_id("refund")
    _add_refund_direct((ref_id, txn_id, fmt(refund_date_early), 55.00))
    filed = date(2026, 10, 5)
    complaint = "I returned something and I'm not sure if I got my refund. Can you check?"
    did = _plant_dispute(txn_id, cid, filed, complaint)
    case_id = next_id("case")
    _add_case(case_id, did, txn_id, cid, filed, complaint, "13.6", "deny", "",
              "Refund was posted to the account before the dispute was filed; no chargeback needed.")

    # -----------------------------------------------------------------------
    # 10.4 Fraud online – file_chargeback x4
    # New device + new address + no purchase history with merchant
    # -----------------------------------------------------------------------
    fraud_cb_custs = case_custs[19:23]  # CUST-0020 to CUST-0023
    fraud_mid = online_retail_mids[0]   # Veldt Supply Co.

    for i, fcid in enumerate(fraud_cb_custs):
        fcard = _card(fcid)
        # Use a brand-new device and address not in this customer's known set
        dev_counter += 1
        new_dev = f"DEV-{dev_counter:04d}"
        addr_counter += 1
        new_addr = f"ADDR-{addr_counter:04d}"
        txn_dt = datetime(2026, 10, i + 5, 3, 22)
        amount = rand_amount(150, 400)
        txn_id, stmt = _plant_txn(fcard, fcid, fraud_mid, txn_dt, amount,
                                   "online", device_id=new_dev,
                                   shipping_address_id=new_addr)
        _, _ = _plant_shipment(txn_id, txn_dt.date(), "in_transit", 0,
                                expected_offset=7, shipped_offset=1)
        filed = date(2026, 10, 14)
        texts = [
            "I never made this online purchase. My card must have been compromised.",
            "There's a charge I don't recognize from an online store. I didn't buy anything there.",
            "Someone used my card online without my permission. Please investigate.",
            "I see a charge I definitely didn't make. I haven't even heard of this merchant.",
        ]
        complaint = texts[i]
        did = _plant_dispute(txn_id, fcid, filed, complaint)
        case_id = next_id("case")
        _add_case(case_id, did, txn_id, fcid, filed, complaint, "10.4", "file_chargeback", "",
                  "Transaction used a device and address never previously associated with this customer; no prior purchase history with this merchant.")

    # -----------------------------------------------------------------------
    # DEMO B – 10.4 escalate (friendly fraud)
    # Customer has 3+ earlier purchases from same merchant, same device+addr.
    # -----------------------------------------------------------------------
    cid_B = case_custs[23]  # CUST-0024
    card_B = _card(cid_B)
    fraud_mid_B = online_retail_mids[1]  # Thornwick Goods
    dev_B = _dev(cid_B)
    addr_B = _addr(cid_B)

    # 3 earlier undisputed purchases 120–365 days before the disputed charge
    disputed_dt_B = datetime(2026, 10, 5, 22, 15)
    prior_offsets = [150, 220, 310]
    for off in prior_offsets:
        prior_dt = disputed_dt_B - timedelta(days=off)
        _plant_txn(card_B, cid_B, fraud_mid_B, prior_dt,
                   rand_amount(80, 200), "online",
                   device_id=dev_B, shipping_address_id=addr_B)

    # Two past resolved_merchant disputes for this customer (friendly-fraud signal)
    bg_txn_for_B = all_txn_rows[:2]
    for i, brow in enumerate(bg_txn_for_B[:2]):
        d_id2 = next_id("dispute")
        bdt = datetime.strptime(brow[4], "%Y-%m-%dT%H:%M:%S").date()
        _add_dispute_direct((d_id2, brow[0], cid_B,
                              fmt(bdt + timedelta(days=10)),
                              "I don't recognize this charge.",
                              "resolved_merchant"))

    txn_id_B, stmt_B = _plant_txn(card_B, cid_B, fraud_mid_B, disputed_dt_B,
                                   340.00, "online",
                                   device_id=dev_B, shipping_address_id=addr_B)
    _, _ = _plant_shipment(txn_id_B, disputed_dt_B.date(), "delivered", 1,
                           expected_offset=6, shipped_offset=2, delivered_offset=7)
    filed_B = date(2026, 10, 12)
    complaint_B = "I never made this $340 online order. I don't know where this came from."
    did_B = _plant_dispute(txn_id_B, cid_B, filed_B, complaint_B)
    case_B = next_id("case")
    _add_case(case_B, did_B, txn_id_B, cid_B, filed_B, complaint_B, "10.4", "escalate", "B",
              "Customer has 3 earlier undisputed purchases at same merchant with same device and address; likely friendly fraud.")

    # -----------------------------------------------------------------------
    # 10.4 escalate #2 (friendly fraud)
    # -----------------------------------------------------------------------
    cid = case_custs[24]
    card = _card(cid)
    fraud_mid_esc2 = "MERCH-023"  # Ridgeline Outfitters – reserved for escalate cases
    dev_esc2 = _dev(cid)
    addr_esc2 = _addr(cid)
    disputed_dt2 = datetime(2026, 10, 6, 21, 0)
    for off in [130, 200, 290]:
        prior_dt = disputed_dt2 - timedelta(days=off)
        _plant_txn(card, cid, fraud_mid_esc2, prior_dt,
                   rand_amount(100, 300), "online",
                   device_id=dev_esc2, shipping_address_id=addr_esc2)
    txn_id2, _ = _plant_txn(card, cid, fraud_mid_esc2, disputed_dt2,
                              275.00, "online",
                              device_id=dev_esc2, shipping_address_id=addr_esc2)
    filed2 = date(2026, 10, 13)
    complaint2 = "This charge is not mine. I never ordered anything from this electronics site."
    did2 = _plant_dispute(txn_id2, cid, filed2, complaint2)
    case_id = next_id("case")
    _add_case(case_id, did2, txn_id2, cid, filed2, complaint2, "10.4", "escalate", "",
              "Multiple prior purchases at same merchant with same device and address; friendly-fraud indicators present.")

    # -----------------------------------------------------------------------
    # 10.4 escalate #3 (friendly fraud)
    # -----------------------------------------------------------------------
    cid = case_custs[25]
    card = _card(cid)
    fraud_mid_esc3 = "MERCH-025"  # Northwall Supply – reserved for escalate cases
    dev_esc3 = _dev(cid)
    addr_esc3 = _addr(cid)
    disputed_dt3 = datetime(2026, 10, 7, 20, 30)
    for off in [160, 240, 340]:
        prior_dt = disputed_dt3 - timedelta(days=off)
        _plant_txn(card, cid, fraud_mid_esc3, prior_dt,
                   rand_amount(50, 180), "online",
                   device_id=dev_esc3, shipping_address_id=addr_esc3)
    txn_id3, _ = _plant_txn(card, cid, fraud_mid_esc3, disputed_dt3,
                              198.00, "online",
                              device_id=dev_esc3, shipping_address_id=addr_esc3)
    filed3 = date(2026, 10, 14)
    complaint3 = "There's a large charge I don't recognize. Someone must have stolen my card details."
    did3 = _plant_dispute(txn_id3, cid, filed3, complaint3)
    case_id = next_id("case")
    _add_case(case_id, did3, txn_id3, cid, filed3, complaint3, "10.4", "escalate", "",
              "Customer has purchase history with merchant using same device and address; escalate for review.")

    # -----------------------------------------------------------------------
    # DEMO C – Filed too late 13.1 (deny, ~150 days, spring 2026)
    # Transaction in spring 2026 (~150 days before Oct-15 = ~May 18, 2026)
    # -----------------------------------------------------------------------
    cid_C = case_custs[26]
    card_C = _card(cid_C)
    mid_C = online_retail_mids[0]
    # ~150 days before filed_date; filed around Oct 12 so txn ≈ May 15
    txn_dt_C = datetime(2026, 5, 15, 14, 0)
    txn_id_C, stmt_C = _plant_txn(card_C, cid_C, mid_C, txn_dt_C, 110.00, "online",
                                   device_id=_dev(cid_C), shipping_address_id=_addr(cid_C))
    _, _ = _plant_shipment(txn_id_C, txn_dt_C.date(), "lost", 0,
                           expected_offset=10, shipped_offset=2, delivered_offset=None)
    filed_C = date(2026, 10, 12)   # 150 days after May 15
    complaint_C = "I want to dispute this charge from last spring. The item never arrived and I forgot to call sooner."
    did_C = _plant_dispute(txn_id_C, cid_C, filed_C, complaint_C)
    case_C = next_id("case")
    _add_case(case_C, did_C, txn_id_C, cid_C, filed_C, complaint_C, "13.1", "deny", "C",
              "Filed approximately 150 days after the transaction; exceeds the 120-day network limit and 60-day Reg Z/E window.")

    # -----------------------------------------------------------------------
    # Filed too late #2 – 13.3
    # -----------------------------------------------------------------------
    cid = case_custs[27]
    card = _card(cid)
    mid_late2 = electronics_mids[0]
    txn_dt_l2 = datetime(2026, 5, 20, 11, 0)
    txn_id_l2, stmt_l2 = _plant_txn(card, cid, mid_late2, txn_dt_l2, 250.00, "online",
                                     device_id=_dev(cid), shipping_address_id=_addr(cid))
    _, _ = _plant_shipment(txn_id_l2, txn_dt_l2.date(), "delivered", 0,
                           expected_offset=7, shipped_offset=2, delivered_offset=8)
    filed_l2 = date(2026, 10, 12)  # ~145 days after May 20
    complaint_l2 = "This item was defective but I've been dealing with the merchant for months. Now I want a dispute."
    did_l2 = _plant_dispute(txn_id_l2, cid, filed_l2, complaint_l2)
    case_id = next_id("case")
    _add_case(case_id, did_l2, txn_id_l2, cid, filed_l2, complaint_l2, "13.3", "deny", "",
              "Filed more than 120 days after the transaction; outside the allowable dispute window.")

    # -----------------------------------------------------------------------
    # Filed too late #3 – 13.6
    # -----------------------------------------------------------------------
    cid = case_custs[28]
    card = _card(cid)
    mid_late3 = online_retail_mids[1]
    txn_dt_l3 = datetime(2026, 5, 25, 10, 0)
    txn_id_l3, stmt_l3 = _plant_txn(card, cid, mid_late3, txn_dt_l3, 85.00, "online",
                                     device_id=_dev(cid), shipping_address_id=_addr(cid))
    filed_l3 = date(2026, 10, 13)  # ~141 days after May 25
    complaint_l3 = "I was promised a refund back in June and never got it. Only now finding the time to dispute."
    did_l3 = _plant_dispute(txn_id_l3, cid, filed_l3, complaint_l3)
    case_id = next_id("case")
    _add_case(case_id, did_l3, txn_id_l3, cid, filed_l3, complaint_l3, "13.6", "deny", "",
              "Filed more than 120 days after the transaction; time limit for refund dispute has expired.")

    # -----------------------------------------------------------------------
    # Unclear complaint – request_more_info
    # Charge from a subscription the customer may have forgotten
    # -----------------------------------------------------------------------
    cid = case_custs[29]
    card = _card(cid)
    stream_mid_unc = streaming_merchants[0]
    # Create a subscription for this customer
    sub_id_unc = next_id("sub")
    _add_sub_direct((sub_id_unc, cid, card, stream_mid_unc,
                     13.99, fmt(days_before(180)), None))
    txn_dt_unc = datetime(2026, 10, 1, 0, 2)
    txn_id_unc, _ = _plant_txn(card, cid, stream_mid_unc, txn_dt_unc,
                                13.99, "recurring", subscription_id=sub_id_unc)
    filed_unc = date(2026, 10, 10)
    complaint_unc = "I see a charge on my card from some company and I have no idea what it's for. Please help."
    did_unc = _plant_dispute(txn_id_unc, cid, filed_unc, complaint_unc)
    case_id = next_id("case")
    _add_case(case_id, did_unc, txn_id_unc, cid, filed_unc, complaint_unc,
              "N/A", "request_more_info", "",
              "Charge is a recurring subscription the customer may have forgotten; more information needed.")

    # -----------------------------------------------------------------------
    # Write cases.csv
    # -----------------------------------------------------------------------
    CSV_FIELDS = [
        "case_id", "dispute_id", "transaction_id", "customer_id",
        "filed_date", "complaint_text", "expected_reason_code",
        "expected_outcome", "demo_case", "notes",
    ]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(cases_csv)

    conn.commit()
    conn.close()

    print(f"✓ Database written to {DB_PATH}")
    print(f"✓ {len(cases_csv)} cases written to {CSV_PATH}")
    total_txns = _counters["txn"]
    print(f"  transactions: {total_txns}")
    print(f"  disputes:     {_counters['dispute']}")


if __name__ == "__main__":
    build_database()
