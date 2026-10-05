"""
Nutrition Manager Module for IronPulse Fitness Tracker
Handles food library database, food search, macro target calculations from profile,
and daily meal logging across Breakfast, Lunch, Dinner, and Snacks.
"""

from datetime import date
import sqlite3
import re

# Default nutritional food database (per standard serving size)
# Specifically includes: Eggs, Milk, Curd, Paneer, Soy chunks, Dal, Peanuts, Oats, Rice, Chicken, Fish + staples
COMMON_FOODS = [
    {
        "name": "Eggs (Boiled / Whole)",
        "category": "Dairy & Eggs",
        "serving_size": "2 large whole eggs (100g)",
        "serving_unit": "servings (2 eggs)",
        "calories": 143,
        "protein_g": 12.6,
        "carbs_g": 0.8,
        "fats_g": 9.5,
        "is_muscle_building": 1,
        "description": "Gold standard biological value protein rich in choline and essential micronutrients."
    },
    {
        "name": "Egg Whites",
        "category": "Dairy & Eggs",
        "serving_size": "4 egg whites (132g)",
        "serving_unit": "servings (4 whites)",
        "calories": 68,
        "protein_g": 14.4,
        "carbs_g": 0.9,
        "fats_g": 0.2,
        "is_muscle_building": 1,
        "description": "Pure lean bioavailable protein with zero fat and minimal calories."
    },
    {
        "name": "Cow Milk (Toned / Low Fat)",
        "category": "Dairy & Eggs",
        "serving_size": "1 glass (250ml)",
        "serving_unit": "glasses (250ml)",
        "calories": 150,
        "protein_g": 8.5,
        "carbs_g": 12.0,
        "fats_g": 7.5,
        "is_muscle_building": 1,
        "description": "Natural blend of whey and slow-digesting micellar casein plus calcium."
    },
    {
        "name": "Curd / Dahi (Greek / Plain)",
        "category": "Dairy & Eggs",
        "serving_size": "1 cup (200g)",
        "serving_unit": "cups (200g)",
        "calories": 130,
        "protein_g": 12.0,
        "carbs_g": 9.0,
        "fats_g": 4.5,
        "is_muscle_building": 1,
        "description": "Probiotic-rich gut booster with dense dairy protein matrix."
    },
    {
        "name": "Paneer (Cottage Cheese)",
        "category": "Dairy & Eggs",
        "serving_size": "100g",
        "serving_unit": "100g",
        "calories": 265,
        "protein_g": 18.5,
        "carbs_g": 3.5,
        "fats_g": 20.0,
        "is_muscle_building": 1,
        "description": "Classic vegetarian muscle builder rich in slow-release casein protein."
    },
    {
        "name": "Low-Fat Paneer",
        "category": "Dairy & Eggs",
        "serving_size": "100g",
        "serving_unit": "100g",
        "calories": 175,
        "protein_g": 25.0,
        "carbs_g": 4.0,
        "fats_g": 6.5,
        "is_muscle_building": 1,
        "description": "High-density protein paneer with reduced saturated fat for clean bulking/cutting."
    },
    {
        "name": "Soy Chunks (Nutrela / Textured Soy)",
        "category": "Plant Protein",
        "serving_size": "50g dry (yields ~150g cooked)",
        "serving_unit": "servings (50g dry)",
        "calories": 173,
        "protein_g": 26.0,
        "carbs_g": 16.5,
        "fats_g": 0.5,
        "is_muscle_building": 1,
        "description": "Massive 52% protein density plant powerhouse with complete amino acid spectrum."
    },
    {
        "name": "Dal (Cooked Yellow Toor / Moong)",
        "category": "Legumes & Pulses",
        "serving_size": "1 large bowl (200g cooked)",
        "serving_unit": "bowls (200g)",
        "calories": 180,
        "protein_g": 9.5,
        "carbs_g": 28.0,
        "fats_g": 3.0,
        "is_muscle_building": 1,
        "description": "Essential staple providing complex carbohydrates, dietary fiber, and plant protein."
    },
    {
        "name": "Peanuts (Roasted / Unsalted)",
        "category": "Nuts & Seeds",
        "serving_size": "1 handful (30g)",
        "serving_unit": "handfuls (30g)",
        "calories": 175,
        "protein_g": 7.8,
        "carbs_g": 4.8,
        "fats_g": 14.8,
        "is_muscle_building": 1,
        "description": "Calorie-dense healthy monounsaturated fats and arginine for sustained energy."
    },
    {
        "name": "Peanut Butter (100% Natural)",
        "category": "Nuts & Seeds",
        "serving_size": "2 tablespoons (32g)",
        "serving_unit": "tbsp (32g)",
        "calories": 190,
        "protein_g": 8.0,
        "carbs_g": 6.0,
        "fats_g": 16.0,
        "is_muscle_building": 1,
        "description": "Ideal caloric surplus driver with clean unsaturated fats and zero added sugar."
    },
    {
        "name": "Rolled Oats",
        "category": "Grains & Carbs",
        "serving_size": "1 bowl (60g dry)",
        "serving_unit": "servings (60g dry)",
        "calories": 230,
        "protein_g": 8.5,
        "carbs_g": 40.0,
        "fats_g": 4.0,
        "is_muscle_building": 1,
        "description": "Low glycemic complex carbs providing sustained intramuscular glycogen loading."
    },
    {
        "name": "White Basmati Rice (Cooked)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium bowl (150g cooked)",
        "serving_unit": "bowls (150g)",
        "calories": 195,
        "protein_g": 4.0,
        "carbs_g": 43.0,
        "fats_g": 0.5,
        "is_muscle_building": 1,
        "description": "Easy-to-digest post-workout carbohydrate source for rapid glycogen refill."
    },
    {
        "name": "Brown Jasmine Rice (Cooked)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium bowl (150g cooked)",
        "serving_unit": "bowls (150g)",
        "calories": 185,
        "protein_g": 4.5,
        "carbs_g": 38.0,
        "fats_g": 1.5,
        "is_muscle_building": 1,
        "description": "Whole grain with intact bran layer, magnesium, and dietary fiber."
    },
    {
        "name": "Chicken Breast (Boneless / Skinless Grilled)",
        "category": "Poultry & Meat",
        "serving_size": "150g cooked",
        "serving_unit": "150g",
        "calories": 240,
        "protein_g": 46.5,
        "carbs_g": 0.0,
        "fats_g": 4.8,
        "is_muscle_building": 1,
        "description": "Ultra-lean high leucine bodybuilding staple for maximum muscle protein synthesis."
    },
    {
        "name": "Fish (Salmon Fillet Grilled)",
        "category": "Seafood",
        "serving_size": "150g fillet",
        "serving_unit": "150g",
        "calories": 310,
        "protein_g": 34.0,
        "carbs_g": 0.0,
        "fats_g": 18.0,
        "is_muscle_building": 1,
        "description": "Rich in anti-inflammatory Omega-3 fatty acids (EPA/DHA) and high biological value protein."
    },
    {
        "name": "Fish (White Fish / Tilapia / Rohu Grilled)",
        "category": "Seafood",
        "serving_size": "150g fillet",
        "serving_unit": "150g",
        "calories": 145,
        "protein_g": 31.0,
        "carbs_g": 0.0,
        "fats_g": 2.2,
        "is_muscle_building": 1,
        "description": "Ultra low-calorie lean white fish, great for fat loss cutting phases."
    },
    {
        "name": "Whey Protein Powder (100% Isolate/Concentrate)",
        "category": "Supplements",
        "serving_size": "1 scoop (32g)",
        "serving_unit": "scoops (32g)",
        "calories": 125,
        "protein_g": 25.0,
        "carbs_g": 2.5,
        "fats_g": 1.5,
        "is_muscle_building": 1,
        "description": "Fast-digesting whey delivering 3g+ leucine straight into the bloodstream post-workout."
    },
    {
        "name": "Banana (Ripe)",
        "category": "Fruits",
        "serving_size": "1 medium banana (118g)",
        "serving_unit": "medium bananas",
        "calories": 105,
        "protein_g": 1.3,
        "carbs_g": 27.0,
        "fats_g": 0.3,
        "is_muscle_building": 1,
        "description": "High potassium, fast digesting simple carbs perfect for pre or post workout energy."
    },
    {
        "name": "Sweet Potato (Baked / Boiled)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium potato (150g)",
        "serving_unit": "medium potatoes (150g)",
        "calories": 135,
        "protein_g": 2.8,
        "carbs_g": 31.0,
        "fats_g": 0.2,
        "is_muscle_building": 1,
        "description": "Complex carbohydrate packed with beta-carotene, Vitamin A, and potassium."
    },
    {
        "name": "Almonds (Raw)",
        "category": "Nuts & Seeds",
        "serving_size": "20 kernels (25g)",
        "serving_unit": "servings (25g)",
        "calories": 145,
        "protein_g": 5.5,
        "carbs_g": 5.0,
        "fats_g": 12.5,
        "is_muscle_building": 0,
        "description": "Vitamin E rich healthy fats supporting cellular membranes and hormonal recovery."
    },
    {
        "name": "Chickpeas / Chana (Cooked)",
        "category": "Legumes & Pulses",
        "serving_size": "1 cup (164g cooked)",
        "serving_unit": "cups (164g)",
        "calories": 269,
        "protein_g": 14.5,
        "carbs_g": 45.0,
        "fats_g": 4.2,
        "is_muscle_building": 1,
        "description": "High fiber legume with steady energy release and solid plant protein."
    },
    {
        "name": "Roti / Chapati (Whole Wheat)",
        "category": "Grains & Carbs",
        "serving_size": "2 medium rotis (70g)",
        "serving_unit": "servings (2 rotis)",
        "calories": 180,
        "protein_g": 6.2,
        "carbs_g": 36.0,
        "fats_g": 1.5,
        "is_muscle_building": 0,
        "description": "Classic Indian whole grain flatbread loaded with complex carbohydrates."
    },
    {
        "name": "Dosa (Crispy Plain)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium dosa (100g)",
        "serving_unit": "dosa (100g)",
        "calories": 168,
        "protein_g": 3.9,
        "carbs_g": 29.0,
        "fats_g": 4.2,
        "is_muscle_building": 1,
        "description": "Fermented lentil and rice crepe offering clean carbohydrates and gut probiotics."
    },
    {
        "name": "Mixed Vegetables (Steamed / Sautéed)",
        "category": "Vegetables",
        "serving_size": "1 cup (150g)",
        "serving_unit": "cups (150g)",
        "calories": 75,
        "protein_g": 3.0,
        "carbs_g": 14.0,
        "fats_g": 1.5,
        "is_muscle_building": 1,
        "description": "Micronutrient-dense blend of carrots, green beans, peas, and florets."
    },
    {
        "name": "White Rice (Cooked)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium bowl (150g cooked)",
        "serving_unit": "bowls (150g)",
        "calories": 195,
        "protein_g": 4.0,
        "carbs_g": 43.0,
        "fats_g": 0.5,
        "is_muscle_building": 1,
        "description": "Easily digestible steamed white rice for intramuscular glycogen replenishment."
    },
    {
        "name": "Sambar (Lentil & Vegetable Stew)",
        "category": "Legumes & Pulses",
        "serving_size": "1 medium bowl (200ml)",
        "serving_unit": "bowls (200ml)",
        "calories": 130,
        "protein_g": 4.5,
        "carbs_g": 22.0,
        "fats_g": 2.5,
        "is_muscle_building": 1,
        "description": "Traditional South Indian spiced lentil and vegetable stew."
    },
    {
        "name": "Idli (Steamed Rice Cakes)",
        "category": "Grains & Carbs",
        "serving_size": "2 medium idlis (100g)",
        "serving_unit": "servings (2 idlis)",
        "calories": 130,
        "protein_g": 4.0,
        "carbs_g": 26.0,
        "fats_g": 0.6,
        "is_muscle_building": 1,
        "description": "Steamed fermented rice and urad dal cakes, light and gut-friendly."
    },
    {
        "name": "Parotta (Malabar Layered Flatbread)",
        "category": "Grains & Carbs",
        "serving_size": "1 parotta (80g)",
        "serving_unit": "parottas (80g)",
        "calories": 260,
        "protein_g": 5.5,
        "carbs_g": 38.0,
        "fats_g": 9.5,
        "is_muscle_building": 0,
        "description": "Flaky layered South Indian flatbread cooked with oil."
    },
    {
        "name": "Bread (Whole Wheat / Multigrain)",
        "category": "Grains & Carbs",
        "serving_size": "2 slices (60g)",
        "serving_unit": "slices (2 slices)",
        "calories": 140,
        "protein_g": 6.0,
        "carbs_g": 24.0,
        "fats_g": 1.8,
        "is_muscle_building": 1,
        "description": "Whole wheat fiber bread for quick post-workout toast."
    },
    {
        "name": "Noodles (Stir-Fried Veg / Egg)",
        "category": "Grains & Carbs",
        "serving_size": "1 medium bowl (180g)",
        "serving_unit": "bowls (180g)",
        "calories": 220,
        "protein_g": 6.0,
        "carbs_g": 39.0,
        "fats_g": 4.5,
        "is_muscle_building": 0,
        "description": "Stir-fried noodles prepared with vegetables and light seasoning."
    },
    {
        "name": "Pasta (Whole Wheat / Penne Cooked)",
        "category": "Grains & Carbs",
        "serving_size": "1 cup cooked (140g)",
        "serving_unit": "cups (140g)",
        "calories": 210,
        "protein_g": 7.5,
        "carbs_g": 42.0,
        "fats_g": 1.5,
        "is_muscle_building": 1,
        "description": "Durum wheat semolina pasta for sustained intramuscular energy."
    },
    {
        "name": "Biryani (Chicken / Vegetable Dum)",
        "category": "Poultry & Meat",
        "serving_size": "1 plate (250g)",
        "serving_unit": "plates (250g)",
        "calories": 380,
        "protein_g": 18.0,
        "carbs_g": 50.0,
        "fats_g": 11.5,
        "is_muscle_building": 1,
        "description": "Fragrant basmati rice cooked with spiced chicken, herbs, and saffron."
    },
    {
        "name": "Mixed Fresh Fruits (Salad / Bowl)",
        "category": "Fruits",
        "serving_size": "1 medium bowl (180g)",
        "serving_unit": "bowls (180g)",
        "calories": 95,
        "protein_g": 1.2,
        "carbs_g": 23.0,
        "fats_g": 0.4,
        "is_muscle_building": 1,
        "description": "Vibrant blend of fresh fruits rich in antioxidants and vitamins."
    }
]

