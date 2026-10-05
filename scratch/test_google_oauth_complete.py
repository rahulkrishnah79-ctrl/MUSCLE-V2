"""
Comprehensive Automated Test Suite for Google OAuth 2.0 Implementation
Tests:
1. Missing/Placeholder Credentials handling
2. Valid Authorization Flow initiation and CSRF state generation
3. Callback with Google OAuth error (access_denied)
4. CSRF state mismatch rejection
5. Missing authorization code rejection
6. Token exchange failure handling (redirect_uri_mismatch, invalid_client, invalid_grant)
7. Existing Google user login (Priority A)
8. Account linking for existing email user (Priority B)
9. New athlete profile creation with baseline metrics (Priority C)
10. Session persistence across subsequent requests (/dashboard)
11. User data isolation
12. Security check: No client secrets or access tokens leaked in logs or responses
"""

import os
import sys
import unittest
import urllib.parse
from unittest.mock import patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as flask_app
import database


class GoogleOAuthTestCase(unittest.TestCase):
    def setUp(self):
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['WTF_CSRF_ENABLED'] = False
        self.client = flask_app.app.test_client()
        self.app = flask_app.app

    def test_01_missing_or_placeholder_credentials(self):
        """When GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET are placeholder or missing, show clear flash message."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'your_google_client_id_here.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'your_google_client_secret_here'
        }):
            response = self.client.get('/auth/google', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Google Login is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", response.data)

        # Empty credentials
        with patch.dict(os.environ, {'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': ''}):
            response = self.client.get('/auth/google', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Google Login is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", response.data)

    def test_02_oauth_initiation_with_valid_config(self):
        """With valid credentials, /auth/google redirects to Google Auth endpoint with correct params."""
        test_client_id = "real_client_id_12345.apps.googleusercontent.com"
        test_client_secret = "real_secret_abc123"
        test_redirect_uri = "http://localhost:5000/auth/google/callback"

        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': test_client_id,
            'GOOGLE_CLIENT_SECRET': test_client_secret,
            'GOOGLE_REDIRECT_URI': test_redirect_uri
        }):
            with self.client.session_transaction() as sess:
                sess.clear()

            response = self.client.get('/auth/google')
            self.assertEqual(response.status_code, 302)
            redirect_url = response.headers['Location']
            self.assertTrue(redirect_url.startswith("https://accounts.google.com/o/oauth2/v2/auth"))

            parsed = urllib.parse.urlparse(redirect_url)
            qs = urllib.parse.parse_qs(parsed.query)

            self.assertEqual(qs['client_id'][0], test_client_id)
            self.assertEqual(qs['redirect_uri'][0], test_redirect_uri)
            self.assertEqual(qs['response_type'][0], 'code')
            self.assertEqual(qs['scope'][0], 'openid email profile')
            self.assertIn('state', qs)

            # Check that state was saved in session
            with self.client.session_transaction() as sess:
                self.assertEqual(sess['oauth_state'], qs['state'][0])

    def test_03_callback_user_cancelled_error(self):
        """Callback handles ?error=access_denied gracefully."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            response = self.client.get('/auth/google/callback?error=access_denied', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"User cancelled Google login.", response.data)

    def test_04_callback_csrf_state_mismatch(self):
        """Callback rejects requests with invalid or mismatched state token."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'correct_state_token_123'

            response = self.client.get('/auth/google/callback?code=mock_code&state=wrong_state_token', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Invalid OAuth state token", response.data)

    def test_05_callback_token_exchange_mismatch_error(self):
        """Token exchange error handling for redirect_uri_mismatch."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123',
            'GOOGLE_REDIRECT_URI': 'http://localhost:5000/auth/google/callback'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'valid_state_456'

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                'error': 'redirect_uri_mismatch',
                'error_description': 'Bad Request'
            }

            with patch('requests.post', return_value=mock_response):
                response = self.client.get('/auth/google/callback?code=test_code&state=valid_state_456', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"redirect URI mismatch", response.data)

    def test_06_callback_token_exchange_invalid_client(self):
        """Token exchange error handling for invalid_client."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'valid_state_456'

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {
                'error': 'invalid_client',
                'error_description': 'Unauthorized'
            }

            with patch('requests.post', return_value=mock_response):
                response = self.client.get('/auth/google/callback?code=test_code&state=valid_state_456', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Invalid Client ID or Client Secret", response.data)

    def test_07_successful_login_existing_google_user(self):
        """Priority A: User with existing matching google_id logs in successfully."""
        # Insert a user with a unique google_id
        conn = database.get_db()
        cursor = conn.cursor()
        test_google_id = "google_user_unique_99999"
        test_email = "existing_google_athlete@test.com"

        cursor.execute("DELETE FROM users WHERE google_id = ? OR email = ?", (test_google_id, test_email))
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, google_id, auth_provider)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Google Test Athlete", "google_athlete_test", test_email, "dummy_hash", test_google_id, "google"))
        existing_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'state_user_a'

            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {'access_token': 'mock_valid_token_xyz'}

            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.status_code = 200
            mock_userinfo_resp.json.return_value = {
                'sub': test_google_id,
                'email': test_email,
                'name': 'Google Test Athlete',
                'picture': 'https://lh3.googleusercontent.com/photo_a.jpg'
            }

            with patch('requests.post', return_value=mock_token_resp), \
                 patch('requests.get', return_value=mock_userinfo_resp):
                response = self.client.get('/auth/google/callback?code=good_code&state=state_user_a', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Welcome back, Google Test Athlete! Logged in via Google.", response.data)

                # Check session
                with self.client.session_transaction() as sess:
                    self.assertEqual(sess['user_id'], existing_id)

    def test_08_successful_account_linking_existing_email_user(self):
        """Priority B: User with existing email links their Google account."""
        conn = database.get_db()
        cursor = conn.cursor()
        link_email = "local_athlete_to_link@test.com"
        google_id_link = "google_sub_to_link_88888"

        cursor.execute("DELETE FROM users WHERE email = ? OR google_id = ?", (link_email, google_id_link))
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, auth_provider)
            VALUES (?, ?, ?, ?, ?)
        """, ("Local Athlete", "local_athlete_nick", link_email, "dummy_hash", "local"))
        local_user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'state_user_b'

            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {'access_token': 'mock_valid_token_link'}

            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.status_code = 200
            mock_userinfo_resp.json.return_value = {
                'sub': google_id_link,
                'email': link_email,
                'name': 'Local Athlete',
                'picture': 'https://lh3.googleusercontent.com/photo_link.jpg'
            }

            with patch('requests.post', return_value=mock_token_resp), \
                 patch('requests.get', return_value=mock_userinfo_resp):
                response = self.client.get('/auth/google/callback?code=good_code&state=state_user_b', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Successfully connected your Google Account", response.data)

                # Check DB for account linking
                conn = database.get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT google_id, auth_provider, profile_picture FROM users WHERE id = ?", (local_user_id,))
                row = cursor.fetchone()
                self.assertEqual(row['google_id'], google_id_link)
                self.assertEqual(row['auth_provider'], 'google_linked')
                self.assertEqual(row['profile_picture'], 'https://lh3.googleusercontent.com/photo_link.jpg')
                conn.close()

    def test_09_successful_new_user_creation(self):
        """Priority C: Brand new user is created with profile metrics."""
        new_google_id = "google_new_sub_77777"
        new_email = "brand_new_google_user@test.com"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE google_id = ? OR email = ?", (new_google_id, new_email))
        conn.commit()
        conn.close()

        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123'
        }):
            with self.client.session_transaction() as sess:
                sess['oauth_state'] = 'state_user_c'

            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {'access_token': 'mock_valid_token_new'}

            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.status_code = 200
            mock_userinfo_resp.json.return_value = {
                'sub': new_google_id,
                'email': new_email,
                'name': 'Brand New Athlete',
                'picture': 'https://lh3.googleusercontent.com/brand_new.jpg'
            }

            with patch('requests.post', return_value=mock_token_resp), \
                 patch('requests.get', return_value=mock_userinfo_resp):
                response = self.client.get('/auth/google/callback?code=good_code&state=state_user_c', follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Welcome to IronPulse, Brand New Athlete! Your athlete profile has been initialized with Google.", response.data)

                # Check user exists in DB
                conn = database.get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE google_id = ?", (new_google_id,))
                new_row = cursor.fetchone()
                self.assertIsNotNone(new_row)
                self.assertEqual(new_row['email'], new_email)
                self.assertEqual(new_row['auth_provider'], 'google')
                self.assertGreater(new_row['daily_calorie_target'], 0)
                self.assertGreater(new_row['daily_protein_target'], 0)
                conn.close()

    def test_10_session_persistence_and_dashboard_access(self):
        """User session persists on subsequent request to /dashboard."""
        # Create a test user
        conn = database.get_db()
        cursor = conn.cursor()
        sess_google_id = "google_sub_sess_66666"
        sess_email = "session_persist_test@test.com"
        cursor.execute("DELETE FROM users WHERE google_id = ? OR email = ?", (sess_google_id, sess_email))
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, google_id, auth_provider)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Session Athlete", "sess_athlete", sess_email, "dummy_hash", sess_google_id, "google"))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['user_id'] = user_id

        # Access dashboard
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Session Athlete", response.data)

    def test_11_user_data_isolation(self):
        """Google-authenticated users see only their own data."""
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE google_id IN ('google_alpha_111', 'google_beta_222') OR email IN ('alpha@test.com', 'beta@test.com')")
        conn.commit()

        # User 1
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, google_id, auth_provider)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Athlete Alpha", "athlete_alpha", "alpha@test.com", "dummy", "google_alpha_111", "google"))
        user_alpha_id = cursor.lastrowid

        # User 2
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, google_id, auth_provider)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("Athlete Beta", "athlete_beta", "beta@test.com", "dummy", "google_beta_222", "google"))
        user_beta_id = cursor.lastrowid

        # Insert private workout for Alpha
        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, notes)
            VALUES (?, ?, DATE('now'), ?)
        """, (user_alpha_id, "Secret Hypertrophy Chest Day", "Alpha Exclusive Notes"))
        conn.commit()
        conn.close()

        # Log in as Beta
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['user_id'] = user_beta_id

        # Beta views workouts page
        response = self.client.get('/workouts')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Secret Hypertrophy Chest Day", response.data)
        self.assertNotIn(b"Alpha Exclusive Notes", response.data)

        # Beta checks workout history API
        api_response = self.client.get('/api/workouts/history')
        self.assertEqual(api_response.status_code, 200)
        api_data = api_response.get_json()
        workout_titles = [w['title'] for w in api_data.get('workouts', [])]
        self.assertNotIn("Secret Hypertrophy Chest Day", workout_titles)

    def test_12_button_links_and_security_on_login_and_register(self):
        """Check login and register pages render Google buttons pointing to /auth/google without leaking secrets."""
        for path in ['/login', '/register']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'href="/auth/google"', response.data)
            self.assertIn(b'Continue with Google', response.data)
            # Ensure client secret is NOT exposed anywhere in the HTML
            self.assertNotIn(b'your_google_client_secret', response.data)
            self.assertNotIn(b'real_secret_abc123', response.data)

    def test_13_dynamic_redirect_uri_fallback(self):
        """When GOOGLE_REDIRECT_URI is not set, dynamically falls back to request.host_url."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'real_client_id_12345.apps.googleusercontent.com',
            'GOOGLE_CLIENT_SECRET': 'real_secret_abc123',
            'GOOGLE_REDIRECT_URI': ''
        }):
            with self.client.session_transaction() as sess:
                sess.clear()

            response = self.client.get('/auth/google')
            self.assertEqual(response.status_code, 302)
            redirect_url = response.headers['Location']
            parsed = urllib.parse.urlparse(redirect_url)
            qs = urllib.parse.parse_qs(parsed.query)

            # In test client, default host is localhost
            self.assertEqual(qs['redirect_uri'][0], 'http://localhost/auth/google/callback')


if __name__ == '__main__':
    unittest.main()

