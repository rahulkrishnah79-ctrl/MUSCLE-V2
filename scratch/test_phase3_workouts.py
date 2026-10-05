"""
Automated Comprehensive Test Suite for Phase 3: Workout Management
Tests:
1. Browse workouts catalog & plan structures
2. Add workout routine to user's personal plan
3. Edit workout metadata
4. Exercise manipulation: add exercise, edit sets/reps/rest/weight, reorder, remove exercise
5. Replace workout routine
6. Mark workout as completed and verify volume & streak updates
7. Remove workout with data isolation verification (global library intact)
8. Verify UI templates contain confirmation dialog "Are you sure you want to remove this workout?" with "Cancel" and "Remove Workout" buttons
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
import database
import workout_manager
from app import app
from datetime import date, timedelta

class Phase3WorkoutManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Initialize test user
        self.username = "test_athlete_phase3"
        self.password = "Password123!"
        self.email = "phase3_athlete@ironpulse.test"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (self.username,))
        conn.commit()
        conn.close()

        # Register user
        resp = self.client.post('/register', data={
            'full_name': 'Phase3 Tester',
            'username': self.username,
            'email': self.email,
            'password': self.password,
            'confirm_password': self.password
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Get user ID
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (self.username,))
        self.user_id = cursor.fetchone()['id']
        conn.close()

    def login(self):
        return self.client.post('/login', data={
            'username_or_email': self.username,
            'password': self.password
        }, follow_redirects=True)

    def test_01_browse_workouts(self):
        """Verify browsing workout plans, days, and exercises."""
        conn = database.get_db()
        plans = workout_manager.get_all_plans_with_details(conn)
        conn.close()

        self.assertGreaterEqual(len(plans), 3, "Should have at least 3 seeded workout plans")
        for p in plans:
            self.assertIn('name', p)
            self.assertIn('days', p)
            self.assertGreater(len(p['days']), 0, f"Plan {p['name']} should have days")
            for d in p['days']:
                self.assertIn('day_title', d)
                self.assertIn('exercises', d)
                self.assertGreater(len(d['exercises']), 0, f"Day {d['day_title']} should have exercises")

    def test_02_add_routine_to_personal_plan(self):
        """Verify adding a routine to personal schedule creates a workout with copied exercises."""
        self.login()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workout_plan_days LIMIT 1")
        plan_day_id = cursor.fetchone()['id']
        conn.close()

        target_date = (date.today() + timedelta(days=1)).isoformat()
        resp = self.client.post('/workouts/add-to-plan', data={
            'plan_day_id': plan_day_id,
            'date': target_date,
            'status': 'scheduled'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify in DB
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE user_id = ? AND date = ?", (self.user_id, target_date))
        w = cursor.fetchone()
        self.assertIsNotNone(w, "Scheduled workout should exist")
        self.assertEqual(w['status'], 'scheduled')

        cursor.execute("SELECT COUNT(*) FROM workout_exercises WHERE workout_id = ?", (w['id'],))
        ex_count = cursor.fetchone()[0]
        self.assertGreater(ex_count, 0, "Prescribed exercises should be copied to user's workout")
        conn.close()

    def test_03_edit_workout_details(self):
        """Verify editing workout title, date, duration, intensity, and notes."""
        self.login()
        # Add a workout
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workout_plan_days LIMIT 1")
        plan_day_id = cursor.fetchone()['id']
        conn.close()

        w_id = workout_manager.add_routine_to_user_schedule(self.user_id, plan_day_id, date.today().isoformat())

        # Edit workout
        new_title = "Modified Heavy Push Blast"
        resp = self.client.post(f'/workouts/edit/{w_id}', data={
            'title': new_title,
            'date': date.today().isoformat(),
            'duration_minutes': 75,
            'intensity_rating': 9,
            'target_muscle_group': 'Chest & Shoulders',
            'notes': 'Felt high energy and achieved pump.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (w_id,))
        updated = cursor.fetchone()
        conn.close()

        self.assertEqual(updated['title'], new_title)
        self.assertEqual(updated['duration_minutes'], 75)
        self.assertEqual(updated['intensity_rating'], 9)
        self.assertEqual(updated['target_muscle_group'], 'Chest & Shoulders')

    def test_04_exercise_crud_and_reorder(self):
        """Verify adding, editing, reordering, and deleting exercises in a workout."""
        self.login()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM exercises LIMIT 2")
        exercises = cursor.fetchall()
        ex1_id, ex2_id = exercises[0]['id'], exercises[1]['id']

        cursor.execute("SELECT id FROM workout_plan_days LIMIT 1")
        plan_day_id = cursor.fetchone()['id']
        conn.close()

        w_id = workout_manager.add_routine_to_user_schedule(self.user_id, plan_day_id, date.today().isoformat())

        # 1. Add exercise to workout
        resp = self.client.post('/workouts/exercise/add', data={
            'workout_id': w_id,
            'exercise_id': ex1_id,
            'sets': 4,
            'reps': 12,
            'weight_kg': 65.5,
            'rest_seconds': 90,
            'notes': 'Added accessory movement'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout_exercises WHERE workout_id = ? AND exercise_id = ? ORDER BY id DESC LIMIT 1", (w_id, ex1_id))
        we = cursor.fetchone()
        self.assertIsNotNone(we)
        we_id = we['id']
        self.assertEqual(we['sets'], 4)
        self.assertEqual(we['reps'], 12)
        self.assertEqual(we['weight_kg'], 65.5)

        # 2. Edit exercise
        resp = self.client.post(f'/workouts/exercise/edit/{we_id}', data={
            'sets': 5,
            'reps': 15,
            'weight_kg': 70.0,
            'rest_seconds': 60,
            'notes': 'Pushed to near failure'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        cursor.execute("SELECT * FROM workout_exercises WHERE id = ?", (we_id,))
        we_updated = cursor.fetchone()
        self.assertEqual(we_updated['sets'], 5)
        self.assertEqual(we_updated['reps'], 15)
        self.assertEqual(we_updated['weight_kg'], 70.0)
        self.assertEqual(we_updated['rest_seconds'], 60)

        # 3. Reorder exercise
        old_order = we_updated['order_idx']
        resp = self.client.post(f'/workouts/exercise/reorder/{we_id}', data={'direction': 'up'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 4. Remove exercise
        resp = self.client.post(f'/workouts/exercise/delete/{we_id}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        cursor.execute("SELECT * FROM workout_exercises WHERE id = ?", (we_id,))
        self.assertIsNone(cursor.fetchone(), "Exercise should be removed from workout")

        # Verify global exercise is intact
        cursor.execute("SELECT * FROM exercises WHERE id = ?", (ex1_id,))
        self.assertIsNotNone(cursor.fetchone(), "Global exercise must remain intact!")
        conn.close()

    def test_05_replace_workout(self):
        """Verify replacing a workout with another routine."""
        self.login()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, day_title FROM workout_plan_days ORDER BY id ASC LIMIT 2")
        days = cursor.fetchall()
        day1, day2 = days[0], days[1]
        conn.close()

        w_id = workout_manager.add_routine_to_user_schedule(self.user_id, day1['id'], date.today().isoformat())

        # Replace with day2
        resp = self.client.post(f'/workouts/replace/{w_id}', data={
            'plan_day_id': day2['id']
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (w_id,))
        w_replaced = cursor.fetchone()
        self.assertEqual(w_replaced['title'], day2['day_title'])
        conn.close()

    def test_06_mark_workout_completed(self):
        """Verify marking workout as completed updates completion status and streak."""
        self.login()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workout_plan_days LIMIT 1")
        day_id = cursor.fetchone()['id']
        conn.close()

        w_id = workout_manager.add_routine_to_user_schedule(self.user_id, day_id, date.today().isoformat())

        resp = self.client.post(f'/workouts/complete/{w_id}', data={
            'duration_minutes': 65,
            'intensity_rating': 9,
            'notes': 'Completed session fully!'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (w_id,))
        w = cursor.fetchone()
        self.assertEqual(w['status'], 'completed')
        self.assertEqual(w['completion_rate'], 100)
        self.assertEqual(w['duration_minutes'], 65)
        self.assertEqual(w['intensity_rating'], 9)

        # Dashboard stats reflect completion and streak
        stats = workout_manager.calculate_dashboard_workout_stats(self.user_id, 4)
        self.assertGreaterEqual(stats['weekly_count'], 1)
        self.assertGreaterEqual(stats['streak'], 1)
        self.assertGreaterEqual(stats['total_completed'], 1)
        conn.close()

    def test_07_remove_workout_and_isolation(self):
        """Verify removing a workout deletes user's session but protects global plans and exercises."""
        self.login()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM exercises")
        initial_ex_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM workout_plans")
        initial_plan_count = cursor.fetchone()[0]

        cursor.execute("SELECT id FROM workout_plan_days LIMIT 1")
        day_id = cursor.fetchone()['id']
        conn.close()

        w_id = workout_manager.add_routine_to_user_schedule(self.user_id, day_id, date.today().isoformat())

        # Remove workout
        resp = self.client.post(f'/workouts/delete/{w_id}', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE id = ?", (w_id,))
        self.assertIsNone(cursor.fetchone(), "Workout should be deleted from user's schedule")

        # Verify global catalog isolation
        cursor.execute("SELECT COUNT(*) FROM exercises")
        self.assertEqual(cursor.fetchone()[0], initial_ex_count, "Global exercises count must not change")

        cursor.execute("SELECT COUNT(*) FROM workout_plans")
        self.assertEqual(cursor.fetchone()[0], initial_plan_count, "Global workout plans count must not change")
        conn.close()

    def test_08_confirmation_dialog_and_buttons(self):
        """Verify workout page contains the confirmation dialog and required buttons."""
        self.login()
        resp = self.client.get('/workouts')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Check required prompt
        self.assertIn("Are you sure you want to remove this workout?", html)
        self.assertIn("Cancel", html)
        self.assertIn("Remove Workout", html)

    def test_09_dashboard_integration(self):
        """Verify dashboard displays current workout, streak, and completion rate."""
        self.login()
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn("Workout Streak", html)
        self.assertIn("Weekly Completion", html)
        self.assertTrue("TODAY'S WORKOUT" in html or "TODAY&#39;S WORKOUT" in html)

if __name__ == '__main__':
    unittest.main()
