"""SQLite storage for the specialist's clients and their plans."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("APP_DB", "nutriai.db")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created TEXT NOT NULL,
            updated TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            created TEXT NOT NULL,
            updated TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created TEXT NOT NULL,
            updated TEXT NOT NULL
        );
        -- client logins: one per client file
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            pw_version INTEGER NOT NULL DEFAULT 1,
            created TEXT NOT NULL
        );
        -- questions from clients and the specialist's answers
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            sender TEXT NOT NULL CHECK (sender IN ('client', 'admin')),
            text TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_client ON messages(client_id);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        empty = c.execute("SELECT COUNT(*) FROM meals").fetchone()[0] == 0
    if empty:
        import meals_seed
        for m in meals_seed.meals():
            save_meal(m)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _client(row):
    return {"id": row["id"], "created": row["created"], "updated": row["updated"], **json.loads(row["data"])}


def list_clients():
    with conn() as c:
        rows = c.execute("SELECT * FROM clients ORDER BY updated DESC").fetchall()
    return [_client(r) for r in rows]


def get_client(cid):
    with conn() as c:
        r = c.execute("SELECT * FROM clients WHERE id = ?", (cid,)).fetchone()
    return _client(r) if r else None


def save_client(data, cid=None):
    data = {k: v for k, v in data.items() if k not in ("id", "created", "updated")}
    name = (data.get("name") or "").strip() or "Unnamed client"
    data["name"] = name
    now = _now()
    with conn() as c:
        if cid:
            c.execute("UPDATE clients SET name=?, data=?, updated=? WHERE id=?",
                      (name, json.dumps(data, ensure_ascii=False), now, cid))
        else:
            cid = c.execute("INSERT INTO clients (name, data, created, updated) VALUES (?,?,?,?)",
                            (name, json.dumps(data, ensure_ascii=False), now, now)).lastrowid
    return get_client(cid)


def delete_client(cid):
    with conn() as c:
        c.execute("DELETE FROM clients WHERE id = ?", (cid,))


def _plan(row, full=True):
    data = json.loads(row["data"])
    out = {"id": row["id"], "client_id": row["client_id"], "created": row["created"], "updated": row["updated"]}
    if full:
        out.update(data)
    else:
        out["days"] = len(data.get("days", []))
        out["calories"] = data.get("targets", {}).get("calories")
        out["shared"] = bool(data.get("shared"))
    return out


def list_plans(cid):
    with conn() as c:
        rows = c.execute("SELECT * FROM plans WHERE client_id = ? ORDER BY id DESC", (cid,)).fetchall()
    return [_plan(r, full=False) for r in rows]


def get_plan(pid):
    with conn() as c:
        r = c.execute("SELECT * FROM plans WHERE id = ?", (pid,)).fetchone()
    return _plan(r) if r else None


def save_plan(cid, data, pid=None):
    data = {k: v for k, v in data.items() if k not in ("id", "client_id", "created", "updated")}
    now = _now()
    with conn() as c:
        if pid:
            c.execute("UPDATE plans SET data=?, updated=? WHERE id=?",
                      (json.dumps(data, ensure_ascii=False), now, pid))
        else:
            pid = c.execute("INSERT INTO plans (client_id, data, created, updated) VALUES (?,?,?,?)",
                            (cid, json.dumps(data, ensure_ascii=False), now, now)).lastrowid
    return get_plan(pid)


def delete_plan(pid):
    with conn() as c:
        c.execute("DELETE FROM plans WHERE id = ?", (pid,))


# ---------- meal library ----------
def _meal(row):
    return {"id": row["id"], **json.loads(row["data"])}


def list_meals():
    with conn() as c:
        rows = c.execute("SELECT * FROM meals ORDER BY name COLLATE NOCASE").fetchall()
    return [_meal(r) for r in rows]


def get_meal(mid):
    with conn() as c:
        r = c.execute("SELECT * FROM meals WHERE id = ?", (mid,)).fetchone()
    return _meal(r) if r else None


def save_meal(data, mid=None):
    data = {k: v for k, v in data.items() if k not in ("id", "created", "updated")}
    name = (data.get("name") or "").strip() or "Unnamed meal"
    data["name"] = name
    now = _now()
    with conn() as c:
        if mid:
            c.execute("UPDATE meals SET name=?, data=?, updated=? WHERE id=?",
                      (name, json.dumps(data, ensure_ascii=False), now, mid))
        else:
            mid = c.execute("INSERT INTO meals (name, data, created, updated) VALUES (?,?,?,?)",
                            (name, json.dumps(data, ensure_ascii=False), now, now)).lastrowid
    return get_meal(mid)


def delete_meal(mid):
    with conn() as c:
        c.execute("DELETE FROM meals WHERE id = ?", (mid,))


# ---------- settings ----------
def get_setting(key, default=None):
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


# ---------- client accounts ----------
def _account(row):
    return dict(row) if row else None


def get_account(aid=None, client_id=None, email=None, phone=None):
    col, val = next((k, v) for k, v in (("id", aid), ("client_id", client_id),
                                        ("email", email), ("phone", phone)) if v is not None)
    with conn() as c:
        return _account(c.execute(f"SELECT * FROM accounts WHERE {col} = ?", (val,)).fetchone())


def create_account(client_id, email, phone, password_hash):
    with conn() as c:
        aid = c.execute("INSERT INTO accounts (client_id, email, phone, password_hash, created) VALUES (?,?,?,?,?)",
                        (client_id, email, phone, password_hash, _now())).lastrowid
    return get_account(aid=aid)


def update_account(aid, email, phone, password_hash=None):
    with conn() as c:
        if password_hash:
            c.execute("UPDATE accounts SET email=?, phone=?, password_hash=?, pw_version=pw_version+1 WHERE id=?",
                      (email, phone, password_hash, aid))
        else:
            c.execute("UPDATE accounts SET email=?, phone=? WHERE id=?", (email, phone, aid))
    return get_account(aid=aid)


def delete_account(client_id):
    with conn() as c:
        c.execute("DELETE FROM accounts WHERE client_id = ?", (client_id,))


# ---------- questions ----------
def list_messages(client_id):
    with conn() as c:
        rows = c.execute("SELECT * FROM messages WHERE client_id = ? ORDER BY id", (client_id,)).fetchall()
    return [dict(r) for r in rows]


def add_message(client_id, sender, text):
    with conn() as c:
        c.execute("INSERT INTO messages (client_id, sender, text, created) VALUES (?,?,?,?)",
                  (client_id, sender, text, _now()))


def mark_read(client_id, sender):
    """Mark messages written by `sender` as read (by the other side)."""
    with conn() as c:
        c.execute("UPDATE messages SET read = 1 WHERE client_id = ? AND sender = ? AND read = 0",
                  (client_id, sender))


def unread_counts(sender):
    """{client_id: number of unread messages written by `sender`}"""
    with conn() as c:
        rows = c.execute("SELECT client_id, COUNT(*) n FROM messages WHERE sender = ? AND read = 0 "
                         "GROUP BY client_id", (sender,)).fetchall()
    return {r["client_id"]: r["n"] for r in rows}
