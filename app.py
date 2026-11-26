import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

import requests  # noqa: E402
from flask import Flask, g, jsonify, redirect, request, send_from_directory  # noqa: E402

import auth  # noqa: E402
import calc  # noqa: E402
import db  # noqa: E402
import planner  # noqa: E402
import quickparse  # noqa: E402
import usda  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# static_folder=None: pages are only served through the routes below, which check the login
app = Flask(__name__, static_folder=None)
db.init()
app.config.update(
    SECRET_KEY=auth.secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE") == "1",   # set to 1 when served over https only
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)


def err(msg, code=400):
    return jsonify(error=msg), code


# ---------- access control: client health data must not be public ----------
PUBLIC = {"/login", "/api/auth/login", "/api/auth/signup", "/api/health", "/api/clinic"}
CLIENT_PATHS = ("/me", "/api/my", "/quick", "/api/analyze", "/api/auth/")


@app.before_request
def guard():
    path = request.path
    # JSON-only API: a form on another website cannot send JSON, which blocks cross-site requests
    if path.startswith("/api/") and request.method in ("POST", "PUT", "DELETE") and not request.is_json:
        return err("Requests must be JSON.", 415)
    g.user = auth.current_user()
    if path in PUBLIC:
        return None
    if not g.user:
        return err("Please log in.", 401) if path.startswith("/api/") else redirect("/login")
    if g.user["role"] == "admin" or path == "/" or path.startswith(CLIENT_PATHS):
        return None
    return err("Not allowed.", 403) if path.startswith("/api/") else redirect("/me")


@app.after_request
def no_cache_for_private_data(resp):
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- pages ----------
def page(name):
    return send_from_directory(STATIC, name)


@app.get("/")
def index():
    return page("index.html") if g.user["role"] == "admin" else redirect("/me")


@app.get("/login")
def login_page():
    return redirect("/") if g.user else page("login.html")


@app.get("/me")
def portal():
    return redirect("/") if g.user["role"] == "admin" else page("portal.html")


@app.get("/quick")
def quick():
    return page("quick.html")


@app.get("/library")
def library():
    return page("library.html")


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- login / sign-up ----------
@app.post("/api/auth/login")
def auth_login():
    body = request.get_json(silent=True) or {}
    user, error = auth.login(body.get("login"), body.get("password") or "")
    return jsonify(user) if user else err(error, 401)


@app.post("/api/auth/signup")
def auth_signup():
    b = request.get_json(silent=True) or {}
    name = (b.get("name") or "").strip()
    email = auth.normalize_email(b.get("email"))
    phone = auth.normalize_phone(b.get("phone"))
    password = b.get("password") or ""
    if not name:
        return err("Enter your full name.")
    if not auth.valid_email(email):
        return err("Enter a valid email address.")
    if not auth.valid_phone(phone):
        return err("Enter a valid phone number.")
    if problem := auth.password_problem(password):
        return err(problem)
    if email == auth.APP_USER.lower():
        return err("This email can't be used.")
    if db.get_account(email=email):
        return err("An account with this email already exists. Log in instead.", 409)
    if db.get_account(phone=phone):
        return err("An account with this phone number already exists. Log in instead.", 409)
    client = db.save_client({"name": name, "phone": phone, "email": email, "new_signup": True,
                             "sex": "female", "activity": "light", "goal": "lose", "meals_per_day": "4",
                             "plan_language": "English", "cuisine": "Lebanese / Mediterranean"})
    acc = db.create_account(client["id"], email, phone, auth.hash_password(password))
    auth.start_client_session(acc)
    return jsonify(auth.current_user()), 201


@app.post("/api/auth/logout")
def auth_logout():
    auth.logout()
    return jsonify(ok=True)


@app.get("/api/auth/me")
def auth_me():
    return jsonify(g.user)


# ---------- settings (clinic name shown to clients and on printouts) ----------
@app.get("/api/clinic")
def clinic_public():
    """Only the clinic name, for the login page."""
    return jsonify(clinic=db.get_setting("clinic", ""))


