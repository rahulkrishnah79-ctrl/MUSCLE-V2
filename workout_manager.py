"""
IronPulse - Complete Workout Management System
Handles workout plan generation, daily workout scheduling, active session logging,
exercise completion tracking, and consistency streaks.
"""

from datetime import date, datetime, timedelta
import database

CATEGORIES = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Core', 'Abs']

def get_or_create_default_plans(conn):
    """Seed comprehensive workout plans if none exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM workout_plans")
    if cursor.fetchone()[0] > 0:
        return

    # Seed 4 Core Foundation Workout Plans
    plans = [
        # Plan 1: 4-Day Upper / Lower Hypertrophy Split
        {
            "name": "4-Day Hypertrophy Upper/Lower Split",
            "description": "Evidence-based 4-day split alternating heavy upper body compound density and lower body quad/posterior chain overload. Ideal for progressive hypertrophy.",
            "fitness_goal": "Muscle Hypertrophy & Strength",
            "experience_level": "Intermediate (1-3 Years)",
            "days_per_week": 4,
            "available_equipment": "Full Commercial Gym",
            "target_muscle_group": "All",
            "is_default": 1,
            "days": [
                {
                    "day_number": 1,
                    "day_title": "Upper Body Push & Pull Heavy",
                    "focus_category": "Chest & Back",
                    "exercises": [
                        ("Barbell Bench Press", 4, 8, 90, "Focus on deep pec stretch and controlled eccentric."),
                        ("Bent-Over Barbell Row", 4, 8, 90, "Pull to upper navel, squeeze rhomboids and lats."),
                        ("Overhead Barbell Press (OHP)", 3, 8, 90, "Brace glutes and core, strict press overhead."),
                        ("Pull-Ups", 3, 10, 75, "Full extension to chin over bar."),
                        ("Tricep Rope Pushdown", 3, 12, 60, "Lock out elbows at bottom, flare rope."),
                        ("Barbell Bicep Curl", 3, 10, 60, "Strict elbows pinned to ribs.")
                    ]
                },
                {
                    "day_number": 2,
                    "day_title": "Lower Body Power & Core",
                    "focus_category": "Legs & Core",
                    "exercises": [
                        ("Barbell Back Squat", 4, 8, 120, "Parallel or below, drive through mid-foot."),
                        ("Romanian Deadlift (RDL)", 3, 10, 90, "Push hips back until hamstrings load deeply."),
                        ("Leg Press", 3, 12, 90, "Full depth without rounding lower back."),
                        ("Standing Calf Raise", 4, 15, 60, "1-sec pause at peak plantarflexion."),
                        ("Hanging Leg Raise", 3, 12, 60, "Slow pelvic tilt, no momentum swing.")
                    ]
                },
                {
                    "day_number": 3,
                    "day_title": "Upper Body Hypertrophy & Arms",
                    "focus_category": "Chest, Shoulders & Arms",
                    "exercises": [
                        ("Incline Dumbbell Press", 4, 10, 90, "Set bench to 30 degrees, target clavicular head."),
                        ("Seated Cable Row", 3, 10, 75, "Neutral grip, lead with elbows."),
                        ("Dumbbell Lateral Raise", 4, 12, 60, "Slight forward lean, raise arms to parallel."),
                        ("Skull Crushers (Lying Triceps Extension)", 3, 10, 60, "Keep upper arms vertical, full tricep stretch."),
                        ("Incline Dumbbell Curl", 3, 12, 60, "Let arms hang deep for maximum long head stretch."),
                        ("Cable Woodchoppers", 3, 15, 60, "Engage rotational obliques.")
                    ]
                },
                {
                    "day_number": 4,
                    "day_title": "Lower Body Posterior & Core",
                    "focus_category": "Legs & Core",
                    "exercises": [
                        ("Barbell Deadlift", 4, 5, 150, "Full reset between reps, lock lats and drive."),
                        ("Walking Dumbbell Lunges", 3, 12, 90, "Controlled knee descent, upright posture."),
                        ("Dips", 3, 10, 75, "Chest leaning forward for lower pec activation."),
                        ("Face Pulls", 3, 15, 60, "High pull to forehead, externally rotate wrists."),
                        ("Abdominal Crunch Machine", 3, 15, 60, "Full abdominal contraction.")
                    ]
                }
            ]
        },
        # Plan 2: 5-Day Push / Pull / Legs + Upper / Lower
        {
            "name": "5-Day Advanced PPL & Power Split",
            "description": "High-frequency bodybuilding hypertrophy split with dedicated Push, Pull, Leg sessions and weekend power upper/lower volume blocks.",
            "fitness_goal": "Lean Bulk",
            "experience_level": "Advanced (3+ Years)",
            "days_per_week": 5,
            "available_equipment": "Full Commercial Gym",
            "target_muscle_group": "All",
            "is_default": 0,
            "days": [
                {
                    "day_number": 1,
                    "day_title": "Push Day: Chest, Delts & Triceps",
                    "focus_category": "Chest",
                    "exercises": [
                        ("Barbell Bench Press", 4, 6, 120, "Heavy compound strength driver."),
                        ("Incline Dumbbell Press", 3, 10, 90, "Upper pec hypertrophy."),
                        ("Overhead Barbell Press (OHP)", 3, 8, 90, "Deltoid power."),
                        ("Cable Chest Fly", 3, 12, 60, "Continuous tension pec flyes."),
                        ("Tricep Rope Pushdown", 4, 12, 60, "Tricep burnout."),
                        ("Dips", 3, 10, 60, "Chest and tricep finisher.")
                    ]
                },
                {
                    "day_number": 2,
                    "day_title": "Pull Day: Back, Biceps & Rear Delts",
                    "focus_category": "Back",
                    "exercises": [
                        ("Barbell Deadlift", 4, 5, 150, "Posterior chain baseline."),
                        ("Pull-Ups", 4, 8, 90, "Lat width V-taper builder."),
                        ("Bent-Over Barbell Row", 3, 8, 90, "Upper back density."),
                        ("Barbell Bicep Curl", 4, 10, 60, "Arm mass recruitment."),
                        ("Hammer Curls", 3, 12, 60, "Brachialis and forearm fullness."),
                        ("Face Pulls", 3, 15, 60, "Rear delts and postural health.")
                    ]
                },
                {
                    "day_number": 3,
                    "day_title": "Leg Day: Quad & Calves Annihilation",
                    "focus_category": "Legs",
                    "exercises": [
                        ("Barbell Back Squat", 4, 8, 120, "King of quad builders."),
                        ("Romanian Deadlift (RDL)", 4, 8, 90, "Hamstring eccentric overload."),
                        ("Leg Press", 3, 12, 90, "High-rep quad burnout."),
                        ("Standing Calf Raise", 4, 15, 60, "Peak plantar contraction."),
                        ("Hanging Leg Raise", 3, 12, 60, "Lower abdominal builder.")
                    ]
                },
                {
                    "day_number": 4,
                    "day_title": "Upper Body Specialization: Chest & Back",
                    "focus_category": "Chest & Back",
                    "exercises": [
                        ("Incline Dumbbell Press", 4, 8, 90, "Upper pec focus."),
                        ("Seated Cable Row", 4, 10, 75, "Scapular squeeze."),
                        ("Dumbbell Lateral Raise", 4, 15, 60, "Side delt cap developer."),
                        ("Incline Dumbbell Curl", 3, 10, 60, "Peak bicep elongation."),
                        ("Skull Crushers (Lying Triceps Extension)", 3, 10, 60, "Long head tricep mass.")
                    ]
                },
                {
                    "day_number": 5,
                    "day_title": "Lower Body & Core Power",
                    "focus_category": "Legs & Core",
                    "exercises": [
                        ("Barbell Back Squat", 3, 10, 90, "Volume squat loading."),
                        ("Walking Dumbbell Lunges", 3, 12, 75, "Glute and quad stabilizer."),
                        ("Cable Woodchoppers", 3, 15, 60, "Oblique core rotation."),
                        ("Standing Calf Raise", 3, 15, 60, "Calf volume.")
                    ]
                }
            ]
        },
        # Plan 3: 3-Day Full Body Recomposition
        {
            "name": "3-Day Full Body Muscle Builder",
            "description": "High-efficiency 3-day routine targeting all major muscle groups thrice weekly. Maximizes recovery and protein synthesis frequency.",
            "fitness_goal": "Cutting & Fat Loss",
            "experience_level": "Beginner (< 1 Year)",
            "days_per_week": 3,
            "available_equipment": "Full Commercial Gym",
            "target_muscle_group": "All",
            "is_default": 0,
            "days": [
                {
                    "day_number": 1,
                    "day_title": "Full Body Compound A",
                    "focus_category": "Full Body",
                    "exercises": [
                        ("Barbell Back Squat", 3, 10, 90, "Leg builder."),
                        ("Barbell Bench Press", 3, 10, 90, "Upper push."),
                        ("Seated Cable Row", 3, 10, 75, "Horizontal pull."),
                        ("Dumbbell Lateral Raise", 3, 12, 60, "Deltoids."),
                        ("Hanging Leg Raise", 3, 12, 60, "Core.")
                    ]
                },
                {
                    "day_number": 2,
                    "day_title": "Full Body Compound B",
                    "focus_category": "Full Body",
                    "exercises": [
                        ("Romanian Deadlift (RDL)", 3, 10, 90, "Posterior chain."),
                        ("Overhead Barbell Press (OHP)", 3, 8, 90, "Vertical press."),
                        ("Pull-Ups", 3, 8, 90, "Vertical pull."),
                        ("Barbell Bicep Curl", 3, 10, 60, "Biceps."),
                        ("Tricep Rope Pushdown", 3, 12, 60, "Triceps.")
                    ]
                },
                {
                    "day_number": 3,
                    "day_title": "Full Body Hypertrophy C",
                    "focus_category": "Full Body",
                    "exercises": [
                        ("Leg Press", 3, 12, 90, "Quad loading."),
                        ("Incline Dumbbell Press", 3, 10, 75, "Upper chest."),
                        ("Bent-Over Barbell Row", 3, 10, 75, "Mid-back density."),
                        ("Hammer Curls", 3, 12, 60, "Arm thickness."),
                        ("Abdominal Crunch Machine", 3, 15, 60, "Core.")
                    ]
                }
            ]
        },
        # Plan 4: 4-Day Dumbbells & Bench Routine
        {
            "name": "4-Day Dumbbells & Bench Home Gym Routine",
            "description": "Complete muscle building routine optimized for dumbbells and an adjustable bench. Full range of motion and joint-friendly hypertrophy.",
            "fitness_goal": "Muscle Hypertrophy & Strength",
            "experience_level": "Intermediate (1-3 Years)",
            "days_per_week": 4,
            "available_equipment": "Dumbbells & Bench",
            "target_muscle_group": "All",
            "is_default": 0,
            "days": [
                {
                    "day_number": 1,
                    "day_title": "Dumbbell Chest & Triceps",
                    "focus_category": "Chest & Triceps",
                    "exercises": [
                        ("Incline Dumbbell Press", 4, 10, 90, "Upper chest builder."),
                        ("Push-Ups", 3, 15, 60, "Chest volume."),
                        ("Overhead Dumbbell Tricep Extension", 3, 12, 60, "Tricep long head."),
                        ("Bench Tricep Dips", 3, 12, 60, "Tricep burnout.")
                    ]
                },
                {
                    "day_number": 2,
                    "day_title": "Dumbbell Back & Biceps",
                    "focus_category": "Back & Biceps",
                    "exercises": [
                        ("Pull-Ups", 4, 8, 90, "Lat width."),
                        ("Incline Dumbbell Curl", 3, 12, 60, "Bicep peak."),
                        ("Hammer Curls", 3, 12, 60, "Brachialis and forearms.")
                    ]
                },
                {
                    "day_number": 3,
                    "day_title": "Dumbbell Shoulders & Core",
                    "focus_category": "Shoulders & Core",
                    "exercises": [
                        ("Arnold Press", 4, 10, 90, "Complete shoulder compound."),
                        ("Dumbbell Lateral Raise", 4, 12, 60, "Side delt width."),
                        ("Dumbbell Rear Delt Fly", 3, 12, 60, "Rear deltoids.")
                    ]
                },
                {
                    "day_number": 4,
                    "day_title": "Dumbbell Legs & Glutes",
                    "focus_category": "Legs",
                    "exercises": [
                        ("Walking Dumbbell Lunges", 4, 12, 90, "Quad and glute hypertrophy."),
                        ("Romanian Deadlift (RDL)", 3, 10, 90, "Hamstrings.")
                    ]
                }
            ]
        }
    ]

    for p in plans:
        cursor.execute("""
            INSERT INTO workout_plans (name, description, fitness_goal, experience_level, days_per_week, available_equipment, target_muscle_group, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (p['name'], p['description'], p['fitness_goal'], p['experience_level'], p['days_per_week'], p['available_equipment'], p['target_muscle_group'], p['is_default']))
        plan_id = cursor.lastrowid

        for d in p['days']:
            cursor.execute("""
                INSERT INTO workout_plan_days (plan_id, day_number, day_title, focus_category)
                VALUES (?, ?, ?, ?)
            """, (plan_id, d['day_number'], d['day_title'], d['focus_category']))
            day_id = cursor.lastrowid

            for idx, ex_data in enumerate(d['exercises'], start=1):
                ex_name, sets, reps, rest_sec, notes = ex_data
                # Find exercise_id
                cursor.execute("SELECT id FROM exercises WHERE name = ?", (ex_name,))
                row = cursor.fetchone()
                if row:
                    ex_id = row[0]
                    cursor.execute("""
                        INSERT INTO workout_plan_exercises (plan_day_id, exercise_id, sets, reps, rest_seconds, order_idx, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (day_id, ex_id, sets, reps, rest_sec, idx, notes))

    conn.commit()

def ensure_user_has_active_plan(user_id, user_row):
    """Ensures the user has an active workout plan matching their profile attributes."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT plan_id FROM user_active_plans WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return existing[0]

    # Find the best plan matching user goal, equipment, or default
    goal = user_row['fitness_goal'] or 'Muscle Hypertrophy & Strength'
    equipment = user_row['available_equipment'] or 'Full Commercial Gym'
    days = user_row['training_days_per_week'] or 4

    cursor.execute("""
        SELECT id FROM workout_plans
        WHERE days_per_week = ? OR is_default = 1
        ORDER BY is_default DESC, id ASC
        LIMIT 1
    """, (days,))
    matched_plan = cursor.fetchone()

    plan_id = matched_plan[0] if matched_plan else 1

    cursor.execute("""
        INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at)
        VALUES (?, ?, ?)
    """, (user_id, plan_id, date.today().isoformat()))
    conn.commit()
    conn.close()
    return plan_id

def ensure_daily_schedule_table(conn):
    """Ensures user_daily_schedules table exists."""
    cursor = conn.cursor()
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

def get_user_daily_schedule(user_id, date_str, conn=None):
    """Fetches user's custom schedule for the given date, or empty list if none."""
    close_at_end = False
    if conn is None:
        conn = database.get_db()
        close_at_end = True
    cursor = conn.cursor()
    ensure_daily_schedule_table(conn)

    cursor.execute("""
        SELECT uds.*, e.name as exercise_name, e.category as category,
               e.muscle_group as target_muscle, e.difficulty, e.instructions,
               e.youtube_id, e.youtube_url, e.equipment,
               uds.rest_time as rest_seconds
        FROM user_daily_schedules uds
        JOIN exercises e ON uds.exercise_id = e.id
        WHERE uds.user_id = ? AND uds.date = ?
        ORDER BY uds.exercise_order ASC, uds.id ASC
    """, (user_id, date_str))
    rows = [dict(r) for r in cursor.fetchall()]

    if close_at_end:
        conn.close()
    return rows

def save_user_daily_schedule(user_id, date_str, workout_title, workout_id=None, target_muscle_group="General", duration_minutes=60, notes="", exercises=None, conn=None):
    """
    Saves a user's customized schedule for a specific date in user_daily_schedules.
    exercises is a list of dicts:
    [{ 'exercise_id': int, 'sets': int, 'reps': int, 'rest_time': int, 'exercise_order': int, 'notes': str }]
    """
    close_at_end = False
    if conn is None:
        conn = database.get_db()
        close_at_end = True
    cursor = conn.cursor()

    ensure_daily_schedule_table(conn)

    if not exercises:
        exercises = []

    # 1. Delete previous custom daily schedule for this user on this date
    cursor.execute("DELETE FROM user_daily_schedules WHERE user_id = ? AND date = ?", (user_id, date_str))

    # 2. Insert new schedule rows
    for idx, ex in enumerate(exercises, start=1):
        ex_id = int(ex.get('exercise_id') or 0)
        sets = int(ex.get('sets') or 3)
        reps = int(ex.get('reps') or 10)
        rest_time = int(ex.get('rest_time') or ex.get('rest_seconds') or 90)
        order_idx = int(ex.get('exercise_order') or idx)
        ex_notes = (ex.get('notes') or '').strip()

        cursor.execute("""
            INSERT INTO user_daily_schedules (
                user_id, date, workout_id, workout_title, target_muscle_group,
                duration_minutes, exercise_id, sets, reps, rest_time,
                exercise_order, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, date_str, workout_id, workout_title, target_muscle_group,
            duration_minutes, ex_id, sets, reps, rest_time,
            order_idx, ex_notes
        ))

    # 3. If there is an active session in 'workouts' for today with status 'in_progress':
    # Safely update it so the live workout session reflects the updated schedule
    # without touching any completed historical records (Requirement 9)
    cursor.execute("""
        SELECT id FROM workouts
        WHERE user_id = ? AND date = ? AND status = 'in_progress'
        ORDER BY id DESC LIMIT 1
    """, (user_id, date_str))
    active_w = cursor.fetchone()

    if active_w:
        w_id = active_w['id']
        cursor.execute("""
            UPDATE workouts
            SET title = ?, duration_minutes = ?, target_muscle_group = ?, notes = ?
            WHERE id = ?
        """, (workout_title, duration_minutes, target_muscle_group, notes, w_id))

        # Check existing exercises in this workout
        cursor.execute("SELECT * FROM workout_exercises WHERE workout_id = ?", (w_id,))
        existing_we = cursor.fetchall()
        # Keep completed exercises
        completed_ex_ids = {row['exercise_id'] for row in existing_we if row['completed'] == 1}

        # Remove non-completed exercises and re-populate from new schedule
        cursor.execute("DELETE FROM workout_exercises WHERE workout_id = ? AND completed = 0", (w_id,))

        for idx, ex in enumerate(exercises, start=1):
            ex_id = int(ex.get('exercise_id') or 0)
            if ex_id not in completed_ex_ids:
                sets = int(ex.get('sets') or 3)
                reps = int(ex.get('reps') or 10)
                rest_time = int(ex.get('rest_time') or ex.get('rest_seconds') or 90)
                order_idx = int(ex.get('exercise_order') or idx)
                ex_notes = (ex.get('notes') or '').strip()

                cursor.execute("""
                    INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
                    VALUES (?, ?, ?, ?, 0.0, ?, 0, ?, ?)
                """, (w_id, ex_id, sets, reps, rest_time, order_idx, ex_notes))

    conn.commit()
    if close_at_end:
        conn.close()
    return True

def reset_todays_workout(user_id, date_str=None, conn=None):
    """
    Resets today's customized workout for the user:
    - Removes today's custom schedule from user_daily_schedules
    - If there is an uncompleted session (in_progress or scheduled) for today in workouts, removes it
      so today reverts to the default routine from active plan.
    - Completed workouts from previous dates and today are preserved.
    - Global exercise library remains untouched.
    """
    close_at_end = False
    if conn is None:
        conn = database.get_db()
        close_at_end = True
    cursor = conn.cursor()
    ensure_daily_schedule_table(conn)

    if date_str is None:
        date_str = date.today().isoformat()

    # 1. Remove custom schedule entries for today
    cursor.execute("DELETE FROM user_daily_schedules WHERE user_id = ? AND date = ?", (user_id, date_str))

    # 2. Remove any uncompleted workout session for today
    cursor.execute("""
        SELECT id FROM workouts
        WHERE user_id = ? AND date = ? AND status != 'completed'
    """, (user_id, date_str))
    uncompleted = cursor.fetchall()
    for w in uncompleted:
        w_id = w['id']
        cursor.execute("DELETE FROM workout_exercises WHERE workout_id = ?", (w_id,))
        cursor.execute("DELETE FROM workouts WHERE id = ?", (w_id,))

    conn.commit()
    if close_at_end:
        conn.close()
    return True

def get_todays_workout_details(user_id, user_row):
    """
    Returns today's workout information:
    - active_workout: existing session in DB for today if started/completed
    - plan_day: the scheduled plan day if not yet started
    - exercises: list of exercises with target muscle, sets, reps, rest time, instructions, completion status
    - completion_pct: 0-100%
    """
    conn = database.get_db()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    ensure_daily_schedule_table(conn)

    # 1. Check if user already has a workout for today
    cursor.execute("""
        SELECT * FROM workouts
        WHERE user_id = ? AND date = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id, today_str))
    todays_workout = cursor.fetchone()

    # 2. Check if user has a customized daily schedule in user_daily_schedules
    cursor.execute("""
        SELECT uds.*, e.name as exercise_name, e.category as category,
               e.muscle_group as target_muscle, e.difficulty, e.instructions,
               e.youtube_id, e.youtube_url, e.equipment,
               uds.rest_time as rest_seconds
        FROM user_daily_schedules uds
        JOIN exercises e ON uds.exercise_id = e.id
        WHERE uds.user_id = ? AND uds.date = ?
        ORDER BY uds.exercise_order ASC, uds.id ASC
    """, (user_id, today_str))
    custom_sched_rows = [dict(r) for r in cursor.fetchall()]

    if todays_workout:
        # Fetch exercises attached to this workout
        cursor.execute("""
            SELECT we.*, e.name as exercise_name, e.category as category,
                   e.muscle_group as target_muscle, e.difficulty, e.instructions,
                   e.youtube_id, e.youtube_url, e.equipment,
                   we.rest_seconds as rest_time
            FROM workout_exercises we
            JOIN exercises e ON we.exercise_id = e.id
            WHERE we.workout_id = ?
            ORDER BY we.order_idx ASC, we.id ASC
        """, (todays_workout['id'],))
        workout_exercises = [dict(r) for r in cursor.fetchall()]

        total_ex = len(workout_exercises)
        completed_ex = sum(1 for we in workout_exercises if we.get('completed') == 1)
        completion_pct = int((completed_ex / total_ex * 100)) if total_ex > 0 else 0

        conn.close()
        return {
            'has_workout': True,
            'is_started': True,
            'workout': dict(todays_workout),
            'exercises': workout_exercises,
            'total_exercises': total_ex,
            'completed_exercises': completed_ex,
            'completion_pct': completion_pct,
            'status': todays_workout['status'],
            'has_custom_schedule': len(custom_sched_rows) > 0,
            'custom_schedule': custom_sched_rows
        }

    # If no workout logged for today yet, but user has a custom schedule in user_daily_schedules
    if custom_sched_rows:
        first = custom_sched_rows[0]
        total_ex = len(custom_sched_rows)
        conn.close()
        return {
            'has_workout': True,
            'is_started': False,
            'is_custom_schedule': True,
            'status': 'scheduled',
            'workout': {
                'id': None,
                'title': first['workout_title'] or "Today's Custom Workout",
                'target_muscle_group': first['target_muscle_group'] or "General",
                'duration_minutes': first['duration_minutes'] or 60,
                'notes': first['notes'] or '',
                'workout_id': first.get('workout_id')
            },
            'exercises': custom_sched_rows,
            'total_exercises': total_ex,
            'completed_exercises': 0,
            'completion_pct': 0,
            'has_custom_schedule': True,
            'custom_schedule': custom_sched_rows
        }

    # 3. If no workout logged for today yet and no custom schedule, find the scheduled plan day from user's active plan
    plan_id = ensure_user_has_active_plan(user_id, user_row)
    
    # Calculate which day of the split applies today
    # (Day of week: Monday=1, Sunday=7)
    weekday = date.today().isoweekday() # 1 to 7

    cursor.execute("""
        SELECT * FROM workout_plan_days
        WHERE plan_id = ?
        ORDER BY day_number ASC
    """, (plan_id,))
    all_plan_days = cursor.fetchall()

    if not all_plan_days:
        conn.close()
        return {'has_workout': False, 'is_started': False, 'exercises': []}

    # Map weekday to plan day
    day_idx = (weekday - 1) % len(all_plan_days)
    plan_day = all_plan_days[day_idx]

    # Fetch exercises for this plan day
    cursor.execute("""
        SELECT wpe.*, e.name as exercise_name, e.category as category,
               e.muscle_group as target_muscle, e.difficulty, e.instructions,
               e.youtube_id, e.youtube_url, e.equipment,
               wpe.rest_seconds as rest_time
        FROM workout_plan_exercises wpe
        JOIN exercises e ON wpe.exercise_id = e.id
        WHERE wpe.plan_day_id = ?
        ORDER BY wpe.order_idx ASC
    """, (plan_day['id'],))
    plan_exercises = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        'has_workout': True,
        'is_started': False,
        'plan_day': dict(plan_day),
        'exercises': plan_exercises,
        'total_exercises': len(plan_exercises),
        'completed_exercises': 0,
        'completion_pct': 0,
        'status': 'scheduled',
        'has_custom_schedule': False
    }

