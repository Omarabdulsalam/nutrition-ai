"""Deterministic nutrition calculations. No AI here: every number is reproducible.

Formulas
- BMR: Mifflin-St Jeor (default) or Katch-McArdle when body-fat % is known
- TDEE: BMR x activity factor
- Goal: deficit/surplus from target rate (7700 kcal ~ 1 kg body mass)
- Protein: g/kg of reference weight (adjusted weight when BMI >= 30)
- Fat: % of calories; carbs: the remainder
"""

ACTIVITY = {
    "sedentary": (1.2, "Little or no exercise"),
    "light": (1.375, "Light exercise 1-3 days/week"),
    "moderate": (1.55, "Moderate exercise 3-5 days/week"),
    "active": (1.725, "Hard exercise 6-7 days/week"),
    "very_active": (1.9, "Very hard exercise / physical job"),
}
KCAL_PER_KG = 7700
DEFAULT_PROTEIN_G_PER_KG = {"lose": 1.8, "maintain": 1.4, "gain": 1.8}
DEFAULT_RATE = {"lose": 0.5, "maintain": 0.0, "gain": 0.25}  # kg per week
MAX_DEFICIT_PCT = 0.25


class ValidationError(ValueError):
    pass


def _num(p, key, lo, hi, required=True, default=None):
    v = p.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"'{key}' is required")
        return default
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"'{key}' must be a number")
    if not lo <= v <= hi:
        raise ValidationError(f"'{key}' must be between {lo} and {hi}")
    return v


def compute(p: dict) -> dict:
    sex = p.get("sex")
    if sex not in ("male", "female"):
        raise ValidationError("'sex' must be 'male' or 'female'")
    age = _num(p, "age", 10, 100)
    height = _num(p, "height_cm", 100, 250)
    weight = _num(p, "weight_kg", 25, 350)
    body_fat = _num(p, "body_fat_pct", 3, 70, required=False)
    activity = p.get("activity", "light")
    if activity not in ACTIVITY:
        raise ValidationError(f"'activity' must be one of {list(ACTIVITY)}")
    goal = p.get("goal", "maintain")
    if goal not in DEFAULT_RATE:
        raise ValidationError("'goal' must be lose, maintain or gain")
    rate = _num(p, "rate_kg_week", 0, 1.5, required=False, default=DEFAULT_RATE[goal])
    if goal == "maintain":
        rate = 0.0

    warnings = []
    if age < 18:
        warnings.append("Client is under 18: adult formulas and deficits are not appropriate. "
                        "Use pediatric growth charts and specialist judgement.")
    if p.get("pregnant_or_breastfeeding"):
        warnings.append("Pregnancy/breastfeeding: energy needs differ. Adjust targets manually.")

    h_m = height / 100
    bmi = weight / h_m ** 2
    healthy_min, healthy_max = 18.5 * h_m ** 2, 24.9 * h_m ** 2

    if body_fat:
        lean = weight * (1 - body_fat / 100)
        bmr = 370 + 21.6 * lean
        bmr_formula = "Katch-McArdle"
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex == "male" else -161)
        bmr_formula = "Mifflin-St Jeor"

    factor = ACTIVITY[activity][0]
    tdee = bmr * factor

    daily_delta = rate * KCAL_PER_KG / 7
    if goal == "lose":
        max_deficit = max(tdee * MAX_DEFICIT_PCT, 550)  # always allow 0.5 kg/week
        if daily_delta > max_deficit:
            daily_delta = max_deficit
            warnings.append(f"Requested rate was too aggressive; deficit capped at {round(max_deficit)} kcal/day.")
        target = tdee - daily_delta
    elif goal == "gain":
        target = tdee + daily_delta
    else:
        target = tdee

    floor = max(1500 if sex == "male" else 1200, bmr)
    if goal == "lose" and target < floor:
        target = floor
        warnings.append(f"Calories raised to the safety floor of {round(floor)} kcal (not below BMR / "
                        f"{1500 if sex == 'male' else 1200} kcal).")
    if goal == "lose" and bmi < 18.5:
        warnings.append("BMI is under 18.5: weight loss is not recommended.")

    # Protein reference weight: adjusted weight for BMI >= 30
    ref_weight = weight
    if bmi >= 30:
        ideal = 25 * h_m ** 2
        ref_weight = ideal + 0.25 * (weight - ideal)
        warnings.append(f"BMI >= 30: protein based on adjusted weight ({ref_weight:.1f} kg).")

    protein_per_kg = _num(p, "protein_g_per_kg", 0.6, 3.0, required=False,
                          default=DEFAULT_PROTEIN_G_PER_KG[goal])
    fat_pct = _num(p, "fat_pct", 15, 45, required=False, default=28) / 100

    target = round(target / 10) * 10
    protein_g = round(ref_weight * protein_per_kg)
    fat_g = round(target * fat_pct / 9)
    carbs_g = round((target - protein_g * 4 - fat_g * 9) / 4)
    if carbs_g < 100:
        warnings.append(f"Carbs are low ({carbs_g} g). Consider lowering the protein or fat settings.")
    carbs_g = max(carbs_g, 0)

    weekly_change = None
    if goal != "maintain":
        weekly_change = round((target - tdee) * 7 / KCAL_PER_KG, 2)

    return {
        "bmi": round(bmi, 1),
        "bmi_category": _bmi_category(bmi),
        "healthy_weight_range_kg": [round(healthy_min, 1), round(healthy_max, 1)],
        "bmr": round(bmr),
        "bmr_formula": bmr_formula,
        "activity_factor": factor,
        "tdee": round(tdee),
        "goal": goal,
        "expected_weekly_change_kg": weekly_change,
        "targets": {
            "calories": target,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "fiber_g": round(target / 1000 * 14),
        },
        "macro_split_pct": {
            "protein": round(protein_g * 4 / target * 100),
            "carbs": round(carbs_g * 4 / target * 100),
            "fat": round(fat_g * 9 / target * 100),
        },
        "water_l": round(weight * 0.035, 1),
        "warnings": warnings,
    }


def _bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"
