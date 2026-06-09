"""Deterministic synthetic data generator for personal-finance-analytics.

Populates source-db (schema `core`) with ~100 users and ~2 years of activity:
accounts, transactions, monthly budgets, month-end balances, and investment
holdings. Categories/merchants are read from the DB (seeded by 02-seed-static).

Deterministic by design: a fixed RNG seed + a fixed 24-month window means every
`docker compose run --rm mock-data` produces byte-identical data. Re-running
TRUNCATEs the generated tables first, so the script is safe to repeat.
"""

from __future__ import annotations

import calendar
import os
import random
from datetime import date, datetime, timedelta

import psycopg
from faker import Faker

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
SEED = 42
NUM_USERS = 100
WINDOW_END = date(2026, 5, 1)   # last month generated (inclusive)
NUM_MONTHS = 24                 # 2 years
DEFAULT_CURRENCY = "USD"

rng = random.Random(SEED)
fake = Faker()
Faker.seed(SEED)

COUNTRIES = ["United States", "United Kingdom", "Germany", "Canada", "Netherlands"]
AGE_BANDS = ["18-25", "26-35", "36-45", "46-55", "56+"]
EMPLOYMENT = ["employed", "self_employed", "student", "retired"]

# Monthly net income range (USD) by income band.
INCOME_RANGES = {"low": (2500, 4000), "mid": (4500, 8000), "high": (9000, 18000)}

# Group-level monthly budget as a fraction of monthly income.
BUDGET_GROUPS = {"Food": (2, 0.14), "Transport": (3, 0.06),
                 "Shopping": (4, 0.08), "Entertainment": (5, 0.04)}

# Investable universe for holdings: (symbol, asset_class, ~starting price).
ASSET_UNIVERSE = [
    ("VOO", "etf", 400), ("VTI", "etf", 230), ("QQQ", "etf", 380),
    ("AAPL", "equity", 190), ("MSFT", "equity", 410), ("GOOGL", "equity", 150),
    ("AMZN", "equity", 175), ("TSLA", "equity", 250), ("NVDA", "equity", 120),
    ("BTC", "crypto", 60000), ("ETH", "crypto", 3000), ("BND", "bond", 72),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("SOURCE_DB_HOST", "localhost"),
        port=os.environ.get("SOURCE_DB_PORT", "5432"),
        dbname=os.environ.get("SOURCE_DB_NAME", "source"),
        user=os.environ.get("SOURCE_DB_USER", "finance"),
        password=os.environ.get("SOURCE_DB_PASSWORD", "changeme"),
    )


def month_starts() -> list[date]:
    """First day of each month in the window, oldest first."""
    months: list[date] = []
    y, m = WINDOW_END.year, WINDOW_END.month
    for _ in range(NUM_MONTHS):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(months))


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def random_ts_in_month(d: date) -> datetime:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return datetime(d.year, d.month, rng.randint(1, last_day),
                    rng.randint(7, 22), rng.randint(0, 59))


def money(value: float) -> float:
    return round(max(value, 0.01), 2)


class Counter:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


