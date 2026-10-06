import sqlite3
import os
import shutil
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

def get_database_path():
    """
    Resolves the SQLite database path.
    In Vercel serverless environment (detected via VERCEL env var or AWS_LAMBDA_FUNCTION_NAME),
    copies or creates the database in writable /tmp to allow read-write operations.
    In local development, uses fitness_tracker.db in the project directory.
    Can be explicitly overridden via the DATABASE_PATH environment variable.
    """
    configured_path = os.environ.get('DATABASE_PATH')
    if configured_path:
        return configured_path

    # If running on Vercel or serverless environment
    if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        tmp_db = '/tmp/fitness_tracker.db'
        repo_db = os.path.join(BASE_DIR, 'fitness_tracker.db')
        # If tmp_db does not exist yet in this container instance
        if not os.path.exists(tmp_db):
            if os.path.exists(repo_db) and os.path.getsize(repo_db) > 0:
                try:
                    shutil.copyfile(repo_db, tmp_db)
                except Exception:
                    pass
        return tmp_db

    return os.path.join(BASE_DIR, 'fitness_tracker.db')

DATABASE_PATH = get_database_path()

def get_db():
    """Establish connection to SQLite database with row factory for dictionary-like access."""
    db_path = get_database_path()
    db_existed = os.path.exists(db_path) and os.path.getsize(db_path) > 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # If the database was newly created in a serverless environment like /tmp, initialize it
    if not db_existed:
        try:
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.commit()
                migrate_tables(conn)
                import exercise_catalog
                exercise_catalog.seed_exercise_catalog(conn)
                import workout_manager
                workout_manager.get_or_create_default_plans(conn)
                import nutrition_manager
                nutrition_manager.init_food_library(conn)
                import ai_assistant
                ai_assistant.init_chat_tables(conn)
                seed_demo_user_and_data(conn)
        except Exception:
            pass

    return conn