def start_or_get_workout_session(user_id, user_row, plan_day_id=None):
    """Initializes an active workout session in the database for today."""
    conn = database.get_db()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    ensure_daily_schedule_table(conn)

    # Check if already started
    cursor.execute("SELECT id FROM workouts WHERE user_id = ? AND date = ?", (user_id, today_str))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing[0]

    # Check if user has a customized daily schedule in user_daily_schedules
    cursor.execute("""
        SELECT uds.*, e.name as exercise_name, e.category as category
        FROM user_daily_schedules uds
        JOIN exercises e ON uds.exercise_id = e.id
        WHERE uds.user_id = ? AND uds.date = ?
        ORDER BY uds.exercise_order ASC, uds.id ASC
    """, (user_id, today_str))
    custom_sched = cursor.fetchall()

    if custom_sched:
        first = custom_sched[0]
        title = first['workout_title'] or "Today's Custom Workout"
        category = first['target_muscle_group'] or "General"
        duration = first['duration_minutes'] or 60
        notes = first['notes'] or "Custom schedule session"

        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, notes)
            VALUES (?, ?, ?, ?, 0, 8, 'in_progress', ?, ?)
        """, (user_id, title, today_str, duration, category, notes))
        workout_id = cursor.lastrowid

        for idx, ce in enumerate(custom_sched, start=1):
            order_val = ce['exercise_order'] if ce['exercise_order'] else idx
            cursor.execute("""
                INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
                VALUES (?, ?, ?, ?, 0.0, ?, 0, ?, ?)
            """, (workout_id, ce['exercise_id'], ce['sets'], ce['reps'], ce['rest_time'], order_val, ce['notes']))

        conn.commit()
        conn.close()
        return workout_id

    # If plan_day_id not specified, find from active plan
    if not plan_day_id:
        plan_id = ensure_user_has_active_plan(user_id, user_row)
        weekday = date.today().isoweekday()
        cursor.execute("SELECT * FROM workout_plan_days WHERE plan_id = ? ORDER BY day_number ASC", (plan_id,))
        days = cursor.fetchall()
        day_idx = (weekday - 1) % len(days) if days else 0
        plan_day = days[day_idx]
    else:
        cursor.execute("SELECT * FROM workout_plan_days WHERE id = ?", (plan_day_id,))
        plan_day = cursor.fetchone()

    title = plan_day['day_title'] if plan_day else "Hypertrophy Training Session"
    category = plan_day['focus_category'] if plan_day else "Chest & Core"

    cursor.execute("""
        INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, notes)
        VALUES (?, ?, ?, 60, 0, 8, 'in_progress', ?, 'Active session in progress.')
    """, (user_id, title, today_str, category))
    workout_id = cursor.lastrowid

    # Populate workout_exercises from plan
    if plan_day:
        cursor.execute("""
            SELECT exercise_id, sets, reps, rest_seconds, order_idx, notes
            FROM workout_plan_exercises
            WHERE plan_day_id = ?
            ORDER BY order_idx ASC
        """, (plan_day['id'],))
        plan_exs = cursor.fetchall()

        for idx, pe in enumerate(plan_exs, start=1):
            order_val = pe['order_idx'] if pe['order_idx'] else idx
            cursor.execute("""
                INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
                VALUES (?, ?, ?, ?, 0.0, ?, 0, ?, ?)
            """, (workout_id, pe['exercise_id'], pe['sets'], pe['reps'], pe['rest_seconds'], order_val, pe['notes']))

    conn.commit()
    conn.close()
    return workout_id

def toggle_exercise_completion_status(workout_id, exercise_id, completed_status, weight_kg=0.0, reps=None):
    """Marks an exercise in the active workout as completed or pending, updating volume."""
    conn = database.get_db()
    cursor = conn.cursor()

    if reps is not None:
        cursor.execute("""
            UPDATE workout_exercises
            SET completed = ?, weight_kg = ?, reps = ?
            WHERE workout_id = ? AND id = ?
        """, (completed_status, weight_kg, reps, workout_id, exercise_id))
    else:
        cursor.execute("""
            UPDATE workout_exercises
            SET completed = ?, weight_kg = ?
            WHERE workout_id = ? AND id = ?
        """, (completed_status, weight_kg, workout_id, exercise_id))

    # Recalculate workout volume & completion rate
    cursor.execute("SELECT sets, reps, weight_kg, completed FROM workout_exercises WHERE workout_id = ?", (workout_id,))
    rows = cursor.fetchall()
    total_volume = sum(r['sets'] * r['reps'] * r['weight_kg'] for r in rows if r['completed'] == 1)
    total_count = len(rows)
    completed_count = sum(1 for r in rows if r['completed'] == 1)
    rate = int((completed_count / total_count * 100)) if total_count > 0 else 0

    cursor.execute("""
        UPDATE workouts
        SET total_volume_kg = ?, completion_rate = ?
        WHERE id = ?
    """, (round(total_volume, 1), rate, workout_id))

    conn.commit()
    conn.close()
    return rate

def calculate_dashboard_workout_stats(user_id, training_days_target=4):
    """
    Computes:
    - Weekly workout count
    - Active workout streak
    - Total workouts completed
    - Total volume lifted
    """
    conn = database.get_db()
    cursor = conn.cursor()
    today = date.today()

    # Calculate start of this calendar week (Monday)
    start_of_week = today - timedelta(days=today.weekday())

    cursor.execute("""
        SELECT COUNT(*) as weekly_count
        FROM workouts
        WHERE user_id = ? AND date >= ? AND status = 'completed'
    """, (user_id, start_of_week.isoformat()))

    weekly_count = cursor.fetchone()['weekly_count']

    # Total completed workouts and volume
    cursor.execute("""
        SELECT COUNT(*) as total_completed,
               COALESCE(SUM(total_volume_kg), 0) as total_volume
        FROM workouts
        WHERE user_id = ? AND status = 'completed'
    """, (user_id,))

    overall = cursor.fetchone()

    # Calculate active workout streak
    cursor.execute("""
        SELECT DISTINCT date
        FROM workouts
        WHERE user_id = ? AND status = 'completed'
        ORDER BY date DESC
    """, (user_id,))

    dates = [
        r['date']
        if isinstance(r['date'], date)
        else datetime.strptime(str(r['date']), "%Y-%m-%d").date()
        for r in cursor.fetchall()
    ]

    streak = 0

    if dates:
        check_date = today

        # If no workout today, check yesterday
        if check_date not in dates:
            check_date = today - timedelta(days=1)

        while check_date in dates:
            streak += 1
            check_date -= timedelta(days=1)

    # Fallback for workouts completed this week
    if streak == 0 and weekly_count > 0:
        streak = weekly_count

    conn.close()

    target = training_days_target or 4

    return {
        'weekly_count': weekly_count,
        'weekly_target': target,
        'weekly_pct': min(
            100,
            int((weekly_count / target) * 100)
        ),
        'streak': streak,
        'total_completed': overall['total_completed'],
        'total_volume': overall['total_volume']
    }
def get_all_plans_with_details(conn=None):
    """
    Fetches all workout plans with their days and exercises
    so users can browse workouts, preview routines, and select them.
    """
    close_at_end = False
    if conn is None:
        conn = database.get_db()
        close_at_end = True
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workout_plans ORDER BY is_default DESC, id ASC")
    plans = [dict(r) for r in cursor.fetchall()]

    for plan in plans:
        cursor.execute("""
            SELECT * FROM workout_plan_days
            WHERE plan_id = ?
            ORDER BY day_number ASC
        """, (plan['id'],))
        days = [dict(d) for d in cursor.fetchall()]
        for day in days:
            cursor.execute("""
                SELECT wpe.*, e.name as exercise_name, e.category, e.muscle_group, e.equipment, e.difficulty, e.instructions,
                       e.youtube_id, e.youtube_url
                FROM workout_plan_exercises wpe
                JOIN exercises e ON wpe.exercise_id = e.id
                WHERE wpe.plan_day_id = ?
                ORDER BY wpe.order_idx ASC, wpe.id ASC
            """, (day['id'],))
            day['exercises'] = [dict(e) for e in cursor.fetchall()]
        plan['days'] = days

    if close_at_end:
        conn.close()
    return plans


def get_user_workout(user_id, workout_id):
    """Fetches a specific workout for the user with all its exercises ordered by order_idx."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id))
    w = cursor.fetchone()
    if not w:
        conn.close()
        return None
    workout = dict(w)

    cursor.execute("""
        SELECT we.*, e.name as exercise_name, e.category as category, e.muscle_group as target_muscle,
               e.equipment, e.difficulty, e.instructions,
               e.youtube_id, e.youtube_url
        FROM workout_exercises we
        JOIN exercises e ON we.exercise_id = e.id
        WHERE we.workout_id = ?
        ORDER BY we.order_idx ASC, we.id ASC
    """, (workout_id,))
    workout['exercises'] = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return workout