# --------------------------------------------------------------------------- #
# Reference data (seeded by 02-seed-static.sql)
# --------------------------------------------------------------------------- #
def load_reference(conn: psycopg.Connection):
    """Return (leaf_by_name, merchants_by_category) — deterministically ordered."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT category_id, name, parent_category_id "
            "FROM core.categories ORDER BY category_id"
        )
        leaf_by_name = {name: cid for cid, name, parent in cur.fetchall()
                        if parent is not None}
        cur.execute(
            "SELECT merchant_id, default_category_id "
            "FROM core.merchants ORDER BY merchant_id"
        )
        merchants_by_category: dict[int, list[int]] = {}
        for mid, cat in cur.fetchall():
            merchants_by_category.setdefault(cat, []).append(mid)
    return leaf_by_name, merchants_by_category


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def gen_users() -> list[tuple]:
    window_start = month_starts()[0]
    rows = []
    for uid in range(1, NUM_USERS + 1):
        income_band = rng.choices(["low", "mid", "high"], weights=[3, 5, 2])[0]
        signup = window_start - timedelta(days=rng.randint(30, 900))
        rows.append((uid, fake.name(), f"user{uid}@example.com",
                     rng.choice(COUNTRIES), rng.choice(AGE_BANDS), income_band,
                     rng.choice(EMPLOYMENT), signup))
    return rows


def gen_accounts(users: list[tuple]):
    """Return (account_rows, accounts_by_user{uid: {type: account_id}})."""
    account_rows, accounts_by_user = [], {}
    window_start = month_starts()[0]
    institutions = ["Chase", "Bank of America", "Wells Fargo", "Citi", "Ally", "Fidelity"]
    aid = Counter()

    for u in users:
        uid = u[0]
        user_accounts: dict[str, int] = {}

        def add(acc_type: str):
            opened = window_start - timedelta(days=rng.randint(60, 1200))
            account_id = aid.next()
            account_rows.append((account_id, uid, acc_type, rng.choice(institutions),
                                 DEFAULT_CURRENCY, opened, True))
            user_accounts[acc_type] = account_id

        add("checking")
        if rng.random() < 0.80:
            add("savings")
        if rng.random() < 0.60:
            add("credit_card")
        if rng.random() < 0.40:
            add("investment")
        accounts_by_user[uid] = user_accounts
    return account_rows, accounts_by_user


def gen_activity(users, accounts_by_user, leaf, merchants_by_cat):
    """Generate transactions, budgets, balances, holdings. Returns dict of rows."""
    txn_id, budget_id, holding_id = Counter(), Counter(), Counter()
    transactions, budgets, balances, holdings = [], [], [], []
    months = month_starts()

    def emit(account_id, when, amount, direction, category_id, description):
        merchant_id = None
        if direction == "debit":
            candidates = merchants_by_cat.get(category_id)
            if candidates:
                merchant_id = rng.choice(candidates)
        transactions.append((txn_id.next(), account_id, when, money(amount),
                             direction, category_id, merchant_id, description,
                             DEFAULT_CURRENCY))

    for u in users:
        uid, income_band, employment = u[0], u[5], u[6]
        accs = accounts_by_user[uid]
        checking = accs["checking"]
        credit = accs.get("credit_card")
        spend_acc = credit or checking          # discretionary spend routing

        lo, hi = INCOME_RANGES[income_band]
        base_income = rng.uniform(lo, hi)
        rent = money(base_income * rng.uniform(0.28, 0.38))
        has_car = rng.random() < 0.6
        num_subs = rng.randint(1, 3)
        has_gym = rng.random() < 0.4

        checking_balance = base_income * rng.uniform(1.0, 3.0)
        savings_balance = base_income * rng.uniform(2.0, 8.0) if "savings" in accs else 0.0

        for m in months:
            txn_start = len(transactions)

            # ---- income ----
            emit(checking, random_ts_in_month(m), base_income * rng.uniform(0.97, 1.03),
                 "credit", leaf["Salary"], "Monthly salary")
            if employment == "self_employed" and rng.random() < 0.7:
                emit(checking, random_ts_in_month(m), base_income * rng.uniform(0.2, 0.8),
                     "credit", leaf["Freelance"], "Freelance payment")

            # ---- recurring essentials (checking) ----
            for cat, amt, desc in [
                (leaf["Rent"], rent, "Rent"),
                (leaf["Electricity"], rng.uniform(60, 160), "Electricity bill"),
                (leaf["Water"], rng.uniform(20, 60), "Water bill"),
                (leaf["Internet"], rng.uniform(40, 80), "Internet"),
                (leaf["Mobile"], rng.uniform(30, 90), "Mobile plan"),
                (leaf["Insurance"], rng.uniform(80, 250), "Insurance"),
            ]:
                emit(checking, random_ts_in_month(m), amt, "debit", cat, desc)

            # ---- subscriptions / gym (discretionary) ----
            for _ in range(num_subs):
                emit(spend_acc, random_ts_in_month(m), rng.uniform(8, 20),
                     "debit", leaf["Streaming"], "Subscription")
            if has_gym:
                emit(spend_acc, random_ts_in_month(m), rng.uniform(30, 60),
                     "debit", leaf["Fitness"], "Gym membership")

            # ---- variable spend ----
            plan = [
                (leaf["Groceries"], rng.randint(4, 8), (25, 120), checking),
                (leaf["Dining Out"], rng.randint(2, 7), (12, 70), spend_acc),
                (leaf["Coffee"], rng.randint(0, 12), (3, 8), spend_acc),
                (leaf["Clothing"], rng.randint(0, 3), (25, 180), spend_acc),
                (leaf["General Merchandise"], rng.randint(0, 4), (10, 150), spend_acc),
                (leaf["Pharmacy"], rng.randint(0, 2), (8, 40), spend_acc),
                (leaf["Cash Withdrawal"], rng.randint(0, 2), (40, 200), checking),
            ]
            if has_car:
                plan.append((leaf["Fuel"], rng.randint(2, 4), (35, 80), checking))
            else:
                plan.append((leaf["Ride Share"], rng.randint(2, 8), (8, 30), spend_acc))
                plan.append((leaf["Public Transport"], rng.randint(0, 2), (20, 90), spend_acc))

            for cat, count, (amin, amax), acc in plan:
                for _ in range(count):
                    emit(acc, random_ts_in_month(m), rng.uniform(amin, amax),
                         "debit", cat, None)

            # ---- occasional one-offs ----
            if rng.random() < 0.10:
                emit(spend_acc, random_ts_in_month(m), rng.uniform(300, 1500),
                     "debit", leaf["Electronics"], "Electronics purchase")
            if rng.random() < 0.08:   # travel month
                emit(spend_acc, random_ts_in_month(m), rng.uniform(200, 900),
                     "debit", leaf["Flights"], "Flight")
                emit(spend_acc, random_ts_in_month(m), rng.uniform(150, 700),
                     "debit", leaf["Hotels"], "Hotel")

            # ---- budgets (group-level monthly limits) ----
            for _, (gid, frac) in BUDGET_GROUPS.items():
                limit = base_income * frac * rng.uniform(0.85, 1.15)
                budgets.append((budget_id.next(), uid, gid, m, money(limit),
                               DEFAULT_CURRENCY))

            # ---- month-end balances ----
            # checking flow is reconciled directly from this month's transactions
            flow = sum((row[3] if row[4] == "credit" else -row[3])
                       for row in transactions[txn_start:] if row[1] == checking)
            checking_balance = max(checking_balance + flow, 50.0)
            balances.append((checking, month_end(m), money(checking_balance)))

            if "savings" in accs:
                savings_balance += base_income * rng.uniform(0.02, 0.12)
                balances.append((accs["savings"], month_end(m), money(savings_balance)))
            if credit:
                balances.append((credit, month_end(m),
                                -money(base_income * rng.uniform(0.05, 0.30))))

        # ---- investment holdings (month-end snapshots) ----
        if "investment" in accs:
            inv = accs["investment"]
            # positions: [symbol, asset_class, quantity, cost_basis, price]
            positions = []
            for symbol, asset_class, price0 in rng.sample(ASSET_UNIVERSE, k=rng.randint(3, 6)):
                qty = round(rng.uniform(0.5, 20) * (1 if price0 < 1000 else 0.05), 6)
                positions.append([symbol, asset_class, qty, money(qty * price0), float(price0)])
            for m in months:
                total = 0.0
                for pos in positions:
                    pos[4] *= rng.uniform(0.97, 1.04)        # monthly price drift
                    mv = money(pos[2] * pos[4])
                    total += mv
                    holdings.append((holding_id.next(), inv, pos[0], pos[1],
                                    pos[2], pos[3], mv, month_end(m)))
                balances.append((inv, month_end(m), money(total)))

    return {"transactions": transactions, "budgets": budgets,
            "account_balances": balances, "holdings": holdings}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def truncate(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE core.transactions, core.budgets, core.account_balances,
                     core.holdings, core.accounts, core.users RESTART IDENTITY CASCADE
        """)


