import json
import random
import time

import aiosqlite

from .config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance REAL NOT NULL DEFAULT 0,
    total_spent REAL NOT NULL DEFAULT 0,
    lang TEXT NOT NULL DEFAULT 'tj',
    currency TEXT NOT NULL DEFAULT 'TJS',
    theme TEXT NOT NULL DEFAULT 'dark',
    pin_hash TEXT,
    ref_by INTEGER,
    ref_earned REAL NOT NULL DEFAULT 0,
    banned INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    items TEXT NOT NULL,
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    game_uid TEXT NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL,           -- unpaid | processing | done | cancelled
    supplier_ref TEXT,
    note TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS topups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL,           -- waiting | review | approved | rejected | cancelled
    order_id INTEGER,
    receipt_file_id TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    kind TEXT NOT NULL,             -- topup | purchase | refund | referral | admin
    ref TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_overrides (
    product_id TEXT PRIMARY KEY,
    price REAL,
    active INTEGER NOT NULL DEFAULT 1
);
"""


def now() -> int:
    return int(time.time())


def order_code(order_id: int) -> str:
    return f"ORD-{order_id + 1000}"


def topup_code(topup_id: int) -> str:
    return f"TOP-{topup_id + 2600}"


class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()
        config.overrides.update({r["key"]: r["value"] for r in await self.fetchall("SELECT * FROM settings")})
        if config.overrides.get("supplier_api_key"):  # key changed in /panel wins over .env
            from .supplier import supplier
            supplier.configure(config.overrides["supplier_api_key"])
        for admin_id in config.overrides.get("admin_ids", "").split(","):  # admins added with the owner link
            if admin_id.strip().isdigit() and int(admin_id) not in config.admin_ids:
                config.admin_ids.append(int(admin_id))
        removed = {int(x) for x in config.overrides.get("removed_admins", "").split(",") if x.isdigit()}
        owner = config.overrides.get("owner_claimed", "")
        for admin_id in [a for a in config.admin_ids if a in removed and str(a) != owner]:
            config.admin_ids.remove(admin_id)  # removed in the panel, even if still listed in .env

    async def _migrate(self):
        """Add columns introduced after the first release to existing databases."""
        new_columns = {
            "topups": {"reject_reason": "TEXT", "receipt_unique_id": "TEXT", "reminded": "INTEGER NOT NULL DEFAULT 0",
                       "handled_by": "INTEGER"},
            "orders": {"handled_by": "INTEGER", "fields": "TEXT"},
        }
        for table, cols in new_columns.items():
            existing = {r["name"] for r in await self.fetchall(f"PRAGMA table_info({table})")}
            for name, decl in cols.items():
                if name not in existing:
                    await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    # ---------- settings ----------
    async def add_admin(self, user_id: int):
        if user_id not in config.admin_ids:
            config.admin_ids.append(user_id)  # routers' admin filters read this same list
        saved = [x for x in config.overrides.get("admin_ids", "").split(",") if x]
        if str(user_id) not in saved:
            await self.set_setting("admin_ids", ",".join(saved + [str(user_id)]))
        removed = [x for x in config.overrides.get("removed_admins", "").split(",") if x]
        if str(user_id) in removed:
            await self.set_setting("removed_admins", ",".join(x for x in removed if x != str(user_id)))

    async def set_setting(self, key: str, value: str):
        await self.execute("INSERT INTO settings (key, value) VALUES (?, ?)"
                           " ON CONFLICT(key) DO UPDATE SET value=excluded.value", key, value)
        config.overrides[key] = value

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def fetchone(self, sql: str, *args) -> dict | None:
        async with self.conn.execute(sql, args) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, *args) -> list[dict]:
        async with self.conn.execute(sql, args) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def execute(self, sql: str, *args) -> int:
        cur = await self.conn.execute(sql, args)
        await self.conn.commit()
        return cur.lastrowid

    # ---------- users ----------
    async def get_user(self, user_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM users WHERE id=?", user_id)

    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None,
                          ref_by: int | None = None) -> tuple[dict, bool]:
        user = await self.get_user(user_id)
        if user:
            await self.execute("UPDATE users SET username=?, first_name=? WHERE id=?",
                               username, first_name, user_id)
            return await self.get_user(user_id), False
        if ref_by == user_id or (ref_by and not await self.get_user(ref_by)):
            ref_by = None
        await self.execute(
            "INSERT INTO users (id, username, first_name, ref_by, created_at) VALUES (?,?,?,?,?)",
            user_id, username, first_name, ref_by, now())
        return await self.get_user(user_id), True

    async def set_user_field(self, user_id: int, field: str, value):
        assert field in {"lang", "currency", "theme", "pin_hash", "banned"}
        await self.execute(f"UPDATE users SET {field}=? WHERE id=?", value, user_id)

    async def change_balance(self, user_id: int, delta: float, kind: str, ref: str = "") -> bool:
        """Atomically change balance; refuses to go below zero."""
        cur = await self.conn.execute(
            "UPDATE users SET balance = ROUND(balance + ?, 2) WHERE id=? AND balance + ? >= -0.001",
            (delta, user_id, delta))
        if cur.rowcount == 0:
            await self.conn.commit()
            return False
        await self.conn.execute(
            "INSERT INTO transactions (user_id, amount, kind, ref, created_at) VALUES (?,?,?,?,?)",
            (user_id, round(delta, 2), kind, ref, now()))
        await self.conn.commit()
        return True

    async def count_users(self) -> int:
        row = await self.fetchone("SELECT COUNT(*) c FROM users")
        return row["c"]

    async def all_user_ids(self) -> list[int]:
        return [r["id"] for r in await self.fetchall("SELECT id FROM users WHERE banned=0")]

    async def referrals_count(self, user_id: int) -> int:
        row = await self.fetchone("SELECT COUNT(*) c FROM users WHERE ref_by=?", user_id)
        return row["c"]

    # ---------- orders ----------
    async def create_order(self, user_id: int, items: list[dict], title: str, amount: float,
                           game_uid: str, method: str, status: str, fields: dict | None = None) -> int:
        t = now()
        return await self.execute(
            "INSERT INTO orders (user_id, items, title, amount, game_uid, method, status, fields, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            user_id, json.dumps(items, ensure_ascii=False), title, round(amount, 2), game_uid, method, status,
            json.dumps(fields or {}, ensure_ascii=False), t, t)

    async def update_order_items(self, order_id: int, items: list[dict]):
        await self.execute("UPDATE orders SET items=?, updated_at=? WHERE id=?",
                           json.dumps(items, ensure_ascii=False), now(), order_id)

    async def get_order(self, order_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM orders WHERE id=?", order_id)

    async def set_order_status(self, order_id: int, status: str, supplier_ref: str | None = None,
                               note: str | None = None, only_from: str | None = None,
                               handled_by: int | None = None) -> bool:
        sql = ("UPDATE orders SET status=?, supplier_ref=COALESCE(?, supplier_ref), note=COALESCE(?, note),"
               " handled_by=COALESCE(?, handled_by), updated_at=? WHERE id=?")
        args = [status, supplier_ref, note, handled_by, now(), order_id]
        if only_from:
            sql += " AND status=?"
            args.append(only_from)
        cur = await self.conn.execute(sql, args)
        await self.conn.commit()
        return cur.rowcount > 0

    async def user_orders(self, user_id: int, limit: int = 100) -> list[dict]:
        return await self.fetchall("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", user_id, limit)

    async def orders_by_status(self, status: str, limit: int = 20) -> list[dict]:
        return await self.fetchall("SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?", status, limit)

    # ---------- topups ----------
    async def create_topup(self, user_id: int, amount: float, method: str, order_id: int | None = None) -> int:
        t = now()
        return await self.execute(
            "INSERT INTO topups (user_id, amount, method, status, order_id, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?)", user_id, round(amount, 2), method, "waiting", order_id, t, t)

    async def get_topup(self, topup_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM topups WHERE id=?", topup_id)

    async def waiting_topup(self, user_id: int) -> dict | None:
        return await self.fetchone(
            "SELECT * FROM topups WHERE user_id=? AND status='waiting' ORDER BY id DESC LIMIT 1", user_id)

    async def set_topup_status(self, topup_id: int, status: str, only_from: tuple[str, ...],
                               receipt_file_id: str | None = None, receipt_unique_id: str | None = None,
                               reject_reason: str | None = None, handled_by: int | None = None,
                               amount: float | None = None) -> bool:
        marks = ",".join("?" * len(only_from))
        cur = await self.conn.execute(
            f"UPDATE topups SET status=?, receipt_file_id=COALESCE(?, receipt_file_id),"
            f" receipt_unique_id=COALESCE(?, receipt_unique_id), reject_reason=COALESCE(?, reject_reason),"
            f" handled_by=COALESCE(?, handled_by), amount=COALESCE(?, amount), updated_at=?"
            f" WHERE id=? AND status IN ({marks})",
            (status, receipt_file_id, receipt_unique_id, reject_reason, handled_by, amount, now(), topup_id,
             *only_from))
        await self.conn.commit()
        return cur.rowcount > 0

    async def unique_amount(self, base: float) -> float:
        """Add random cents so the admin can match a transfer to a request."""
        for _ in range(50):
            amount = round(base + random.randint(1, 99) / 100, 2)
            busy = await self.fetchone(
                "SELECT id FROM topups WHERE amount=? AND status IN ('waiting','review')", amount)
            if not busy:
                return amount
        return round(base + random.randint(1, 99) / 100, 2)

    async def topups_by_status(self, status: str, limit: int = 20) -> list[dict]:
        return await self.fetchall("SELECT * FROM topups WHERE status=? ORDER BY id LIMIT ?", status, limit)

    async def receipt_duplicates(self, unique_id: str, exclude_id: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM topups WHERE receipt_unique_id=? AND id<>? ORDER BY id",
                                   unique_id, exclude_id)

    async def topups_to_remind(self, older_than: int, reminded_below: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM topups WHERE status='review' AND updated_at<=? AND reminded<?",
                                   now() - older_than, reminded_below)

    async def mark_reminded(self, topup_id: int, level: int):
        await self.execute("UPDATE topups SET reminded=? WHERE id=?", level, topup_id)

    async def user_topups(self, user_id: int, limit: int = 100) -> list[dict]:
        return await self.fetchall("SELECT * FROM topups WHERE user_id=? ORDER BY id DESC LIMIT ?", user_id, limit)

    async def orders_by_game_uid(self, game_uid: str, limit: int = 10) -> list[dict]:
        return await self.fetchall("SELECT * FROM orders WHERE game_uid=? ORDER BY id DESC LIMIT ?", game_uid, limit)

    async def receipts_since(self, since: int, status: str | None = None) -> list[dict]:
        """Requests with a receipt photo updated since `since`, newest first (optionally one status only)."""
        sql = "SELECT * FROM topups WHERE receipt_file_id IS NOT NULL AND updated_at>=?"
        args: list = [since]
        if status:
            sql += " AND status=?"
            args.append(status)
        return await self.fetchall(sql + " ORDER BY id DESC", *args)

    async def find_user(self, query: str) -> dict | None:
        q = query.strip().lstrip("@")
        if q.isdigit():
            return await self.get_user(int(q))
        return await self.fetchone("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", q)

    # ---------- transactions ----------
    async def user_transactions(self, user_id: int, limit: int = 100) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT ?", user_id, limit)

    async def add_spent(self, user_id: int, amount: float):
        await self.execute("UPDATE users SET total_spent = ROUND(total_spent + ?, 2) WHERE id=?", amount, user_id)

    async def add_ref_earned(self, user_id: int, amount: float):
        await self.execute("UPDATE users SET ref_earned = ROUND(ref_earned + ?, 2) WHERE id=?", amount, user_id)

    # ---------- notifications ----------
    async def notify(self, user_id: int, text: str):
        await self.execute("INSERT INTO notifications (user_id, text, created_at) VALUES (?,?,?)",
                           user_id, text, now())

    async def notifications(self, user_id: int, limit: int = 50) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?", user_id, limit)

    async def unread_count(self, user_id: int) -> int:
        row = await self.fetchone("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", user_id)
        return row["c"]

    async def mark_read(self, user_id: int):
        await self.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", user_id)

    # ---------- prices ----------
    async def price_overrides(self) -> dict[str, dict]:
        rows = await self.fetchall("SELECT * FROM price_overrides")
        return {r["product_id"]: r for r in rows}

    async def set_price(self, product_id: str, price: float | None = None, active: int | None = None):
        await self.execute("INSERT OR IGNORE INTO price_overrides (product_id) VALUES (?)", product_id)
        if price is not None:
            await self.execute("UPDATE price_overrides SET price=? WHERE product_id=?", price, product_id)
        if active is not None:
            await self.execute("UPDATE price_overrides SET active=? WHERE product_id=?", active, product_id)

    async def clear_price(self, product_id: str):
        await self.execute("UPDATE price_overrides SET price=NULL WHERE product_id=?", product_id)

    async def remove_admin(self, user_id: int):
        if user_id in config.admin_ids:
            config.admin_ids.remove(user_id)
        saved = [x for x in config.overrides.get("admin_ids", "").split(",") if x and x != str(user_id)]
        await self.set_setting("admin_ids", ",".join(saved))
        removed = [x for x in config.overrides.get("removed_admins", "").split(",") if x]
        if str(user_id) not in removed:
            await self.set_setting("removed_admins", ",".join(removed + [str(user_id)]))

    async def report(self, since: int, until: int) -> dict:
        """Sales between two unix times (orders by completion time, top-ups by approval time)."""
        done = await self.fetchall("SELECT * FROM orders WHERE status='done' AND updated_at>=? AND updated_at<?",
                                   since, until)
        cost_usd, unknown_cost, products = 0.0, 0, {}
        for o in done:
            for it in json.loads(o["items"]):
                if it.get("cost_usd") is not None:
                    cost_usd += float(it["cost_usd"]) * it["qty"]
                else:
                    unknown_cost += 1
                products[it["title"]] = products.get(it["title"], 0) + it["qty"]
        q = self.fetchone
        return {
            "orders": len(done), "revenue": round(sum(o["amount"] for o in done), 2),
            "cost_usd": round(cost_usd, 4), "unknown_cost": unknown_cost,
            "cancelled": (await q("SELECT COUNT(*) c FROM orders WHERE status='cancelled' AND updated_at>=? AND updated_at<?",
                                  since, until))["c"],
            "topups": await q("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM topups WHERE status='approved'"
                              " AND updated_at>=? AND updated_at<?", since, until),
            "rejected": (await q("SELECT COUNT(*) c FROM topups WHERE status='rejected' AND updated_at>=? AND updated_at<?",
                                 since, until))["c"],
            "new_users": (await q("SELECT COUNT(*) c FROM users WHERE created_at>=? AND created_at<?", since, until))["c"],
            "buyers": (await q("SELECT COUNT(DISTINCT user_id) c FROM orders WHERE status='done' AND updated_at>=?"
                               " AND updated_at<?", since, until))["c"],
            "top": sorted(products.items(), key=lambda kv: -kv[1])[:5],
        }

    async def users_page(self, offset: int, limit: int = 10) -> list[dict]:
        return await self.fetchall(
            "SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id AND o.status='done') AS done_orders"
            " FROM users u ORDER BY u.created_at DESC LIMIT ? OFFSET ?", limit, offset)

    async def user_history(self, user_id: int, offset: int, limit: int = 15) -> list[dict]:
        """Orders, top-ups and balance changes of a customer in one list, newest first."""
        rows = await self.fetchall(
            "SELECT 'order' AS kind, id, amount, status, title AS info, created_at AS ts FROM orders WHERE user_id=?"
            " UNION ALL SELECT 'topup', id, amount, status, method, created_at FROM topups WHERE user_id=?"
            " UNION ALL SELECT 'tx', id, amount, kind, ref, created_at FROM transactions WHERE user_id=?"
            " ORDER BY ts DESC LIMIT ? OFFSET ?", user_id, user_id, user_id, limit, offset)
        return rows

    # ---------- stats ----------
    async def stats(self) -> dict:
        day = now() - 86400
        q = self.fetchone
        return {
            "users": (await q("SELECT COUNT(*) c FROM users"))["c"],
            "users_today": (await q("SELECT COUNT(*) c FROM users WHERE created_at>=?", day))["c"],
            "orders_done": (await q("SELECT COUNT(*) c FROM orders WHERE status='done'"))["c"],
            "orders_processing": (await q("SELECT COUNT(*) c FROM orders WHERE status='processing'"))["c"],
            "revenue": (await q("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='done'"))["s"],
            "revenue_today": (await q("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='done'"
                                      " AND updated_at>=?", day))["s"],
            "topups_review": (await q("SELECT COUNT(*) c FROM topups WHERE status='review'"))["c"],
            "balances": (await q("SELECT COALESCE(SUM(balance),0) s FROM users"))["s"],
        }


db = DB(config.db_path)
