"""
Test Suite for Session Cookie Configuration across Localhost and Vercel.
Validates:
1. Localhost configuration (VERCEL not set):
   - SESSION_COOKIE_SECURE is False (allows HTTP localhost cookies).
   - SESSION_COOKIE_HTTPONLY is True.
   - SESSION_COOKIE_SAMESITE is 'Lax'.
   - Set-Cookie header does NOT contain 'Secure' attribute.
   - Session persists and user accesses /dashboard.
2. Vercel production configuration (VERCEL='1'):
   - SESSION_COOKIE_SECURE is True (enforces HTTPS secure cookies).
   - SESSION_COOKIE_HTTPONLY is True.
   - SESSION_COOKIE_SAMESITE is 'Lax'.
   - Set-Cookie header DOES contain 'Secure' attribute.
   - Session persists and user accesses /dashboard.
3. Environment variable override for SESSION_COOKIE_SECURE.
4. SECRET_KEY configuration handling (env var and default).
"""

import os
import sys

# Ensure root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def run_session_tests():
    print("=" * 70)
    print("STARTING SESSION COOKIE CONFIGURATION TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # PART 1: LOCALHOST (NON-VERCEL) SIMULATION
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Localhost session cookie behavior...")
    # Clear Vercel env vars
    os.environ.pop('VERCEL', None)
    os.environ.pop('VERCEL_ENV', None)
    os.environ.pop('SESSION_COOKIE_SECURE', None)
    os.environ['SECRET_KEY'] = 'test-secret-key-local-2026'

    # Re-import or reload app
    if 'app' in sys.modules:
        import importlib
        import app
        importlib.reload(app)
    else:
        import app

    from app import app as flask_app
    flask_app.config['TESTING'] = True

    # Assert localhost config values
    assert flask_app.config['SESSION_COOKIE_SECURE'] is False, "Localhost SESSION_COOKIE_SECURE should be False"
    assert flask_app.config['SESSION_COOKIE_HTTPONLY'] is True, "SESSION_COOKIE_HTTPONLY should be True"
    assert flask_app.config['SESSION_COOKIE_SAMESITE'] == 'Lax', "SESSION_COOKIE_SAMESITE should be 'Lax'"
    assert flask_app.config['SESSION_COOKIE_NAME'] == 'ironpulse_session', "Cookie name should be 'ironpulse_session'"
    assert flask_app.config['SECRET_KEY'] == 'test-secret-key-local-2026', "SECRET_KEY was not correctly configured"
    print("[PASS] Localhost configuration attributes verified.")

    # Test login on localhost
    local_client = flask_app.test_client()
    resp = local_client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'})
    assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
    assert resp.headers['Location'] == '/dashboard' or resp.headers['Location'].endswith('/dashboard')

    cookie_headers = resp.headers.getlist('Set-Cookie')
    assert len(cookie_headers) > 0, "Set-Cookie header was missing"
    cookie_str = cookie_headers[0]
    print(f"Localhost Set-Cookie: {cookie_str}")

    assert 'ironpulse_session=' in cookie_str
    assert 'HttpOnly' in cookie_str
    assert 'SameSite=Lax' in cookie_str
    assert 'Secure' not in cookie_str, "Localhost cookie should NOT have 'Secure' flag (breaks HTTP dev server)"

    # Verify session is retained on the subsequent request
    dash_resp = local_client.get('/dashboard')
    assert dash_resp.status_code == 200
    assert b"Welcome, Alex Mercer" in dash_resp.data
    print("[PASS] Localhost session successfully persisted to /dashboard.")

    # -------------------------------------------------------------
    # PART 2: VERCEL (PRODUCTION) SIMULATION
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Vercel production session cookie behavior...")
    os.environ['VERCEL'] = '1'
    os.environ['SECRET_KEY'] = 'test-secret-key-vercel-2026'

    import importlib
    import app
    importlib.reload(app)
    from app import app as vercel_app
    vercel_app.config['TESTING'] = True

    # Assert Vercel production config values
    assert vercel_app.config['SESSION_COOKIE_SECURE'] is True, "Vercel SESSION_COOKIE_SECURE must be True"
    assert vercel_app.config['SESSION_COOKIE_HTTPONLY'] is True, "SESSION_COOKIE_HTTPONLY should be True"
    assert vercel_app.config['SESSION_COOKIE_SAMESITE'] == 'Lax', "SESSION_COOKIE_SAMESITE should be 'Lax'"
    assert vercel_app.config['SESSION_COOKIE_NAME'] == 'ironpulse_session', "Cookie name should be 'ironpulse_session'"
    assert vercel_app.config['PREFERRED_URL_SCHEME'] == 'https', "PREFERRED_URL_SCHEME must be https on Vercel"
    assert vercel_app.config['SECRET_KEY'] == 'test-secret-key-vercel-2026', "SECRET_KEY was not correctly configured"
    print("[PASS] Vercel production configuration attributes verified.")

    # Test login on Vercel
    vercel_client = vercel_app.test_client()
    resp = vercel_client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'}, base_url='https://ironpulse.vercel.app')
    assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"

    cookie_headers = resp.headers.getlist('Set-Cookie')
    assert len(cookie_headers) > 0, "Set-Cookie header was missing"
    cookie_str = cookie_headers[0]
    print(f"Vercel Set-Cookie: {cookie_str}")

    assert 'ironpulse_session=' in cookie_str
    assert 'HttpOnly' in cookie_str
    assert 'SameSite=Lax' in cookie_str
    assert 'Secure' in cookie_str, "Vercel production cookie MUST have 'Secure' flag for modern browser HTTPS retention"

    # Verify session is retained on the subsequent request
    dash_resp = vercel_client.get('/dashboard', base_url='https://ironpulse.vercel.app')
    assert dash_resp.status_code == 200
    assert b"Welcome, Alex Mercer" in dash_resp.data
    print("[PASS] Vercel production session successfully persisted to /dashboard.")

    # -------------------------------------------------------------
    # PART 3: OVERRIDE VIA ENVIRONMENT VARIABLE
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing SESSION_COOKIE_SECURE environment override...")
    os.environ['SESSION_COOKIE_SECURE'] = 'false'
    importlib.reload(app)
    assert app.app.config['SESSION_COOKIE_SECURE'] is False
    print("[PASS] Explicit override to false verified.")

    os.environ['SESSION_COOKIE_SECURE'] = 'true'
    importlib.reload(app)
    assert app.app.config['SESSION_COOKIE_SECURE'] is True
    print("[PASS] Explicit override to true verified.")

    # -------------------------------------------------------------
    # PART 4: SECRET_KEY SECURITY CHECKS
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing SECRET_KEY enforcement & fallback behavior...")
    from unittest.mock import patch
    
    # 4A: Production MUST fail clearly if SECRET_KEY is missing or empty
    os.environ['VERCEL'] = '1'
    os.environ.pop('SECRET_KEY', None)
    
    error_raised = False
    with patch('dotenv.load_dotenv'):
        try:
            importlib.reload(app)
        except RuntimeError as e:
            error_raised = True
            assert "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is missing or empty" in str(e)
            print(f"[PASS] Production cleanly rejected startup without SECRET_KEY: {e}")
    assert error_raised, "Expected RuntimeError when SECRET_KEY is missing in production!"

    # Also test empty string SECRET_KEY in production
    os.environ['SECRET_KEY'] = '   '
    error_raised_blank = False
    with patch('dotenv.load_dotenv'):
        try:
            importlib.reload(app)
        except RuntimeError as e:
            error_raised_blank = True
            assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(e)
            print(f"[PASS] Production cleanly rejected blank/whitespace SECRET_KEY.")
    assert error_raised_blank, "Expected RuntimeError when SECRET_KEY is blank in production!"

    # 4B: Local development MUST work and fallback to dev-only secret if unset
    os.environ.pop('VERCEL', None)
    os.environ.pop('SECRET_KEY', None)
    with patch('dotenv.load_dotenv'):
        importlib.reload(app)
    assert app.app.secret_key == 'dev-only-insecure-secret-key-for-local-development', f"Unexpected secret: {app.app.secret_key}"
    
    dev_client = app.app.test_client()
    dev_resp = dev_client.post('/login', data={'username': 'alex_pulse', 'password': 'fitness123'})
    assert dev_resp.status_code == 302, f"Expected 302 redirect on localhost with dev fallback, got {dev_resp.status_code}"
    print("[PASS] Local development successfully fell back to dev-only key and authentication worked.")

    # 4C: Verify legacy hardcoded key is completely absent
    assert 'ironpulse-fitness-secret-key-2026' != app.app.secret_key
    print("[PASS] Confirmed hardcoded secret key 'ironpulse-fitness-secret-key-2026' is eliminated.")

    # Cleanup
    os.environ.pop('VERCEL', None)
    os.environ.pop('SESSION_COOKIE_SECURE', None)
    os.environ.pop('SECRET_KEY', None)
    importlib.reload(app)

    print("\n" + "=" * 70)
    print("ALL SESSION COOKIE & SECRET KEY FIX TESTS PASSED SUCCESSFULLY! (4/4)")
    print("=" * 70)

if __name__ == '__main__':
    run_session_tests()

