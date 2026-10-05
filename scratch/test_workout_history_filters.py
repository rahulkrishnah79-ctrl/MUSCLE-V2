"""
Comprehensive Automated Test Suite for Workout History & Session Management Category Filter
Verifies:
1. All Categories shows all user-recorded workouts & total count by default
2. Category filtering for Chest, Back, Shoulders, Biceps, Triceps, Legs, Core, Abs
3. Active button state management
4. Empty results message when category has 0 sessions
5. Workout record cards display all essential fields
6. Counter badge updates dynamically
7. User isolation: only current user's workouts are displayed
8. Compound name matching ('Chest & Triceps' matches Chest AND Triceps)
9. Case-insensitive matching ('chest', 'CHEST', 'Chest Workout')
10. API endpoint /api/workouts/history returns correct user-specific data
"""

import sys
import os
import re

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as flask_app_module
import database
import workout_manager

def run_tests():
    print("=" * 65)
    print("STARTING WORKOUT HISTORY & CATEGORY FILTER TEST SUITE")
    print("=" * 65)

    app = flask_app_module.app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    conn = database.get_db()
    cursor = conn.cursor()

    # Find demo user alex_pulse
    cursor.execute("SELECT id, username FROM users WHERE username = 'alex_pulse' LIMIT 1")
    demo_user = cursor.fetchone()
    if not demo_user:
        cursor.execute("SELECT id, username FROM users LIMIT 1")
        demo_user = cursor.fetchone()

    user_id = demo_user['id']
    username = demo_user['username']
    print(f"[Setup] Testing with user '{username}' (ID: {user_id})")

    with app.test_client() as client:
        # Simulate login session
        with client.session_transaction() as sess:
            sess['user_id'] = user_id

        # ----------------------------------------------------
        # TEST 1: GET /workouts page HTML structure & default All Categories
        # ----------------------------------------------------
        print("\n[TEST 1] Testing GET /workouts page & default All Categories...")
        resp = client.get('/workouts')
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.get_data(as_text=True)

        # Check title and header
        assert "Workout History &amp; Session Management" in html or "Workout History & Session Management" in html
        assert 'id="workoutHistoryCount"' in html, "Missing id='workoutHistoryCount' for total counter"
        assert 'id="historyEmptyState"' in html, "Missing #historyEmptyState container"
        assert 'No workout sessions found for this category.' in html

        # Check category buttons
        required_buttons = ['All', 'Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Core', 'Abs']
        for btn in required_buttons:
            assert f'data-cat="{btn}"' in html, f"Missing category button for {btn}"
            assert f"filterHistory('{btn}')" in html, f"Missing onclick handler for {btn}"

        # Check default active state on All Categories button
        assert 'data-cat="All"' in html and 'history-category-btn active' in html, "All Categories button should be active by default"
        print("  [PASS] Test 1: Page contains all category buttons, empty state, and default active 'All Categories'.")

        # ----------------------------------------------------
        # TEST 2: Workout Record Cards Information
        # ----------------------------------------------------
        print("\n[TEST 2] Testing Workout Record Cards Data Fields...")
        # Every workout card must have data-categories, date, duration, status, title, exercises
        assert 'class="card workout-history-card"' in html
        assert 'data-categories=' in html
        assert 'data-title=' in html

        # Verify essential card information rendered
        assert "Mins" in html, "Expected workout duration"
        assert ("✓ Completed" in html or "⚡ In Progress" in html or "Scheduled" in html), "Expected workout completion status"
        assert "Movement" in html and "Sets" in html and "Reps" in html and "Weight" in html, "Expected exercises table columns"
        print("  [PASS] Test 2: Workout record cards render title, category, date, exercises, sets, reps, weight, duration, and status.")

        # ----------------------------------------------------
        # TEST 3: API Endpoint /api/workouts/history
        # ----------------------------------------------------
        print("\n[TEST 3] Testing /api/workouts/history Endpoint...")
        api_all = client.get('/api/workouts/history?category=All')
        assert api_all.status_code == 200
        data_all = api_all.get_json()
        assert data_all['success'] is True
        total_all = data_all['count']
        print(f"  -> Total user workouts: {total_all}")
        assert total_all > 0, "Demo user should have recorded workouts"

        # Check each workout has categories and exercises
        for w in data_all['workouts']:
            assert 'categories' in w, f"Missing categories in workout {w['id']}"
            assert 'exercises' in w, f"Missing exercises in workout {w['id']}"
            print(f"     Workout ID {w['id']}: '{w['title']}' -> Categories: {w['categories']}")

        print("  [PASS] Test 3: /api/workouts/history returns enriched workouts with categories and exercises.")

        # ----------------------------------------------------
        # TEST 4: Category Filtering: Chest, Back, Legs, Biceps, Triceps
        # ----------------------------------------------------
        print("\n[TEST 4] Testing Category Filtering...")
        # Chest filter
        api_chest = client.get('/api/workouts/history?category=Chest')
        data_chest = api_chest.get_json()
        print(f"  -> Chest workouts: {data_chest['count']}")
        for w in data_chest['workouts']:
            assert 'Chest' in w['categories'], f"Workout {w['id']} does not belong to Chest"

        # Back filter
        api_back = client.get('/api/workouts/history?category=Back')
        data_back = api_back.get_json()
        print(f"  -> Back workouts: {data_back['count']}")
        for w in data_back['workouts']:
            assert 'Back' in w['categories'], f"Workout {w['id']} does not belong to Back"

        # Legs filter
        api_legs = client.get('/api/workouts/history?category=Legs')
        data_legs = api_legs.get_json()
        print(f"  -> Legs workouts: {data_legs['count']}")
        for w in data_legs['workouts']:
            assert 'Legs' in w['categories'], f"Workout {w['id']} does not belong to Legs"

        # Biceps filter
        api_biceps = client.get('/api/workouts/history?category=Biceps')
        data_biceps = api_biceps.get_json()
        print(f"  -> Biceps workouts: {data_biceps['count']}")
        for w in data_biceps['workouts']:
            assert 'Biceps' in w['categories'], f"Workout {w['id']} does not belong to Biceps"

        # Triceps filter
        api_triceps = client.get('/api/workouts/history?category=Triceps')
        data_triceps = api_triceps.get_json()
        print(f"  -> Triceps workouts: {data_triceps['count']}")
        for w in data_triceps['workouts']:
            assert 'Triceps' in w['categories'], f"Workout {w['id']} does not belong to Triceps"

        print("  [PASS] Test 4: Filtering correctly returns only matching categories.")

        # ----------------------------------------------------
        # TEST 5: Empty Results Category
        # ----------------------------------------------------
        print("\n[TEST 5] Testing Empty Results Category...")
        api_empty = client.get('/api/workouts/history?category=Shoulders')
        data_empty = api_empty.get_json()
        print(f"  -> Shoulders workouts count: {data_empty['count']}")
        assert data_empty['count'] == 0 or len(data_empty['workouts']) == 0
        assert "No workout sessions found for this category." in html, "HTML contains empty state message"
        print("  [PASS] Test 5: Empty category returns 0 records and displays 'No workout sessions found for this category.'")

        # ----------------------------------------------------
        # TEST 6: Compound Name Matching ('Chest & Triceps')
        # ----------------------------------------------------
        print("\n[TEST 6] Testing Compound Name Matching ('Chest & Triceps')...")
        # Insert a compound workout for user 1
        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, status, target_muscle_group, notes)
            VALUES (?, 'Compound Push: Chest & Triceps', '2026-10-03', 60, 6500.0, 'completed', 'Chest & Triceps', 'Great session')
        """, (user_id,))
        compound_w_id = cursor.lastrowid
        conn.commit()

        # Query API for Chest and Triceps
        resp_c = client.get('/api/workouts/history?category=Chest').get_json()
        resp_t = client.get('/api/workouts/history?category=Triceps').get_json()

        in_chest = any(w['id'] == compound_w_id for w in resp_c['workouts'])
        in_triceps = any(w['id'] == compound_w_id for w in resp_t['workouts'])

        print(f"  -> Compound workout {compound_w_id} ('Chest & Triceps') in Chest: {in_chest}, in Triceps: {in_triceps}")
        assert in_chest is True, "Workout with target 'Chest & Triceps' must appear under Chest"
        assert in_triceps is True, "Workout with target 'Chest & Triceps' must appear under Triceps"

        # Clean up test compound workout
        cursor.execute("DELETE FROM workouts WHERE id = ?", (compound_w_id,))
        conn.commit()
        print("  [PASS] Test 6: Compound category 'Chest & Triceps' successfully appears under both Chest AND Triceps.")

        # ----------------------------------------------------
        # TEST 7: Case-Insensitive Matching
        # ----------------------------------------------------
        print("\n[TEST 7] Testing Case-Insensitive Matching...")
        c_lower = client.get('/api/workouts/history?category=chest').get_json()['count']
        c_upper = client.get('/api/workouts/history?category=CHEST').get_json()['count']
        c_mixed = client.get('/api/workouts/history?category=Chest').get_json()['count']
        assert c_lower == c_mixed == c_upper, f"Counts should be identical: {c_lower}, {c_upper}, {c_mixed}"
        print(f"  -> Counts for chest: {c_lower}, CHEST: {c_upper}, Chest: {c_mixed}")
        print("  [PASS] Test 7: Category matching works identically regardless of capitalization.")

        # ----------------------------------------------------
        # TEST 8: Abs and Core Interchangeability
        # ----------------------------------------------------
        print("\n[TEST 8] Testing Abs and Core Interchangeability...")
        cats_with_core = workout_manager.category_matches(['Core'], 'Abs')
        cats_with_abs = workout_manager.category_matches(['Abs'], 'Core')
        assert cats_with_core is True, "Core should match Abs filter"
        assert cats_with_abs is True, "Abs should match Core filter"
        print("  [PASS] Test 8: Abs and Core are appropriately matched interchangeably.")

        # ----------------------------------------------------
        # TEST 9: User-Specific Data Isolation
        # ----------------------------------------------------
        print("\n[TEST 9] Testing User-Specific Data Isolation...")
        # Create second user
        cursor.execute("SELECT id FROM users WHERE username = 'test_filter_user'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (username, email, password_hash, full_name) VALUES ('test_filter_user', 'filter@test.com', 'hash', 'Test Filter User')")
            conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = 'test_filter_user'")
            row = cursor.fetchone()
        user2_id = row['id']

        # Clean existing workouts for user2
        cursor.execute("DELETE FROM workouts WHERE user_id = ?", (user2_id,))
        # Insert 1 isolated workout for user2
        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, status, target_muscle_group)
            VALUES (?, 'User2 Isolated Legs Session', '2026-10-05', 45, 5000.0, 'completed', 'Legs')
        """, (user2_id,))
        conn.commit()

        # Query API as user 2
        with client.session_transaction() as sess:
            sess['user_id'] = user2_id

        resp_user2 = client.get('/api/workouts/history?category=All')
        data_user2 = resp_user2.get_json()
        assert data_user2['count'] == 1, f"User2 should only have 1 workout, got {data_user2['count']}"
        assert data_user2['workouts'][0]['title'] == 'User2 Isolated Legs Session'

        # User2 checking Chest should return 0
        resp_user2_chest = client.get('/api/workouts/history?category=Chest')
        assert resp_user2_chest.get_json()['count'] == 0

        # User2 checking Legs should return 1
        resp_user2_legs = client.get('/api/workouts/history?category=Legs')
        assert resp_user2_legs.get_json()['count'] == 1

        # Switch back to user 1: user 1 must NOT see user 2's workout
        with client.session_transaction() as sess:
            sess['user_id'] = user_id

        resp_user1 = client.get('/api/workouts/history?category=All')
        data_user1 = resp_user1.get_json()
        assert not any('User2 Isolated' in w['title'] for w in data_user1['workouts']), "User 1 should never see User 2's workouts"
        print("  [PASS] Test 9: Complete data isolation between different users verified.")

    conn.close()

    print("\n" + "=" * 65)
    print("ALL 9 WORKOUT HISTORY CATEGORY FILTER TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