def copy_rows(conn: psycopg.Connection, table: str, columns: list[str], rows) -> None:
    cols = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(f"COPY core.{table} ({cols}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def main() -> None:
    with connect() as conn:
        truncate(conn)
        leaf, merchants_by_cat = load_reference(conn)

        users = gen_users()
        accounts, accounts_by_user = gen_accounts(users)
        activity = gen_activity(users, accounts_by_user, leaf, merchants_by_cat)

        copy_rows(conn, "users",
                  ["user_id", "full_name", "email", "country", "age_band",
                   "income_band", "employment_status", "signup_date"], users)
        copy_rows(conn, "accounts",
                  ["account_id", "user_id", "account_type", "institution",
                   "currency", "opened_at", "is_active"], accounts)
        copy_rows(conn, "transactions",
                  ["transaction_id", "account_id", "txn_ts", "amount", "direction",
                   "category_id", "merchant_id", "description", "currency"],
                  activity["transactions"])
        copy_rows(conn, "budgets",
                  ["budget_id", "user_id", "category_id", "period_month",
                   "limit_amount", "currency"], activity["budgets"])
        copy_rows(conn, "account_balances",
                  ["account_id", "as_of_date", "balance"], activity["account_balances"])
        copy_rows(conn, "holdings",
                  ["holding_id", "account_id", "symbol", "asset_class", "quantity",
                   "cost_basis", "market_value", "as_of_date"], activity["holdings"])
        conn.commit()

    print(f"Generated: {len(users)} users, {len(accounts)} accounts, "
          f"{len(activity['transactions'])} transactions, "
          f"{len(activity['budgets'])} budgets, "
          f"{len(activity['account_balances'])} balances, "
          f"{len(activity['holdings'])} holdings.")


if __name__ == "__main__":
    main()
