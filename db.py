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