@app.get("/api/settings")
def settings_get():
    return jsonify(clinic=db.get_setting("clinic", ""))


@app.put("/api/settings")
def settings_put():
    clinic = ((request.get_json(silent=True) or {}).get("clinic") or "").strip()[:120]
    db.set_setting("clinic", clinic)
    return jsonify(clinic=clinic)


# ---------- client portal (the logged-in client's own data only) ----------
CLIENT_VISIBLE = ("name", "phone", "email", "sex", "age", "height_cm", "weight_kg", "goal",
                  "activity", "meals_per_day", "allergies", "plan_language")


@app.get("/api/my")
def my_overview():
    cid = g.user["client_id"]
    client = db.get_client(cid)
    try:
        assessment = calc.compute(client)
    except calc.ValidationError:
        assessment = None
    return jsonify(
        client={k: client.get(k) for k in CLIENT_VISIBLE},
        assessment=assessment,
        plans=[p for p in db.list_plans(cid) if p["shared"]],
        unread=db.unread_counts("admin").get(cid, 0),
        clinic=db.get_setting("clinic", ""),
    )


@app.get("/api/my/plans/<int:pid>")
def my_plan(pid):
    p = db.get_plan(pid)
    if not p or p["client_id"] != g.user["client_id"] or not p.get("shared"):
        return err("Plan not found", 404)
    hidden = ("warnings", "client_snapshot")   # notes meant for the specialist only
    return jsonify({k: v for k, v in p.items() if k not in hidden})


@app.get("/api/my/messages")
def my_messages():
    cid = g.user["client_id"]
    db.mark_read(cid, "admin")
    return jsonify(db.list_messages(cid))


@app.post("/api/my/messages")
def my_message_send():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return err("Write your question first.")
    if len(text) > 2000:
        return err("Keep it under 2000 characters.")
    db.add_message(g.user["client_id"], "client", text)
    return jsonify(db.list_messages(g.user["client_id"])), 201


@app.post("/api/my/password")
def my_password():
    b = request.get_json(silent=True) or {}
    acc = db.get_account(aid=g.user["account_id"])
    if not auth.check_password_hash(acc["password_hash"], b.get("current") or ""):
        return err("Your current password is wrong.")
    if problem := auth.password_problem(b.get("new") or ""):
        return err(problem)
    acc = db.update_account(acc["id"], acc["email"], acc["phone"], auth.hash_password(b["new"]))
    auth.start_client_session(acc)   # keep this device logged in, log out the others
    return jsonify(ok=True)


# ---------- the specialist's view of a client's login and questions ----------
@app.get("/api/clients/<int:cid>/account")
def client_account(cid):
    acc = db.get_account(client_id=cid)
    return jsonify({k: acc[k] for k in ("email", "phone", "created")} if acc else None)


@app.post("/api/clients/<int:cid>/account")
def client_account_save(cid):
    """Create a login for a client, or change their login email/phone or reset their password."""
    if not db.get_client(cid):
        return err("Client not found", 404)
    b = request.get_json(silent=True) or {}
    email, phone = auth.normalize_email(b.get("email")), auth.normalize_phone(b.get("phone"))
    password = b.get("password") or ""
    if not auth.valid_email(email):
        return err("Enter a valid email address.")
    if not auth.valid_phone(phone):
        return err("Enter a valid phone number.")
    acc = db.get_account(client_id=cid)
    if not acc or password:
        if problem := auth.password_problem(password):
            return err(problem)
    for field, value in (("email", email), ("phone", phone)):
        other = db.get_account(**{field: value})
        if other and other["client_id"] != cid:
            return err(f"Another client already uses this {field}.", 409)
    hashed = auth.hash_password(password) if password else None
    acc = db.update_account(acc["id"], email, phone, hashed) if acc else \
        db.create_account(cid, email, phone, hashed)
    return jsonify({k: acc[k] for k in ("email", "phone", "created")})


@app.delete("/api/clients/<int:cid>/account")
def client_account_delete(cid):
    db.delete_account(cid)
    return "", 204