def add_routine_to_user_schedule(user_id, plan_day_id, workout_date=None, status='scheduled'):
    """
    Adds a selected routine (plan day) to the user's personal workout plan for a given date.
    Copies prescribed exercises to workout_exercises.
    Does NOT modify the global workout_plans or exercises.
    """
    if not workout_date:
        workout_date = date.today().isoformat()
    
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM workout_plan_days WHERE id = ?", (plan_day_id,))
    plan_day = cursor.fetchone()
    if not plan_day:
        conn.close()
        return None

    title = plan_day['day_title']
    category = plan_day['focus_category']

    cursor.execute("""
        INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, completion_rate, notes)
        VALUES (?, ?, ?, 60, 0, 8, ?, ?, 0, 'Added to personal schedule from Workout Library.')
    """, (user_id, title, workout_date, status, category))
    workout_id = cursor.lastrowid

    cursor.execute("""
        SELECT exercise_id, sets, reps, rest_seconds, order_idx, notes
        FROM workout_plan_exercises
        WHERE plan_day_id = ?
        ORDER BY order_idx ASC, id ASC
    """, (plan_day_id,))
    p_exs = cursor.fetchall()

    for idx, pe in enumerate(p_exs, start=1):
        order_val = pe['order_idx'] if pe['order_idx'] else idx
        cursor.execute("""
            INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
            VALUES (?, ?, ?, ?, 0.0, ?, 0, ?, ?)
        """, (workout_id, pe['exercise_id'], pe['sets'], pe['reps'], pe['rest_seconds'], order_val, pe['notes']))

    conn.commit()
    conn.close()
    return workout_id


