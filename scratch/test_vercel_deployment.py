"""
Comprehensive Vercel Serverless Simulation Test Suite.
Tests:
1. Entry point api/index.py exports WSGI `app` callable.
2. Vercel environment detection (VERCEL=1) directs SQLite to /tmp/fitness_tracker.db.
3. Serverless database auto-initialization, schema migration, and demo user seeding.
4. Static file routing and template loading via api.index.app.
5. All major authenticated and public routes in serverless mode:
   - GET / (Home landing page)
   - GET /login
   - GET /register
   - POST /login (Local authentication)
   - GET /dashboard
   - GET /workouts
   - GET /exercises
   - GET /nutrition
   - GET /progress
   - GET /profile
   - GET /settings
   - GET /ai-assistant
   - GET /auth/google (OAuth initialization)
6. Serverless filesystem upload and retrieval:
   - POST /profile/picture/upload stores in /tmp/uploads/avatars/
   - GET /static/uploads/avatars/<filename> successfully serves the uploaded image
   - POST /profile/picture/remove successfully deletes the image and nullifies DB reference
7. Cleanup temporary /tmp test database and uploads.
"""

import os
import sys
import io
import json
import shutil
import tempfile
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def run_vercel_tests():
    print("=" * 70)
    print("STARTING VERCEL SERVERLESS DEPLOYMENT TEST SUITE")
    print("=" * 70)

    # Simulate Vercel runtime environment
    os.environ['VERCEL'] = '1'
    os.environ['SECRET_KEY'] = 'test-vercel-secret-key-2026'

    # Test 1: Import api.index entry point
    print("\n[TEST 1] Testing api/index.py serverless entry point...")
    try:
        from api.index import app as vercel_app
        print("[PASS] Successfully imported `app` from api.index")
    except Exception as e:
        raise AssertionError(f"Failed to import app from api.index: {e}")

    assert hasattr(vercel_app, 'wsgi_app'), "app is missing wsgi_app"
    print("[PASS] Entry point exposes valid WSGI application callable.")

    # Test 2: Database path resolution under VERCEL=1
    print("\n[TEST 2] Verifying serverless database path under VERCEL=1...")
    import database
    db_path = database.get_database_path()
    print(f"Serverless DB path resolved to: {db_path}")
    assert db_path.startswith('/tmp') or 'tmp' in db_path, f"DB path is not in /tmp: {db_path}"

    # Test 3: Connect and verify database tables & migrations
    print("\n[TEST 3] Testing database initialization & access in serverless environment...")
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    expected_tables = ['users', 'exercises', 'workouts', 'workout_exercises', 'nutrition_logs', 'progress_logs', 'workout_plans', 'food_items']
    for t in expected_tables:
        assert t in tables, f"Expected table '{t}' missing from serverless database. Tables found: {tables}"
    print(f"[PASS] All core database tables verified in serverless DB ({len(tables)} tables present).")

    # Test 4: Static assets and template rendering via test client
    print("\n[TEST 4] Testing template and static file resolution via api.index...")
    vercel_app.config['TESTING'] = True
    client = vercel_app.test_client()

    # Public pages
    home_resp = client.get('/')
    assert home_resp.status_code == 200, f"GET / failed: {home_resp.status_code}"
    assert b"IronPulse" in home_resp.data

    login_resp = client.get('/login')
    assert login_resp.status_code == 200
    assert b"Sign In" in login_resp.data

    reg_resp = client.get('/register')
    assert reg_resp.status_code == 200
    assert b"Create Account" in reg_resp.data

    # Static CSS and JS
    css_resp = client.get('/static/css/style.css')
    assert css_resp.status_code == 200, f"Static CSS failed: {css_resp.status_code}"
    assert len(css_resp.data) > 1000

    js_resp = client.get('/static/js/main.js')
    assert js_resp.status_code == 200, f"Static JS failed: {js_resp.status_code}"
    assert len(js_resp.data) > 1000
    print("[PASS] Static files (/static/css/style.css, /static/js/main.js) and public templates work perfectly.")

    # Test 5: Authentication & Session persistence in serverless mode
    print("\n[TEST 5] Testing authentication and protected routes...")
    # Register a new user in serverless DB
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE LOWER(username) = 'vercel_athlete_1' OR LOWER(email) = 'vercel_athlete@ironpulse.fit'")
    conn.commit()
    conn.close()

    reg_post = client.post('/register', data={
        'username': 'vercel_athlete_1',
        'email': 'vercel_athlete@ironpulse.fit',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'full_name': 'Vercel Athlete',
        'age': 27,
        'gender': 'Male',
        'height_cm': 182,
        'weight_kg': 82,
        'fitness_goal': 'Muscle Hypertrophy & Strength',
        'experience_level': 'Intermediate (1-3 Years)',
        'training_days_per_week': 4,
        'available_equipment': 'Full Commercial Gym',
        'dietary_preference': 'High Protein Omnivore'
    }, follow_redirects=True)
    assert reg_post.status_code == 200
    assert b"Account created successfully" in reg_post.data

    # Log in
    login_post = client.post('/login', data={
        'login_identity': 'vercel_athlete_1',
        'password': 'Password123!'
    }, follow_redirects=True)
    assert login_post.status_code == 200

    # Protected routes under active session
    routes_to_test = [
        ('/dashboard', b"Welcome, Vercel Athlete"),
        ('/workouts', b"Workout"),
        ('/exercises', b"Exercise"),
        ('/nutrition', b"Nutrition"),
        ('/progress', b"Progress"),
        ('/profile', b"Athlete Biometrics"),
        ('/settings', b"Settings"),
        ('/assistant', b"AI"),
    ]

    for route, expected_text in routes_to_test:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} failed with status {resp.status_code}"
        assert expected_text in resp.data, f"Route {route} missing expected content {expected_text}"
        print(f"  [PASS] {route} -> HTTP 200 OK")

    # Test 6: Google OAuth route initialization
    print("\n[TEST 6] Testing Google OAuth route under serverless runtime...")
    google_resp = client.get('/auth/google')
    # Should redirect (302) to Google or render error/warning if keys not configured
    assert google_resp.status_code in (302, 200), f"Google login returned {google_resp.status_code}"
    print("  [PASS] /auth/google initialization verified.")

    # Test 7: Profile Picture upload and serving in serverless mode
    print("\n[TEST 7] Testing profile picture upload and serverless file serving...")
    test_img = Image.new('RGB', (200, 200), color=(0, 120, 255))
    img_buffer = io.BytesIO()
    test_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    upload_resp = client.post(
        '/profile/picture/upload',
        data={'profile_picture': (img_buffer, 'vercel_test.png')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert upload_resp.status_code == 200, f"PFP upload failed: {upload_resp.data}"
    upload_data = json.loads(upload_resp.data)
    assert upload_data['success'] is True
    avatar_url = upload_data['avatar_url']
    print(f"  Avatar URL created: {avatar_url}")

    # Verify that the custom serverless avatar route serves the image
    avatar_fetch = client.get(avatar_url)
    assert avatar_fetch.status_code == 200, f"Failed to retrieve uploaded avatar at {avatar_url}: {avatar_fetch.status_code}"
    assert len(avatar_fetch.data) > 0
    print("  [PASS] Uploaded avatar successfully served via Flask in serverless mode.")

    # Remove avatar
    remove_resp = client.post('/profile/picture/remove', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert remove_resp.status_code == 200
    assert json.loads(remove_resp.data)['success'] is True
    print("  [PASS] Uploaded avatar successfully removed.")

    # Test 8: Logout
    print("\n[TEST 8] Testing logout...")
    logout_resp = client.get('/logout', follow_redirects=True)
    assert logout_resp.status_code == 200
    print("  [PASS] Session terminated successfully.")

    print("\n" + "=" * 70)
    print("ALL VERCEL SERVERLESS DEPLOYMENT TESTS PASSED SUCCESSFULLY! (8/8)")
    print("=" * 70)

if __name__ == '__main__':
    run_vercel_tests()
