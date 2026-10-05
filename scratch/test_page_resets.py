import sys
import os
import unittest
from datetime import date, timedelta

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app
import database
import workout_manager
import nutrition_manager
import progress_manager

class TestPageResets(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Setup test database
        database.init_db()
        conn = database.get_db()
        cursor = conn.cursor()

        # Create or ensure test users
        cursor.execute("SELECT id FROM users WHERE username = 'reset_tester_1'")
        user1 = cursor.fetchone()
        if not user1:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, weight_kg, height_cm, age, gender, fitness_goal, training_days_per_week, available_equipment, dietary_preference, experience_level)
                VALUES ('reset_tester_1', 'tester1@ironpulse.test', 'fakehash', 'Tester One', 75.0, 178.0, 25, 'male', 'Bulk', 5, 'Dumbbells Only', 'Vegan', 'Beginner')
            """)
            self.user1_id = cursor.lastrowid
        else:
            self.user1_id = user1['id']

        cursor.execute("SELECT id FROM users WHERE username = 'reset_tester_2'")
        user2 = cursor.fetchone()
        if not user2:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, weight_kg, height_cm, age, gender, fitness_goal, training_days_per_week, available_equipment, dietary_preference, experience_level)
                VALUES ('reset_tester_2', 'tester2@ironpulse.test', 'fakehash', 'Tester Two', 80.0, 182.0, 28, 'male', 'Cut', 3, 'Full Commercial Gym', 'Keto', 'Advanced')
            """)
            self.user2_id = cursor.lastrowid
        else:
            self.user2_id = user2['id']

        conn.commit()
        conn.close()

    def login_as(self, user_id):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id

    # ==============================================================
    # 1. WORKOUT RESET TEST
    # ==============================================================
    def test_workout_reset(self):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        conn = database.get_db()
        cursor = conn.cursor()

        # Create custom daily schedule for user1 today
        cursor.execute("SELECT id FROM exercises LIMIT 1")
        ex_row = cursor.fetchone()
        ex_id = ex_row['id'] if ex_row else 1
        cursor.execute("""
            INSERT OR REPLACE INTO user_daily_schedules (user_id, date, workout_title, target_muscle_group, duration_minutes, exercise_id, sets, reps, rest_time, notes)
            VALUES (?, ?, 'Custom Shoulders Blast', 'Shoulders', 45, ?, 4, 12, 60, 'Heavy drop sets')
        """, (self.user1_id, today, ex_id))

        # Create an uncompleted workout session for today
        cursor.execute("""
            INSERT INTO workouts (user_id, date, title, target_muscle_group, duration_minutes, intensity_rating, status)
            VALUES (?, ?, 'Uncompleted Today Session', 'Shoulders', 45, 9, 'in_progress')
        """, (self.user1_id, today))
        uncompleted_id = cursor.lastrowid

        # Create a completed workout from yesterday (should NOT be deleted)
        cursor.execute("""
            INSERT INTO workouts (user_id, date, title, target_muscle_group, duration_minutes, intensity_rating, status)
            VALUES (?, ?, 'Completed Yesterday Session', 'Chest', 60, 8, 'completed')
        """, (self.user1_id, yesterday))
        completed_yesterday_id = cursor.lastrowid

        # Create workout for user2 today (should NOT be affected)
        cursor.execute("""
            INSERT INTO workouts (user_id, date, title, target_muscle_group, duration_minutes, intensity_rating, status)
            VALUES (?, ?, 'User2 Workout Today', 'Legs', 50, 7, 'in_progress')
        """, (self.user2_id, today))
        user2_workout_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Perform Workout Reset as user1
        self.login_as(self.user1_id)
        resp = self.client.post('/workouts/reset-today', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"Today&#39;s workout has been reset." in resp.data or b"Today's workout has been reset." in resp.data)

        # Verify DB state
        conn = database.get_db()
        cursor = conn.cursor()

        # user1 custom schedule should be deleted
        cursor.execute("SELECT * FROM user_daily_schedules WHERE user_id = ? AND date = ?", (self.user1_id, today))
        self.assertIsNone(cursor.fetchone())

        # user1 uncompleted session for today should be deleted
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (uncompleted_id,))
        self.assertIsNone(cursor.fetchone())

        # user1 completed session from yesterday must still exist
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (completed_yesterday_id,))
        self.assertIsNotNone(cursor.fetchone())

        # user2 workout must still exist
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (user2_workout_id,))
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    # ==============================================================
    # 2. NUTRITION RESET TEST
    # ==============================================================
    def test_nutrition_reset(self):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        conn = database.get_db()
        cursor = conn.cursor()

        # Log meals for user1 today
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g, quantity)
            VALUES (?, ?, 'Lunch', 'Chicken Breast and Rice', 650, 55, 60, 10, 1.0)
        """, (self.user1_id, today))
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g, quantity)
            VALUES (?, ?, 'Snack', 'Whey Protein Shake', 140, 25, 3, 2, 1.0)
        """, (self.user1_id, today))

        # Log meal for user1 yesterday (must NOT be deleted)
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g, quantity)
            VALUES (?, ?, 'Dinner', 'Salmon and Sweet Potato', 700, 45, 50, 22, 1.0)
        """, (self.user1_id, yesterday))
        yesterday_log_id = cursor.lastrowid

        # Log meal for user2 today (must NOT be deleted)
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g, quantity)
            VALUES (?, ?, 'Lunch', 'Beef Steak', 800, 60, 0, 40, 1.0)
        """, (self.user2_id, today))
        user2_log_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Perform Nutrition Reset for user1 today
        self.login_as(self.user1_id)
        resp = self.client.post('/nutrition/reset-today', data={'date': today}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"Today&#39;s nutrition has been reset." in resp.data or b"Today's nutrition has been reset." in resp.data)

        # Verify DB state
        conn = database.get_db()
        cursor = conn.cursor()

        # user1 today logs should be 0
        cursor.execute("SELECT COUNT(*) as cnt FROM nutrition_logs WHERE user_id = ? AND date = ?", (self.user1_id, today))
        self.assertEqual(cursor.fetchone()['cnt'], 0)

        # user1 yesterday log must remain
        cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (yesterday_log_id,))
        self.assertIsNotNone(cursor.fetchone())

        # user2 today log must remain
        cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (user2_log_id,))
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    # ==============================================================
    # 3. PROGRESS RESET TEST
    # ==============================================================
    def test_progress_reset(self):
        today = date.today().isoformat()
        conn = database.get_db()
        cursor = conn.cursor()

        # Add progress logs for user1
        cursor.execute("""
            INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, waist_cm, arms_cm, thighs_cm, notes)
            VALUES (?, ?, 75.5, 14.5, 102.0, 80.0, 38.0, 58.0, 'Initial check-in')
        """, (self.user1_id, today))
        cursor.execute("""
            INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, waist_cm, arms_cm, thighs_cm, notes)
            VALUES (?, ?, 76.0, 14.2, 103.0, 80.0, 38.5, 58.5, 'Week 2 check-in')
        """, (self.user1_id, (date.today() - timedelta(days=7)).isoformat()))

        # Add progress log for user2 (must NOT be deleted)
        cursor.execute("""
            INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, waist_cm, arms_cm, thighs_cm, notes)
            VALUES (?, ?, 81.0, 12.0, 110.0, 82.0, 41.0, 62.0, 'User 2 progress')
        """, (self.user2_id, today))
        user2_prog_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Perform Progress Reset as user1
        self.login_as(self.user1_id)
        resp = self.client.post('/progress/reset', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Progress data has been reset.", resp.data)

        # Verify DB state
        conn = database.get_db()
        cursor = conn.cursor()

        # user1 progress logs should be 0
        cursor.execute("SELECT COUNT(*) as cnt FROM progress_logs WHERE user_id = ?", (self.user1_id,))
        self.assertEqual(cursor.fetchone()['cnt'], 0)

        # user2 progress log should still exist
        cursor.execute("SELECT * FROM progress_logs WHERE id = ?", (user2_prog_id,))
        self.assertIsNotNone(cursor.fetchone())

        # user1 account itself must still exist
        cursor.execute("SELECT * FROM users WHERE id = ?", (self.user1_id,))
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    # ==============================================================
    # 4. EXERCISE FILTER RESET TEST
    # ==============================================================
    def test_exercise_filters_reset(self):
        self.login_as(self.user1_id)
        resp = self.client.get('/exercises/reset-filters', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Exercise filters cleared.", resp.data)

        # Exercises table must still exist with exercises intact
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM exercises")
        count = cursor.fetchone()['cnt']
        self.assertGreaterEqual(count, 15)
        conn.close()

    # ==============================================================
    # 5. AI ASSISTANT CLEAR TEST
    # ==============================================================
    def test_assistant_clear(self):
        conn = database.get_db()
        cursor = conn.cursor()

        # Ensure ai_chat_messages table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Add messages for user1 and user2
        cursor.execute("INSERT INTO ai_chat_messages (user_id, sender, message) VALUES (?, 'user', 'What is best chest exercise?')", (self.user1_id,))
        cursor.execute("INSERT INTO ai_chat_messages (user_id, sender, message) VALUES (?, 'ai', 'Barbell bench press is excellent.')", (self.user1_id,))
        cursor.execute("INSERT INTO ai_chat_messages (user_id, sender, message) VALUES (?, 'user', 'User2 question here')", (self.user2_id,))
        user2_msg_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Clear AI conversation as user1
        self.login_as(self.user1_id)
        resp = self.client.post('/assistant/clear', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"AI conversation cleared.", resp.data)

        # Verify DB state
        conn = database.get_db()
        cursor = conn.cursor()

        # user1 chat messages should be 0
        cursor.execute("SELECT COUNT(*) as cnt FROM ai_chat_messages WHERE user_id = ?", (self.user1_id,))
        self.assertEqual(cursor.fetchone()['cnt'], 0)

        # user2 message should still exist
        cursor.execute("SELECT * FROM ai_chat_messages WHERE id = ?", (user2_msg_id,))
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    # ==============================================================
    # 6. PROFILE / SETTINGS PREFERENCES RESET TEST
    # ==============================================================
    def test_profile_preferences_reset(self):
        conn = database.get_db()
        cursor = conn.cursor()

        # Change user1 preferences to non-default values
        cursor.execute("""
            UPDATE users SET
                fitness_goal = 'Fat Loss & Cardio',
                training_days_per_week = 6,
                available_equipment = 'Dumbbells Only',
                dietary_preference = 'Vegan',
                experience_level = 'Advanced (3+ Years)',
                weight_kg = 75.0,
                height_cm = 178.0,
                age = 25,
                email = 'tester1@ironpulse.test'
            WHERE id = ?
        """, (self.user1_id,))
        conn.commit()
        conn.close()

        # Perform Preferences Reset as user1
        self.login_as(self.user1_id)
        resp = self.client.post('/profile/reset-preferences', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Fitness preferences have been reset.", resp.data)

        # Verify DB state
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (self.user1_id,))
        u = cursor.fetchone()

        # Preferences reset to defaults:
        self.assertEqual(u['fitness_goal'], "Muscle Hypertrophy & Strength")
        self.assertEqual(u['training_days_per_week'], 4)
        self.assertEqual(u['available_equipment'], "Full Commercial Gym")
        self.assertEqual(u['dietary_preference'], "High Protein Omnivore")
        self.assertEqual(u['experience_level'], "Intermediate (1-3 Years)")

        # Auth and biometric properties MUST be preserved:
        self.assertEqual(u['weight_kg'], 75.0)
        self.assertEqual(u['height_cm'], 178.0)
        self.assertEqual(u['age'], 25)
        self.assertEqual(u['email'], 'tester1@ironpulse.test')
        self.assertEqual(u['password_hash'], 'fakehash')

        conn.close()

    # ==============================================================
    # 7. TEMPLATE MODAL TEXT & BUTTON VERIFICATION
    # ==============================================================
    def test_templates_contain_modals_and_exact_text(self):
        self.login_as(self.user1_id)

        # 1. Workouts page
        resp_w = self.client.get('/workouts')
        self.assertEqual(resp_w.status_code, 200)
        self.assertIn(b"Reset today's workout?", resp_w.data)
        self.assertIn(b"This will remove your custom changes for today's workout and restore the original workout schedule.", resp_w.data)
        self.assertIn(b"Reset Workout", resp_w.data)

        # 2. Nutrition page
        resp_n = self.client.get('/nutrition')
        self.assertEqual(resp_n.status_code, 200)
        self.assertIn(b"Reset today's nutrition?", resp_n.data)
        self.assertIn(b"This will remove all food entries recorded today.", resp_n.data)
        self.assertIn(b"Reset Nutrition", resp_n.data)

        # 3. Progress page
        resp_p = self.client.get('/progress')
        self.assertEqual(resp_p.status_code, 200)
        self.assertIn(b"Reset progress data?", resp_p.data)
        self.assertIn(b"This will permanently remove your saved body measurements and progress records.", resp_p.data)
        self.assertIn(b"Reset Progress", resp_p.data)

        # 4. Exercises page
        resp_e = self.client.get('/exercises')
        self.assertEqual(resp_e.status_code, 200)
        self.assertIn(b"Reset Filters", resp_e.data)

        # 5. Assistant page
        resp_a = self.client.get('/assistant')
        self.assertEqual(resp_a.status_code, 200)
        self.assertIn(b"Clear this conversation?", resp_a.data)
        self.assertIn(b"Clear Chat", resp_a.data)
        self.assertIn(b"Conversation cleared. How can I help you today?", resp_a.data)

        # 6. Profile page
        resp_prof = self.client.get('/profile')
        self.assertEqual(resp_prof.status_code, 200)
        self.assertIn(b"Reset fitness preferences?", resp_prof.data)
        self.assertIn(b"This will reset your workout and nutrition preferences back to default values.", resp_prof.data)
        self.assertIn(b"Reset Fitness Preferences", resp_prof.data)

        # 7. Settings page
        resp_s = self.client.get('/settings')
        self.assertEqual(resp_s.status_code, 200)
        self.assertIn(b"Reset fitness preferences?", resp_s.data)
        self.assertIn(b"This will reset your workout and nutrition preferences back to default values.", resp_s.data)
        self.assertIn(b"Reset Fitness Preferences", resp_s.data)

        # 8. Dashboard page
        resp_d = self.client.get('/dashboard')
        self.assertEqual(resp_d.status_code, 200)
        self.assertIn(b"Reset today's workout?", resp_d.data)
        self.assertIn(b"Reset Workout", resp_d.data)

if __name__ == '__main__':
    unittest.main()