def replace_user_workout(user_id, workout_id, plan_day_id):
    """
    Replaces an existing workout on user's plan with a routine from a plan day.
    Replaces title, category, and all exercises.
    Only modifies the current user's workout data.
    """
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id))
    w = cursor.fetchone()
    if not w:
        conn.close()
        return False

    cursor.execute("SELECT * FROM workout_plan_days WHERE id = ?", (plan_day_id,))
    plan_day = cursor.fetchone()
    if not plan_day:
        conn.close()
        return False

    # Update workout metadata
    cursor.execute("""
        UPDATE workouts SET
            title = ?,
            target_muscle_group = ?,
            total_volume_kg = 0,
            completion_rate = 0,
            notes = 'Replaced with routine from workout catalog.'
        WHERE id = ? AND user_id = ?
    """, (plan_day['day_title'], plan_day['focus_category'], workout_id, user_id))

    # Remove existing exercises for this workout
    cursor.execute("DELETE FROM workout_exercises WHERE workout_id = ?", (workout_id,))

    # Insert new exercises
    cursor.execute("""
        SELECT exercise_id, sets, reps, rest_seconds, order_idx, notes
        FROM workout_plan_exercises
        WHERE plan_day_id = ?
        ORDER BY order_idx ASC, id ASC
    """, (plan_day_id,))
    p_exs = cursor.fetchall()

    for idx, pe in enumerate(p_exs, start=1):
        order_val = pe['order_idx'] if pe['order_idx'] else idx
        cursor.execute("""
            INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
            VALUES (?, ?, ?, ?, 0.0, ?, 0, ?, ?)
        """, (workout_id, pe['exercise_id'], pe['sets'], pe['reps'], pe['rest_seconds'], order_val, pe['notes']))

    conn.commit()
    conn.close()
    return True


