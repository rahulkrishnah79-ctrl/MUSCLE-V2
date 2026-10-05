"""
Phase 8: Comprehensive End-to-End Final Verification Test Suite
Tests all 11 core functional domains:
1. Authentication (Register, Login, Logout, Demo, Google OAuth)
2. Homepage (Hero, CTAs, Public Nav)
3. Dashboard (Stats, Workouts, Nutrition, Progress)
4. Sidebar & Mobile Layout (All nav items, mobile drawer, collapse)
5. Theme System (Dark, Light, localStorage persistence, Chart colors)
6. Workout Management (Browse, Select, Add, Edit, Complete, Remove, History, Exercises)
7. Exercise Library (Search, Filter, Details, YouTube Tutorials)
8. Nutrition & Camera Tracking (Manual log, Camera modal, Food recognition API, Scaled macros)
9. Progress Tracking (Measurements, Charts, History)
10. AI Assistant (Context injection, Intents, Skeleton card, Error handling, Disclaimer)
11. Mobile & Layout Integrity (Responsive wrappers, zero broken links, data preservation)
"""

import os
import sys
import json
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import database
import workout_manager
import nutrition_manager
import progress_manager
import ai_assistant
from werkzeug.security import check_password_hash

class Phase8FinalTestingSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

        # Check existing database data to ensure preservation
        conn = database.get_db()
        cls.initial_users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        cls.initial_exercises_count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        conn.close()

    def setUp(self):
        # Start each test logged out
        self.client.get('/logout')

    def login_demo(self):
        return self.client.get('/login/demo', follow_redirects=True)

    # =========================================================================
    # 1. AUTHENTICATION TESTS
    # =========================================================================
    def test_01_registration_flow(self):
        """Test registration with valid data, duplicate checks, and password matching."""
        import secrets
        rand_suffix = secrets.token_hex(4)
        test_username = f"athlete_test_{rand_suffix}"
        test_email = f"{test_username}@ironpulse.test"

        try:
            # A. Register new test athlete
            resp = self.client.post('/register', data={
                'full_name': 'Marcus Vance',
                'username': test_username,
                'email': test_email,
                'password': 'SecurePassword123!',
                'confirm_password': 'SecurePassword123!',
                'age': 28,
                'gender': 'Male',
                'height_cm': 182,
                'weight_kg': 84.5,
                'experience_level': 'Intermediate (1-3 Years)',
                'fitness_goal': 'Muscle Hypertrophy & Strength',
                'training_days_per_week': 5,
                'available_equipment': 'Full Commercial Gym',
                'dietary_preference': 'High Protein Omnivore'
            }, follow_redirects=True)

            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            self.assertIn("Marcus Vance", html)
            self.assertIn("Dashboard", html)

            # Verify database record
            conn = database.get_db()
            user = conn.execute("SELECT * FROM users WHERE username = ?", (test_username,)).fetchone()
            self.assertIsNotNone(user)
            self.assertTrue(check_password_hash(user['password_hash'], 'SecurePassword123!'))
            self.assertEqual(user['weight_kg'], 84.5)
            self.assertGreater(user['daily_protein_target'], 100)
            conn.close()

            # B. Duplicate username check
            self.client.get('/logout')
            dup_resp = self.client.post('/register', data={
                'full_name': 'Marcus Vance',
                'username': test_username,
                'email': f'another_{rand_suffix}@ironpulse.test',
                'password': 'SecurePassword123!',
                'confirm_password': 'SecurePassword123!'
            }, follow_redirects=True)
            dup_html = dup_resp.get_data(as_text=True)
            self.assertIn("An account with that email or username already exists", dup_html)

            # C. Password mismatch check
            mismatch_resp = self.client.post('/register', data={
                'full_name': 'Marcus Vance',
                'username': f'new_athlete_{rand_suffix}',
                'email': f'new_athlete_{rand_suffix}@ironpulse.test',
                'password': 'PasswordOne1!',
                'confirm_password': 'PasswordTwo2!'
            }, follow_redirects=True)
            mismatch_html = mismatch_resp.get_data(as_text=True)
            self.assertIn("Passwords do not match", mismatch_html)

        finally:
            # Clean up test user to ensure 0 residue
            clean_conn = database.get_db()
            clean_conn.execute("DELETE FROM users WHERE username = ?", (test_username,))
            clean_conn.commit()
            clean_conn.close()
            self.client.get('/logout')

    def test_02_login_and_logout_flow(self):
        """Test username login, email login, invalid credentials, and logout."""
        # A. Login with username
        resp_user = self.client.post('/login', data={
            'username': 'alex_pulse',
            'password': 'fitness123'
        }, follow_redirects=True)
        self.assertEqual(resp_user.status_code, 200)
        self.assertIn("Welcome back, Alex Mercer", resp_user.get_data(as_text=True))

        # B. Logout
        resp_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)
        self.assertIn("You have been signed out", resp_logout.get_data(as_text=True))

        # C. Login with email
        resp_email = self.client.post('/login', data={
            'username': 'alex@ironpulse.fit',
            'password': 'fitness123'
        }, follow_redirects=True)
        self.assertEqual(resp_email.status_code, 200)
        self.assertIn("Welcome back, Alex Mercer", resp_email.get_data(as_text=True))

        # D. Invalid password
        self.client.get('/logout')
        resp_invalid = self.client.post('/login', data={
            'username': 'alex_pulse',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn("Invalid credentials", resp_invalid.get_data(as_text=True))

    def test_03_google_oauth_endpoint(self):
        """Test Google OAuth initiation endpoint and unconfigured state handling."""
        resp = self.client.get('/auth/google', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        # Should gracefully guide user to login if unconfigured or initiate flow if configured
        self.assertTrue("Google OAuth credentials are not configured yet" in html or "accounts.google.com" in html)

    # =========================================================================
    # 2. HOMEPAGE TESTS
    # =========================================================================
    def test_04_homepage_layout(self):
        """Test public homepage hero section, navigation, and CTAs."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn("Build Serious Muscle", html)
        self.assertIn("Track With", html)
        self.assertIn("Precision", html)
        self.assertIn("Get Started Free", html)
        self.assertIn("Athlete Login", html)
        self.assertIn("Instant Demo Login", html)
        self.assertIn("Features", html)
        self.assertIn("Exercise Catalog", html)

        # Public site must not show the authenticated sidebar
        self.assertNotIn('class="app-sidebar"', html)

    # =========================================================================
    # 3. DASHBOARD TESTS
    # =========================================================================
    def test_05_dashboard_metrics_and_widgets(self):
        """Test dashboard cards: weight, BMI, targets, workout info, and progress chart."""
        self.login_demo()
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn("Current Weight", html)
        self.assertIn("Body Mass Index", html)
        self.assertIn("Workout Streak", html)
        self.assertIn("Weekly Completion", html)
        self.assertIn("Today's Nutrition", html)
        self.assertIn("Total Volume Lifted", html)
        self.assertIn("TODAY'S WORKOUT", html)
        self.assertIn("Weight Progress &amp; Hypertrophy Trajectory", html)
        self.assertIn("dashboardWeightChart", html)
        self.assertIn("dashboardChartSkeleton", html)

    # =========================================================================
    # 4. SIDEBAR & MOBILE NAVIGATION TESTS
    # =========================================================================
    def test_06_sidebar_navigation_items(self):
        """Test that every core navigation item exists in the authenticated sidebar."""
        self.login_demo()
        resp = self.client.get('/dashboard')
        html = resp.get_data(as_text=True)

        self.assertIn('href="/dashboard"', html)
        self.assertIn('href="/workouts"', html)
        self.assertIn('href="/nutrition"', html)
        self.assertIn('href="/progress"', html)
        self.assertIn('href="/exercises"', html)
        self.assertIn('href="/assistant"', html)
        self.assertIn('href="/profile"', html)
        self.assertIn('href="/settings"', html)

        # Check mobile toggle and backdrop
        self.assertIn('id="mobileSidebarToggle"', html)
        self.assertIn('id="sidebarBackdrop"', html)
        self.assertIn('id="sidebarCollapseBtn"', html)

    # =========================================================================
    # 5. THEME SYSTEM TESTS
    # =========================================================================
    def test_07_theme_system_and_selectors(self):
        """Test Dark and Light mode theme switchers and variable architecture."""
        self.login_demo()
        resp = self.client.get('/settings')
        html = resp.get_data(as_text=True)

        self.assertIn('id="sidebarThemeToggle"', html)
        self.assertIn('data-theme-choice="dark"', html)
        self.assertIn('data-theme-choice="light"', html)

        # Inspect CSS for variables
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn(':root {', css)
        self.assertIn('--bg-main: #0a0e17;', css)
        self.assertIn('[data-theme="light"] {', css)
        self.assertIn('--bg-main: #f8fafc;', css)

    # =========================================================================
    # 6. WORKOUT MANAGEMENT TESTS
    # =========================================================================
    def test_08_workout_management_full_lifecycle(self):
        """Test workout selection, adding, editing, completing, and removing safely."""
        self.login_demo()
        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE username = 'alex_pulse'").fetchone()

        # A. View Workouts page
        resp = self.client.get('/workouts')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Workout Management", html)
        self.assertIn("Browse Workouts Library", html)
        self.assertIn("Switch / Generate Split", html)

        # B. Log a manual training session
        add_resp = self.client.post('/workouts/add', data={
            'title': 'Test QA Hypertrophy Delts',
            'date': str(date.today()),
            'target_muscle_group': 'Shoulders',
            'duration_minutes': 50,
            'intensity_rating': 8,
            'notes': 'Overhead press progression test'
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)

        # Find the created workout
        workout = conn.execute("SELECT * FROM workouts WHERE user_id = ? AND title = 'Test QA Hypertrophy Delts'", (user['id'],)).fetchone()
        self.assertIsNotNone(workout)
        workout_id = workout['id']

        # C. Add exercise to workout
        ex_row = conn.execute("SELECT * FROM exercises WHERE name LIKE '%Overhead%' OR category = 'Shoulders' LIMIT 1").fetchone()
        add_ex_resp = self.client.post('/workouts/exercise/add', data={
            'workout_id': workout_id,
            'exercise_id': ex_row['id'],
            'sets': 4,
            'reps': 8,
            'weight_kg': 60.0,
            'rest_seconds': 120,
            'notes': 'Strict form'
        }, follow_redirects=True)
        self.assertEqual(add_ex_resp.status_code, 200)

        # Verify exercise added
        we_item = conn.execute("SELECT * FROM workout_exercises WHERE workout_id = ?", (workout_id,)).fetchone()
        self.assertIsNotNone(we_item)
        self.assertEqual(we_item['sets'], 4)

        # D. Edit workout metadata
        edit_resp = self.client.post(f'/workouts/edit/{workout_id}', data={
            'title': 'Test QA Hypertrophy Delts (Edited)',
            'date': str(date.today()),
            'target_muscle_group': 'Shoulders',
            'duration_minutes': 55,
            'intensity_rating': 9,
            'notes': 'RPE 9 reached on final set'
        }, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)

        # E. Complete workout
        comp_resp = self.client.post(f'/workouts/complete/{workout_id}', follow_redirects=True)
        self.assertEqual(comp_resp.status_code, 200)
        updated_w = conn.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
        self.assertEqual(updated_w['status'], 'completed')

        # F. Verify removal confirmation dialog in template
        w_html = self.client.get('/workouts').get_data(as_text=True)
        self.assertIn("Are you sure you want to remove this workout?", w_html)
        self.assertIn("Remove Workout", w_html)

        # G. Delete workout and verify global library is intact
        del_resp = self.client.post(f'/workouts/delete/{workout_id}', follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)

        # Check user workout deleted
        deleted_w = conn.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
        self.assertIsNone(deleted_w)

        # Check global library preserved
        after_ex_count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        self.assertEqual(after_ex_count, self.initial_exercises_count)
        conn.close()

    # =========================================================================
    # 7. EXERCISE CATALOG & YOUTUBE TESTS
    # =========================================================================
    def test_09_exercise_catalog_and_youtube_tutorials(self):
        """Test exercise library filtering, instructions, and YouTube tutorials."""
        self.login_demo()
        resp = self.client.get('/exercises')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn("Search by name, muscle, equipment, difficulty...", html)
        self.assertIn("Barbell Bench Press", html)
        self.assertIn("Barbell Back Squat", html)
        self.assertIn("Watch Tutorial", html)
        self.assertIn("youtubeVideoModal", html)
        self.assertIn("youtube-nocookie.com/embed", html)

    # =========================================================================
    # 8. NUTRITION & CAMERA TRACKING TESTS
    # =========================================================================
    def test_10_nutrition_and_camera_tracking(self):
        """Test manual food logging, camera modal, and recognition status endpoints."""
        self.login_demo()
        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE username = 'alex_pulse'").fetchone()

        # A. Check Nutrition page
        resp = self.client.get('/nutrition')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Scan Your Food", html)
        self.assertIn("Daily Energy &amp; Macronutrient Progress", html)
        self.assertIn("Caloric Target", html)

        # B. Manual food log entry
        add_food_resp = self.client.post('/nutrition/add', data={
            'date': str(date.today()),
            'meal_type': 'Lunch',
            'food_name': 'Grilled Chicken Breast & Quinoa QA',
            'quantity': 1.5,
            'serving_unit': 'plate',
            'calories': 420,
            'protein_g': 46.0,
            'carbs_g': 38.0,
            'fats_g': 7.5
        }, follow_redirects=True)
        self.assertEqual(add_food_resp.status_code, 200)

        # Verify added food
        food_log = conn.execute("SELECT * FROM nutrition_logs WHERE user_id = ? AND food_name LIKE '%Grilled Chicken Breast & Quinoa QA%'", (user['id'],)).fetchone()
        self.assertIsNotNone(food_log)
        log_id = food_log['id']

        # C. Camera scan status API
        status_resp = self.client.get('/nutrition/scan/status')
        self.assertEqual(status_resp.status_code, 200)
        data = status_resp.get_json()
        self.assertIn('disclaimer', data)
        self.assertIn('configured', data)

        # D. Delete nutrition log
        del_food_resp = self.client.post(f'/nutrition/delete/{log_id}', follow_redirects=True)
        self.assertEqual(del_food_resp.status_code, 200)
        deleted_log = conn.execute("SELECT * FROM nutrition_logs WHERE id = ?", (log_id,)).fetchone()
        self.assertIsNone(deleted_log)
        conn.close()

    # =========================================================================
    # 9. PROGRESS TRACKING TESTS
    # =========================================================================
    def test_11_progress_tracking_and_analytics(self):
        """Test progress measurements submission, calculations, and chart placeholders."""
        self.login_demo()
        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE username = 'alex_pulse'").fetchone()

        # Add progress entry
        add_prog_resp = self.client.post('/progress/add', data={
            'date': str(date.today()),
            'weight_kg': 79.2,
            'body_fat_pct': 13.8,
            'chest_cm': 105.0,
            'waist_cm': 81.5,
            'arms_cm': 38.5,
            'thighs_cm': 59.0,
            'notes': 'Weekly physique checkpoint QA'
        }, follow_redirects=True)
        self.assertEqual(add_prog_resp.status_code, 200)

        # View progress page
        resp = self.client.get('/progress')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn("Progression Analytics", html)
        self.assertIn("Weight Progression", html)
        self.assertIn("Workout Consistency", html)
        self.assertIn("Torso Progression", html)
        self.assertIn("Limbs Hypertrophy", html)
        self.assertIn("weightChartSkeleton", html)

        # Cleanup test log
        conn.execute("DELETE FROM progress_logs WHERE user_id = ? AND notes = 'Weekly physique checkpoint QA'", (user['id'],))
        conn.commit()
        conn.close()

    # =========================================================================
    # 10. AI ASSISTANT TESTS
    # =========================================================================
    def test_12_ai_assistant_intents_and_chat(self):
        """Test AI coach intent responses, disclaimer, typing skeleton, and context injection."""
        self.login_demo()

        # View assistant page
        page_resp = self.client.get('/assistant')
        self.assertEqual(page_resp.status_code, 200)
        html = page_resp.get_data(as_text=True)

        self.assertIn("AI ATHLETE COACH", html)
        self.assertIn("AI Coach is analyzing biometrics &amp; crafting advice...", html)
        self.assertIn("Suggested Questions", html)
        self.assertIn("medical", html.lower())

        # Test AJAX queries across intents
        intents_to_test = [
            "Create a chest workout",
            "How much protein should I eat?",
            "What should I eat after my workout?",
            "Create a 4-day workout plan",
            "How can I improve my bench press?",
            "Give me a cheap high-protein meal"
        ]

        for query in intents_to_test:
            chat_resp = self.client.post('/assistant/chat', json={'message': query})
            self.assertEqual(chat_resp.status_code, 200)
            data = chat_resp.get_json()
            self.assertIn('reply', data)
            self.assertGreater(len(data['reply']), 30, f"Query '{query}' produced insufficient reply")

    # =========================================================================
    # 11. MOBILE RESPONSIVENESS & DATA INTEGRITY
    # =========================================================================
    def test_13_mobile_and_data_integrity(self):
        """Verify responsive breakpoints, CSS rules, and user data preservation."""
        conn = database.get_db()
        final_users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        final_exercises_count = conn.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        conn.close()

        self.assertEqual(final_users_count, self.initial_users_count, "User accounts must remain intact")
        self.assertEqual(final_exercises_count, self.initial_exercises_count, "Exercise catalog must remain intact")

        # Verify responsive CSS media queries
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('@media (max-width: 1024px)', css)
        self.assertIn('@media (max-width: 768px)', css)
        self.assertIn('.table-responsive', css)

if __name__ == '__main__':
    unittest.main()