@app.get("/api/clients/<int:cid>/messages")
def client_messages(cid):
    db.mark_read(cid, "client")
    return jsonify(db.list_messages(cid))


@app.post("/api/clients/<int:cid>/messages")
def client_message_reply(cid):
    if not db.get_client(cid):
        return err("Client not found", 404)
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return err("Write your answer first.")
    db.add_message(cid, "admin", text[:4000])
    return jsonify(db.list_messages(cid)), 201


@app.post("/api/plans/<int:pid>/share")
def plan_share(pid):
    p = db.get_plan(pid)
    if not p:
        return err("Plan not found", 404)
    p["shared"] = bool((request.get_json(silent=True) or {}).get("shared"))
    return jsonify(db.save_plan(p["client_id"], p, pid))


# ---------- calculations ----------
@app.post("/api/calc")
def calculate():
    try:
        return jsonify(calc.compute(request.get_json(silent=True) or {}))
    except calc.ValidationError as e:
        return err(str(e))


# ---------- clients ----------
@app.get("/api/clients")
def clients_list():
    unread = db.unread_counts("client")
    clients = db.list_clients()
    for c in clients:
        c["unread"] = unread.get(c["id"], 0)
    return jsonify(clients)


@app.post("/api/clients")
def clients_create():
    return jsonify(db.save_client(request.get_json(silent=True) or {})), 201


@app.get("/api/clients/<int:cid>")
def clients_get(cid):
    c = db.get_client(cid)
    return jsonify(c) if c else err("Client not found", 404)


@app.put("/api/clients/<int:cid>")
def clients_update(cid):
    if not db.get_client(cid):
        return err("Client not found", 404)
    body = request.get_json(silent=True) or {}
    body.pop("unread", None)
    body["new_signup"] = False      # the specialist has looked at this client's profile
    return jsonify(db.save_client(body, cid))


@app.delete("/api/clients/<int:cid>")
def clients_delete(cid):
    db.delete_client(cid)
    return "", 204


# ---------- plans ----------
@app.get("/api/clients/<int:cid>/plans")
def plans_list(cid):
    return jsonify(db.list_plans(cid))


@app.post("/api/clients/<int:cid>/plans")
def plans_generate(cid):
    client = db.get_client(cid)
    if not client:
        return err("Client not found", 404)
    body = request.get_json(silent=True) or {}
    days = max(1, min(7, int(body.get("days") or 7)))
    language = body.get("language") or client.get("plan_language") or "English"

    try:
        result = calc.compute(client)
    except calc.ValidationError as e:
        return err(f"Client profile incomplete: {e}")

    # Specialist overrides win over calculated targets
    targets = dict(result["targets"])
    for k, v in (body.get("targets") or {}).items():
        if k in targets and v not in (None, ""):
            try:
                targets[k] = float(v)
            except (TypeError, ValueError):
                return err(f"Target '{k}' must be a number")

    try:
        plan = planner.generate(client, result, targets, days=days, language=language)
    except RuntimeError as e:
        return err(str(e), 422)

    plan["assessment"] = {k: v for k, v in result.items() if k != "targets"}
    plan["client_snapshot"] = {k: client.get(k) for k in
                               ("name", "sex", "age", "height_cm", "weight_kg", "goal", "allergies")}
    return jsonify(db.save_plan(cid, plan)), 201


@app.get("/api/plans/<int:pid>")
def plans_get(pid):
    p = db.get_plan(pid)
    return jsonify(p) if p else err("Plan not found", 404)


@app.put("/api/plans/<int:pid>")
def plans_update(pid):
    existing = db.get_plan(pid)
    if not existing:
        return err("Plan not found", 404)
    body = request.get_json(silent=True) or {}
    if "days" not in body:
        return err("Plan must include days")
    plan = {**existing, **body}
    planner.recompute(plan)  # never trust totals sent by the browser
    return jsonify(db.save_plan(existing["client_id"], plan, pid))


@app.delete("/api/plans/<int:pid>")
def plans_delete(pid):
    db.delete_plan(pid)
    return "", 204


