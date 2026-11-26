"""LLM layer: turns free text into structured food items, and writes a short summary.

The LLM never invents nutrition numbers. It only:
  1. extracts foods + estimated grams from the user's text
  2. phrases the final answer from numbers computed by our backend
"""
import json
import os

from anthropic import Anthropic

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
_client = None


def client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


EXTRACT_TOOL = {
    "name": "record_foods",
    "description": "Record every food or drink in the user's meal with an estimated weight in grams.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Short label as the user said it, e.g. '2 eggs'.",
                        },
                        "search_term": {
                            "type": "string",
                            "description": "Simple generic English term for the USDA database, "
                            "e.g. 'egg whole cooked', 'bread white', 'olive oil'.",
                        },
                        "grams": {
                            "type": "number",
                            "description": "Best estimate of the total weight in grams.",
                        },
                    },
                    "required": ["name", "search_term", "grams"],
                },
            }
        },
        "required": ["items"],
    },
}

EXTRACT_SYSTEM = """You extract foods from meal descriptions for a nutrition calculator.
- The user may write in any language (English, Arabic, Lebanese dialect, etc.). Always output English search terms.
- Convert quantities to grams using typical portion sizes (1 large egg ~50 g, 1 slice bread ~30 g,
  1 tbsp oil ~14 g, 1 cup cooked rice ~160 g, 1 medium apple ~180 g).
- If a dish is unlikely to exist in the USDA database (e.g. manoushe, mjadra, fattoush, koshari),
  break it into its main ingredients with grams for each (dough, za'atar, olive oil...).
- Include cooking oil or sauces only if mentioned or clearly implied.
- If the text contains no food at all, return an empty items list."""


def extract_foods(text: str) -> list[dict]:
    resp = client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=EXTRACT_SYSTEM,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "record_foods"},
        messages=[{"role": "user", "content": text}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            items = block.input.get("items", [])
            # basic sanity: drop junk and clamp absurd weights
            clean = []
            for it in items:
                try:
                    grams = float(it["grams"])
                except (KeyError, TypeError, ValueError):
                    continue
                if 0 < grams <= 5000 and it.get("search_term"):
                    clean.append({**it, "grams": round(grams, 1)})
            return clean
    return []


SUMMARY_SYSTEM = """You are a friendly nutrition assistant. You are given a meal and its nutrition totals,
which were computed from the USDA database. Write 2-4 short sentences: restate the key numbers
(calories, protein, carbs, fat) and give one practical, non-medical tip.
Use ONLY the numbers provided; never invent new ones. Reply in the same language the user wrote in.
Do not give medical advice."""


def summarize(text: str, totals: dict, items: list[dict]) -> str:
    payload = {
        "meal": text,
        "totals": totals,
        "items": [
            {"name": i["name"], "grams": i["grams"], "matched": i.get("matched")}
            for i in items
        ],
    }
    resp = client().messages.create(
        model=MODEL,
        max_tokens=400,
        system=SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
