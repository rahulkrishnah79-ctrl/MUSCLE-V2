"""
AI Fitness Assistant Engine for IronPulse
Provides personalized general fitness guidance using the athlete's:
- Weight, Height, Age, Gender
- Fitness Goal & Experience level
- Training frequency & Available equipment
- Dietary preference
- Workout history & Recent nutrition logs

Also handles specific questions like:
- "Create a chest workout"
- "How much protein should I eat?"
- "What should I eat after my workout?"
- "Create a 4-day workout plan"
- "How can I improve my bench press?"
- "Give me a cheap high-protein meal"
"""

from datetime import date, datetime, timedelta
import re
import database

DISCLAIMER_TEXT = (
    "⚠️ **Health & Medical Disclaimer**: I am an AI fitness assistant designed to provide general exercise, "
    "training, and nutritional information based on exercise science principles and your profile metrics. "
    "This guidance is not medical advice and is not a substitute for clinical diagnosis, treatment, or individualized "
    "counseling from a qualified physician, physical therapist, or registered dietitian. Always consult a healthcare "
    "professional before starting any new intense exercise regime or drastic dietary modification."
)

SUGGESTED_QUESTIONS = [
    "Create a chest workout",
    "How much protein should I eat?",
    "What should I eat after my workout?",
    "Create a 4-day workout plan",
    "How can I improve my bench press?",
    "Give me a cheap high-protein meal"
]

