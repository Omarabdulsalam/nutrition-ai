"""USDA FoodData Central lookup with a SQLite cache.

Uses Foundation + SR Legacy data types, whose nutrient values are per 100 g.
Free API key: https://fdc.nal.usda.gov/api-key-signup
"""
import json
import os
import re
import sqlite3
import threading

import requests

API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")  # DEMO_KEY is heavily rate-limited
DB_PATH = os.getenv("CACHE_DB", "cache.db")

# Our field -> USDA nutrient numbers (first match wins)
NUTRIENTS = {
    "calories": ["208", "958", "957"],  # kcal; Foundation foods sometimes only have Atwater energy
    "protein_g": ["203"],
    "carbs_g": ["205"],
    "fat_g": ["204"],
    "fiber_g": ["291"],
    "sugar_g": ["269"],
    "sodium_mg": ["307"],
}

_lock = threading.Lock()

# Bump when the matching logic changes so old cached matches are not reused.
CACHE_VERSION = "v2"

# Words marking a processed / special form. Penalised unless the user asked for them,
# so "banana" finds "Bananas, raw" rather than "Bananas, dehydrated, or banana powder".
PROCESSED = {
    "dried", "dehydrated", "powder", "powdered", "flour", "babyfood",
    "chip", "chips", "juice", "candy", "candies", "cracker", "crackers", "dessert",
    "substitute", "supplement", "breaded", "mix", "nugget", "nuggets", "frozen", "canned",
    "bar", "oil", "sauce", "soup", "pudding", "pie", "cake", "cakes", "cookie", "cookies",
    "muffin", "muffins", "bagel", "bagels", "roll", "rolls", "strudel", "croissant",
    "croissants", "butter", "beverage", "beverages", "lunchmeat", "deli", "flavor",
    "flavored", "sweetened", "condensed", "imitation", "toddler", "prepackaged", "fast",
    "smoked", "cured", "pickled", "stick", "sticks", "glazed", "seasoned", "crumb", "crumbs",
    "dry", "buttermilk",
}
# Words of a plain, everyday form: a small nudge when the user did not specify.
PLAIN = {"raw", "whole", "plain", "fresh", "regular"}
COOKED = {"cooked", "boiled", "roasted", "baked", "fried", "grilled", "steamed",
          "broiled", "stewed", "scrambled", "poached", "braised", "toasted"}
# USDA starts some names with a category ("Nuts, almonds", "Fish, salmon, raw");
# those first words say nothing about whether the entry is the food asked for.
CATEGORY = {"nut", "fish", "cereal", "seed", "spice", "bean", "legume", "beef", "pork",
            "lamb", "veal", "cheese", "oil", "vegetable", "fruit", "grain", "snack"}
# Single words too vague to rank: USDA's results for them lack the everyday food entirely
# (e.g. "milk" returns sheep and buffalo milk but not regular whole milk).
DEFAULTS = {"milk": "milk whole", "bread": "bread white", "rice": "rice white cooked"}
STOP = {"and", "or", "with", "without", "in", "of", "the", "a", "to", "for", "from",
        "by", "no", "not", "added", "include", "includes", "type"}


def _stem(word: str) -> str:
    """Crude singular form so 'bananas' matches 'banana' and 'potatoes' matches 'potato'."""
    if len(word) > 4 and word.endswith("oes"):
        return word[:-2]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z]+", text.lower())]


def _score(query: list[str], description: str) -> float:
    q = set(query) - STOP
    text = re.sub(r"\([^)]*\)", "", description)      # drop "(Includes foods for ...)" notes
    segments = [set(_words(s)) - STOP for s in text.split(",")]
    words = set().union(*segments)
    head = segments[0]

    score = -12.0 * len(q - words)           # every search word should be in the name
    if q & head:
        score += 4                           # "Bananas, raw" names the food first
    # Extra words in the food's own name make it a different food:
    # "Almond milk", "Sweet potato", "Wild rice", "Bread, potato", "Pepper, banana".
    score -= 4 * len(head - q - CATEGORY - PLAIN - COOKED)
    score -= 6 * len((words & PROCESSED) - q)
    if re.search(r"\b[A-Z]{3,}\b", text):
        score -= 4                           # brand products: "Yogurt, Greek, ..., CHOBANI"
    if re.search(r"\band\b", text, re.I) and "and" not in query:
        score -= 3                           # mixtures like "Oil, corn, peanut, and olive"
    # Nudge towards the everyday form ("Egg, whole", "Rice, white, long-grain, regular"),
    # counting only stand-alone segments so "whole-wheat" does not get it.
    plain = {next(iter(s)) for s in segments if len(s) == 1} & PLAIN
    if q & COOKED:
        plain.discard("raw")
    score += 1.5 * len(plain - q)
    score -= 0.3 * len(words - q)            # prefer short, generic entries
    return score


def _best(term: str, foods: list[dict]) -> dict | None:
    query = _words(term)
    # Skip entries without calories when any candidate has them.
    with_kcal = [f for f in foods if _parse(f)["per_100g"]["calories"] is not None]
    pool = with_kcal or foods
    # max() keeps the first of equal scores, so USDA's own relevance order breaks ties.
    return max(pool, key=lambda f: _score(query, f.get("description") or ""), default=None)


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS cache (term TEXT PRIMARY KEY, data TEXT)")
    return conn


def _parse(food: dict) -> dict:
    by_number = {}
    for n in food.get("foodNutrients", []):
        num = str(n.get("nutrientNumber", ""))
        unit = (n.get("unitName") or "").upper()
        if num in ("208", "957", "958") and unit != "KCAL":
            continue  # skip kJ energy rows
        if n.get("value") is not None:
            by_number.setdefault(num, n["value"])

    per_100g = {}
    for field, numbers in NUTRIENTS.items():
        per_100g[field] = next((by_number[x] for x in numbers if x in by_number), None)

    return {
        "fdc_id": food.get("fdcId"),
        "description": food.get("description"),
        "data_type": food.get("dataType"),
        "per_100g": per_100g,
    }


def lookup(term: str) -> dict | None:
    term = term.strip().lower()
    term = DEFAULTS.get(term, term)
    key =f"{CACHE_VERSION}:{term}"
    with _lock, _db() as conn:
        row = conn.execute("SELECT data FROM cache WHERE term = ?", (key,)).fetchone()
        if row:
            return json.loads(row[0])

    # USDA's top hit is often wrong ("banana" -> banana powder, "rice" -> rice crackers),
    # so fetch a page of candidates and rank them ourselves.
    resp = requests.post(
        API_URL,
        params={"api_key": API_KEY},
        json={"query": term, "dataType": ["Foundation", "SR Legacy"], "pageSize": 50},
        timeout=15,
    )
    resp.raise_for_status()
    best = _best(term, resp.json().get("foods", []))
    result = _parse(best) if best else None

    if result:
        with _lock, _db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (term, data) VALUES (?, ?)",
                (key, json.dumps(result)),
            )
    return result
