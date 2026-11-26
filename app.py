import hmac
import os

from dotenv import load_dotenv

load_dotenv()

import requests  # noqa: E402
from flask import Flask, Response, jsonify, request, send_from_directory  # noqa: E402

import calc  # noqa: E402
import db  # noqa: E402
import planner  # noqa: E402
import quickparse  # noqa: E402
import usda  # noqa: E402

app = Flask(__name__, static_folder="static")
db.init()

APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


# ---------- auth: client health data must not be public ----------
@app.before_request
def require_login():
    if not APP_PASSWORD or request.path == "/api/health":
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.username or "", APP_USER) \
            and hmac.compare_digest(auth.password or "", APP_PASSWORD):
        return None
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="NutriAI"'})


def err(msg, code=400):
    return jsonify(error=msg), code


# ---------- pages ----------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/quick")
def quick():
    return send_from_directory(app.static_folder, "quick.html")


@app.get("/library")
def library():
    return send_from_directory(app.static_folder, "library.html")


@app.get("/api/health")
def health():
    return {"ok": True}


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
    return jsonify(db.list_clients())


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
    return jsonify(db.save_client(request.get_json(silent=True) or {}, cid))


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
