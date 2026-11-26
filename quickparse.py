"""Free, rule-based meal reader for the quick analyzer (replaces the paid AI).

Turns simple English like "2 eggs, a slice of toast with butter and a cup of milk" into
food items with estimated grams. Users can correct grams on the page afterwards.
"""
import re

NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "half": .5, "some": 1, "few": 3, "couple": 2}

# unit -> grams per unit (food-independent default)
UNITS = {
    "g": 1, "gram": 1, "grams": 1, "gr": 1, "kg": 1000, "ml": 1, "l": 1000,
    "cup": 200, "cups": 200, "bowl": 300, "bowls": 300, "plate": 350, "plates": 350,
    "glass": 250, "glasses": 250, "mug": 250, "mugs": 250, "can": 330, "cans": 330,
    "tbsp": 15, "tablespoon": 15, "tablespoons": 15, "spoon": 15, "spoons": 15,
    "tsp": 5, "teaspoon": 5, "teaspoons": 5,
    "slice": 30, "slices": 30, "piece": 100, "pieces": 100, "handful": 30, "handfuls": 30,
    "scoop": 30, "scoops": 30, "serving": 150, "servings": 150, "loaf": 60, "loaves": 60,
}

# food word -> (better USDA search term, grams for one piece / typical portion)
FOODS = {
    "egg": ("egg whole cooked hard-boiled", 50), "eggs": ("egg whole cooked hard-boiled", 50),
    "fried egg": ("egg whole cooked fried", 50), "fried eggs": ("egg whole cooked fried", 50),
    "scrambled egg": ("egg whole cooked scrambled", 50), "scrambled eggs": ("egg whole cooked scrambled", 50),
    "boiled egg": ("egg whole cooked hard-boiled", 50), "boiled eggs": ("egg whole cooked hard-boiled", 50),
    "toast": ("bread white toasted", 30), "bread": ("bread white", 30),
    "pita": ("pita bread", 60), "pita bread": ("pita bread", 60), "arabic bread": ("pita bread", 60),
    "butter": ("butter salted", 10), "olive oil": ("olive oil", 14),
    "banana": ("banana raw", 120), "bananas": ("banana raw", 120),
    "apple": ("apples raw with skin", 180), "apples": ("apples raw with skin", 180),
    "orange": ("oranges raw", 130), "oranges": ("oranges raw", 130),
    "date": ("dates deglet noor", 7), "dates": ("dates deglet noor", 7),
    "coffee": ("coffee brewed", 240), "tea": ("tea brewed", 240),
    "coke": ("carbonated beverage cola", 330), "cola": ("carbonated beverage cola", 330),
    "pepsi": ("carbonated beverage cola", 330), "soda": ("carbonated beverage cola", 330),
    "milk": ("milk whole", 245), "rice": ("rice white cooked", 160),
    "chicken": ("chicken breast cooked roasted", 120), "chicken breast": ("chicken breast cooked roasted", 120),
    # bowl/cup units apply to the cooked oatmeal, so use the cooked entry
    "oatmeal": ("cereals oats regular and quick not fortified cooked with water", 240),
    "oats": ("oats rolled dry", 40),
    "peanut butter": ("peanut butter smooth", 16), "honey": ("honey", 7),
    "yogurt": ("yogurt plain whole milk", 170), "labneh": ("yogurt greek plain whole milk", 60),
    "hummus": ("hummus", 60), "cheese": ("cheese cheddar", 30), "feta": ("feta cheese", 30),
    "tomato": ("tomatoes red ripe raw", 120), "tomatoes": ("tomatoes red ripe raw", 120),
    "cucumber": ("cucumber raw", 100), "cucumbers": ("cucumber raw", 100),
    "potato": ("potatoes boiled cooked without skin flesh", 150), "fries": ("potatoes french fried", 120),
    "salad": ("lettuce romaine raw", 100), "pasta": ("pasta cooked", 200),
    "sugar": ("sugars granulated", 4), "almonds": ("almonds", 1.2), "walnuts": ("walnuts", 2),
}

FILLER = {"of", "with", "and", "a", "an", "the", "some", "my", "small", "large", "big", "medium", "little"}
SIZE = {"small": .7, "large": 1.4, "big": 1.4}


def _quantity(words: list[str]) -> tuple[float, list[str]]:
    """Leading number ('2', '1.5', '1/2', 'two', 'half a') -> (amount, remaining words)."""
    qty, rest = None, list(words)
    while rest:
        w = rest[0]
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:/(\d+))?", w)
        if m:
            v = float(m.group(1)) / (float(m.group(2)) if m.group(2) else 1)
            qty = v if qty is None else qty * v
        elif w in NUMBER_WORDS:
            qty = NUMBER_WORDS[w] if qty is None else qty * NUMBER_WORDS[w]
        else:
            break
        rest.pop(0)
    return (qty if qty is not None else 1), rest


def parse(text: str) -> list[dict]:
    text = text.lower()
    text = re.sub(r"(\d)\s*(g|gr|kg|ml|l)\b", r"\1 \2", text)           # "150g" -> "150 g"
    chunks = re.split(r",|;|\+|\n|\band\b|\bwith\b|&", text)
    items = []
    for chunk in chunks:
        words = re.findall(r"[a-z]+|\d+(?:\.\d+)?(?:/\d+)?", chunk)
        if not words:
            continue
        qty, rest = _quantity(words)
        size = 1.0
        unit_g = None
        while rest and (rest[0] in UNITS or rest[0] in SIZE or rest[0] in FILLER):
            w = rest.pop(0)
            if w in UNITS and unit_g is None:
                unit_g = UNITS[w]
            elif w in SIZE:
                size = SIZE[w]
        food_words = [w for w in rest if w not in FILLER]
        if not food_words:
            continue
        name = " ".join(food_words)
        # longest known food phrase at the end ("scrambled eggs", "peanut butter", "chicken")
        known = None
        for n in range(len(food_words), 0, -1):
            for i in range(len(food_words) - n + 1):
                phrase = " ".join(food_words[i:i + n])
                if phrase in FOODS:
                    known = FOODS[phrase]
                    break
            if known:
                break
        term = known[0] if known else name
        if unit_g is not None:
            grams = qty * unit_g
        else:
            grams = qty * (known[1] if known else 100) * size
        items.append({"name": " ".join(chunk.split()), "search_term": term,
                      "grams": round(grams, 1), "estimated": known is None and unit_g is None})
    return [i for i in items if 0 < i["grams"] <= 5000]


def summarize(totals: dict) -> str:
    kcal, p, c, f = (round(totals.get(k) or 0) for k in ("calories", "protein_g", "carbs_g", "fat_g"))
    tips = []
    if p < 15:
        tips.append("add a protein source such as eggs, yogurt, chicken or legumes")
    if (totals.get("fiber_g") or 0) < 5:
        tips.append("add vegetables, fruit or whole grains for fibre")
    if (totals.get("sodium_mg") or 0) > 1000:
        tips.append("this meal is quite salty, so keep the rest of the day lower in salt")
    text = f"This meal has about {kcal} kcal: {p} g protein, {c} g carbs and {f} g fat."
    if tips:
        text += " Tip: " + "; ".join(tips) + "."
    return text