def init_food_library(conn):
    """
    Ensure food_items table exists and seed default muscle-building foods.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            serving_size TEXT NOT NULL,
            serving_unit TEXT NOT NULL,
            calories INTEGER NOT NULL,
            protein_g REAL DEFAULT 0,
            carbs_g REAL DEFAULT 0,
            fats_g REAL DEFAULT 0,
            is_muscle_building INTEGER DEFAULT 1,
            description TEXT
        )
    """)

    # Check if nutrition_logs has quantity and serving_unit columns, add if missing
    cursor.execute("PRAGMA table_info(nutrition_logs)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'quantity' not in columns:
        cursor.execute("ALTER TABLE nutrition_logs ADD COLUMN quantity REAL DEFAULT 1.0")
    if 'serving_unit' not in columns:
        cursor.execute("ALTER TABLE nutrition_logs ADD COLUMN serving_unit TEXT DEFAULT 'serving'")

    # Seed food library
    for food in COMMON_FOODS:
        cursor.execute("SELECT id FROM food_items WHERE name = ?", (food['name'],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO food_items (name, category, serving_size, serving_unit, calories, protein_g, carbs_g, fats_g, is_muscle_building, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                food['name'], food['category'], food['serving_size'], food['serving_unit'],
                food['calories'], food['protein_g'], food['carbs_g'], food['fats_g'],
                food['is_muscle_building'], food['description']
            ))

    conn.commit()

def search_foods(conn, query="", category=""):
    """
    Search foods in library by text query and optional category.
    Returns list of food dictionaries.
    """
    cursor = conn.cursor()
    sql = "SELECT * FROM food_items WHERE 1=1"
    params = []

    if query:
        sql += " AND (name LIKE ? OR category LIKE ? OR description LIKE ?)"
        q_wild = f"%{query.strip()}%"
        params.extend([q_wild, q_wild, q_wild])

    if category and category != 'All':
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY is_muscle_building DESC, name ASC"
    cursor.execute(sql, params)
    return [dict(r) for r in cursor.fetchall()]

def get_food_by_id(conn, food_id):
    """Fetch single food item by primary key."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food_items WHERE id = ?", (food_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

def get_daily_nutrition_summary(conn, user_id, date_str, user_profile):
    """
    Calculates detailed daily nutrition intake, grouped meals (Breakfast, Lunch, Dinner, Snack),
    total consumed, targets from profile, remaining calories, remaining protein, and macro percentages.
    """
    cursor = conn.cursor()

    # Fetch all logged meals for date
    cursor.execute("""
        SELECT * FROM nutrition_logs
        WHERE user_id = ? AND date = ?
        ORDER BY 
            CASE meal_type
                WHEN 'Breakfast' THEN 1
                WHEN 'Lunch' THEN 2
                WHEN 'Dinner' THEN 3
                WHEN 'Snack' THEN 4
                WHEN 'Post-Workout' THEN 5
                ELSE 6
            END, id ASC
    """, (user_id, date_str))
    all_meals = [dict(r) for r in cursor.fetchall()]

    # Group meals by standardized 4 categories: Breakfast, Lunch, Dinner, Snacks
    grouped_meals = {
        'Breakfast': [],
        'Lunch': [],
        'Dinner': [],
        'Snack': []
    }

    meal_subtotals = {
        'Breakfast': {'calories': 0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0},
        'Lunch': {'calories': 0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0},
        'Dinner': {'calories': 0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0},
        'Snack': {'calories': 0, 'protein': 0.0, 'carbs': 0.0, 'fats': 0.0}
    }

    total_calories = 0
    total_protein = 0.0
    total_carbs = 0.0
    total_fats = 0.0

    for m in all_meals:
        m_type = m['meal_type']
        # Map Post-Workout to Snack or keep clean
        target_group = 'Snack'
        if m_type in ['Breakfast', 'Lunch', 'Dinner']:
            target_group = m_type
        elif 'Snack' in m_type or 'Post' in m_type or 'Pre' in m_type:
            target_group = 'Snack'

        grouped_meals[target_group].append(m)

        cals = m.get('calories', 0)
        prot = m.get('protein_g', 0.0) or 0.0
        carbs = m.get('carbs_g', 0.0) or 0.0
        fats = m.get('fats_g', 0.0) or 0.0

        total_calories += cals
        total_protein += prot
        total_carbs += carbs
        total_fats += fats

        meal_subtotals[target_group]['calories'] += cals
        meal_subtotals[target_group]['protein'] += prot
        meal_subtotals[target_group]['carbs'] += carbs
        meal_subtotals[target_group]['fats'] += fats

    # Profile Targets
    profile_dict = dict(user_profile) if user_profile else {}
    cal_target = profile_dict.get('daily_calorie_target') or 2800
    protein_target = profile_dict.get('daily_protein_target') or 180
    carbs_target = profile_dict.get('daily_carbs_target') or 320
    fats_target = profile_dict.get('daily_fats_target') or 75

    # Remaining calculations
    remaining_calories = cal_target - total_calories
    remaining_protein = round(protein_target - total_protein, 1)
    remaining_carbs = round(carbs_target - total_carbs, 1)
    remaining_fats = round(fats_target - total_fats, 1)

    # Percentage caps for progress bars
    cal_pct = min(100, int((total_calories / cal_target) * 100)) if cal_target > 0 else 0
    protein_pct = min(100, int((total_protein / protein_target) * 100)) if protein_target > 0 else 0
    carbs_pct = min(100, int((total_carbs / carbs_target) * 100)) if carbs_target > 0 else 0
    fats_pct = min(100, int((total_fats / fats_target) * 100)) if fats_target > 0 else 0

    return {
        'all_meals': all_meals,
        'grouped_meals': grouped_meals,
        'meal_subtotals': meal_subtotals,
        'totals': {
            'calories': total_calories,
            'protein': round(total_protein, 1),
            'carbs': round(total_carbs, 1),
            'fats': round(total_fats, 1)
        },
        'targets': {
            'calories': cal_target,
            'protein': protein_target,
            'carbs': carbs_target,
            'fats': fats_target
        },
        'remaining': {
            'calories': remaining_calories,
            'protein': remaining_protein,
            'carbs': remaining_carbs,
            'fats': remaining_fats
        },
        'percentages': {
            'calories': cal_pct,
            'protein': protein_pct,
            'carbs': carbs_pct,
            'fats': fats_pct
        }
    }

# Standard fallback nutrition data for foods not directly in food_items table
STANDARD_FALLBACK_FOODS = {
    "apple": {"serving_size": "1 medium apple (182g)", "serving_unit": "apple", "calories": 95, "protein_g": 0.5, "carbs_g": 25.0, "fats_g": 0.3},
    "orange": {"serving_size": "1 medium orange (131g)", "serving_unit": "orange", "calories": 62, "protein_g": 1.2, "carbs_g": 15.4, "fats_g": 0.2},
    "pizza": {"serving_size": "1 slice (107g)", "serving_unit": "slice", "calories": 285, "protein_g": 12.0, "carbs_g": 36.0, "fats_g": 10.0},
    "burger": {"serving_size": "1 medium burger (150g)", "serving_unit": "burger", "calories": 354, "protein_g": 17.0, "carbs_g": 29.0, "fats_g": 17.0},
    "salad": {"serving_size": "1 bowl (180g)", "serving_unit": "bowl", "calories": 120, "protein_g": 3.0, "carbs_g": 10.0, "fats_g": 8.0},
    "pasta": {"serving_size": "1 cup cooked (140g)", "serving_unit": "cup", "calories": 210, "protein_g": 7.5, "carbs_g": 42.0, "fats_g": 1.5},
    "sandwich": {"serving_size": "1 sandwich (140g)", "serving_unit": "sandwich", "calories": 250, "protein_g": 12.0, "carbs_g": 28.0, "fats_g": 10.0},
    "idli": {"serving_size": "2 medium idlis (80g)", "serving_unit": "idlis", "calories": 130, "protein_g": 4.0, "carbs_g": 26.0, "fats_g": 0.6},
    "sambar": {"serving_size": "1 bowl (180g)", "serving_unit": "bowl", "calories": 115, "protein_g": 4.5, "carbs_g": 18.0, "fats_g": 2.5},
    "parotta": {"serving_size": "1 parotta (80g)", "serving_unit": "parotta", "calories": 260, "protein_g": 5.0, "carbs_g": 38.0, "fats_g": 9.5},
    "bread": {"serving_size": "2 slices (60g)", "serving_unit": "slices", "calories": 140, "protein_g": 6.0, "carbs_g": 24.0, "fats_g": 1.8},
    "noodles": {"serving_size": "1 bowl (180g)", "serving_unit": "bowl", "calories": 220, "protein_g": 6.0, "carbs_g": 39.0, "fats_g": 4.5},
    "curd": {"serving_size": "1 bowl (150g)", "serving_unit": "bowl", "calories": 100, "protein_g": 5.0, "carbs_g": 7.0, "fats_g": 5.5},
    "vada": {"serving_size": "1 medu vada (50g)", "serving_unit": "vada", "calories": 140, "protein_g": 3.5, "carbs_g": 15.0, "fats_g": 7.5},
    "samosa": {"serving_size": "1 piece (100g)", "serving_unit": "piece", "calories": 260, "protein_g": 3.5, "carbs_g": 32.0, "fats_g": 13.0},
    "biryani": {"serving_size": "1 plate (250g)", "serving_unit": "plate", "calories": 380, "protein_g": 18.0, "carbs_g": 50.0, "fats_g": 11.5},
    "tofu": {"serving_size": "100g", "serving_unit": "100g", "calories": 80, "protein_g": 9.0, "carbs_g": 2.0, "fats_g": 4.5},
    "soya chunks": {"serving_size": "50g dry", "serving_unit": "serving", "calories": 173, "protein_g": 26.0, "carbs_g": 16.5, "fats_g": 0.5},
}

CANONICAL_ALIASES = {
    # 1. Rice
    "rice": "White Basmati Rice (Cooked)",
    "white rice": "White Basmati Rice (Cooked)",
    "cooked rice": "White Basmati Rice (Cooked)",
    "steamed rice": "White Basmati Rice (Cooked)",
    "basmati rice": "White Basmati Rice (Cooked)",
    "brown rice": "Brown Jasmine Rice (Cooked)",
    # 2. Dal
    "dal": "Dal (Cooked Yellow Toor / Moong)",
    "cooked dal": "Dal (Cooked Yellow Toor / Moong)",
    "daal": "Dal (Cooked Yellow Toor / Moong)",
    "dhal": "Dal (Cooked Yellow Toor / Moong)",
    "yellow dal": "Dal (Cooked Yellow Toor / Moong)",
    "toor dal": "Dal (Cooked Yellow Toor / Moong)",
    "moong dal": "Dal (Cooked Yellow Toor / Moong)",
    "lentils": "Dal (Cooked Yellow Toor / Moong)",
    # 3. Sambar
    "sambar": "Sambar (Lentil & Vegetable Stew)",
    "sambhar": "Sambar (Lentil & Vegetable Stew)",
    "south indian sambar": "Sambar (Lentil & Vegetable Stew)",
    # 4. Idli
    "idli": "Idli (Steamed Rice Cakes)",
    "idly": "Idli (Steamed Rice Cakes)",
    "idlis": "Idli (Steamed Rice Cakes)",
    "steamed idli": "Idli (Steamed Rice Cakes)",
    # 5. Dosa
    "dosa": "Dosa (Crispy Plain)",
    "plain dosa": "Dosa (Crispy Plain)",
    "crispy dosa": "Dosa (Crispy Plain)",
    "masala dosa": "Dosa (Crispy Plain)",
    "ghee roast dosa": "Dosa (Crispy Plain)",
    # 6. Chapati / Roti
    "roti": "Roti / Chapati (Whole Wheat)",
    "chapati": "Roti / Chapati (Whole Wheat)",
    "chappathi": "Roti / Chapati (Whole Wheat)",
    "phulka": "Roti / Chapati (Whole Wheat)",
    "wheat roti": "Roti / Chapati (Whole Wheat)",
    # 7. Parotta / Paratha
    "parotta": "Parotta (Malabar Layered Flatbread)",
    "paratha": "Parotta (Malabar Layered Flatbread)",
    "malabar parotta": "Parotta (Malabar Layered Flatbread)",
    "kerala parotta": "Parotta (Malabar Layered Flatbread)",
    # 8. Chicken
    "chicken": "Chicken Breast (Boneless / Skinless Grilled)",
    "grilled chicken": "Chicken Breast (Boneless / Skinless Grilled)",
    "chicken breast": "Chicken Breast (Boneless / Skinless Grilled)",
    "cooked chicken": "Chicken Breast (Boneless / Skinless Grilled)",
    "roast chicken": "Chicken Breast (Boneless / Skinless Grilled)",
    # 9. Egg
    "egg": "Eggs (Boiled / Whole)",
    "eggs": "Eggs (Boiled / Whole)",
    "boiled egg": "Eggs (Boiled / Whole)",
    "boiled eggs": "Eggs (Boiled / Whole)",
    "whole egg": "Eggs (Boiled / Whole)",
    "egg white": "Egg Whites",
    "egg whites": "Egg Whites",
    # 10. Fish
    "fish": "Fish (Salmon Fillet Grilled)",
    "grilled fish": "Fish (Salmon Fillet Grilled)",
    "salmon": "Fish (Salmon Fillet Grilled)",
    "white fish": "Fish (White Fish / Tilapia / Rohu Grilled)",
    "tilapia": "Fish (White Fish / Tilapia / Rohu Grilled)",
    "fish fillet": "Fish (Salmon Fillet Grilled)",
    # 11. Paneer
    "paneer": "Paneer (Cottage Cheese)",
    "cottage cheese": "Paneer (Cottage Cheese)",
    "paneer curry": "Paneer (Cottage Cheese)",
    "paneer tikka": "Paneer (Cottage Cheese)",
    "low fat paneer": "Low-Fat Paneer",
    # 12. Curd / Yogurt
    "curd": "Curd / Dahi (Greek / Plain)",
    "dahi": "Curd / Dahi (Greek / Plain)",
    "yogurt": "Curd / Dahi (Greek / Plain)",
    "yoghurt": "Curd / Dahi (Greek / Plain)",
    "greek yogurt": "Curd / Dahi (Greek / Plain)",
    # 13. Vegetables
    "vegetable": "Mixed Vegetables (Steamed / Sautéed)",
    "vegetables": "Mixed Vegetables (Steamed / Sautéed)",
    "veggies": "Mixed Vegetables (Steamed / Sautéed)",
    "mixed veg": "Mixed Vegetables (Steamed / Sautéed)",
    "mixed vegetables": "Mixed Vegetables (Steamed / Sautéed)",
    "green vegetables": "Mixed Vegetables (Steamed / Sautéed)",
    "steamed vegetables": "Mixed Vegetables (Steamed / Sautéed)",
    # 14. Fruits
    "fruit": "Mixed Fresh Fruits (Salad / Bowl)",
    "fruits": "Mixed Fresh Fruits (Salad / Bowl)",
    "fresh fruits": "Mixed Fresh Fruits (Salad / Bowl)",
    "mixed fruits": "Mixed Fresh Fruits (Salad / Bowl)",
    "fruit salad": "Mixed Fresh Fruits (Salad / Bowl)",
    "fruit bowl": "Mixed Fresh Fruits (Salad / Bowl)",
    "apple": "Mixed Fresh Fruits (Salad / Bowl)",
    "banana": "Banana (Ripe)",
    # 15. Oats
    "oats": "Rolled Oats",
    "oatmeal": "Rolled Oats",
    "rolled oats": "Rolled Oats",
    "oat porridge": "Rolled Oats",
    # 16. Bread
    "bread": "Bread (Whole Wheat / Multigrain)",
    "toast": "Bread (Whole Wheat / Multigrain)",
    "brown bread": "Bread (Whole Wheat / Multigrain)",
    "white bread": "Bread (Whole Wheat / Multigrain)",
    "whole wheat bread": "Bread (Whole Wheat / Multigrain)",
    "multigrain bread": "Bread (Whole Wheat / Multigrain)",
    # 17. Noodles
    "noodles": "Noodles (Stir-Fried Veg / Egg)",
    "noodle": "Noodles (Stir-Fried Veg / Egg)",
    "fried noodles": "Noodles (Stir-Fried Veg / Egg)",
    "stir fried noodles": "Noodles (Stir-Fried Veg / Egg)",
    "chow mein": "Noodles (Stir-Fried Veg / Egg)",
    # 18. Pasta
    "pasta": "Pasta (Whole Wheat / Penne Cooked)",
    "penne": "Pasta (Whole Wheat / Penne Cooked)",
    "macaroni": "Pasta (Whole Wheat / Penne Cooked)",
    "spaghetti": "Pasta (Whole Wheat / Penne Cooked)",
    # 19. Soya Chunks
    "soya chunks": "Soy Chunks (Nutrela / Textured Soy)",
    "soy chunks": "Soy Chunks (Nutrela / Textured Soy)",
    "soya": "Soy Chunks (Nutrela / Textured Soy)",
    "soy": "Soy Chunks (Nutrela / Textured Soy)",
    "nutrela": "Soy Chunks (Nutrela / Textured Soy)",
    "textured vegetable protein": "Soy Chunks (Nutrela / Textured Soy)",
    # 20. Biryani
    "biryani": "Biryani (Chicken / Vegetable Dum)",
    "chicken biryani": "Biryani (Chicken / Vegetable Dum)",
    "veg biryani": "Biryani (Chicken / Vegetable Dum)",
    "dum biryani": "Biryani (Chicken / Vegetable Dum)",
    # Additional Fitness Staples
    "milk": "Cow Milk (Toned / Low Fat)",
    "sweet potato": "Sweet Potato (Baked / Boiled)",
    "peanuts": "Peanuts (Roasted / Unsalted)",
    "peanut butter": "Peanut Butter (100% Natural)",
    "chana": "Chickpeas / Chana (Cooked)",
    "chickpeas": "Chickpeas / Chana (Cooked)",
    "whey": "Whey Protein Powder (100% Isolate/Concentrate)",
    "whey protein": "Whey Protein Powder (100% Isolate/Concentrate)",
    "protein powder": "Whey Protein Powder (100% Isolate/Concentrate)",
    "protein shake": "Whey Protein Powder (100% Isolate/Concentrate)",
}

def resolve_food_nutrition(conn, query, quantity=1.0):
    """
    Resolves identified food to exact nutritional metrics using application's database.
    1. Checks alias mapping to canonical database entries.
    2. Searches food_items table (exact match, prefix, substring).
    3. If not found in DB, uses standard fallback reference marked as an estimate.
    Returns normalized dictionary with exact macros and serving details.
    """
    if not query or not query.strip():
        return None
    cleaned = query.strip()
    norm_key = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned).strip().lower()
    cursor = conn.cursor()

    # 1. Alias lookup in canonical map (exact match first)
    canonical_name = CANONICAL_ALIASES.get(norm_key)
    if not canonical_name:
        # Check sorted by descending length to match longest/most specific phrase first (e.g. 'egg white' before 'egg')
        for k, v in sorted(CANONICAL_ALIASES.items(), key=lambda item: -len(item[0])):
            if re.search(r'\b' + re.escape(k) + r'\b', norm_key):
                canonical_name = v
                break
    if not canonical_name:
        for k, v in sorted(CANONICAL_ALIASES.items(), key=lambda item: -len(item[0])):
            if k in norm_key:
                canonical_name = v
                break

    match = None
    if canonical_name:
        cursor.execute("SELECT * FROM food_items WHERE name = ? LIMIT 1", (canonical_name,))
        match = cursor.fetchone()

    # 2. Database direct lookup
    if not match:
        cursor.execute("SELECT * FROM food_items WHERE name = ? COLLATE NOCASE LIMIT 1", (cleaned,))
        match = cursor.fetchone()

    if not match:
        cursor.execute("SELECT * FROM food_items WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1", (f"{cleaned}%",))
        match = cursor.fetchone()

    if not match:
        cursor.execute("SELECT * FROM food_items WHERE name LIKE ? ORDER BY is_muscle_building DESC, LENGTH(name) ASC LIMIT 1", (f"%{cleaned}%",))
        match = cursor.fetchone()

    if match:
        m = dict(match)
        qty = float(quantity or 1.0)
        return {
            "name": cleaned.title(),
            "display_name": cleaned.title(),
            "matched_database_item": m['name'],
            "food_id": m.get('id'),
            "category": m.get('category', 'General'),
            "serving_size": m['serving_size'],
            "serving_unit": m['serving_unit'],
            "quantity": qty,
            "base_calories": m['calories'],
            "base_protein_g": m['protein_g'],
            "base_carbs_g": m['carbs_g'],
            "base_fats_g": m['fats_g'],
            "calories": int(round(m['calories'] * qty)),
            "protein_g": round(m['protein_g'] * qty, 1),
            "carbs_g": round(m['carbs_g'] * qty, 1),
            "fats_g": round(m['fats_g'] * qty, 1),
            "is_estimate": False,
            "source": "database"
        }

    # 3. Standard nutritional reference fallback
    fallback = None
    for k, v in STANDARD_FALLBACK_FOODS.items():
        if k in norm_key:
            fallback = v
            break

    if fallback:
        qty = float(quantity or 1.0)
        return {
            "name": cleaned.title(),
            "display_name": cleaned.title(),
            "matched_database_item": None,
            "food_id": None,
            "category": "Standard Reference",
            "serving_size": fallback['serving_size'],
            "serving_unit": fallback['serving_unit'],
            "quantity": qty,
            "base_calories": fallback['calories'],
            "base_protein_g": fallback['protein_g'],
            "base_carbs_g": fallback['carbs_g'],
            "base_fats_g": fallback['fats_g'],
            "calories": int(round(fallback['calories'] * qty)),
            "protein_g": round(fallback['protein_g'] * qty, 1),
            "carbs_g": round(fallback['carbs_g'] * qty, 1),
            "fats_g": round(fallback['fats_g'] * qty, 1),
            "is_estimate": True,
            "source": "standard_reference"
        }

    # Generic fallback
    qty = float(quantity or 1.0)
    return {
        "name": cleaned.title(),
        "display_name": cleaned.title(),
        "matched_database_item": None,
        "food_id": None,
        "category": "Estimated",
        "serving_size": "1 serving",
        "serving_unit": "serving",
        "quantity": qty,
        "base_calories": 250,
        "base_protein_g": 10.0,
        "base_carbs_g": 35.0,
        "base_fats_g": 7.0,
        "calories": int(round(250 * qty)),
        "protein_g": round(10.0 * qty, 1),
        "carbs_g": round(35.0 * qty, 1),
        "fats_g": round(7.0 * qty, 1),
        "is_estimate": True,
        "source": "estimated"
    }

def estimate_food_macros_by_query(conn, query, quantity=1.0):
    """
    Looks up closest matching food items to estimate serving size and macronutrients.
    Returns estimated dict with calories, protein, carbs, fats, or None.
    """
    if not query or not query.strip():
        return None
    cursor = conn.cursor()
    cleaned = query.strip()

    # 1. Exact match
    cursor.execute("SELECT * FROM food_items WHERE name = ? COLLATE NOCASE LIMIT 1", (cleaned,))
    match = cursor.fetchone()

    # 2. Prefix match
    if not match:
        cursor.execute("SELECT * FROM food_items WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1", (f"{cleaned}%",))
        match = cursor.fetchone()

    # 3. Substring match
    if not match:
        cursor.execute("SELECT * FROM food_items WHERE name LIKE ? ORDER BY is_muscle_building DESC, LENGTH(name) ASC LIMIT 1", (f"%{cleaned}%",))
        match = cursor.fetchone()

    # 4. Multi-item combination (e.g. "Rice + Dal" or "Chicken + Rice")
    if not match:
        parts = [p.strip() for p in re.split(r'[\+,/&]', cleaned) if p.strip()]
        if len(parts) > 1:
            sub_matches = []
            for p in parts:
                cursor.execute("SELECT * FROM food_items WHERE name LIKE ? LIMIT 1", (f"%{p}%",))
                m = cursor.fetchone()
                if m:
                    sub_matches.append(dict(m))
            if sub_matches:
                total_cals = int(round(sum(m['calories'] for m in sub_matches) * quantity))
                total_p = round(sum(m['protein_g'] for m in sub_matches) * quantity, 1)
                total_c = round(sum(m['carbs_g'] for m in sub_matches) * quantity, 1)
                total_f = round(sum(m['fats_g'] for m in sub_matches) * quantity, 1)
                return {
                    "food_name": cleaned,
                    "serving_size": "1 combined plate",
                    "serving_unit": "plate",
                    "quantity": quantity,
                    "calories": total_cals,
                    "protein_g": total_p,
                    "carbs_g": total_c,
                    "fats_g": total_f,
                    "matched_items": [m['name'] for m in sub_matches]
                }

    if match:
        m = dict(match)
        return {
            "food_name": m['name'],
            "serving_size": m['serving_size'],
            "serving_unit": m['serving_unit'],
            "quantity": quantity,
            "calories": int(round(m['calories'] * quantity)),
            "protein_g": round(m['protein_g'] * quantity, 1),
            "carbs_g": round(m['carbs_g'] * quantity, 1),
            "fats_g": round(m['fats_g'] * quantity, 1),
            "matched_items": [m['name']]
        }

    return None

def update_nutrition_log(conn, user_id, log_id, new_quantity, calories=None, protein_g=None, carbs_g=None, fats_g=None, meal_type=None):
    """
    Updates the quantity and macro values of an existing nutrition log belonging to user_id.
    If explicit macros are not provided, scales the original macros proportionally according to quantity.
    Returns the updated log dictionary or None if not found/unauthorized.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nutrition_logs WHERE id = ? AND user_id = ?", (log_id, user_id))
    entry = cursor.fetchone()
    if not entry:
        return None

    entry_dict = dict(entry)
    old_qty = float(entry_dict.get('quantity') or 1.0)
    if old_qty <= 0:
        old_qty = 1.0

    ratio = new_quantity / old_qty if old_qty > 0 else 1.0

    final_cals = calories if calories is not None else max(1, int(round((entry_dict.get('calories') or 0) * ratio)))
    final_p = protein_g if protein_g is not None else round((entry_dict.get('protein_g') or 0.0) * ratio, 1)
    final_c = carbs_g if carbs_g is not None else round((entry_dict.get('carbs_g') or 0.0) * ratio, 1)
    final_f = fats_g if fats_g is not None else round((entry_dict.get('fats_g') or 0.0) * ratio, 1)
    final_meal_type = meal_type if meal_type else entry_dict.get('meal_type')

    cursor.execute("""
        UPDATE nutrition_logs
        SET quantity = ?, calories = ?, protein_g = ?, carbs_g = ?, fats_g = ?, meal_type = ?
        WHERE id = ? AND user_id = ?
    """, (new_quantity, final_cals, final_p, final_c, final_f, final_meal_type, log_id, user_id))
    conn.commit()

    cursor.execute("SELECT * FROM nutrition_logs WHERE id = ? AND user_id = ?", (log_id, user_id))
    updated = cursor.fetchone()
    return dict(updated) if updated else None

def reset_daily_nutrition(conn, user_id, date_str):
    """
    Deletes all food entries recorded for a specific date belonging to the user.
    Preserves previous and other days' nutrition logs.
    """
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """, (user_id, date_str))
    conn.commit()
    return True

