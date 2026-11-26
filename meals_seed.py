"""Starter meal library: Lebanese / Mediterranean meals loaded into an empty database.

The specialist edits, deletes or adds meals on the Meal library page; this file is only used
the first time the app starts (or when the library is empty).

Each food has an English and an Arabic name, the USDA search term used for its nutrients,
and optionally a household unit (name + grams per unit) so plans can say "2 eggs" instead of "100 g".
"""

# key: (English name, Arabic name, USDA search term, unit EN, unit AR, grams per unit)
FOODS = {
    "pita":        ("Pita bread", "خبز عربي", "pita bread", "small pita", "رغيف صغير", 60),
    "brown_bread": ("Whole-wheat bread", "خبز أسمر", "bread whole-wheat commercially prepared", "slice", "شريحة", 30),
    "labneh":      ("Labneh", "لبنة", "yogurt greek plain whole milk", "tbsp", "ملعقة كبيرة", 20),
    "cucumber":    ("Cucumber", "خيار", "cucumber raw", "cucumber", "خيارة", 100),
    "tomato":      ("Tomato", "بندورة", "tomatoes red ripe raw", "medium tomato", "حبة بندورة", 120),
    "olive_oil":   ("Olive oil", "زيت زيتون", "olive oil", "tsp", "ملعقة صغيرة", 5),
    "mint":        ("Fresh mint", "نعناع", "spearmint fresh", None, None, None),
    "egg_scr":     ("Scrambled eggs", "بيض مخفوق", "egg whole cooked scrambled", "egg", "بيضة", 50),
    "egg_boiled":  ("Boiled egg", "بيض مسلوق", "egg whole cooked hard-boiled", "egg", "بيضة", 50),
    "egg_omelet":  ("Omelette eggs", "بيض عجة", "egg whole cooked omelet", "egg", "بيضة", 50),
    "fava":        ("Fava beans (foul), cooked", "فول مدمس", "broadbeans fava mature seeds cooked boiled", "cup", "كوب", 170),
    "lemon":       ("Lemon juice", "عصير حامض", "lemon juice raw", "tbsp", "ملعقة كبيرة", 15),
    "garlic":      ("Garlic", "ثوم", "garlic raw", "clove", "فص", 3),
    "oats":        ("Rolled oats", "شوفان", "oats rolled dry", "tbsp", "ملعقة كبيرة", 10),
    "milk_low":    ("Low-fat milk", "حليب قليل الدسم", "milk lowfat fluid 1% milkfat", "cup", "كوب", 245),
    "banana":      ("Banana", "موز", "banana raw", "banana", "موزة", 120),
    "cinnamon":    ("Cinnamon", "قرفة", "spices cinnamon ground", None, None, None),
    "thyme":       ("Za'atar (dried thyme)", "زعتر", "spices thyme dried", "tsp", "ملعقة صغيرة", 1.5),
    "sesame":      ("Sesame seeds", "سمسم", "sesame seeds whole dried", "tsp", "ملعقة صغيرة", 3),
    "feta":        ("White cheese (feta)", "جبنة بيضاء", "feta cheese", None, None, None),
    "olives":      ("Olives", "زيتون", "olives ripe canned", "olive", "حبة زيتون", 4),
    "greek_yog":   ("Greek yogurt, low-fat", "لبن يوناني قليل الدسم", "yogurt greek plain nonfat", "cup", "كوب", 225),
    "strawberry":  ("Strawberries", "فريز", "strawberries raw", "cup", "كوب", 150),
    "walnuts":     ("Walnuts", "جوز", "walnuts", "walnut half", "نصف جوزة", 2),
    "honey":       ("Honey", "عسل", "honey", "tsp", "ملعقة صغيرة", 7),
    "onion":       ("Onion", "بصل", "onions raw", None, None, None),
    "red_pepper":  ("Red bell pepper", "فليفلة حمراء", "peppers sweet red raw", None, None, None),
    "tomato_can":  ("Tomatoes, canned", "بندورة معلبة", "tomatoes red ripe canned", None, None, None),
    "pb":          ("Peanut butter", "زبدة الفستق", "peanut butter smooth", "tbsp", "ملعقة كبيرة", 16),
    "apple":       ("Apple", "تفاح", "apples raw with skin", "apple", "تفاحة", 180),
    "almonds":     ("Almonds", "لوز", "almonds", "almond", "حبة لوز", 1.2),
    "hummus":      ("Hummus", "حمص بطحينة", "hummus", "tbsp", "ملعقة كبيرة", 15),
    "carrot":      ("Carrot", "جزر", "carrots raw", "carrot", "جزرة", 60),
    "dates":       ("Dates", "تمر", "dates deglet noor", "date", "تمرة", 7),
    "orange":      ("Orange", "برتقال", "oranges raw", "orange", "برتقالة", 130),
    "cottage":     ("Cottage cheese, low-fat", "جبنة قريش", "cheese cottage lowfat 2% milkfat", "tbsp", "ملعقة كبيرة", 30),
    "pear":        ("Pear", "إجاص", "pears raw", "pear", "إجاصة", 180),
    "pistachio":   ("Pistachios", "فستق حلبي", "pistachio nuts raw", "pistachio", "حبة فستق", 0.7),
    "popcorn":     ("Air-popped popcorn", "فوشار", "popcorn air-popped", "cup", "كوب", 8),
    "chicken":     ("Grilled chicken breast", "صدر دجاج مشوي", "chicken breast cooked roasted", None, None, None),
    "rice":        ("White rice, cooked", "أرز أبيض مطبوخ", "rice white cooked", "cup", "كوب", 160),
    "lettuce":     ("Lettuce", "خس", "lettuce romaine raw", None, None, None),
    "lentils":     ("Lentils, cooked", "عدس مطبوخ", "lentils cooked", "cup", "كوب", 200),
    "bulgur":      ("Bulgur, cooked", "برغل مطبوخ", "bulgur cooked", "cup", "كوب", 180),
    "cabbage":     ("Cabbage", "ملفوف", "cabbage raw", None, None, None),
    "fish":        ("White fish fillet, baked", "فيليه سمك مشوي", "fish tilapia cooked dry heat", None, None, None),
    "potato":      ("Potato, boiled", "بطاطا مسلوقة", "potatoes boiled cooked without skin flesh", "medium potato", "حبة بطاطا", 150),
    "beef":        ("Lean ground beef, cooked", "لحمة مفرومة مطبوخة", "beef ground 90% lean cooked", None, None, None),
    "parsley":     ("Parsley", "بقدونس", "parsley fresh", None, None, None),
    "peas":        ("Green peas, cooked", "بازيلا مطبوخة", "peas green frozen cooked boiled", "cup", "كوب", 160),
    "carrot_ck":   ("Carrots, cooked", "جزر مطبوخ", "carrots cooked boiled", None, None, None),
    "white_beans": ("White beans, cooked", "فاصوليا بيضاء مطبوخة", "beans white mature seeds cooked boiled", "cup", "كوب", 180),
    "green_beans": ("Green beans, cooked", "لوبية مطبوخة", "beans snap green cooked boiled", "cup", "كوب", 125),
    "yogurt":      ("Plain yogurt", "لبن", "yogurt plain whole milk", "cup", "كوب", 245),
    "tuna":        ("Tuna in water, drained", "تونة بالماء", "tuna canned in water", "can", "علبة", 120),
    "chickpeas":   ("Chickpeas, cooked", "حمص حب مطبوخ", "chickpeas cooked", "cup", "كوب", 165),
    "pickles":     ("Pickles", "كبيس", "pickles cucumber dill", None, None, None),
    "spinach_ck":  ("Spinach, cooked", "سبانخ مطبوخة", "spinach cooked boiled", None, None, None),
    "spinach":     ("Spinach, raw", "سبانخ", "spinach raw", None, None, None),
    "salmon":      ("Salmon, baked", "سلمون مشوي", "salmon atlantic farmed cooked dry heat", None, None, None),
    "quinoa":      ("Quinoa, cooked", "كينوا مطبوخة", "quinoa cooked", "cup", "كوب", 185),
    "broccoli":    ("Broccoli, cooked", "بروكلي مطبوخ", "broccoli cooked boiled", None, None, None),
    "radish":      ("Radishes", "فجل", "radishes raw", None, None, None),
    "zucchini":    ("Zucchini, cooked", "كوسا مطبوخة", "squash summer zucchini cooked boiled", None, None, None),
    "eggplant":    ("Eggplant, cooked", "باذنجان مطبوخ", "eggplant cooked boiled", None, None, None),
}

