"""Meal-plan generation from the specialist's own meal library (no AI, no paid services).

For each day the planner picks one meal per slot (breakfast, snack, lunch, dinner) from the
library, skipping meals that contain the client's allergens or dislikes or that clash with
their medical notes, avoiding the same meal on back-to-back days, and preferring meals whose
protein share is close to the target. Portions are then scaled so each slot gets its share of
the daily calories, and nutrients are computed from USDA data.
"""
import random
import re
from concurrent.futures import ThreadPoolExecutor

import requests

import db
import usda

NUTRIENT_KEYS = list(usda.NUTRIENTS)

# Daily slots per meals_per_day: (slot, time, share of daily calories)
SLOTS = {
    3: [("breakfast", "08:00", .30), ("lunch", "13:30", .40), ("dinner", "19:30", .30)],
    4: [("breakfast", "08:00", .25), ("lunch", "13:30", .35), ("snack", "16:30", .12),
        ("dinner", "19:30", .28)],
    5: [("breakfast", "08:00", .22), ("snack", "10:30", .10), ("lunch", "13:30", .33),
        ("snack", "16:30", .10), ("dinner", "19:30", .25)],
    6: [("breakfast", "08:00", .20), ("snack", "10:30", .10), ("lunch", "13:30", .30),
        ("snack", "16:30", .10), ("dinner", "19:30", .22), ("snack", "21:30", .08)],
}

SLOT_NAMES = {
    "English": {"breakfast": "Breakfast", "snack": "Snack", "lunch": "Lunch", "dinner": "Dinner"},
    "Arabic": {"breakfast": "فطور", "snack": "وجبة خفيفة", "lunch": "غداء", "dinner": "عشاء"},
    "French": {"breakfast": "Petit-déjeuner", "snack": "Collation", "lunch": "Déjeuner", "dinner": "Dîner"},
}

NOTES = {
    "English": [
        "Drink about {water} L of water a day.",
        "Weights are for food as eaten: weigh cooked foods after cooking.",
        "You can swap any meal for another meal of the same type (e.g. one breakfast for another).",
        "Use herbs, lemon and spices for flavour instead of extra salt.",
    ],
    "Arabic": [
        "اشرب حوالي {water} ليتر من الماء يومياً.",
        "الأوزان للطعام كما يؤكل: الأطعمة المطبوخة توزن بعد الطبخ.",
        "يمكنك تبديل أي وجبة بوجبة أخرى من نفس النوع (مثلاً فطور مكان فطور).",
        "استعمل الأعشاب والحامض والبهارات بدل الملح الزائد.",
    ],
    "French": [
        "Buvez environ {water} L d'eau par jour.",
        "Les poids correspondent aux aliments tels que consommés : pesez les aliments cuits après cuisson.",
        "Vous pouvez remplacer un repas par un autre du même type (un petit-déjeuner par un autre).",
        "Utilisez herbes, citron et épices plutôt que du sel en plus.",
    ],
}

ALLERGEN_KEYWORDS = {
    "nut": ["almond", "walnut", "cashew", "pistachio", "hazelnut", "pecan", "peanut", "nut"],
    "peanut": ["peanut"],
    "dairy": ["milk", "cheese", "yogurt", "yoghurt", "labneh", "butter", "cream", "whey", "halloumi", "akkawi"],
    "milk": ["milk", "cheese", "yogurt", "yoghurt", "labneh", "butter", "cream", "whey", "halloumi", "akkawi"],
    "lactose": ["milk", "cheese", "yogurt", "labneh", "cream", "whey"],
    "gluten": ["wheat", "bread", "pasta", "flour", "barley", "couscous", "bulgur", "freekeh", "rye", "pita", "oat",
               "manoushe"],
    "wheat": ["wheat", "bread", "pasta", "flour", "couscous", "bulgur", "freekeh", "pita", "manoushe"],
    "egg": ["egg", "omelette", "omelet", "shakshuka"],
    "fish": ["fish", "salmon", "tuna", "sardine", "cod", "tilapia", "mackerel"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "shellfish", "mussel", "clam", "squid"],
    "seafood": ["fish", "salmon", "tuna", "sardine", "cod", "tilapia", "mackerel", "shrimp", "prawn", "crab",
                "lobster", "shellfish", "mussel", "clam", "squid"],
    "soy": ["soy", "tofu", "edamame", "tempeh"],
    "sesame": ["sesame", "tahini", "halva", "za'atar", "zaatar", "hummus"],
}

