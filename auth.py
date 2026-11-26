"""Logins: the specialist (admin, from .env) and client accounts (stored in the database).

The admin logs in with APP_USER / APP_PASSWORD from .env. Clients sign up with name, phone,
email and password, and log in with their email or phone. Sessions are signed cookies.
"""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

import db

APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

MAX_FAILURES, WINDOW = 10, 15 * 60          # 10 wrong passwords per login name per 15 minutes
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def secret_key() -> str:
    """Session signing key: SECRET_KEY from .env, else one generated once and kept in the database."""
    key = os.getenv("SECRET_KEY") or db.get_setting("secret_key")
    if not key:
        key = secrets.token_hex(32)
        db.set_setting("secret_key", key)
    return key


def _admin_fingerprint() -> str:
    # changes when APP_PASSWORD changes, which logs the admin out everywhere
    return hashlib.sha256(("nutriai-admin:" + APP_PASSWORD).encode()).hexdigest()[:24]


def normalize_phone(phone: str) -> str:
    """Keep digits (and a leading +) so '+961 3 123 456' and '+9613123456' are the same login."""
    phone = (phone or "").strip()
    digits = re.sub(r"\D", "", phone)
    return ("+" if phone.startswith("+") else "") + digits


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def valid_phone(phone: str) -> bool:
    return 7 <= len(phone.lstrip("+")) <= 15


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def password_problem(password: str) -> str | None:
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    return None


# ---------- brute-force protection ----------
def _blocked(name: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _failures.get(name, []) if now - t < WINDOW]
        _failures[name] = recent
        return len(recent) >= MAX_FAILURES


def _failed(name: str):
    with _lock:
        _failures.setdefault(name, []).append(time.time())


# ---------- login / logout ----------
def login(identifier: str, password: str) -> tuple[dict | None, str | None]:
    """Returns (user, error). On success the session is set."""
    ident = (identifier or "").strip()
    key = ident.lower()
    if not ident or not password:
        return None, "Enter your email or phone and your password."
    if _blocked(key):
        return None, "Too many wrong passwords. Try again in 15 minutes."

    if APP_PASSWORD and hmac.compare_digest(key, APP_USER.lower()):
        if hmac.compare_digest(password, APP_PASSWORD):
            session.clear()
            session.permanent = True
            session["role"] = "admin"
            session["fp"] = _admin_fingerprint()
            return current_user(), None
        _failed(key)
        return None, "Wrong login or password."

    acc = None
    if "@" in ident:
        acc = db.get_account(email=normalize_email(ident))
    else:
        phone = normalize_phone(ident)
        if phone:
            acc = db.get_account(phone=phone)
    if not acc or not check_password_hash(acc["password_hash"], password):
        _failed(key)
        return None, "Wrong login or password."
    start_client_session(acc)
    return current_user(), None


def start_client_session(acc: dict):
    session.clear()
    session.permanent = True
    session["role"] = "client"
    session["aid"] = acc["id"]
    session["pwv"] = acc["pw_version"]


def logout():
    session.clear()


def current_user() -> dict | None:
    role = session.get("role")
    if role == "admin":
        if APP_PASSWORD and session.get("fp") == _admin_fingerprint():
            return {"role": "admin", "name": APP_USER}
        return None
    if role == "client":
        acc = db.get_account(aid=session.get("aid"))
        # a password reset (pw_version change) or deleted account ends old sessions
        if not acc or acc["pw_version"] != session.get("pwv"):
            return None
        client = db.get_client(acc["client_id"])
        if not client:
            return None
        return {"role": "client", "client_id": acc["client_id"], "account_id": acc["id"],
                "name": client.get("name"), "email": acc["email"], "phone": acc["phone"]}
    return None