# (English name, Arabic name, slots, tags, [(food key, grams), ...])
# slots: breakfast, snack, lunch, dinner
# tags the planner understands: vegetarian, vegan, high_sodium, high_sugar
MEALS = [
    # ---------- breakfast ----------
    ("Labneh sandwich with cucumber & mint", "سندويش لبنة مع خيار ونعناع", ["breakfast", "dinner"], ["vegetarian"],
     [("pita", 60), ("labneh", 60), ("cucumber", 80), ("mint", 3), ("olive_oil", 5)]),
    ("Eggs with tomatoes", "بيض بالبندورة", ["breakfast", "dinner"], ["vegetarian"],
     [("egg_scr", 100), ("tomato", 120), ("olive_oil", 5), ("pita", 30)]),
    ("Foul medammas", "فول مدمس", ["breakfast"], ["vegan"],
     [("fava", 170), ("lemon", 15), ("garlic", 3), ("olive_oil", 10), ("tomato", 60), ("pita", 30)]),
    ("Oatmeal with banana & cinnamon", "شوفان مع موز وقرفة", ["breakfast"], ["vegetarian"],
     [("oats", 40), ("milk_low", 200), ("banana", 60), ("cinnamon", 1)]),
    ("Za'atar manoushe with vegetables", "منقوشة زعتر مع خضار", ["breakfast"], ["vegan"],
     [("pita", 60), ("thyme", 3), ("sesame", 3), ("olive_oil", 10), ("tomato", 80), ("cucumber", 80), ("mint", 3)]),
    ("White cheese plate with vegetables", "صحن جبنة بيضاء مع خضار", ["breakfast", "dinner"], ["vegetarian", "high_sodium"],
     [("feta", 40), ("tomato", 80), ("cucumber", 80), ("olives", 16), ("pita", 30)]),
    ("Greek yogurt with strawberries & walnuts", "لبن يوناني مع فريز وجوز", ["breakfast", "snack"], ["vegetarian"],
     [("greek_yog", 170), ("strawberry", 100), ("walnuts", 10), ("honey", 5)]),
    ("Shakshuka", "شكشوكة", ["breakfast", "dinner"], ["vegetarian"],
     [("egg_scr", 100), ("tomato_can", 150), ("onion", 40), ("red_pepper", 50), ("olive_oil", 7), ("pita", 30)]),
    ("Peanut butter toast with banana", "توست بزبدة الفستق مع موز", ["breakfast"], ["vegan"],
     [("brown_bread", 60), ("pb", 16), ("banana", 60)]),

    # ---------- snacks ----------
    ("Apple with almonds", "تفاحة مع لوز", ["snack"], ["vegan"], [("apple", 150), ("almonds", 15)]),
    ("Hummus with carrot sticks", "حمص مع أصابع جزر", ["snack"], ["vegan"], [("hummus", 60), ("carrot", 100)]),
    ("Dates with milk", "تمر مع حليب", ["snack"], ["vegetarian", "high_sugar"], [("dates", 21), ("milk_low", 200)]),
    ("Orange with walnuts", "برتقالة مع جوز", ["snack"], ["vegan"], [("orange", 130), ("walnuts", 10)]),
    ("Cottage cheese with cucumber", "جبنة قريش مع خيار", ["snack"], ["vegetarian"], [("cottage", 100), ("cucumber", 100)]),
    ("Pear with pistachios", "إجاصة مع فستق حلبي", ["snack"], ["vegan"], [("pear", 180), ("pistachio", 15)]),
    ("Popcorn", "فوشار", ["snack"], ["vegan"], [("popcorn", 24)]),
    ("Banana", "موزة", ["snack"], ["vegan"], [("banana", 120)]),

    # ---------- lunch ----------
    ("Grilled chicken with rice & salad", "دجاج مشوي مع أرز وسلطة", ["lunch"], [],
     [("chicken", 130), ("rice", 150), ("lettuce", 60), ("tomato", 60), ("cucumber", 60), ("olive_oil", 7), ("lemon", 10)]),
    ("Mjadra with cabbage salad", "مجدرة مع سلطة ملفوف", ["lunch"], ["vegan"],
     [("lentils", 150), ("bulgur", 100), ("onion", 50), ("olive_oil", 12), ("cabbage", 80), ("tomato", 50), ("lemon", 10)]),
    ("Baked fish with potatoes & salad", "سمك بالفرن مع بطاطا وسلطة", ["lunch", "dinner"], [],
     [("fish", 150), ("potato", 150), ("olive_oil", 10), ("garlic", 3), ("lettuce", 50), ("tomato", 50), ("lemon", 10)]),
    ("Kafta with rice & tomatoes", "كفتة مع أرز وبندورة", ["lunch"], [],
     [("beef", 120), ("onion", 30), ("parsley", 10), ("rice", 120), ("tomato", 80)]),
    ("Pea & carrot stew with chicken and rice", "يخنة بازيلا وجزر مع دجاج وأرز", ["lunch"], [],
     [("chicken", 100), ("peas", 100), ("carrot_ck", 60), ("tomato_can", 60), ("rice", 120), ("olive_oil", 5)]),
    ("White bean stew with rice", "فاصوليا بيضاء مع أرز", ["lunch"], ["vegan"],
     [("white_beans", 150), ("tomato_can", 100), ("onion", 30), ("olive_oil", 8), ("rice", 120)]),
    ("Green beans in olive oil with yogurt", "لوبية بزيت مع لبن", ["lunch", "dinner"], ["vegetarian"],
     [("green_beans", 200), ("tomato_can", 100), ("onion", 40), ("olive_oil", 12), ("pita", 45), ("yogurt", 100)]),
    ("Tuna & chickpea salad", "سلطة تونة وحمص", ["lunch", "dinner"], [],
     [("tuna", 120), ("chickpeas", 80), ("lettuce", 60), ("tomato", 60), ("cucumber", 60), ("olive_oil", 10), ("lemon", 10)]),
    ("Homemade chicken shawarma plate", "صحن شاورما دجاج بيتي", ["lunch"], ["high_sodium"],
     [("chicken", 130), ("pita", 60), ("yogurt", 50), ("garlic", 3), ("lettuce", 40), ("tomato", 50), ("pickles", 20)]),
    ("Spinach stew with meat and rice", "سبانخ باللحمة مع أرز", ["lunch"], [],
     [("beef", 90), ("spinach_ck", 150), ("onion", 30), ("olive_oil", 5), ("rice", 130), ("lemon", 10)]),
    ("Salmon with quinoa & broccoli", "سلمون مع كينوا وبروكلي", ["lunch", "dinner"], [],
     [("salmon", 130), ("quinoa", 150), ("broccoli", 100), ("olive_oil", 5), ("lemon", 10)]),

    # ---------- dinner ----------
    ("Fattoush with grilled chicken", "فتوش مع دجاج مشوي", ["dinner"], [],
     [("lettuce", 80), ("tomato", 80), ("cucumber", 80), ("radish", 30), ("pita", 30), ("olive_oil", 10), ("lemon", 15), ("chicken", 100)]),
    ("Tabbouleh with labneh", "تبولة مع لبنة", ["dinner"], ["vegetarian"],
     [("parsley", 80), ("bulgur", 50), ("tomato", 80), ("onion", 20), ("olive_oil", 10), ("lemon", 15), ("labneh", 100)]),
    ("Lentil soup", "شوربة عدس", ["dinner", "lunch"], ["vegan"],
     [("lentils", 200), ("carrot_ck", 40), ("onion", 30), ("olive_oil", 5), ("lemon", 10), ("pita", 30)]),
    ("Vegetable omelette", "عجة بالخضار", ["dinner", "breakfast"], ["vegetarian"],
     [("egg_omelet", 100), ("spinach", 40), ("onion", 20), ("tomato", 50), ("olive_oil", 5), ("pita", 30)]),
    ("Baked chicken with zucchini & potato", "دجاج بالفرن مع كوسا وبطاطا", ["dinner", "lunch"], [],
     [("chicken", 120), ("zucchini", 150), ("potato", 100), ("olive_oil", 8), ("garlic", 3)]),
    ("Hummus plate with vegetables", "صحن حمص مع خضار", ["dinner"], ["vegan"],
     [("hummus", 100), ("pita", 45), ("tomato", 60), ("cucumber", 60), ("olives", 12)]),
    ("Yogurt & cucumber salad with boiled egg", "لبن بخيار مع بيضة مسلوقة", ["dinner"], ["vegetarian"],
     [("yogurt", 200), ("cucumber", 100), ("mint", 3), ("garlic", 2), ("egg_boiled", 50), ("pita", 30)]),
    ("Eggplant & chickpea stew (maghmour)", "مغمور باذنجان وحمص", ["dinner", "lunch"], ["vegan"],
     [("eggplant", 200), ("chickpeas", 80), ("tomato_can", 100), ("onion", 30), ("olive_oil", 10), ("pita", 30)]),
]


def item(key: str, grams: float) -> dict:
    en, ar, term, unit, unit_ar, unit_g = FOODS[key]
    return {"food": en, "food_ar": ar, "search_term": term, "grams": grams,
            "unit": unit, "unit_ar": unit_ar, "unit_g": unit_g}


def meals() -> list[dict]:
    return [{"name": en, "name_ar": ar, "slots": slots, "tags": tags,
             "items": [item(k, g) for k, g in items]}
            for en, ar, slots, tags, items in MEALS]