def init_chat_tables(conn):
    """Ensure ai_chat_messages table exists in SQLite."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL, -- 'user' or 'ai'
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    conn.commit()

def get_user_fitness_context(conn, user_id, user_row):
    """
    Assembles complete multi-domain context for the AI:
    - Profile attributes
    - Recent workouts & volume
    - Today's and recent nutrition logs
    - Latest body measurements
    """
    cursor = conn.cursor()
    profile = dict(user_row) if user_row else {}

    # 1. Profile Core
    weight = profile.get('weight_kg', 75.0) or 75.0
    height = profile.get('height_cm', 178.0) or 178.0
    age = profile.get('age', 25) or 25
    gender = profile.get('gender', 'Male') or 'Male'
    goal = profile.get('fitness_goal', 'Muscle Hypertrophy & Strength') or 'Muscle Hypertrophy & Strength'
    experience = profile.get('experience_level', 'Intermediate (1-3 Years)') or 'Intermediate (1-3 Years)'
    frequency = profile.get('training_days_per_week', 4) or 4
    equipment = profile.get('available_equipment', 'Full Commercial Gym') or 'Full Commercial Gym'
    diet = profile.get('dietary_preference', 'High Protein Omnivore') or 'High Protein Omnivore'
    target_weight = profile.get('target_weight_kg', 80.0) or 80.0

    cal_target = profile.get('daily_calorie_target', 2800) or 2800
    protein_target = profile.get('daily_protein_target', 180) or 180
    carbs_target = profile.get('daily_carbs_target', 320) or 320
    fats_target = profile.get('daily_fats_target', 75) or 75

    # 2. Recent Workouts (Last 5)
    cursor.execute("""
        SELECT title, date, duration_minutes, total_volume_kg, status, target_muscle_group
        FROM workouts
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 5
    """, (user_id,))
    recent_workouts = [dict(r) for r in cursor.fetchall()]

    # 3. Today's Nutrition Intake
    today_str = date.today().isoformat()
    cursor.execute("""
        SELECT COALESCE(SUM(calories), 0) as total_cals,
               COALESCE(SUM(protein_g), 0) as total_protein,
               COALESCE(SUM(carbs_g), 0) as total_carbs,
               COALESCE(SUM(fats_g), 0) as total_fats
        FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """, (user_id, today_str))
    nutr = cursor.fetchone()
    today_cals = nutr['total_cals']
    today_protein = round(nutr['total_protein'], 1)

    # 4. Latest progress log measurements
    cursor.execute("""
        SELECT weight_kg, chest_cm, waist_cm, arms_cm, thighs_cm, body_fat_pct
        FROM progress_logs
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 1
    """, (user_id,))
    latest_progress = cursor.fetchone()
    latest_measurements = dict(latest_progress) if latest_progress else {}

    return {
        'weight': weight,
        'height': height,
        'age': age,
        'gender': gender,
        'goal': goal,
        'experience': experience,
        'frequency': frequency,
        'equipment': equipment,
        'diet': diet,
        'target_weight': target_weight,
        'cal_target': cal_target,
        'protein_target': protein_target,
        'carbs_target': carbs_target,
        'fats_target': fats_target,
        'macro_targets': {
            'calories': cal_target,
            'protein': protein_target,
            'carbs': carbs_target,
            'fats': fats_target
        },
        'today_cals': today_cals,
        'today_protein': today_protein,
        'today_nutrition': {
            'calories': today_cals,
            'protein': today_protein
        },
        'recent_workouts': recent_workouts,
        'latest_measurements': latest_measurements
    }

def generate_ai_response(user_query, context):
    """
    Generates intelligent, highly contextual, scientifically accurate fitness advice
    explicitly referencing the user's weight, height, goal, experience, frequency,
    equipment, dietary preference, and recent workout/nutrition stats.
    """
    q = user_query.strip().lower()

    weight = context['weight']
    height = context['height']
    goal = context['goal']
    experience = context['experience']
    frequency = context['frequency']
    equipment = context['equipment']
    diet = context['diet']
    cal_target = context['cal_target']
    prot_target = context['protein_target']
    today_cals = context['today_cals']
    today_prot = context['today_protein']
    recent_workouts = context['recent_workouts']

    # Context Header Summary
    user_badge = (
        f"**Profile Context**: {weight} kg | {height} cm | **Goal**: {goal} | "
        f"**Level**: {experience} | **Schedule**: {frequency} Days/Wk | **Equipment**: {equipment} | **Diet**: {diet}\n\n"
    )

    # ---------------- INTENT 1: CHEST WORKOUT ----------------
    if "chest workout" in q or ("chest" in q and ("workout" in q or "routine" in q or "session" in q)):
        if "dumbbell" in equipment.lower() and "barbell" not in equipment.lower() and "commercial" not in equipment.lower():
            exercises = [
                "1. **Incline Dumbbell Press**: 4 sets × 8–10 reps (RPE 8, 90s rest) - Upper chest focus",
                "2. **Flat Dumbbell Bench Press**: 4 sets × 8–10 reps (RPE 8.5, 90s rest) - Mid-pectoral mass",
                "3. **Floor Dumbbell Flyes / Incline Flyes**: 3 sets × 12 reps (60s rest) - Full chest adduction",
                "4. **Deficit Push-Ups (Hands on Dumbbells)**: 3 sets × max reps to technical failure (60s rest)"
            ]
        elif "bodyweight" in equipment.lower():
            exercises = [
                "1. **Feet-Elevated Decline Push-Ups**: 4 sets × 12–15 reps (60s rest) - Upper chest emphasis",
                "2. **Parallel Bar / Chair Dips**: 4 sets × 8–12 reps (Forward torso lean, 75s rest) - Lower chest",
                "3. **Standard Push-Ups with 3s Eccentric Tempo**: 3 sets × 15–20 reps (60s rest)",
                "4. **Diamond Push-Ups**: 3 sets × failure (60s rest) - Inner sternal & tricep finish"
            ]
        else: # Barbell / Full Commercial Gym
            exercises = [
                "1. **Barbell Bench Press**: 4 sets × 6–8 reps (Heavy compound builder, 2m rest)",
                "2. **Incline Dumbbell Press (30° Angle)**: 3 sets × 8–10 reps (Deep stretch, 90s rest)",
                "3. **Cable Chest Flyes (Mid Pulley)**: 3 sets × 12–15 reps (Peak 1s squeeze, 60s rest)",
                "4. **Chest Dips**: 3 sets × 10–12 reps (Torso tilted forward 30°, 75s rest)",
                "5. **High-to-Low Cable Crossover**: 2 sets × 15 reps (Lower pectoral burnout)"
            ]

        response = (
            user_badge +
            f"Here is a tailored **Hypertrophy Chest Routine** calibrated for your **{experience}** level, **{equipment}**, and **{goal}** goal:\n\n" +
            "\n".join(exercises) + "\n\n"
            f"💡 **Coaching Cue for Your {weight} kg Frame**:\n"
            "- Retract and depress your scapulae before every pressing set. Maintain a modest arch in your mid-back.\n"
            "- Track progressive overload: aim to add 1 kg or +1 rep to your top set each week while eating to support your **{cal_target} kcal** target."
        )
        return response

    # ---------------- INTENT 2: PROTEIN INTAKE ----------------
    if "how much protein" in q or "protein requirement" in q or ("protein" in q and ("eat" in q or "need" in q or "grams" in q)):
        g_per_kg = round(prot_target / weight, 2)
        diet_sources = ""
        if "veg" in diet.lower() or "vegan" in diet.lower():
            diet_sources = (
                f"- **Recommended for your {diet} diet**: Soy chunks (52g protein/100g), Paneer, Greek Curd/Dahi, "
                "Tofu, Dal/Lentils with Rice (for complete amino acid complement), Peanuts, and Plant/Whey isolate."
            )
        else:
            diet_sources = (
                f"- **Recommended for your {diet} diet**: Chicken breast, Eggs & Egg whites, Fish (Salmon/Tilapia), "
                "Paneer, Greek Curd, Milk, Dal, and Whey Protein."
            )

        response = (
            user_badge +
            f"Based on your current weight of **{weight} kg** and fitness goal (**{goal}**):\n\n"
            f"🎯 **Recommended Daily Protein**: **{prot_target} grams / day** (~**{g_per_kg}g per kg** of bodyweight).\n\n"
            f"📊 **Current Status Today**: You have logged **{today_prot}g** of protein so far today "
            f"({max(0, round(prot_target - today_prot, 1))}g remaining).\n\n"
            "🔬 **Why this target?**:\n"
            "- Evidence-based sports nutrition for natural muscle building recommends between **1.8g and 2.2g per kg** to maximize Muscle Protein Synthesis (MPS) and leucine thresholds.\n"
            f"- Split this across **3 to 5 meals** (~35–45g of quality protein per meal with ~3g leucine).\n\n"
            f"🥗 **Top Sources for You**:\n{diet_sources}"
        )
        return response

    # ---------------- INTENT 3: POST-WORKOUT NUTRITION ----------------
    if "post-workout" in q or "after my workout" in q or "after workout" in q or "post workout" in q:
        post_prot = int(round(weight * 0.4))
        post_carbs = int(round(weight * 0.6))
        
        if "veg" in diet.lower():
            meal_option = (
                "- **Option 1**: Whey/Plant Protein Shake + 1 large ripe banana + 30g rolled oats.\n"
                "- **Option 2**: 150g Paneer Bhurji / Low-fat Paneer with 2 rotis or 1.5 cups white rice.\n"
                "- **Option 3**: 200g Greek Curd / Hung Dahi with honey, blueberries, and a handful of roasted peanuts."
            )
        else:
            meal_option = (
                "- **Option 1**: 150g Grilled Chicken Breast + 1.5 bowls cooked White Basmati Rice + steamed greens.\n"
                "- **Option 2**: 1 Scoop Whey Protein Isolate + 1 large banana + 50g rolled oats (Rapid absorption).\n"
                "- **Option 3**: 3 Whole Boiled Eggs + 3 Egg Whites + 2 slices whole wheat toast or 1 bowl sweet potato."
            )

        response = (
            user_badge +
            f"Post-workout nutrition for your **{weight} kg** body should accomplish two physiological goals:\n"
            f"1. **Stimulate Muscle Protein Synthesis (MPS)** via ~**{post_prot}g of fast-acting protein** (high leucine).\n"
            f"2. **Replenish Intramuscular Glycogen** via ~**{post_carbs}g of easily digestible carbohydrates**.\n\n"
            f"🍽️ **Tailored Post-Workout Meals ({diet})**:\n{meal_option}\n\n"
            "⏰ **Anabolic Timing**:\n"
            "- Consume within 45–90 minutes post-training. Rapid simple/moderate glycemic carbs (like white rice, banana, oats) cause an insulin response that shunts amino acids directly into recovering muscle fibers."
        )
        return response

    # ---------------- INTENT 4: WORKOUT PLAN (4-DAY OR ANY SPLIT) ----------------
    if "workout plan" in q or "workout split" in q or "4-day" in q or "split" in q:
        days = 4
        if "3-day" in q or "3 day" in q: days = 3
        elif "5-day" in q or "5 day" in q: days = 5
        elif "6-day" in q or "6 day" in q: days = 6

        if days == 4:
            split_details = (
                "📅 **4-Day Upper / Lower Hypertrophy Split** (Gold Standard for Muscle Growth):\n\n"
                "- **Day 1: Upper Body Power (Chest, Back, Shoulders, Arms)**\n"
                "  • Barbell Bench Press: 4×6–8 | Bent-Over Barbell Row: 4×6–8\n"
                "  • Overhead Press: 3×8 | Incline Dumbbell Curl: 3×10 | Skull Crushers: 3×10\n\n"
                "- **Day 2: Lower Body & Core (Quads, Hamstrings, Calves, Abs)**\n"
                "  • Barbell Back Squat: 4×6–8 | Romanian Deadlift: 3×8–10\n"
                "  • Leg Press / Walking Lunges: 3×12 | Standing Calf Raise: 4×15 | Hanging Leg Raise: 3×12\n\n"
                "- **Day 3: Rest & Active Recovery / Cardio**\n\n"
                "- **Day 4: Upper Body Hypertrophy (Pump & Volume)**\n"
                "  • Incline Dumbbell Press: 4×10–12 | Lat Pulldown: 4×10–12\n"
                "  • Cable Chest Fly: 3×12–15 | Dumbbell Lateral Raise: 4×15 | Hammer Curls: 3×12\n\n"
                "- **Day 5: Lower Body Posterior & Hypertrophy**\n"
                "  • Barbell Deadlift: 3×5 | Leg Press: 4×12 | Walking Lunges: 3×12 | Cable Woodchoppers: 3×12\n\n"
                "- **Days 6 & 7: Rest & Macro Fulfillment**"
            )
        else:
            split_details = (
                f"📅 **Custom {days}-Day Split for {equipment}**:\n"
                "- Tailored to hit each major muscle group every 4–5 days.\n"
                "- You can also activate this split directly via **Workouts &rarr; Generate Custom Split** in IronPulse!"
            )

        response = (
            user_badge +
            f"Here is a comprehensive science-backed routine designed for your **{experience}** level using **{equipment}**:\n\n" +
            split_details + "\n\n"
            "💡 **Progressive Overload Rule**:\n"
            "Keep an RPE (Rating of Perceived Exertion) of 7.5–9 on working sets. Ensure at least 48 hours of recovery before training the same muscle group again."
        )
        return response

    # ---------------- INTENT 5: BENCH PRESS IMPROVEMENT ----------------
    if "bench press" in q or "bench" in q or "chest press" in q:
        response = (
            user_badge +
            f"To systematically increase your **Bench Press** for your **{weight} kg** frame and **{experience}** level, focus on these 5 mechanical and physiological pillars:\n\n"
            "1. 🔩 **Set Up a Rock-Solid Arch & Scapular Shelf**:\n"
            "   - Squeeze shoulder blades together like you are holding a pencil between them and pin them into the bench.\n"
            "   - Drive your heels into the floor (leg drive) to push your body back toward the rack, anchoring your base.\n\n"
            "2. 📐 **Elbow Flare & Bar Path (The J-Curve)**:\n"
            "   - Do NOT press in a straight vertical line or flare elbows at 90°. Touch the bar at your lower sternum/nipple line with elbows at ~60–75°, then press up and slightly backward over your eyes in a shallow curve.\n\n"
            "3. ⚡ **Strengthen the Key Synergists (Triceps & Upper Back)**:\n"
            "   - Lockout power comes from your triceps: prioritize **Skull Crushers**, **Close-Grip Bench**, and **Dips**.\n"
            "   - Stability comes from your lats: perform heavy **Barbell Rows** and **Face Pulls**.\n\n"
            "4. 📈 **Periodization Scheme (Wave Loading)**:\n"
            "   - Week 1: 3 sets × 8 reps @ 70% 1RM\n"
            "   - Week 2: 4 sets × 6 reps @ 75% 1RM\n"
            "   - Week 3: 5 sets × 4 reps @ 80% 1RM\n"
            "   - Week 4: Deload (3 sets × 6 reps light)\n\n"
            f"5. 🥩 **Energetic Fueling**: You cannot maximize pushing strength in an aggressive caloric deficit. Make sure you hit your daily **{cal_target} kcal** target and **{prot_target}g protein**!"
        )
        return response

    # ---------------- INTENT 6: CHEAP HIGH-PROTEIN MEAL ----------------
    if "cheap" in q or "budget" in q or "affordable" in q or "high-protein meal" in q:
        if "veg" in diet.lower():
            meal_breakdown = (
                "🌱 **The ₹40–₹50 Budget High-Protein Vegetarian Feast (Soy Chunks & Dal Khichdi)**:\n\n"
                "• **Ingredients**:\n"
                "  - 60g Soy Chunks (Nutrela): ~**31g Protein**, ₹12\n"
                "  - 50g Yellow Moong / Toor Dal: ~**12g Protein**, ₹8\n"
                "  - 100g Curd / Dahi: ~**6g Protein**, ₹10\n"
                "  - 100g Rice / 2 Rotis + Spices: ~**6g Protein**, ₹10\n\n"
                "• **Total Macro Yield**:\n"
                "  - **Calories**: ~580 kcal\n"
                "  - **Protein**: **55g complete protein**\n"
                "  - **Cost per Serving**: ~₹40 total!\n\n"
                "• **Quick Prep**: Boil soy chunks for 5 mins, squeeze excess water. Sauté in pan with onion, tomatoes, and spices. Serve with cooked dal and cool curd."
            )
        else:
            meal_breakdown = (
                "🥚 **The Budget Muscle Fuel: 4-Egg & Dal Rice Bowl (Under ₹45 / $1.50)**:\n\n"
                "• **Ingredients**:\n"
                "  - 4 Whole Eggs (Boiled or Scrambled): ~**25g Protein**, ₹28\n"
                "  - 1 Large Bowl Cooked Dal: ~**10g Protein**, ₹8\n"
                "  - 1.5 Bowls Cooked White/Brown Rice: ~**5g Protein**, ₹7\n"
                "  - 1 Cup Curd / Milk: ~**8g Protein**, ₹10\n\n"
                "• **Total Macro Yield**:\n"
                "  - **Calories**: ~620 kcal\n"
                "  - **Protein**: **48g biological value protein**\n"
                "  - **Cost per Serving**: Extremely economical!\n\n"
                "• **Alternative (Poultry)**: 200g Raw Chicken Breast purchased in bulk yields **62g protein** for around ₹60."
            )

        response = (
            user_badge +
            f"Here is a high-yield, budget-friendly meal tailored to your **{diet}** preference:\n\n" +
            meal_breakdown + "\n\n"
            f"💡 **Macro Alignment**: This single meal delivers over 25% of your daily **{prot_target}g** protein goal at minimal cost!"
        )
        return response

    # ---------------- INTENT 7: GENERAL NUTRITION / RECENT ACTIVITY ----------------
    if "nutrition" in q or "calories" in q or "macros" in q or "diet" in q:
        response = (
            user_badge +
            f"Here is your nutritional blueprint based on your **{weight} kg** bodyweight and **{goal}** goal:\n\n"
            f"• **Daily Calorie Target**: **{cal_target} kcal**\n"
            f"• **Protein Target**: **{prot_target}g** (~2.1g/kg for anabolic signaling)\n"
            f"• **Carbohydrates**: **{context['carbs_target']}g** (for fueling glycolytic weightlifting)\n"
            f"• **Fats**: **{context['fats_target']}g** (essential for testosterone and hormone synthesis)\n\n"
            f"📊 **Today's Logged Progress**: {today_cals} / {cal_target} kcal, {today_prot} / {prot_target}g protein logged.\n"
            f"Keep your daily food logging updated under the **Nutrition** tab to maintain progressive tracking!"
        )
        return response

    # ---------------- INTENT 8: GENERAL FITNESS GUIDANCE FALLBACK ----------------
    last_workout_str = "No workouts recorded yet."
    if recent_workouts:
        last = recent_workouts[0]
        last_workout_str = f"'{last['title']}' on {last['date']} ({last['total_volume_kg']} kg volume)."

    response = (
        user_badge +
        f"Hello athlete! Based on your current profile (**{weight} kg**, **{height} cm**, **{experience}** aiming for **{goal}**):\n\n"
        f"• **Training Split**: You are set for **{frequency} days per week** using **{equipment}**.\n"
        f"• **Latest Session**: {last_workout_str}\n"
        f"• **Target Nutrition**: {cal_target} kcal and {prot_target}g protein daily.\n\n"
        "Here are common things you can ask me:\n"
        "- *'Create a chest workout'* (or Back, Legs, Shoulders, Arms, Core)\n"
        "- *'How much protein should I eat?'*\n"
        "- *'What should I eat after my workout?'*\n"
        "- *'Create a 4-day workout plan'*\n"
        "- *'How can I improve my bench press?'*\n"
        "- *'Give me a cheap high-protein meal'*\n\n"
        "How can I assist your training or nutrition goals today?"
    )
    return response

def get_chat_history(conn, user_id, limit=30):
    """Fetches recent chat messages for the user."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ai_chat_messages
        WHERE user_id = ?
        ORDER BY created_at ASC, id ASC
        LIMIT ?
    """, (user_id, limit))
    return [dict(r) for r in cursor.fetchall()]

def save_chat_message(conn, user_id, sender, message):
    """Saves a message to the database."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ai_chat_messages (user_id, sender, message)
        VALUES (?, ?, ?)
    """, (user_id, sender, message))
    conn.commit()
    return cursor.lastrowid