def migrate_tables(conn):
    """Ensures existing tables have all columns and creates any new tables."""
    cursor = conn.cursor()

    # 1. Users table migration
    cursor.execute("PRAGMA table_info(users)")
    existing_user_cols = [row[1] for row in cursor.fetchall()]
    needed_user_cols = [
        ("age", "INTEGER DEFAULT 26"),
        ("gender", "TEXT DEFAULT 'Male'"),
        ("training_days_per_week", "INTEGER DEFAULT 4"),
        ("available_equipment", "TEXT DEFAULT 'Full Commercial Gym'"),
        ("dietary_preference", "TEXT DEFAULT 'High Protein Omnivore'"),
        ("google_id", "TEXT"),
        ("profile_picture", "TEXT"),
        ("auth_provider", "TEXT DEFAULT 'local'")
    ]
    for col_name, col_def in needed_user_cols:
        if col_name not in existing_user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id) WHERE google_id IS NOT NULL")

    # 2. Exercises table migration
    cursor.execute("PRAGMA table_info(exercises)")
    existing_ex_cols = [row[1] for row in cursor.fetchall()]
    needed_ex_cols = [
        ("default_sets", "INTEGER DEFAULT 3"),
        ("default_reps", "INTEGER DEFAULT 10"),
        ("rest_seconds", "INTEGER DEFAULT 90"),
        ("recommended_sets", "TEXT DEFAULT '3-4 sets'"),
        ("recommended_reps", "TEXT DEFAULT '8-12 reps'"),
        ("common_mistakes", "TEXT DEFAULT 'Rushing the eccentric tempo, incomplete range of motion.'")
    ]
    for col_name, col_def in needed_ex_cols:
        if col_name not in existing_ex_cols:
            cursor.execute(f"ALTER TABLE exercises ADD COLUMN {col_name} {col_def}")

    # 3. Workouts table migration
    cursor.execute("PRAGMA table_info(workouts)")
    existing_w_cols = [row[1] for row in cursor.fetchall()]
    needed_w_cols = [
        ("status", "TEXT DEFAULT 'completed'"),
        ("target_muscle_group", "TEXT DEFAULT 'General'"),
        ("completion_rate", "INTEGER DEFAULT 100")
    ]
    for col_name, col_def in needed_w_cols:
        if col_name not in existing_w_cols:
            cursor.execute(f"ALTER TABLE workouts ADD COLUMN {col_name} {col_def}")

    # 4. Workout exercises table migration
    cursor.execute("PRAGMA table_info(workout_exercises)")
    existing_we_cols = [row[1] for row in cursor.fetchall()]
    needed_we_cols = [
        ("rest_seconds", "INTEGER DEFAULT 90"),
        ("completed", "INTEGER DEFAULT 1"),
        ("order_idx", "INTEGER DEFAULT 1")
    ]
    for col_name, col_def in needed_we_cols:
        if col_name not in existing_we_cols:
            cursor.execute(f"ALTER TABLE workout_exercises ADD COLUMN {col_name} {col_def}")

    # 5. Progress logs table migration
    cursor.execute("PRAGMA table_info(progress_logs)")
    existing_p_cols = [row[1] for row in cursor.fetchall()]
    if "thighs_cm" not in existing_p_cols:
        cursor.execute("ALTER TABLE progress_logs ADD COLUMN thighs_cm REAL")

    # 6. Exercises table migration for YouTube references
    cursor.execute("PRAGMA table_info(exercises)")
    existing_ex_cols = [row[1] for row in cursor.fetchall()]
    needed_ex_cols = [
        ("youtube_id", "TEXT"),
        ("youtube_url", "TEXT")
    ]
    for col_name, col_def in needed_ex_cols:
        if col_name not in existing_ex_cols:
            cursor.execute(f"ALTER TABLE exercises ADD COLUMN {col_name} {col_def}")

    # 7. Nutrition logs table migration for camera tracking & estimates
    cursor.execute("PRAGMA table_info(nutrition_logs)")
    existing_n_cols = [row[1] for row in cursor.fetchall()]
    needed_n_cols = [
        ("logged_via", "TEXT DEFAULT 'manual'"),
        ("is_estimate", "INTEGER DEFAULT 0"),
        ("image_path", "TEXT")
    ]
    for col_name, col_def in needed_n_cols:
        if col_name not in existing_n_cols:
            cursor.execute(f"ALTER TABLE nutrition_logs ADD COLUMN {col_name} {col_def}")

    # Migrate any legacy 'Arms' exercises into Biceps / Triceps
    cursor.execute("UPDATE exercises SET category = 'Biceps' WHERE category = 'Arms' AND name LIKE '%Curl%'")
    cursor.execute("UPDATE exercises SET category = 'Triceps' WHERE category = 'Arms'")

    # 8. User daily schedules table for editable daily workout schedules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            workout_id INTEGER,
            workout_title TEXT,
            target_muscle_group TEXT DEFAULT 'General',
            duration_minutes INTEGER DEFAULT 60,
            exercise_id INTEGER NOT NULL,
            sets INTEGER NOT NULL DEFAULT 3,
            reps INTEGER NOT NULL DEFAULT 10,
            rest_time INTEGER NOT NULL DEFAULT 90,
            exercise_order INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (exercise_id) REFERENCES exercises (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_daily_schedules ON user_daily_schedules (user_id, date)")

    conn.commit()

def init_db():
    """Initializes tables and populates seed data if empty."""
    conn = get_db()
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

    migrate_tables(conn)

    # Seed comprehensive exercise catalog with all 8 categories
    import exercise_catalog
    exercise_catalog.seed_exercise_catalog(conn)

    # Initialize workout plans
    import workout_manager
    workout_manager.get_or_create_default_plans(conn)

    # Initialize food items library
    import nutrition_manager
    nutrition_manager.init_food_library(conn)

    # Initialize AI assistant chat tables
    import ai_assistant
    ai_assistant.init_chat_tables(conn)

    # Check if demo user exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_demo_user_and_data(conn)

    conn.close()

def seed_exercises(conn):
    """Seeds comprehensive exercises across Chest, Back, Shoulders, Biceps, Triceps, Legs, Core."""
    exercises = [
        # Chest
        ("Barbell Bench Press", "Chest", "Pectoralis Major, Anterior Deltoid, Triceps", "Barbell", "Intermediate",
         "The fundamental compound movement for building upper body pushing strength and chest mass.",
         "Lie flat on the bench with eyes under the bar. Grip slightly wider than shoulder width. Lower bar smoothly to mid-chest, press upward driving through the feet.",
         4, 8, 90),
        ("Incline Dumbbell Press", "Chest", "Clavicular Pectoral Head (Upper Chest), Front Delts", "Dumbbell", "Intermediate",
         "Isolates the upper chest fibers while allowing a natural wrist rotation and deep stretch.",
         "Set bench to 30-45 degrees. Press dumbbells upward together while maintaining engaged shoulder blades.",
         3, 10, 90),
        ("Cable Chest Fly", "Chest", "Sternal Pectoral Head, Inner Chest Squeeze", "Cable", "Beginner",
         "Provides continuous tension across the entire chest muscle range of motion.",
         "Set pulleys at chest height. Step forward, keep slight bend in elbows, and bring hands together in a hugging motion.",
         3, 12, 60),
        ("Dips", "Chest", "Lower Pectorals, Anterior Deltoid, Triceps", "Bodyweight", "Intermediate",
         "High-intensity compound push for chest lower head and pushing strength.",
         "Grip parallel bars. Lean torso forward ~30 degrees, descend until upper arms are parallel to floor, drive back up.",
         3, 10, 75),
        ("Push-Ups", "Chest", "Pectorals, Anterior Delts, Triceps, Core", "Bodyweight", "Beginner",
         "Classic horizontal pressing foundation for endurance and joint stability.",
         "Hands slightly wider than shoulders, core tightly braced. Lower chest to floor and press through palms.",
         3, 15, 60),

        # Back
        ("Barbell Deadlift", "Back", "Erector Spinae, Latissimus Dorsi, Traps, Glutes, Hamstrings", "Barbell", "Advanced",
         "The king of posterior chain exercises for full-body strength and back thickness.",
         "Stand with mid-foot under the bar. Hinge hips back, grip bar firmly, engage lats, and drive the floor away to stand upright.",
         4, 5, 150),
        ("Pull-Ups", "Back", "Latissimus Dorsi, Rhomboids, Biceps, Core", "Bodyweight", "Intermediate",
         "Classic bodyweight movement that develops the coveted V-taper lat width.",
         "Grip pull-up bar slightly wider than shoulder-width. Drive elbows down toward your hips and pull chest to bar.",
         4, 8, 90),
        ("Bent-Over Barbell Row", "Back", "Upper Back, Lats, Rhomboids, Rear Delts", "Barbell", "Intermediate",
         "Builds substantial mid-back density and lat thickness.",
         "Hinge at the hips at a 45-degree angle with a neutral spine. Pull bar to upper abdomen, squeezing shoulder blades together.",
         4, 8, 90),
        ("Seated Cable Row", "Back", "Mid-Back, Lower Lats, Rhomboids", "Cable", "Beginner",
         "Great horizontal pulling exercise for scapular retraction and mid-back control.",
         "Sit upright with knees slightly bent. Pull handle into lower abdomen while keeping spine neutral and shoulders pinned back.",
         3, 10, 75),
        ("Lat Pulldown", "Back", "Latissimus Dorsi, Teres Major, Biceps", "Cable", "Beginner",
         "Vertical pulling alternative allowing controlled overload for wide lats.",
         "Grip wide bar, lean slightly back. Pull bar downward to upper chest, leading with the elbows.",
         3, 10, 75),

        # Shoulders
        ("Overhead Barbell Press (OHP)", "Shoulders", "Anterior & Lateral Deltoids, Triceps, Traps", "Barbell", "Intermediate",
         "Strict vertical pressing movement for boulder shoulders and overhead strength.",
         "Hold bar at shoulder level. Brace core and glutes, press bar vertically directly overhead, locking elbows out safely.",
         4, 8, 120),
        ("Dumbbell Lateral Raise", "Shoulders", "Lateral Deltoids (Side Delts)", "Dumbbell", "Beginner",
         "Crucial isolation movement for widening the shoulders and creating broad capped delts.",
         "Hold dumbbells at sides. Raise arms out to the sides leading with elbows until parallel to floor, lower slowly.",
         4, 12, 60),
        ("Face Pulls", "Shoulders", "Rear Deltoids, Rotator Cuff, Upper Traps", "Cable", "Beginner",
         "Essential for shoulder health, posture alignment, and rear deltoid fullness.",
         "Attach rope to high pulley. Pull rope toward bridge of nose while externally rotating hands backward.",
         3, 15, 60),
        ("Arnold Press", "Shoulders", "Anterior, Lateral & Posterior Deltoids", "Dumbbell", "Intermediate",
         "Rotational overhead dumbbell press hitting all three deltoid heads through a full arc.",
         "Start with palms facing you. Rotate wrists outward as you press overhead until palms face forward at top.",
         3, 10, 90),
        ("Dumbbell Rear Delt Fly", "Shoulders", "Posterior Deltoids, Rhomboids", "Dumbbell", "Beginner",
         "Direct isolation movement for complete 3D shoulder shape and upper back balance.",
         "Bend forward at hips. Raise dumbbells outward to the side with pinkies slightly higher, squeezing rear delts.",
         3, 12, 60),

        # Biceps
        ("Barbell Bicep Curl", "Biceps", "Biceps Brachii, Brachialis", "Barbell", "Beginner",
         "The cornerstone mass builder for arm circumference and peak bicep recruitment.",
         "Stand tall with shoulders pinned. Curl barbell upwards toward upper chest without swinging elbows forward.",
         3, 10, 60),
        ("Incline Dumbbell Curl", "Biceps", "Long Head of Biceps (Bicep Peak)", "Dumbbell", "Intermediate",
         "Provides an intense stretch on the long head of the bicep for peak development.",
         "Sit on an incline bench at 60 degrees. Let arms hang back and curl dumbbells up with full supination.",
         3, 10, 60),
        ("Hammer Curls", "Biceps", "Brachialis, Brachioradialis, Biceps", "Dumbbell", "Beginner",
         "Develops arm thickness, pushing the bicep up while forging strong forearms.",
         "Hold dumbbells with neutral palms-facing-in grip. Curl upward strictly without rotating wrists.",
         3, 12, 60),
        ("Cable Preacher Curl", "Biceps", "Short Head Bicep Peak, Inner Biceps", "Cable", "Intermediate",
         "Isolates the bicep apex with continuous mechanical cable tension.",
         "Rest upper arms on preacher pad. Curl bar toward forehead, pausing 1 second at maximum contraction.",
         3, 10, 60),

        # Triceps
        ("Skull Crushers (Lying Triceps Extension)", "Triceps", "Triceps Brachii (All 3 Heads)", "Barbell", "Intermediate",
         "Direct tricep developer targeting long and lateral heads for horseshoe triceps.",
         "Lie on flat bench with EZ bar overhead. Lower bar slowly toward forehead by bending at elbows, press back up.",
         3, 10, 90),
        ("Tricep Rope Pushdown", "Triceps", "Lateral & Medial Tricep Heads", "Cable", "Beginner",
         "Controlled isolation exercise for constant tricep burnout.",
         "Use rope attachment. Pin elbows to sides and push downward, flaring rope slightly at bottom.",
         4, 12, 60),
        ("Overhead Dumbbell Tricep Extension", "Triceps", "Long Head of Triceps", "Dumbbell", "Beginner",
         "Maximum stretch on the largest head of the tricep for arm size.",
         "Hold single dumbbell overhead with both hands. Lower behind head bending elbows, extend upward to lockout.",
         3, 12, 60),
        ("Bench Tricep Dips", "Triceps", "Triceps Brachii, Anterior Deltoids", "Bodyweight", "Beginner",
         "Effective bodyweight tricep burner accessible anywhere.",
         "Hands on edge of bench behind back. Lower hips until elbows hit 90 degrees, press up through palms.",
         3, 12, 60),

        # Legs
        ("Barbell Back Squat", "Legs", "Quadriceps, Glutes, Adductors, Core", "Barbell", "Advanced",
         "The premier lower body compound builder for leg mass, power, and athletic performance.",
         "Rest bar across upper traps. Break at hips and knees simultaneously, descend until thighs are parallel or lower, drive up.",
         4, 8, 120),
        ("Romanian Deadlift (RDL)", "Legs", "Hamstrings, Gluteus Maximus, Lower Back", "Barbell", "Intermediate",
         "Superior eccentric movement for hamstring hypertrophy and hip hinge mastery.",
         "Keep slight bend in knees. Push hips back as far as possible while lowering the bar along your shins until hamstrings stretch.",
         3, 10, 90),
        ("Leg Press", "Legs", "Quadriceps, Glutes", "Machine", "Beginner",
         "Allows heavy quad loading with reduced lower back spinal compression.",
         "Position feet shoulder-width on platform. Lower sled with control until knees reach 90 degrees, press without locking knees.",
         4, 12, 90),
        ("Walking Dumbbell Lunges", "Legs", "Quadriceps, Glutes, Hamstrings, Calves", "Dumbbell", "Intermediate",
         "Unilateral leg developer improving muscular balance and quad sweep.",
         "Step forward into a deep lunge with back knee grazing floor. Push through front heel to step into next stride.",
         3, 12, 90),
        ("Standing Calf Raise", "Legs", "Gastrocnemius, Soleus", "Machine", "Beginner",
         "Targets lower leg definition and explosive ankle flexion.",
         "Balls of feet on edge. Lower heels for a deep stretch, then elevate up onto toes and pause for 1 second.",
         4, 15, 60),

        # Core
        ("Hanging Leg Raise", "Core", "Rectus Abdominis (Lower Abs), Hip Flexors", "Bodyweight", "Intermediate",
         "High-intensity core builder for sculpted abdominal definition.",
         "Hang from pull-up bar. Without swinging, lift knees or straight legs up until thighs reach horizontal or touch chest.",
         3, 12, 60),
        ("Cable Woodchoppers", "Core", "Internal & External Obliques, Transverse Abdominis", "Cable", "Beginner",
         "Rotational abdominal power exercise for a tight, powerful athletic midsection.",
         "Set pulley high. Pull diagonally across torso down toward opposite knee while engaging core.",
         3, 12, 60),
        ("Abdominal Crunch Machine", "Core", "Upper Rectus Abdominis", "Machine", "Beginner",
         "Direct weighted abdominal loading to build defined six-pack brick density.",
         "Adjust seat so chest pad contacts upper torso. Crunch forward flexing spine, hold peak contraction for 1 second.",
         3, 15, 60)
    ]

    for ex in exercises:
        name, cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec = ex
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM exercises WHERE name = ?", (name,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE exercises SET
                    category = ?, muscle_group = ?, equipment = ?, difficulty = ?,
                    description = ?, instructions = ?, default_sets = ?, default_reps = ?, rest_seconds = ?
                WHERE id = ?
            """, (cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO exercises (name, category, muscle_group, equipment, difficulty, description, instructions, default_sets, default_reps, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec))
    conn.commit()

def seed_demo_user_and_data(conn):
    demo_password = generate_password_hash("fitness123")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (
            username, email, password_hash, full_name, age, gender,
            height_cm, weight_kg, experience_level, fitness_goal,
            training_days_per_week, available_equipment, dietary_preference,
            target_weight_kg, daily_calorie_target, daily_protein_target,
            daily_carbs_target, daily_fats_target
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'alex_pulse',
        'alex@ironpulse.fit',
        demo_password,
        'Alex Mercer',
        26,
        'Male',
        181.0,
        78.5,
        'Intermediate (1-3 Years)',
        'Muscle Hypertrophy & Strength',
        5,
        'Full Commercial Gym',
        'High Protein Omnivore',
        82.0,
        2850,
        185,
        320,
        75
    ))
    user_id = cursor.lastrowid

    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    three_days_ago = today - timedelta(days=3)

    # Workouts for demo user
    workouts_data = [
        (user_id, "Heavy Push Session: Chest, Shoulders & Triceps", today.isoformat(), 65, 8420.0, 9, "completed", "Chest & Triceps", 100, "Hit a new PR on Bench Press! Pump was incredible."),
        (user_id, "Power Pull Session: Lats, Biceps & Rear Delts", two_days_ago.isoformat(), 70, 9150.0, 8, "completed", "Back & Biceps", 100, "Great focus on mind-muscle connection during Deadlifts."),
        (user_id, "Leg Hypertrophy: Quads, Hamstrings & Calves", three_days_ago.isoformat(), 75, 11200.0, 9, "completed", "Legs", 100, "Brutal leg day. 4 hard working sets of back squats.")
    ]

    for w in workouts_data:
        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, completion_rate, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, w)
        w_id = cursor.lastrowid

        if "Push" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Bench Press'")
            ex1 = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM exercises WHERE name = 'Incline Dumbbell Press'")
            ex2 = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM exercises WHERE name = 'Tricep Rope Pushdown'")
            ex3 = cursor.fetchone()[0]

            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 8, 90.0, 90, 1, 'RPE 8.5')", (w_id, ex1))
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 3, 10, 32.0, 90, 1, 'Clean stretch')", (w_id, ex2))
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 12, 35.0, 60, 1, 'Drop set on last set')", (w_id, ex3))
        elif "Pull" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Deadlift'")
            ex1 = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Bicep Curl'")
            ex2 = cursor.fetchone()[0]
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 5, 150.0, 150, 1, 'Conventional stance')", (w_id, ex1))
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 3, 12, 35.0, 60, 1, 'Strict form')", (w_id, ex2))
        elif "Leg" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Back Squat'")
            ex1 = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM exercises WHERE name = 'Standing Calf Raise'")
            ex2 = cursor.fetchone()[0]
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 8, 120.0, 120, 1, 'Deep below parallel')", (w_id, ex1))
            cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 15, 60.0, 60, 1, '1-sec squeeze')", (w_id, ex2))

    # Link demo user to default plan
    cursor.execute("SELECT id FROM workout_plans LIMIT 1")
    plan_row = cursor.fetchone()
    if plan_row:
        cursor.execute("INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at) VALUES (?, ?, ?)", (user_id, plan_row[0], today.isoformat()))

    # Nutrition data
    nutrition_data = [
        (user_id, today.isoformat(), "Breakfast", "Oatmeal with Blueberries, Chia Seeds & Whey Protein", 580, 42.0, 72.0, 12.0),
        (user_id, today.isoformat(), "Lunch", "Grilled Chicken Breast, Brown Jasmine Rice & Broccoli", 720, 58.0, 78.0, 14.0),
        (user_id, today.isoformat(), "Post-Workout", "Whey Protein Isolate Shake & Large Banana", 340, 32.0, 45.0, 3.0),
        (user_id, today.isoformat(), "Dinner", "Wild Salmon Fillet, Roasted Sweet Potatoes & Asparagus", 690, 46.0, 58.0, 24.0),
        (user_id, today.isoformat(), "Snack", "Greek Yogurt (0% Fat) with Honey & Almonds", 280, 22.0, 25.0, 9.0)
    ]
    for meal in nutrition_data:
        cursor.execute("INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", meal)

    # Progress data (date, weight, body_fat, chest, arms, waist, thighs, notes)
    progress_data = [
        (user_id, (today - timedelta(days=28)).isoformat(), 76.8, 14.8, 104.0, 38.0, 83.0, 58.0, "Starting hypertrophy training block."),
        (user_id, (today - timedelta(days=21)).isoformat(), 77.2, 14.6, 104.5, 38.2, 83.0, 58.5, "Weight steadily climbing, feeling energetic."),
        (user_id, (today - timedelta(days=14)).isoformat(), 77.8, 14.5, 105.2, 38.5, 82.8, 59.0, "Deload completed, strength restored."),
        (user_id, (today - timedelta(days=7)).isoformat(), 78.1, 14.4, 105.8, 38.8, 82.5, 59.8, "Good vascularity, recovery is on point."),
        (user_id, today.isoformat(), 78.5, 14.2, 106.4, 39.1, 82.3, 60.5, "Hit 78.5kg milestone! Arms up +1.1cm, Thighs +2.5cm.")
    ]
    for p in progress_data:
        cursor.execute("INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, arms_cm, waist_cm, thighs_cm, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", p)

    conn.commit()
