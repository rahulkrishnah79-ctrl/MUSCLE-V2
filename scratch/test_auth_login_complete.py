"""
Comprehensive Test Suite for Username/Email Authentication Flow
Tests:
Case A: Register new account -> logout -> login with username (exact, uppercase, mixed-case, spaces)
Case B: Register new account -> logout -> login with email (exact, uppercase, mixed-case, spaces)
Case C: Wrong password -> rejected with "Invalid username/email or password"
Case D: Wrong username/email -> rejected with "Account not found"
Case E: Refresh after login -> user session persists on dashboard
Case F: Logout -> session cleared, dashboard becomes inaccessible
Case G: Login again -> works successfully
Case H: Existing Google account -> Google login still works and links properly
Case I: Existing normal account -> normal login still works
Extra: Password preserving spaces (no trimming)
Extra: Empty input validation -> "Please enter your username/email and password"
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as flask_app
import database


class AuthenticationFlowTestCase(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        self.client = flask_app.app.test_client()

    def test_case_a_register_logout_login_with_username(self):
        """Case A: Register new account -> logout -> login with username (testing case-insensitivity & spaces)."""
        test_user = "AthleticUserA"
        test_email = "athleteA@ironpulse.test"
        test_pass = "Hypertrophy2026!"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (test_user.lower(), test_email.lower()))
        conn.commit()
        conn.close()

        # 1. Register
        reg_resp = self.client.post('/register', data={
            'full_name': 'Athlete Alpha',
            'username': test_user,
            'email': test_email,
            'password': test_pass,
            'confirm_password': test_pass,
            'fitness_goal': 'Muscle Hypertrophy & Strength',
            'experience_level': 'Intermediate (1-3 Years)',
            'height_cm': 180,
            'weight_kg': 80.0
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)
        self.assertIn(b"Account created successfully", reg_resp.data)

        # 2. Logout
        logout_resp = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertIn(b"You have been signed out", logout_resp.data)

        # 3. Login with exact lowercase username
        login_resp = self.client.post('/login', data={
            'username': test_user.lower(),
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Welcome back", login_resp.data)

        # 4. Logout & login with Capitalized username (User entered: 'AthleticUserA')
        self.client.get('/logout')
        login_cap = self.client.post('/login', data={
            'username': 'AthleticUserA',
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_cap.status_code, 200)
        self.assertIn(b"Welcome back", login_cap.data)

        # 5. Logout & login with Accidental Spaces: '  AthleticUserA  '
        self.client.get('/logout')
        login_spaces = self.client.post('/login', data={
            'username': '   AthleticUserA   ',
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_spaces.status_code, 200)
        self.assertIn(b"Welcome back", login_spaces.data)

    def test_case_b_register_logout_login_with_email(self):
        """Case B: Register new account -> logout -> login with email (testing case-insensitivity & spaces)."""
        test_user = "AthleticUserB"
        test_email = "AthleteB@IronPulse.Test"
        test_pass = "StrongPassword99"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (test_user.lower(), test_email.lower()))
        conn.commit()
        conn.close()

        # 1. Register
        reg_resp = self.client.post('/register', data={
            'full_name': 'Athlete Beta',
            'username': test_user,
            'email': test_email,
            'password': test_pass,
            'confirm_password': test_pass,
            'height_cm': 175,
            'weight_kg': 72.0
        }, follow_redirects=True)
        self.assertEqual(reg_resp.status_code, 200)

        # 2. Logout
        self.client.get('/logout')

        # 3. Login with lowercase email
        login_resp1 = self.client.post('/login', data={
            'username': test_email.lower(),
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_resp1.status_code, 200)
        self.assertIn(b"Welcome back", login_resp1.data)

        # 4. Logout & Login with original uppercase/mixed email: 'AthleteB@IronPulse.Test'
        self.client.get('/logout')
        login_resp2 = self.client.post('/login', data={
            'username': 'AthleteB@IronPulse.Test',
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_resp2.status_code, 200)
        self.assertIn(b"Welcome back", login_resp2.data)

        # 5. Logout & Login with email surrounded by accidental spaces: '  AthleteB@IronPulse.Test  '
        self.client.get('/logout')
        login_resp3 = self.client.post('/login', data={
            'username': '   AthleteB@IronPulse.Test   ',
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_resp3.status_code, 200)
        self.assertIn(b"Welcome back", login_resp3.data)

    def test_case_c_wrong_password_rejected(self):
        """Case C: Wrong password -> rejected with 'Invalid username/email or password'."""
        self.client.get('/logout')
        resp = self.client.post('/login', data={
            'username': 'alex_pulse',
            'password': 'WrongPassword123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Invalid username/email or password", resp.data)

    def test_case_d_wrong_username_email_rejected(self):
        """Case D: Wrong username/email -> rejected with 'Account not found'."""
        self.client.get('/logout')
        resp = self.client.post('/login', data={
            'username': 'completely_nonexistent_user_99999@test.com',
            'password': 'SomePassword123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Account not found", resp.data)

    def test_case_e_refresh_after_login_still_logged_in(self):
        """Case E: Refresh after login -> still logged in on dashboard."""
        self.client.get('/logout')
        login_resp = self.client.post('/login', data={
            'username': 'alex_pulse',
            'password': 'fitness123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # Subsequent GET to dashboard (simulating refresh)
        refresh1 = self.client.get('/dashboard')
        self.assertEqual(refresh1.status_code, 200)
        self.assertIn(b"Alex Mercer", refresh1.data)

        refresh2 = self.client.get('/dashboard')
        self.assertEqual(refresh2.status_code, 200)
        self.assertIn(b"Alex Mercer", refresh2.data)

    def test_case_f_logout_dashboard_becomes_inaccessible(self):
        """Case F: Logout -> dashboard becomes inaccessible (redirects to login)."""
        # Ensure logged in first
        self.client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'})

        # Logout
        logout_resp = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)

        # Attempt to access protected dashboard
        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 302)
        self.assertIn('/login', dash_resp.headers['Location'])

    def test_case_g_login_again_works(self):
        """Case G: Login again after logout works seamlessly."""
        self.client.get('/logout')
        res = self.client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alex Mercer", res.data)

    def test_case_h_existing_google_account_compatibility(self):
        """Case H: Google login links to existing account without duplicating, and normal login continues working."""
        link_email = "link_compatibility_athlete@test.com"
        link_user = "link_compat_athlete"
        local_pass = "LocalPass2026!"
        google_sub = "google_sub_link_compat_999"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(email) = ? OR LOWER(username) = ? OR google_id = ?",
                       (link_email.lower(), link_user.lower(), google_sub))
        conn.commit()
        conn.close()

        # 1. User registers local account first
        self.client.post('/register', data={
            'full_name': 'Compatibility Athlete',
            'username': link_user,
            'email': link_email,
            'password': local_pass,
            'confirm_password': local_pass,
            'height_cm': 178,
            'weight_kg': 75.0
        })
        self.client.get('/logout')

        # 2. Later, logs in via Google using same email
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'state_link_compat'

            mock_token = MagicMock()
            mock_token.status_code = 200
            mock_token.json.return_value = {'access_token': 'mock_token_compat'}

            mock_userinfo = MagicMock()
            mock_userinfo.status_code = 200
            mock_userinfo.json.return_value = {
                'sub': google_sub,
                'email': link_email.upper(),  # Testing case-insensitive email linking
                'name': 'Compatibility Athlete',
                'picture': 'https://lh3.googleusercontent.com/compat.jpg'
            }

            with patch('requests.post', return_value=mock_token), \
                 patch('requests.get', return_value=mock_userinfo):
                google_resp = self.client.get('/auth/google/callback?code=good_code&state=state_link_compat', follow_redirects=True)
                self.assertEqual(google_resp.status_code, 200)
                self.assertIn(b"Successfully connected your Google Account", google_resp.data)

        # Verify no duplicate row was created in DB
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(email) = ?", (link_email.lower(),))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)

        cursor.execute("SELECT auth_provider, google_id FROM users WHERE LOWER(email) = ?", (link_email.lower(),))
        row = cursor.fetchone()
        self.assertEqual(row['auth_provider'], 'google_linked')
        self.assertEqual(row['google_id'], google_sub)
        conn.close()

        # 3. Log out and confirm local username/email login STILL WORKS with original password!
        self.client.get('/logout')
        local_login_resp = self.client.post('/login', data={
            'username': link_user,
            'password': local_pass
        }, follow_redirects=True)
        self.assertEqual(local_login_resp.status_code, 200)
        self.assertIn(b"Welcome back", local_login_resp.data)

    def test_case_i_existing_normal_account_login(self):
        """Case I: Existing normal accounts (like alex_pulse demo) log in via username and via email."""
        # Login with username
        self.client.get('/logout')
        res_user = self.client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'}, follow_redirects=True)
        self.assertEqual(res_user.status_code, 200)
        self.assertIn(b"Alex Mercer", res_user.data)

        # Login with email
        self.client.get('/logout')
        res_email = self.client.post('/login', data={'username': 'alex@ironpulse.fit', 'password': 'fitness123'}, follow_redirects=True)
        self.assertEqual(res_email.status_code, 200)
        self.assertIn(b"Alex Mercer", res_email.data)

    def test_empty_credentials_validation(self):
        """Empty username or password shows clear guidance."""
        self.client.get('/logout')
        res = self.client.post('/login', data={'username': '', 'password': ''}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Please enter your username/email and password", res.data)

    def test_password_with_spaces_preserved(self):
        """Passwords containing spaces are NOT stripped or modified before hashing or verification."""
        test_user = "space_pass_user"
        test_email = "space_pass@test.com"
        test_pass = " pass with leading and trailing spaces "

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (test_user.lower(), test_email.lower()))
        conn.commit()
        conn.close()

        # Register
        self.client.post('/register', data={
            'full_name': 'Space Pass Athlete',
            'username': test_user,
            'email': test_email,
            'password': test_pass,
            'confirm_password': test_pass,
            'height_cm': 178,
            'weight_kg': 75.0
        })
        self.client.get('/logout')

        # Login with exact password including spaces
        login_resp = self.client.post('/login', data={
            'username': test_user,
            'password': test_pass
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Welcome back", login_resp.data)


if __name__ == '__main__':
    unittest.main()
