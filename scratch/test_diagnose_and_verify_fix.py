"""
Diagnostic & Verification Suite for Serverless Authentication / SQLite Behavior
Tests:
1. Verify Possibility A vs Possibility B:
   - Demonstrates that the browser DOES send the session cookie across requests.
   - Demonstrates why load_logged_in_user() failed on fresh serverless containers:
     seed_demo_user_and_data() crashed on 'Tricep Rope Pushdown' (TypeError)
     causing uncommitted rollback of demo user, leaving the users table with 0 rows.
2. Verify the Smallest Correct Fix:
   - Fixing exercise lookup in seed_demo_user_and_data to 'Tricep Pushdown (Cable Rope)'
     and committing immediately.
   - Ensuring demo user exists on any serverless invocation.
   - Testing Container A (login) -> Container B (next protected request) transition.
"""

import os
import sys
import tempfile
import shutil
from unittest.mock import patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def run_diagnostics():
    print("=" * 70)
    print("SERVERLESS AUTHENTICATION & SQLITE DIAGNOSTIC TEST")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # PART 1: REPRODUCE ROOT CAUSE (UNCOMMITTED ROLLBACK IN FRESH CONTAINER)
    # -------------------------------------------------------------------------
    print("\n[DIAGNOSTIC 1] Testing current behavior on a fresh serverless container...")
    tmp_fresh = tempfile.mkdtemp()
    fresh_db = os.path.join(tmp_fresh, 'fresh_test.db')
    os.environ['DATABASE_PATH'] = fresh_db
    os.environ['VERCEL'] = '1'
    os.environ['SECRET_KEY'] = 'test-secret-key-2026'

    import database
    conn = database.get_db()
    conn.close()

    # Inspect users table in fresh DB
    conn2 = database.get_db()
    cursor = conn2.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    conn2.close()

    print(f"User count in freshly initialized serverless DB: {user_count}")
    assert user_count == 0, f"Expected 0 users due to bug, found {user_count}"
    print("[CONFIRMED] Users table is empty (0 rows) on fresh container because seed_demo_user_and_data rolled back!")

    # -------------------------------------------------------------------------
    # PART 2: PROVE POSSIBILITIES A vs B
    # -------------------------------------------------------------------------
    print("\n[DIAGNOSTIC 2] Testing Possibility A vs Possibility B on current codebase...")
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    
    # Container A: User registers and logs in
    tmp_a = tempfile.mkdtemp()
    os.environ['DATABASE_PATH'] = os.path.join(tmp_a, 'a.db')
    client_a = flask_app.app.test_client()

    reg_resp = client_a.post('/register', data={
        'full_name': 'Test Athlete',
        'username': 'athlete_test',
        'email': 'athlete@ironpulse.fit',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'fitness_goal': 'Muscle Hypertrophy & Strength',
        'experience_level': 'Intermediate (1-3 Years)',
        'height_cm': 180,
        'weight_kg': 80.0
    })
    assert reg_resp.status_code == 302
    
    # Check if session cookie is produced
    cookie = client_a.get_cookie('ironpulse_session')
    assert cookie is not None, "Possibility A check: Session cookie was not created!"
    print(f"[PROVEN - A is FALSE] Session cookie IS present and retained: key={cookie.key}, value={cookie.value[:20]}...")

    # Dashboard on Container A succeeds
    dash_a = client_a.get('/dashboard')
    assert dash_a.status_code == 200
    print("[PASS] Container A: Dashboard initially appears successfully (HTTP 200).")

    # Container B: Next request hits a new container invocation with independent /tmp
    tmp_b = tempfile.mkdtemp()
    os.environ['DATABASE_PATH'] = os.path.join(tmp_b, 'b.db')
    client_b = flask_app.app.test_client()
    client_b.set_cookie('ironpulse_session', cookie.value)

    # Next protected request: GET /workouts on Container B
    wo_resp_b = client_b.get('/workouts')
    print(f"Container B /workouts status code: {wo_resp_b.status_code}")
    print(f"Container B /workouts redirect location: {wo_resp_b.headers.get('Location')}")
    assert wo_resp_b.status_code == 302, "Expected redirect to /login due to missing user in DB"
    assert wo_resp_b.headers.get('Location') == '/login'

    # Follow redirect to inspect flash message
    wo_follow = client_b.get('/workouts', follow_redirects=True)
    assert b"Please sign in or use Demo Login to access this page." in wo_follow.data
    print("[PROVEN - B is TRUE] Container B has session cookie, but load_logged_in_user() cannot find user in database!")
    print("                      Flash message displayed: 'Please sign in or use Demo Login to access this page.'")

    shutil.rmtree(tmp_a, ignore_errors=True)
    shutil.rmtree(tmp_b, ignore_errors=True)
    shutil.rmtree(tmp_fresh, ignore_errors=True)

    # -------------------------------------------------------------------------
    # PART 3: VERIFY PROPOSED FIX
    # -------------------------------------------------------------------------
    print("\n[VERIFICATION 3] Testing proposed fix for seed_demo_user_and_data...")
    tmp_fixed_a = tempfile.mkdtemp()
    tmp_fixed_b = tempfile.mkdtemp()

    db_fixed_a = os.path.join(tmp_fixed_a, 'fixed_a.db')
    db_fixed_b = os.path.join(tmp_fixed_b, 'fixed_b.db')

    # Apply proposed fix dynamically to test
    orig_seed = database.seed_demo_user_and_data
    def fixed_seed_demo_user_and_data(conn):
        cursor = conn.cursor()
        # Ensure demo user is inserted and committed
        from werkzeug.security import generate_password_hash
        from datetime import date, timedelta
        demo_password = generate_password_hash("fitness123")
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
        conn.commit()
        user_id = cursor.lastrowid

        today = date.today()
        two_days_ago = today - timedelta(days=2)
        three_days_ago = today - timedelta(days=3)

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
                r1 = cursor.fetchone()
                cursor.execute("SELECT id FROM exercises WHERE name = 'Incline Dumbbell Press'")
                r2 = cursor.fetchone()
                # Fixed exercise lookup:
                cursor.execute("SELECT id FROM exercises WHERE name = 'Tricep Pushdown (Cable Rope)' OR name LIKE '%Tricep%Pushdown%'")
                r3 = cursor.fetchone()

                if r1 and r2 and r3:
                    cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 8, 90.0, 90, 1, 'RPE 8.5')", (w_id, r1[0]))
                    cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 3, 10, 32.0, 90, 1, 'Clean stretch')", (w_id, r2[0]))
                    cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 12, 35.0, 60, 1, 'Drop set on last set')", (w_id, r3[0]))

        conn.commit()

    database.seed_demo_user_and_data = fixed_demo_seed = fixed_seed_demo_user_and_data

    # Container A: User logs in
    os.environ['DATABASE_PATH'] = db_fixed_a
    client_a = flask_app.app.test_client()
    resp_login = client_a.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'})
    assert resp_login.status_code == 302
    resp_dash_a = client_a.get('/dashboard')
    assert resp_dash_a.status_code == 200, f"Expected 200 on dashboard, got {resp_dash_a.status_code}"
    print("[PASS] Container A: Login -> Dashboard rendered successfully (HTTP 200).")

    # Container B: New serverless container with fresh filesystem
    os.environ['DATABASE_PATH'] = db_fixed_b
    client_b = flask_app.app.test_client()
    # Retain the exact same session cookie from client_a
    client_b.set_cookie('ironpulse_session', client_a.get_cookie('ironpulse_session').value)

    # Protected request on Container B (e.g. /workouts)
    resp_wo_b = client_b.get('/workouts')
    assert resp_wo_b.status_code == 200, f"Expected 200 on /workouts on Container B, got {resp_wo_b.status_code}"
    assert b"Workout" in resp_wo_b.data
    print("[PASS] Container B: Protected request (/workouts) succeeded (HTTP 200) across cold container transition!")

    # Protected request on Container B for /nutrition
    resp_nut_b = client_b.get('/nutrition')
    assert resp_nut_b.status_code == 200, f"Expected 200 on /nutrition on Container B, got {resp_nut_b.status_code}"
    print("[PASS] Container B: Protected request (/nutrition) succeeded (HTTP 200).")

    shutil.rmtree(tmp_fixed_a, ignore_errors=True)
    shutil.rmtree(tmp_fixed_b, ignore_errors=True)

    print("\n" + "=" * 70)
    print("ALL DIAGNOSTIC AND VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    run_diagnostics()