# (words in the client's notes, meal tag to exclude, warning for the specialist)
MEDICAL_RULES = [
    (["hypertension", "blood pressure", "ضغط"], "high_sodium",
     "High blood pressure noted: salty meals (pickles, cheese plates, olives) were left out."),
    (["diabet", "insulin", "glucose", "sugar", "سكري"], "high_sugar",
     "Diabetes / blood sugar noted: sugary meals (e.g. dates with milk) were left out. "
     "Check carbs are spread across meals."),
]


def _allergen_words(allergies: list[str]) -> list[str]:
    words = set()
    for a in allergies:
        a = a.strip().lower()
        if not a:
            continue
        words.add(a.rstrip("s"))
        for key, kws in ALLERGEN_KEYWORDS.items():
            if key in a:
                words.update(kws)
    return sorted(words)


def _mentions(words, text: str) -> list[str]:
    """Words found in text as whole words (plurals allowed), so 'egg' does not hit 'eggplant'."""
    return [w for w in words if re.search(rf"\b{re.escape(w)}(s|es)?\b", text)]


def scale(per_100g: dict | None, grams: float) -> dict | None:
    if not per_100g:
        return None
    f = grams / 100.0
    return {k: (round(v * f, 1) if v is not None else None) for k, v in per_100g.items()}


def _sum(rows) -> dict:
    tot = {k: 0.0 for k in NUTRIENT_KEYS}
    for r in rows:
        if not r:
            continue
        for k in NUTRIENT_KEYS:
            if r.get(k) is not None:
                tot[k] += r[k]
    return {k: round(v, 1) for k, v in tot.items()}


# ---------- household measures ----------
def _plural(unit: str) -> str:
    if unit.endswith(("tbsp", "tsp")):
        return unit
    if unit.endswith("half"):
        return unit[:-4] + "halves"
    if unit.endswith(("tomato", "potato")):
        return unit + "es"
    return unit + "s"


def household(it: dict, language: str = "English") -> str:
    """'2 eggs', '1½ small pitas', '3 ملعقة صغيرة' or '120 g', from grams and the food's unit."""
    grams, unit_g = it.get("grams") or 0, it.get("unit_g")
    g = "غ" if language == "Arabic" else "g"
    if not unit_g or not it.get("unit"):
        return f"{grams:g} {g}"
    qty = grams / unit_g
    qty = round(qty * 2) / 2 if qty < 3 else round(qty)
    if qty <= 0:
        return f"{grams:g} {g}"
    whole, half = int(qty), qty % 1 >= .5
    qty_text = (str(whole) if whole else "") + ("½" if half else "")
    if language == "Arabic" and it.get("unit_ar"):
        unit = it["unit_ar"]
    else:
        unit = it["unit"] if qty == 1 or qty < 1 else _plural(it["unit"])
    return f"{qty_text} {unit}"


def _set_grams(it: dict, grams: float, language: str):
    if it.get("unit_g") and it.get("unit"):
        # snap to clean household amounts: whole/half units ("2½ eggs"), whole units from 3 up
        qty = grams / it["unit_g"]
        qty = round(qty * 2) / 2 if qty < 3 else round(qty)
        grams = qty * it["unit_g"] if qty > 0 else grams
    grams = round(grams / 5) * 5 if grams >= 20 else round(grams, 1)
    it["grams"] = int(grams) if grams == int(grams) else grams
    it["household"] = household(it, language)


def recompute(plan: dict) -> dict:
    """Recompute item, meal and day totals (and household measures) from per_100g and grams."""
    language = plan.get("language") or "English"
    for day in plan["days"]:
        for meal in day["meals"]:
            for it in meal["items"]:
                it["nutrients"] = scale(it.get("per_100g"), it["grams"])
                if it.get("unit_g"):
                    it["household"] = household(it, language)
            meal["totals"] = _sum(it["nutrients"] for it in meal["items"])
        day["totals"] = _sum(m["totals"] for m in day["meals"])
    return plan