def edit_workout_details(user_id, workout_id, title, workout_date, duration_minutes, intensity_rating, target_muscle_group, notes):
    """Edits workout header information for a user's workout."""
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE workouts SET
            title = ?,
            date = ?,
            duration_minutes = ?,
            intensity_rating = ?,
            target_muscle_group = ?,
            notes = ?
        WHERE id = ? AND user_id = ?
    """, (title, workout_date, duration_minutes, intensity_rating, target_muscle_group, notes, workout_id, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_user_workout(user_id, workout_id):
    """
    Safely deletes a workout from the user's plan.
    Does NOT affect the global exercises or workout_plans catalog.
    Only deletes the user's workout row (and cascades to workout_exercises).
    """
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def mark_workout_completed(user_id, workout_id, duration_minutes=None, intensity_rating=None, notes=None):
    """
    Marks a workout session as completed.
    Marks all attached exercises as completed if not already done,
    recalculates total volume and updates streak/status.
    """
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id))
    w = cursor.fetchone()
    if not w:
        conn.close()
        return False

    # Mark all exercises as completed
    cursor.execute("""
        UPDATE workout_exercises
        SET completed = 1
        WHERE workout_id = ?
    """, (workout_id,))

    # Compute volume
    cursor.execute("SELECT sets, reps, weight_kg FROM workout_exercises WHERE workout_id = ?", (workout_id,))
    rows = cursor.fetchall()
    total_volume = sum((r['sets'] or 1) * (r['reps'] or 1) * (r['weight_kg'] or 0.0) for r in rows)

    dur = duration_minutes if duration_minutes is not None else (w['duration_minutes'] or 60)
    intensity = intensity_rating if intensity_rating is not None else (w['intensity_rating'] or 8)
    notes_val = notes if notes is not None else (w['notes'] or 'Marked completed.')

    cursor.execute("""
        UPDATE workouts SET
            status = 'completed',
            completion_rate = 100,
            duration_minutes = ?,
            intensity_rating = ?,
            total_volume_kg = ?,
            notes = ?
        WHERE id = ? AND user_id = ?
    """, (dur, intensity, round(total_volume, 1), notes_val, workout_id, user_id))

    conn.commit()
    conn.close()
    return True


def add_exercise_to_workout(user_id, workout_id, exercise_id, sets=3, reps=10, weight_kg=0.0, rest_seconds=90, notes=None):
    """Adds an individual exercise to a specific user workout with proper ordering."""
    conn = database.get_db()
    cursor = conn.cursor()

    # Verify workout belongs to user
    cursor.execute("SELECT id FROM workouts WHERE id = ? AND user_id = ?", (workout_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return None

    # Get max order_idx
    cursor.execute("SELECT COALESCE(MAX(order_idx), 0) FROM workout_exercises WHERE workout_id = ?", (workout_id,))
    max_idx = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, order_idx, notes)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
    """, (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, max_idx + 1, notes or 'Added to session'))
    new_we_id = cursor.lastrowid

    # Recalculate workout completion rate
    _recalc_workout_rate(cursor, workout_id)

    conn.commit()
    conn.close()
    return new_we_id


