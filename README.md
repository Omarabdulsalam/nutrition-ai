# NutriAI: AI diet planner for nutrition specialists

The specialist enters a client's profile. The app calculates BMR, TDEE and macro targets, then AI drafts a
full multi-day meal plan. Every food is checked against USDA data and the portions are balanced to hit the
targets. The specialist reviews and edits the plan, then prints it for the client.

## Features
- **Client records** (SQLite): body stats, goal, activity, allergies, dislikes, medical notes, cuisine, budget
- **Assessment** (calc.py, deterministic, no AI):
  - BMI and healthy weight range
  - BMR: Mifflin-St Jeor, or Katch-McArdle when body-fat % is known
  - TDEE = BMR × activity factor (1.2 to 1.9)
  - Calorie target from the goal rate (7700 kcal ≈ 1 kg). The deficit is capped at max(25% of TDEE, 550 kcal),
    and calories never go below BMR or 1200/1500 kcal
  - Protein in g/kg (adjusted body weight when BMI ≥ 30), fat as % of calories, carbs as the remainder;
    fiber and water targets
  - Warnings for under-18s, pregnancy, low BMI and low carbs
- **AI plan generation** (planner.py): 1 to 7 days, 3 to 6 meals per day, in English, Arabic or French
  - Respects allergies (including hidden sources), dislikes, medical notes and local cuisine
  - All nutrients come from USDA FoodData Central; the AI never supplies the numbers
  - Auto-balances each day's portions to the calorie target (within ±25%)
  - Flags possible allergens and any foods without a USDA match for the specialist to review
- **Plan editor**: edit grams, remove or add foods, see live totals against targets, save
- **Print / PDF**: a clean client handout with the clinic name, assessment and every day of the plan (RTL for Arabic)
- **Password protection** with `APP_PASSWORD`, because client health data must not be public
- Quick meal analyzer at `/quick`

## Setup
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # fill in the keys and set APP_PASSWORD
python app.py           # http://localhost:5000
```
- Anthropic key: https://console.anthropic.com
- USDA key (free, 1000 requests/hour): https://fdc.nal.usda.gov/api-key-signup

## Deploy
Plan generation can take 1 to 2 minutes, so raise the timeout:
```bash
gunicorn app:app -w 2 --timeout 180 -b 0.0.0.0:$PORT
```
Works on Render, Railway or a VPS. Use a persistent disk for `nutriai.db` and `cache.db`, and always set `APP_PASSWORD`.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | /api/calc | Profile → BMI, BMR, TDEE, targets, warnings |
| GET/POST | /api/clients | List / create clients |
| GET/PUT/DELETE | /api/clients/:id | Read / update / delete a client |
| GET | /api/clients/:id/plans | List a client's plans |
| POST | /api/clients/:id/plans | Generate a plan `{days, language, targets?}` |
| GET/PUT/DELETE | /api/plans/:id | Read / save edits / delete a plan |
| GET | /api/food?q= | USDA lookup for manual additions |
| POST | /api/analyze | Quick meal analyzer |

## Cost
One 7-day plan is a single Claude call plus cached USDA lookups. Check current API pricing and include it in your monthly fee.

## Disclaimer
This tool drafts plans for a qualified specialist to review. It is not a substitute for professional judgement,
especially for medical conditions, pregnancy, children or eating disorders.