def _balance(plan: dict, target_kcal: float):
    """Scale each day's portions so calories land on target (up to ±25% per round, 3 rounds)."""
    language = plan.get("language") or "English"
    for _ in range(3):
        for day in plan["days"]:
            kcal = day["totals"]["calories"]
            if not kcal:
                continue
            factor = target_kcal / kcal
            if abs(1 - factor) <= 0.04:
                continue
            factor = max(0.75, min(1.25, factor))
            for meal in day["meals"]:
                for it in meal["items"]:
                    _set_grams(it, it["grams"] * factor, language)
        recompute(plan)


# ---------- generation ----------
def _lookup_all(terms: set[str]) -> dict:
    def safe_lookup(t):
        try:
            return t, usda.lookup(t)
        except requests.RequestException:
            return t, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(ex.map(safe_lookup, terms))


def _meal_text(meal: dict) -> str:
    parts = [meal.get("name"), meal.get("name_ar")]
    for it in meal.get("items", []):
        parts += [it.get("food"), it.get("food_ar"), it.get("search_term")]
    return " ".join(p for p in parts if p).lower()


def generate(client: dict, calc_result: dict, targets: dict, days: int = 7, language: str = "English") -> dict:
    meals_per_day = int(client.get("meals_per_day") or 4)
    slots = SLOTS.get(meals_per_day, SLOTS[4])
    slot_names = SLOT_NAMES.get(language, SLOT_NAMES["English"])
    arabic = language == "Arabic"
    warnings = list(calc_result.get("warnings", []))

    library = db.list_meals()
    if not library:
        raise RuntimeError("Your meal library is empty. Add meals on the Meal library page first.")

    # ---- filter the library for this client ----
    banned = _allergen_words((client.get("allergies") or "").split(","))
    dislikes = [w.strip().lower() for w in (client.get("dislikes") or "").split(",") if w.strip()]
    notes_text = " ".join(str(client.get(k) or "") for k in
                          ("medical_notes", "cuisine", "specialist_notes")).lower()

    excluded_tags = set()
    for words, tag, msg in MEDICAL_RULES:
        if any(w in notes_text for w in words):
            excluded_tags.add(tag)
            warnings.append(msg)
    if "kidney" in notes_text or "renal" in notes_text or "كلى" in notes_text:
        warnings.append("Kidney condition noted: protein was NOT reduced automatically. Review protein targets.")

    required = None
    if "vegan" in notes_text or "نباتي صرف" in notes_text:
        required = {"vegan"}
    elif "vegetarian" in notes_text or "نباتي" in notes_text:
        required = {"vegetarian", "vegan"}

    # ---- nutrients for every food in the library (cached after the first time) ----
    found = _lookup_all({it["search_term"].strip().lower() for m in library for it in m.get("items", [])})

    def kcal_protein(items):
        kcal = protein = 0.0
        for it in items:
            food = found.get(it["search_term"].strip().lower())
            n = scale(food["per_100g"], it["grams"]) if food else None
            kcal += (n or {}).get("calories") or 0
            protein += (n or {}).get("protein_g") or 0
        return kcal, protein

    avoid = banned + dislikes
    allowed = []
    for m in library:
        tags = set(m.get("tags") or [])
        if tags & excluded_tags or (required and not tags & required):
            continue
        if _mentions(avoid, " ".join(filter(None, [m.get("name"), m.get("name_ar")])).lower()):
            continue                     # the dish itself is the problem, e.g. "Za'atar manoushe"
        keep, removed = [], []
        for it in m.get("items") or []:
            text = " ".join(filter(None, [it.get("food"), it.get("food_ar"), it.get("search_term")])).lower()
            (removed if _mentions(avoid, text) else keep).append(it)
        if not keep:
            continue
        kcal, protein = kcal_protein(keep)
        # Drop a clashing side (the pita in foul) but not the core of the dish.
        if removed and kcal < 0.6 * kcal_protein(m["items"])[0]:
            continue
        if kcal > 0:
            allowed.append({**m, "items": keep, "_kcal": kcal, "_protein": protein,
                            "_removed": [it.get("food") or it["search_term"] for it in removed]})

    # Slots with no suitable meal are left out and their calories shared among the others.
    active = [s for s in slots if any(s[0] in (m.get("slots") or []) for m in allowed)]
    for slot in dict.fromkeys(s[0] for s in slots if s not in active):
        warnings.append(f"No {slot} meal in your library suits this client, so {slot} was left out. "
                        f"Add more {slot} meals on the Meal library page.")
    if not active:
        raise RuntimeError("No meal in your library suits this client (allergies, dislikes or diet). "
                           "Add suitable meals on the Meal library page.")
    if days > 2:
        for slot in dict.fromkeys(s[0] for s in active):
            n = sum(slot in (m.get("slots") or []) for m in allowed)
            if n < 3:
                warnings.append(f"Only {n} {slot} meal{'s' if n > 1 else ''} in your library suit this client, "
                                f"so {slot} repeats. Add more {slot} meals for variety.")
    total_share = sum(s[2] for s in active)
    active = [(slot, time, share / total_share) for slot, time, share in active]

    target_ratio = targets["protein_g"] * 4 / targets["calories"] if targets.get("calories") else 0.25
    rng = random.Random()        # new variety every time the plan is generated
    last_used, times_used = {}, {}
    plan_days = []
    reported_removed = set()

    for d in range(days):
        used_today, meals = set(), []
        for slot, time, share in active:
            pool = [m for m in allowed if slot in (m.get("slots") or [])]
            fresh = [m for m in pool if m["id"] not in used_today and d - last_used.get(m["id"], -9) > 1]
            cands = fresh or [m for m in pool if m["id"] not in used_today] or pool
            budget = targets["calories"] * share

            def score(m):
                # protein fit first, then variety, with a little randomness so plans differ
                s = abs(m["_protein"] * 4 / m["_kcal"] - target_ratio)
                s += 0.1 * times_used.get(m["id"], 0) + rng.random() * 0.08
                if not 0.5 <= budget / m["_kcal"] <= 2.0:
                    s += 0.3             # portion would need more than doubling or halving
                return s

            pick = min(cands, key=score)
            if pick["_removed"] and pick["id"] not in reported_removed:
                reported_removed.add(pick["id"])
                warnings.append(f"'{pick['name']}': left out {', '.join(pick['_removed'])} "
                                "(allergy or dislike).")
            used_today.add(pick["id"])
            last_used[pick["id"]] = d
            times_used[pick["id"]] = times_used.get(pick["id"], 0) + 1

            factor = max(0.5, min(2.0, budget / pick["_kcal"]))
            items = []
            for src in pick["items"]:
                food = found.get(src["search_term"].strip().lower())
                it = {
                    "food": (src.get("food_ar") if arabic else None) or src.get("food") or src["search_term"],
                    "search_term": src["search_term"],
                    "unit": src.get("unit"), "unit_ar": src.get("unit_ar"), "unit_g": src.get("unit_g"),
                    "matched": food["description"] if food else None,
                    "fdc_id": food["fdc_id"] if food else None,
                    "per_100g": food["per_100g"] if food else None,
                    "flags": [],
                }
                _set_grams(it, float(src["grams"]) * factor, language)
                items.append(it)
            meals.append({
                "name": slot_names[slot], "time": time,
                "title": (pick.get("name_ar") if arabic else None) or pick["name"],
                "meal_id": pick["id"], "items": items,
            })
        plan_days.append({"day": d + 1, "meals": meals})

    plan = {"days": plan_days, "language": language,
            "notes": [n.format(water=calc_result.get("water_l", 2)) for n in NOTES.get(language, NOTES["English"])]}
    recompute(plan)
    _balance(plan, targets["calories"])

    # ---- checks for the specialist ----
    low_protein = [str(d["day"]) for d in plan["days"]
                   if targets.get("protein_g") and d["totals"]["protein_g"] < 0.85 * targets["protein_g"]]
    if low_protein:
        warnings.append(f"Protein is under target on day {', '.join(low_protein)}. Add a protein food "
                        "(chicken, eggs, yogurt, legumes) or add higher-protein meals to your library.")
    off_kcal = [str(d["day"]) for d in plan["days"]
                if abs(d["totals"]["calories"] - targets["calories"]) > 0.1 * targets["calories"]]
    if off_kcal:
        warnings.append(f"Calories are more than 10% off target on day {', '.join(off_kcal)}. Adjust portions.")
    if (client.get("specialist_notes") or "").strip():
        warnings.append("Your plan instructions are not applied automatically. Check the plan against them: "
                        + client["specialist_notes"].strip())
    if language == "French":
        warnings.append("Food and meal names are in English: the meal library has English and Arabic names only.")

    plan["targets"] = targets
    plan["warnings"] = warnings
    return plan