# ---------- meal library ----------
def _clean_meal(body: dict) -> dict:
    """Validate a meal from the library page; raises ValueError with a readable message."""
    name = (body.get("name") or "").strip()
    if not name:
        raise ValueError("Give the meal a name.")
    slots = [s for s in body.get("slots") or [] if s in ("breakfast", "snack", "lunch", "dinner")]
    if not slots:
        raise ValueError("Pick at least one meal type (breakfast, snack, lunch or dinner).")
    items = []
    for it in body.get("items") or []:
        term = (it.get("search_term") or "").strip()
        if not term:
            continue
        try:
            grams = float(it.get("grams"))
        except (TypeError, ValueError):
            raise ValueError(f"Grams for '{it.get('food') or term}' must be a number.")
        if not 0 < grams <= 2000:
            raise ValueError(f"Grams for '{it.get('food') or term}' must be between 1 and 2000.")
        try:
            unit_g = float(it["unit_g"]) if it.get("unit_g") not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError(f"Grams per measure for '{it.get('food') or term}' must be a number.")
        unit = (it.get("unit") or "").strip() or None
        items.append({
            "food": (it.get("food") or "").strip() or term,
            "food_ar": (it.get("food_ar") or "").strip() or None,
            "search_term": term, "grams": grams,
            "unit": unit if unit_g else None,
            "unit_ar": ((it.get("unit_ar") or "").strip() or None) if unit_g else None,
            "unit_g": unit_g if unit else None,
        })
    if not items:
        raise ValueError("Add at least one food with a USDA search term.")
    tags = [t for t in body.get("tags") or [] if t in ("vegetarian", "vegan", "high_sodium", "high_sugar")]
    return {"name": name, "name_ar": (body.get("name_ar") or "").strip() or None,
            "slots": slots, "tags": tags, "items": items}


@app.get("/api/meals")
def meals_list():
    return jsonify(db.list_meals())


@app.post("/api/meals")
def meals_create():
    try:
        return jsonify(db.save_meal(_clean_meal(request.get_json(silent=True) or {}))), 201
    except ValueError as e:
        return err(str(e))


@app.put("/api/meals/<int:mid>")
def meals_update(mid):
    if not db.get_meal(mid):
        return err("Meal not found", 404)
    try:
        return jsonify(db.save_meal(_clean_meal(request.get_json(silent=True) or {}), mid))
    except ValueError as e:
        return err(str(e))


@app.delete("/api/meals/<int:mid>")
def meals_delete(mid):
    db.delete_meal(mid)
    return "", 204


@app.get("/api/food")
def food_lookup():
    """Look up a food so the specialist can add or swap items manually."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return err("q is required")
    try:
        food = usda.lookup(q)
    except requests.RequestException:
        return err("USDA service unavailable", 502)
    return jsonify(food) if food else err("No match", 404)


# ---------- quick meal analyzer (v1) ----------
@app.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return err("Please describe what you ate.")
    if len(text) > 500:
        return err("Keep it under 500 characters.")
    extracted = quickparse.parse(text)
    if not extracted:
        return err("I couldn't find any food in that. Try something like '2 eggs, 1 slice bread, 1 cup milk'.", 422)

    items = []
    for it in extracted:
        try:
            food = usda.lookup(it["search_term"])
        except requests.RequestException:
            food = None
        items.append({**it,
                      "matched": food["description"] if food else None,
                      "per_100g": food["per_100g"] if food else None,
                      "nutrients": planner.scale(food["per_100g"], it["grams"]) if food else None})
    if not any(i["matched"] for i in items):
        return err("I couldn't find any food in that. Try something like '2 eggs, 1 slice bread, 1 cup milk'.", 422)
    totals = planner._sum(i["nutrients"] for i in items)
    summary = quickparse.summarize(totals) if body.get("summary", True) else None
    return jsonify(items=items, totals=totals, summary=summary, source="USDA FoodData Central")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=int(os.getenv("PORT", 5000)))
