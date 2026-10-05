import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from datetime import date
import sqlite3

# Import application modules
from app import app
import database
import nutrition_manager

class TestNutritionFix(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.today = date.today().isoformat()
        
        # Test athlete: user_id = 1 (alex_pulse)
        self.test_user_id = 1

    def login_test_user(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

    def test_01_existing_user_data_intact(self):
        """Verify that existing user data and database records are fully intact."""
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id = 1")
        alex = cursor.fetchone()
        self.assertIsNotNone(alex)
        self.assertEqual(alex['username'], 'alex_pulse')

        cursor.execute("SELECT COUNT(*) FROM food_items")
        food_count = cursor.fetchone()[0]
        self.assertGreater(food_count, 15)
        conn.close()

    def test_02_food_search_and_scaling(self):
        """Verify search_foods and macro calculation."""
        conn = database.get_db()
        results = nutrition_manager.search_foods(conn, query='Paneer')
        self.assertGreater(len(results), 0)
        paneer = [f for f in results if f['name'] == 'Paneer (Cottage Cheese)'][0]
        self.assertIn('Paneer', paneer['name'])
        self.assertGreater(paneer['calories'], 0)
        self.assertGreater(paneer['protein_g'], 0)

        # Estimate helper
        est = nutrition_manager.estimate_food_macros_by_query(conn, 'Paneer (Cottage Cheese)', quantity=2.0)
        self.assertIsNotNone(est)
        self.assertEqual(est['calories'], int(round(paneer['calories'] * 2.0)))
        conn.close()

    def test_03_add_food_from_library(self):
        """Verify /nutrition/add adds library food with scaled macros."""
        self.login_test_user()
        conn = database.get_db()
        # Find Eggs in library
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM food_items WHERE name LIKE '%Eggs (Boiled / Whole)%' LIMIT 1")
        egg_food = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(egg_food)

        payload = {
            'date': self.today,
            'meal_type': 'Breakfast',
            'food_id': egg_food['id'],
            'quantity': 2.0
        }
        res = self.client.post('/nutrition/add', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        log_id = data['log_id']
        self.assertIsNotNone(log_id)

        # Check DB
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (log_id,))
        logged = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(logged)
        self.assertEqual(logged['user_id'], self.test_user_id)
        self.assertEqual(logged['date'], self.today)
        self.assertEqual(logged['meal_type'], 'Breakfast')
        self.assertEqual(logged['quantity'], 2.0)
        self.assertEqual(logged['calories'], int(round(egg_food['calories'] * 2.0)))
        self.assertAlmostEqual(logged['protein_g'], egg_food['protein_g'] * 2.0, places=1)

        # Cleanup test entry
        conn = database.get_db()
        conn.execute("DELETE FROM nutrition_logs WHERE id = ?", (log_id,))
        conn.commit()
        conn.close()

    def test_04_add_custom_food_entry(self):
        """Verify /nutrition/add handles custom entries without food_id."""
        self.login_test_user()
        payload = {
            'date': self.today,
            'meal_type': 'Dinner',
            'food_name': 'Grilled Salmon & Sweet Potato',
            'quantity': 1.0,
            'serving_unit': 'plate',
            'calories': 550,
            'protein_g': 42.0,
            'carbs_g': 48.0,
            'fats_g': 16.0
        }
        res = self.client.post('/nutrition/add', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        log_id = data['log_id']

        # Check DB
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (log_id,))
        logged = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(logged)
        self.assertEqual(logged['food_name'], 'Grilled Salmon & Sweet Potato')
        self.assertEqual(logged['calories'], 550)
        self.assertEqual(logged['protein_g'], 42.0)

        # Cleanup
        conn = database.get_db()
        conn.execute("DELETE FROM nutrition_logs WHERE id = ?", (log_id,))
        conn.commit()
        conn.close()

    def test_05_validation_errors_no_silent_failures(self):
        """Verify validation errors return clear 400 messages."""
        self.login_test_user()
        # Invalid quantity (0 or negative)
        res = self.client.post('/nutrition/add', data={'date': self.today, 'food_name': 'Oats', 'calories': 200, 'quantity': 0}, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('greater than zero', res.get_json()['message'])

        # Invalid calories and name
        res = self.client.post('/nutrition/add', data={'date': self.today, 'food_name': '', 'calories': 0, 'quantity': 1}, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('greater than 0', res.get_json()['message'])

    def test_06_edit_food_quantity(self):
        """Verify /nutrition/edit/<log_id> updates quantity and scales macros."""
        self.login_test_user()
        # Create a food log first
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, quantity, serving_unit, calories, protein_g, carbs_g, fats_g)
            VALUES (?, ?, 'Lunch', 'Rolled Oats Test', 1.0, 'bowl', 200, 10.0, 35.0, 3.0)
        """, (self.test_user_id, self.today))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Edit portion to 2.5
        payload = {
            'date': self.today,
            'meal_type': 'Lunch',
            'quantity': 2.5
        }
        res = self.client.post(f'/nutrition/edit/{log_id}', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['entry']['quantity'], 2.5)
        self.assertEqual(data['entry']['calories'], 500) # 200 * 2.5
        self.assertEqual(data['entry']['protein_g'], 25.0) # 10.0 * 2.5

        # Cleanup
        conn = database.get_db()
        conn.execute("DELETE FROM nutrition_logs WHERE id = ?", (log_id,))
        conn.commit()
        conn.close()

    def test_07_delete_food_entry(self):
        """Verify /nutrition/delete/<log_id> removes food and returns 200."""
        self.login_test_user()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, quantity, serving_unit, calories, protein_g, carbs_g, fats_g)
            VALUES (?, ?, 'Snack', 'Apple', 1.0, 'medium', 95, 0.5, 25.0, 0.3)
        """, (self.test_user_id, self.today))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()

        res = self.client.post(f'/nutrition/delete/{log_id}', data={'date': self.today}, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (log_id,))
        self.assertIsNone(cursor.fetchone())
        conn.close()

    def test_08_nutrition_page_render_and_summary(self):
        """Verify GET /nutrition renders successfully with all elements and updated totals."""
        self.login_test_user()
        res = self.client.get(f'/nutrition?date={self.today}')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Nutrition & Macros', html)
        self.assertIn('id="searchFoodModal"', html)
        self.assertIn('id="editFoodLogModal"', html)
        self.assertIn('id="addSelectedFoodForm"', html)
        self.assertIn('openEditFoodModal', html)
        self.assertIn('name="protein_g"', html)
        self.assertIn('Essential Muscle-Building Foods', html)

if __name__ == '__main__':
    unittest.main()