def remove_exercise_from_workout(user_id, we_id):
    """Safely removes an exercise from a user's workout."""
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT we.id, we.workout_id
        FROM workout_exercises we
        JOIN workouts w ON we.workout_id = w.id
        WHERE we.id = ? AND w.user_id = ?
    """, (we_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    workout_id = row['workout_id']
    cursor.execute("DELETE FROM workout_exercises WHERE id = ?", (we_id,))

    _recalc_workout_rate(cursor, workout_id)

    conn.commit()
    conn.close()
    return True


def update_exercise_in_workout(user_id, we_id, sets=None, reps=None, rest_seconds=None, weight_kg=None, notes=None):
    """Edits individual exercise parameters (sets, reps, rest time, weight, notes) in a user's workout."""
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT we.*, w.id as wid
        FROM workout_exercises we
        JOIN workouts w ON we.workout_id = w.id
        WHERE we.id = ? AND w.user_id = ?
    """, (we_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    new_sets = sets if sets is not None else row['sets']
    new_reps = reps if reps is not None else row['reps']
    new_rest = rest_seconds if rest_seconds is not None else row['rest_seconds']
    new_weight = weight_kg if weight_kg is not None else row['weight_kg']
    new_notes = notes if notes is not None else row['notes']

    cursor.execute("""
        UPDATE workout_exercises SET
            sets = ?,
            reps = ?,
            rest_seconds = ?,
            weight_kg = ?,
            notes = ?
        WHERE id = ?
    """, (new_sets, new_reps, new_rest, new_weight, new_notes, we_id))

    _recalc_workout_rate(cursor, row['wid'])

    conn.commit()
    conn.close()
    return True


def reorder_workout_exercise(user_id, we_id, direction):
    """
    Reorders an exercise within a workout ('up' or 'down').
    Swaps order_idx with adjacent exercise.
    """
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT we.id, we.workout_id, we.order_idx
        FROM workout_exercises we
        JOIN workouts w ON we.workout_id = w.id
        WHERE we.id = ? AND w.user_id = ?
    """, (we_id, user_id))
    current = cursor.fetchone()
    if not current:
        conn.close()
        return False

    workout_id = current['workout_id']

    # Fetch all exercises in order for this workout
    cursor.execute("""
        SELECT id, order_idx
        FROM workout_exercises
        WHERE workout_id = ?
        ORDER BY order_idx ASC, id ASC
    """, (workout_id,))
    all_exs = [dict(r) for r in cursor.fetchall()]

    curr_pos = None
    for i, ex in enumerate(all_exs):
        if ex['id'] == we_id:
            curr_pos = i
            break

    if curr_pos is None:
        conn.close()
        return False

    swap_pos = curr_pos - 1 if direction == 'up' else curr_pos + 1
    if 0 <= swap_pos < len(all_exs):
        # Swap
        all_exs[curr_pos], all_exs[swap_pos] = all_exs[swap_pos], all_exs[curr_pos]

        # Update order_idx in DB for all
        for pos, ex in enumerate(all_exs, start=1):
            cursor.execute("UPDATE workout_exercises SET order_idx = ? WHERE id = ?", (pos, ex['id']))

        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def _recalc_workout_rate(cursor, workout_id):
    """Helper to recalculate total volume and completion rate for a workout."""
    cursor.execute("SELECT sets, reps, weight_kg, completed FROM workout_exercises WHERE workout_id = ?", (workout_id,))
    rows = cursor.fetchall()
    total_volume = sum((r['sets'] or 1) * (r['reps'] or 1) * (r['weight_kg'] or 0.0) for r in rows if r['completed'] == 1)
    total_count = len(rows)
    completed_count = sum(1 for r in rows if r['completed'] == 1)
    rate = int((completed_count / total_count * 100)) if total_count > 0 else 0

    cursor.execute("""
        UPDATE workouts
        SET total_volume_kg = ?, completion_rate = ?
        WHERE id = ?
    """, (round(total_volume, 1), rate, workout_id))


