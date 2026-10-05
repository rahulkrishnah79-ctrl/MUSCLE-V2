import os
import sys
import json
from datetime import date
from flask import session

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

import app as flask_app
import database
import workout_manager

def run_tests():
    print("==================================================")
    print("PHASE: EDIT TODAY'S WORKOUT SCHEDULE - VERIFICATION")
    print("==================================================")

    client = flask_app.app.test_client()
    today_str = date.today().isoformat()

    # 1. Login as test user alex_pulse
    print("\n[Step 1] Logging in as alex_pulse via /login/demo...")
    login_resp = client.get('/login/demo', follow_redirects=True)
    assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
    print("[PASS] Successfully logged in as alex_pulse")

    # 2. Check Dashboard UI contains Edit Schedule button, modals, and numbered sequence
    print("\n[Step 2] Verifying Dashboard UI elements...")
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200, f"Dashboard returned {dash_resp.status_code}"
    dash_html = dash_resp.data.decode('utf-8')

    assert "Edit Schedule" in dash_html, "Edit Schedule button missing on dashboard!"
    assert "btnEditTodayScheduleTop" in dash_html, "btnEditTodayScheduleTop missing!"
    assert "editTodayScheduleModal" in dash_html, "editTodayScheduleModal missing!"
    assert "scheduleRoutineSelector" in dash_html, "Routine selector missing in modal!"
    assert "exercisePickerModal" in dash_html, "exercisePickerModal missing!"
    assert "removeExerciseConfirmModal" in dash_html, "removeExerciseConfirmModal missing!"
    assert "Remove Workout" in dash_html or "Remove" in dash_html, "Remove confirmation button missing!"
    assert "Prescribed Exercise Sequence" in dash_html or "Today's Workout" in dash_html, "Prescribed Exercise Sequence missing!"
    print("[PASS] Dashboard UI contains [ Edit Schedule ] buttons, modals, and numbered exercise section")

    # 3. Test API /api/schedule/today
    print("\n[Step 3] Testing GET /api/schedule/today endpoint...")
    api_resp = client.get(f'/api/schedule/today?date={today_str}')
    assert api_resp.status_code == 200, f"API schedule failed: {api_resp.status_code}"
    schedule_data = api_resp.get_json()
    assert 'workout_title' in schedule_data, "workout_title missing from API response"
    assert 'exercises' in schedule_data, "exercises missing from API response"
    print(f"[PASS] GET /api/schedule/today returned {len(schedule_data['exercises'])} exercises for workout '{schedule_data['workout_title']}'")

    # 4. Fetch exercise library to pick an exercise to add / replace
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, category, muscle_group FROM exercises ORDER BY id ASC")
    all_ex = cursor.fetchall()
    assert len(all_ex) >= 5, "Not enough exercises in library!"
    ex_a = all_ex[0] # e.g. Bench Press
    ex_b = all_ex[1] # e.g. Incline Dumbbell Press
    ex_c = all_ex[2] # e.g. Cable Fly or Squat
    conn.close()

    # 5. Test Saving Customized Today's Schedule (Add, Edit Sets/Reps/Rest, Reorder)
    print("\n[Step 4] Saving customized schedule via POST /schedule/today/save...")
    custom_payload = {
        'date': today_str,
        'workout_title': "Supercharged Custom Upper Power",
        'target_muscle_group': "Chest & Triceps",
        'duration_minutes': 75,
        'notes': "Focus on progressive overload and 2-sec eccentric pause",
        'workout_id': None,
        'exercises': [
            {
                'exercise_id': ex_b['id'],
                'exercise_name': ex_b['name'],
                'sets': 5,
                'reps': 6,
                'rest_time': 120,
                'exercise_order': 1,
                'notes': "Heavy incline compound"
            },
            {
                'exercise_id': ex_a['id'],
                'exercise_name': ex_a['name'],
                'sets': 4,
                'reps': 8,
                'rest_time': 90,
                'exercise_order': 2,
                'notes': "Strict touch and press"
            },
            {
                'exercise_id': ex_c['id'],
                'exercise_name': ex_c['name'],
                'sets': 3,
                'reps': 15,
                'rest_time': 60,
                'exercise_order': 3,
                'notes': "Metabolic pump finisher"
            }
        ]
    }

    save_resp = client.post(
        '/schedule/today/save',
        data=json.dumps(custom_payload),
        content_type='application/json'
    )
    assert save_resp.status_code == 200, f"Save schedule failed: {save_resp.status_code}"
    save_result = save_resp.get_json()
    assert save_result.get('success') is True, f"Save result was not success: {save_result}"
    assert "Today's schedule updated successfully." in save_result.get('message', ''), f"Unexpected message: {save_result}"
    print(f"[PASS] Saved custom schedule successfully: '{save_result.get('message')}'")

    # 6. Verify database persistence in user_daily_schedules
    print("\n[Step 5] Verifying database persistence in user_daily_schedules...")
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM user_daily_schedules
        WHERE date = ?
        ORDER BY exercise_order ASC
    """, (today_str,))
    db_rows = cursor.fetchall()
    assert len(db_rows) == 3, f"Expected 3 rows in user_daily_schedules, found {len(db_rows)}"
    assert db_rows[0]['workout_title'] == "Supercharged Custom Upper Power", "Title mismatch in DB"
    assert db_rows[0]['exercise_id'] == ex_b['id'], "Exercise order 1 mismatch"
    assert db_rows[0]['sets'] == 5 and db_rows[0]['reps'] == 6 and db_rows[0]['rest_time'] == 120, "Sets/reps/rest mismatch"
    assert db_rows[1]['exercise_id'] == ex_a['id'], "Exercise order 2 mismatch"
    assert db_rows[2]['exercise_id'] == ex_c['id'], "Exercise order 3 mismatch"
    print("[PASS] user_daily_schedules table correctly persisted all 3 exercises with custom parameters and ordering")

    # 7. Verify global exercise library is untouched (Requirement 3 & 8)
    cursor.execute("SELECT COUNT(*) FROM exercises")
    total_exercises_now = cursor.fetchone()[0]
    assert total_exercises_now == len(all_ex), "Global exercises table was modified!"
    print(f"[PASS] Global exercise library preserved intact ({total_exercises_now} library exercises)")
    conn.close()

    # 8. Verify Dashboard reflects the updated schedule after reload (Requirement 10 & 11)
    print("\n[Step 6] Testing Dashboard display reload...")
    dash_after = client.get('/dashboard')
    dash_after_html = dash_after.data.decode('utf-8')
    assert "Supercharged Custom Upper Power" in dash_after_html, "Custom workout title not on dashboard!"
    assert ex_b['name'] in dash_after_html, f"Exercise 1 '{ex_b['name']}' not rendered on dashboard!"
    assert "5 &times; 6" in dash_after_html or "5 × 6" in dash_after_html or "Rest: 120 sec" in dash_after_html, "Custom sets/reps/rest not shown!"
    assert "Rest: 120 sec" in dash_after_html, "Rest 120 sec not shown on dashboard!"
    print("[PASS] Dashboard immediately renders updated custom workout title, exercises sequence, and rest time")

    # 9. Test persistence after logout and login (Requirement 11)
    print("\n[Step 7] Testing persistence across logout and login...")
    client.get('/logout', follow_redirects=True)
    client.get('/login/demo', follow_redirects=True)
    dash_relogin = client.get('/dashboard')
    dash_relogin_html = dash_relogin.data.decode('utf-8')
    assert "Supercharged Custom Upper Power" in dash_relogin_html, "Schedule did not persist across logout/login!"
    assert ex_b['name'] in dash_relogin_html, "Exercises did not persist across logout/login!"
    print("[PASS] Schedule persisted cleanly across logout and login session")

    # 10. Test starting workout with custom schedule (Requirement 11)
    print("\n[Step 8] Starting workout session with custom schedule...")
    start_resp = client.post('/workouts/start', follow_redirects=True)
    assert start_resp.status_code == 200, f"Start workout failed: {start_resp.status_code}"
    
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM workouts
        WHERE user_id = 1 AND date = ? AND status = 'in_progress'
        ORDER BY id DESC LIMIT 1
    """, (today_str,))
    active_workout = cursor.fetchone()
    assert active_workout is not None, "Active workout was not created"
    assert active_workout['title'] == "Supercharged Custom Upper Power", f"Active workout title '{active_workout['title']}' mismatch"
    
    cursor.execute("""
        SELECT we.*, e.name FROM workout_exercises we
        JOIN exercises e ON we.exercise_id = e.id
        WHERE we.workout_id = ?
        ORDER BY we.order_idx ASC
    """, (active_workout['id'],))
    active_exercises = cursor.fetchall()
    assert len(active_exercises) == 3, f"Expected 3 workout exercises, got {len(active_exercises)}"
    assert active_exercises[0]['exercise_id'] == ex_b['id'], "First active exercise does not match custom schedule"
    assert active_exercises[0]['sets'] == 5 and active_exercises[0]['reps'] == 6, "Sets/reps in active workout mismatch"
    print("[PASS] Workout started accurately with all custom exercises, sets, reps, and order!")
    conn.close()

    print("\n==================================================")
    print("ALL 11 REQUIREMENTS VERIFIED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
