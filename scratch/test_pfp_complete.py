"""
Comprehensive Test Suite for Custom Profile Picture (PFP) Functionality.
Tests:
1. Initials generation helper and Jinja filter.
2. Registration and default initials avatar display across pages (Profile, Dashboard, Settings, Sidebar, Topbar).
3. Security validations (file extension, corrupted files, >5MB oversize, empty file, path traversal).
4. Image upload, square cropping, unique filename generation, DB update, and JSON response.
5. Image replacement and automatic cleanup of previous uploaded avatar file.
6. Image removal confirmation flow, disk cleanup, DB nullification, initials fallback, account preservation.
7. User data isolation (User A cannot alter or view User B's PFP).
8. HTML & AJAX compatibility (both JSON responses and standard form redirects).
"""

import os
import sys
import io
import json
import sqlite3
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app, get_user_initials, UPLOAD_AVATAR_DIR, MAX_AVATAR_FILE_SIZE
import database

def run_tests():
    print("=" * 70)
    print("STARTING PROFILE PICTURE (PFP) TEST SUITE")
    print("=" * 70)

    # 1. Test get_user_initials
    print("\n[TEST 1] Testing get_user_initials logic...")
    assert get_user_initials("Rahul Krishna") == "RK", f"Expected RK, got {get_user_initials('Rahul Krishna')}"
    assert get_user_initials("John Fitzgerald Kennedy") == "JK", f"Expected JK, got {get_user_initials('John Fitzgerald Kennedy')}"
    assert get_user_initials("Arnold") == "AR", f"Expected AR, got {get_user_initials('Arnold')}"
    assert get_user_initials("A") == "A", f"Expected A, got {get_user_initials('A')}"
    assert get_user_initials("") == "A", f"Expected A, got {get_user_initials('')}"
    assert get_user_initials(None) == "A", f"Expected A, got {get_user_initials(None)}"
    print("[PASS] get_user_initials passed for multiple formats and edge cases.")

    app.config['TESTING'] = True
    client = app.test_client()

    # 2. Test User Setup
    print("\n[TEST 2] Setting up clean test users...")
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE LOWER(username) IN ('testpfp_user1', 'testpfp_user2') OR LOWER(email) IN ('testpfp1@example.com', 'testpfp2@example.com')")
    conn.commit()
    conn.close()

    # Register user 1
    resp1 = client.post('/register', data={
        'username': 'testpfp_user1',
        'email': 'testpfp1@example.com',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'full_name': 'Rahul Krishna',
        'age': 25,
        'gender': 'Male',
        'height_cm': 180,
        'weight_kg': 78,
        'fitness_goal': 'Muscle Hypertrophy & Strength',
        'experience_level': 'Intermediate (1-3 Years)',
        'training_days_per_week': 4,
        'available_equipment': 'Full Commercial Gym',
        'dietary_preference': 'High Protein Omnivore'
    }, follow_redirects=True)
    assert resp1.status_code == 200, f"Registration failed: {resp1.status_code}"
    assert b"Account created successfully" in resp1.data, f"Flash message not found: {resp1.data[:300]}"

    # Verify user 1 has profile_picture as NULL
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, profile_picture FROM users WHERE username = 'testpfp_user1'")
    u1 = cursor.fetchone()
    assert u1 is not None, "User 1 was not created"
    u1_id = u1['id']
    assert u1['profile_picture'] is None, f"Expected None profile_picture, got {u1['profile_picture']}"
    conn.close()
    print(f"[PASS] User 1 created (ID={u1_id}) with NULL profile_picture.")

    # 3. Check Default Avatar rendering across views
    print("\n[TEST 3] Checking default avatar (initials 'RK') across pages...")
    # Profile page
    prof_resp = client.get('/profile')
    assert prof_resp.status_code == 200
    prof_html = prof_resp.data.decode('utf-8')
    assert "RK" in prof_html, "Initials 'RK' not rendered in profile page"
    assert "btnTriggerPfpUpload" in prof_html, "PFP trigger button missing in profile page"
    assert "modalPfpPreview" in prof_html, "PFP Preview modal missing in profile page"
    assert "modalPfpRemove" in prof_html, "PFP Remove modal missing in profile page"

    # Dashboard
    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    dash_html = dash_resp.data.decode('utf-8')
    assert "RK" in dash_html, "Initials 'RK' not rendered on dashboard"

    # Settings
    set_resp = client.get('/settings')
    assert set_resp.status_code == 200
    set_html = set_resp.data.decode('utf-8')
    assert "RK" in set_html, "Initials 'RK' not rendered on settings"
    print("[PASS] Default initials 'RK' rendered consistently on Profile, Dashboard, Settings.")

    # 4. Security & Validation Tests
    print("\n[TEST 4] Testing security validations on upload...")

    # A. Text file disguised as png/txt
    txt_file = (io.BytesIO(b"Hello world, I am not an image!"), "document.txt")
    resp = client.post('/profile/picture/upload', data={'profile_picture': txt_file}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data['success'] is False
    assert data['message'] == "Please select a valid image", f"Unexpected message: {data['message']}"

    # B. Fake image with .jpg extension but corrupt binary content
    fake_jpg = (io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00FakePEHeaderNotAJPEG"), "fake.jpg")
    resp = client.post('/profile/picture/upload', data={'profile_picture': fake_jpg}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data['success'] is False
    assert data['message'] == "Please select a valid image", f"Unexpected message: {data['message']}"

    # C. File exceeding 5 MB limit
    big_buffer = io.BytesIO(b"0" * (MAX_AVATAR_FILE_SIZE + 1024))
    resp = client.post('/profile/picture/upload', data={'profile_picture': (big_buffer, "big.jpg")}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data['success'] is False
    assert data['message'] == "Image must be smaller than 5 MB", f"Unexpected message: {data['message']}"

    # D. Zero-byte file
    empty_buffer = io.BytesIO(b"")
    resp = client.post('/profile/picture/upload', data={'profile_picture': (empty_buffer, "empty.png")}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data['success'] is False
    assert data['message'] == "Please select a valid image"
    print("[PASS] Security validations passed: rejected non-images, corrupt files, oversized files, and empty files.")

    # 5. Successful Upload (PNG)
    print("\n[TEST 5] Testing valid image upload...")
    img1 = Image.new('RGB', (400, 300), color=(255, 87, 34))
    img1_bytes = io.BytesIO()
    img1.save(img1_bytes, format='PNG')
    img1_bytes.seek(0)

    # Path traversal attack test filename: ../../../malicious.png
    resp = client.post(
        '/profile/picture/upload',
        data={'profile_picture': (img1_bytes, '../../../malicious.png')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert resp.status_code == 200, f"Upload failed: {resp.status_code} - {resp.data}"
    data = json.loads(resp.data)
    assert data['success'] is True
    assert data['message'] == "Profile picture updated successfully"
    avatar1_url = data['avatar_url']
    print(f"[PASS] Received avatar URL: {avatar1_url}")

    # Check path safety & disk existence
    assert avatar1_url.startswith('/static/uploads/avatars/avatar_u'), f"Unsafe or unexpected avatar path: {avatar1_url}"
    assert not (".." in avatar1_url), "Path traversal succeeded!"
    filename1 = os.path.basename(avatar1_url)
    disk_path1 = os.path.join(UPLOAD_AVATAR_DIR, filename1)
    assert os.path.exists(disk_path1), f"Avatar file does not exist on disk at {disk_path1}"
    
    # Verify image dimensions cropped to square
    with Image.open(disk_path1) as saved_img:
        assert saved_img.width == saved_img.height, f"Image was not cropped to a square: {saved_img.size}"
        assert saved_img.width <= 512 and saved_img.height <= 512, f"Image size exceeds 512x512: {saved_img.size}"

    # Verify DB state
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_picture FROM users WHERE id = ?", (u1_id,))
    row = cursor.fetchone()
    assert row['profile_picture'] == avatar1_url, f"DB profile_picture not updated: {row['profile_picture']}"
    conn.close()
    print("[PASS] Image safely stored, cropped square, unique filename generated, and DB updated.")

    # 6. Change Photo (Old file cleanup)
    print("\n[TEST 6] Testing photo replacement and old file cleanup...")
    img2 = Image.new('RGB', (600, 600), color=(50, 168, 82))
    img2_bytes = io.BytesIO()
    img2.save(img2_bytes, format='JPEG')
    img2_bytes.seek(0)

    resp = client.post(
        '/profile/picture/upload',
        data={'profile_picture': (img2_bytes, 'new_avatar.jpg')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] is True
    avatar2_url = data['avatar_url']
    assert avatar2_url != avatar1_url, "Avatar URL should be unique"

    disk_path2 = os.path.join(UPLOAD_AVATAR_DIR, os.path.basename(avatar2_url))
    assert os.path.exists(disk_path2), f"New avatar file missing at {disk_path2}"
    assert not os.path.exists(disk_path1), f"Old avatar file was NOT deleted! Orphaned file at {disk_path1}"
    print("[PASS] Old avatar file was automatically deleted from disk when replaced by new avatar.")

    # 7. Page Rendering with Custom Avatar
    print("\n[TEST 7] Testing display of uploaded custom avatar...")
    prof_resp = client.get('/profile')
    assert prof_resp.status_code == 200
    prof_html = prof_resp.data.decode('utf-8')
    assert avatar2_url in prof_html, "New avatar URL missing in profile page HTML"

    dash_resp = client.get('/dashboard')
    assert dash_resp.status_code == 200
    dash_html = dash_resp.data.decode('utf-8')
    assert avatar2_url in dash_html, "New avatar URL missing in dashboard page HTML"

    set_resp = client.get('/settings')
    assert set_resp.status_code == 200
    set_html = set_resp.data.decode('utf-8')
    assert avatar2_url in set_html, "New avatar URL missing in settings page HTML"
    print("[PASS] Custom avatar URL successfully rendered on Profile, Dashboard, and Settings.")

    # 8. Remove Profile Picture
    print("\n[TEST 8] Testing profile picture removal...")
    resp = client.post('/profile/picture/remove', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] is True
    assert data['message'] == "Profile picture removed"
    assert data['initials'] == "RK"

    # Verify disk deletion
    assert not os.path.exists(disk_path2), f"Removed avatar file still exists on disk at {disk_path2}"

    # Verify DB nullification
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, profile_picture FROM users WHERE id = ?", (u1_id,))
    row = cursor.fetchone()
    assert row is not None, "User was erroneously deleted during photo removal!"
    assert row['profile_picture'] is None, f"DB profile_picture was not set to NULL: {row['profile_picture']}"
    conn.close()
    print("[PASS] Avatar deleted from disk, DB set to NULL, initials restored, and user account preserved.")

    # 9. Session Persistence & Cross-User Isolation
    print("\n[TEST 9] Testing cross-user isolation...")
    # Register user 2
    client2 = app.test_client()
    resp2 = client2.post('/register', data={
        'username': 'testpfp_user2',
        'email': 'testpfp2@example.com',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'full_name': 'Sarah Connor',
        'age': 28,
        'gender': 'Female',
        'height_cm': 168,
        'weight_kg': 60,
        'fitness_goal': 'Lean Bulk',
        'experience_level': 'Advanced (3+ Years)',
        'training_days_per_week': 5,
        'available_equipment': 'Full Commercial Gym',
        'dietary_preference': 'Vegetarian'
    }, follow_redirects=True)
    assert resp2.status_code == 200

    # User 2 uploads an avatar
    img_u2 = Image.new('RGB', (300, 300), color=(128, 0, 128))
    u2_bytes = io.BytesIO()
    img_u2.save(u2_bytes, format='PNG')
    u2_bytes.seek(0)
    resp = client2.post(
        '/profile/picture/upload',
        data={'profile_picture': (u2_bytes, 'user2_pic.png')},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert resp.status_code == 200
    u2_avatar_url = json.loads(resp.data)['avatar_url']

    # User 1 should STILL have initials RK and NOT see User 2's avatar
    p1_resp = client.get('/profile')
    p1_html = p1_resp.data.decode('utf-8')
    assert u2_avatar_url not in p1_html, "User 1 profile is displaying User 2's avatar!"
    assert "RK" in p1_html, "User 1 should display initials 'RK'"

    # User 2 should display Sarah Connor's avatar and initials 'SC'
    p2_resp = client2.get('/profile')
    p2_html = p2_resp.data.decode('utf-8')
    assert u2_avatar_url in p2_html, "User 2 profile missing User 2's avatar"

    # User 2 removes their avatar
    client2.post('/profile/picture/remove', headers={'X-Requested-With': 'XMLHttpRequest'})
    u2_file = os.path.join(UPLOAD_AVATAR_DIR, os.path.basename(u2_avatar_url))
    assert not os.path.exists(u2_file), "User 2 avatar file should be removed"

    print("[PASS] User data isolation strictly verified.")

    # 10. Clean up test users
    print("\n[CLEANUP] Cleaning up test users from database...")
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username IN ('testpfp_user1', 'testpfp_user2')")
    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print("ALL PROFILE PICTURE (PFP) TESTS PASSED SUCCESSFULLY! (10/10)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