def compute_workout_categories(workout, workout_exercises=None):
    """
    Intelligently determines all muscle/workout categories for a given workout.
    Inspects:
    1. constituent exercise categories, muscle groups, and names
    2. target_muscle_group database field
    3. workout title
    4. workout reflections/notes
    Handles compound values (e.g. 'Chest & Triceps', 'Back & Biceps'),
    synonyms (Lats -> Back, Quads -> Legs), and interchangeable Core/Abs.
    """
    import re
    cats = set()
    w_dict = dict(workout) if workout else {}

    # 1. Inspect constituent exercises (primary category)
    for raw_ex in (workout_exercises or []):
        ex = dict(raw_ex) if raw_ex else {}
        cat = (ex.get('exercise_category') or ex.get('category') or '').strip()
        if cat:
            cats.add(cat)
            if cat.lower() in ['abs', 'core']:
                cats.add('Abs')
                cats.add('Core')

    # 2. Text inspection of title, target_muscle_group, notes
    combined_text = f"{w_dict.get('title', '')} {w_dict.get('target_muscle_group', '')} {w_dict.get('notes', '')}".lower()
    mapping = {
        r'\bchest\b|\bpecs?\b': ['Chest'],
        r'\bback\b|\blats?\b': ['Back'],
        r'\bshoulders?\b|\bdelts?\b': ['Shoulders'],
        r'\bbiceps?\b': ['Biceps'],
        r'\btriceps?\b': ['Triceps'],
        r'\barms?\b': ['Biceps', 'Triceps'],
        r'\blegs?\b|\bquads?\b|\bcalves\b|\bcalf\b': ['Legs'],
        r'\bcore\b|\babs\b|\babdom': ['Core', 'Abs']
    }

    for pattern, targets in mapping.items():
        if re.search(pattern, combined_text):
            for t in targets:
                cats.add(t)

    # 3. Explicit parsing of target_muscle_group if non-empty
    tmg = (w_dict.get('target_muscle_group') or '').strip()
    if tmg and tmg.lower() != 'general':
        for part in re.split(r'[,&+/]|\band\b', tmg, flags=re.IGNORECASE):
            cleaned = part.strip()
            if cleaned:
                clow = cleaned.lower()
                if 'chest' in clow: cats.add('Chest')
                elif 'back' in clow: cats.add('Back')
                elif 'shoulder' in clow: cats.add('Shoulders')
                elif 'bicep' in clow: cats.add('Biceps')
                elif 'tricep' in clow: cats.add('Triceps')
                elif 'leg' in clow or 'quad' in clow: cats.add('Legs')
                elif 'core' in clow or 'ab' in clow:
                    cats.add('Core')
                    cats.add('Abs')
                else:
                    cats.add(cleaned.title())

    if not cats:
        cats.add('General')

    return sorted(list(cats))


def category_matches(categories_list, target_category):
    """
    Checks if target_category matches a list of categories case-insensitively.
    Handles 'All', 'Abs' <-> 'Core', and compound values.
    """
    if not target_category or target_category.strip().lower() in ['all', 'all categories']:
        return True

    target = target_category.strip().lower()
    norm_cats = [str(c).strip().lower() for c in (categories_list or [])]

    if target in norm_cats:
        return True

    # Abs and Core are interchangeable
    if target in ['abs', 'core'] and ('abs' in norm_cats or 'core' in norm_cats):
        return True

    for c in norm_cats:
        if target in c or c in target:
            return True

    return False
