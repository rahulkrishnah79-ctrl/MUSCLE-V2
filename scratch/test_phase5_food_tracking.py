import sys
import os
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add workspace directory to path
sys.path.insert(0, r"d:\Projects\MentorConnect")

import database
import food_recognition
import nutrition_manager
from app import app

client = app.test_client()

def test_database_migration():
    print("--- 1. Testing Database Schema Migration for Nutrition Logs ---")
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(nutrition_logs)")
    columns = [row['name'] for row in cursor.fetchall()]
    assert 'logged_via' in columns, "Column 'logged_via' missing from nutrition_logs!"
    assert 'is_estimate' in columns, "Column 'is_estimate' missing from nutrition_logs!"
    assert 'image_path' in columns, "Column 'image_path' missing from nutrition_logs!"
    print("✓ 'logged_via', 'is_estimate', and 'image_path' columns verified in SQLite nutrition_logs.")
    conn.close()

def test_food_recognition_module_integrity():
    print("\n--- 2. Testing Food Recognition Engine & AI Policy ---")
    # Verify no fake AI results when unconfigured
    assert not food_recognition.is_ai_configured(), "Expected AI to be unconfigured by default (no keys in .env)"
    provider = food_recognition.get_configured_provider()
    assert provider == "none", f"Expected provider 'none', got {provider}"
    print(f"✓ AI configuration status: {food_recognition.is_ai_configured()} (Provider: {provider})")

    # Test empty input handling
    res_empty = food_recognition.analyze_food_image(None)
    assert not res_empty['success']
    assert res_empty['status'] == 'invalid_image'
    print("✓ Empty image rejected safely.")

    # Test invalid data handling
    res_inv = food_recognition.analyze_food_image("gibberish_string_not_an_image")
    assert not res_inv['success']
    assert res_inv['status'] == 'invalid_image'
    print("✓ Invalid base64 rejected safely.")

    # Test valid image bytes under unconfigured state (strictly no fake AI guesses!)
    fake_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 500
    res_valid_unconfigured = food_recognition.analyze_food_image(fake_jpeg)
    assert not res_valid_unconfigured['success']
    assert not res_valid_unconfigured['configured']
    assert res_valid_unconfigured['status'] == 'ai_unconfigured'
    assert res_valid_unconfigured['detected_food'] is None, "AI must NOT generate fake detected_food when unconfigured!"
    assert "ESTIMATES" in res_valid_unconfigured['disclaimer'], "Disclaimer missing in unconfigured response!"
    print("✓ Honest unconfigured state verified: zero fake AI results generated.")

def test_macro_estimation_helper():
    print("\n--- 3. Testing Nutritional Macro Estimation Helper ---")
    conn = database.get_db()
    # Test single staple match
    est_rice = nutrition_manager.estimate_food_macros_by_query(conn, "White Basmati Rice", 1.0)
    assert est_rice is not None, "Failed to find baseline for White Basmati Rice"
    assert est_rice['calories'] > 100
    assert est_rice['carbs_g'] > 30
    print(f"✓ Single staple match: {est_rice['food_name']} -> {est_rice['calories']} kcal, {est_rice['protein_g']}g P")

    # Test multi-item combination from prompt ("Rice + Dal")
    est_combo = nutrition_manager.estimate_food_macros_by_query(conn, "Rice + Dal", 1.0)
    assert est_combo is not None, "Failed to compute combination for Rice + Dal"
    assert est_combo['calories'] == 375, f"Expected 375 cals for Rice + Dal, got {est_combo['calories']}"
    assert est_combo['protein_g'] == 13.5
    print(f"✓ Combo estimation ({est_combo['food_name']}): {est_combo['calories']} kcal, {est_combo['protein_g']}g P, {est_combo['carbs_g']}g C, {est_combo['fats_g']}g F")
    conn.close()

def test_nutrition_ui_elements():
    print("\n--- 4. Testing Nutrition Page UI & Camera Modal ---")
    client.get('/login/demo', follow_redirects=True)
    res = client.get('/nutrition')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.get_data(as_text=True)

    # 1. "Scan Your Food" button
    assert 'Scan Your Food' in html, "'Scan Your Food' button missing from /nutrition"
    assert 'openScanFoodModal' in html, "openScanFoodModal trigger missing"
    print("✓ 'Scan Your Food' button present in action header.")

    # 2. Meal window camera quick scan buttons
    assert 'Scan Food' in html, "'Scan Food' buttons missing from meal windows"
    print("✓ 'Scan Food' buttons present in meal window sections.")

    # 3. Camera scanner modal
    assert 'id="scanFoodModal"' in html, "#scanFoodModal missing from nutrition.html"
    assert 'id="scanCameraVideo"' in html, "#scanCameraVideo missing"
    assert 'id="scanCaptureCanvas"' in html, "#scanCaptureCanvas missing"
    assert 'id="scanReticleOverlay"' in html, "#scanReticleOverlay missing"
    assert 'id="btnShutterCapture"' in html, "#btnShutterCapture shutter button missing"
    assert 'id="btnFlipCamera"' in html, "#btnFlipCamera missing"
    assert 'id="scanFileInput"' in html, "#scanFileInput fallback missing"
    print("✓ Camera Viewfinder, Shutter Button, Canvas, and Reticle elements verified.")

    # 4. Error state containers
    assert 'id="cameraPermDeniedAlert"' in html, "#cameraPermDeniedAlert missing"
    assert 'id="cameraUnavailableAlert"' in html, "#cameraUnavailableAlert missing"
    print("✓ Camera permission denied & device unavailable error handlers verified.")

    # 5. Form editing & confirmation fields
    assert 'id="scanInputFoodName"' in html, "#scanInputFoodName input missing"
    assert 'id="scanInputMealType"' in html, "#scanInputMealType select missing"
    assert 'id="scanInputServingUnit"' in html, "#scanInputServingUnit input missing"
    assert 'id="scanInputQuantity"' in html, "#scanInputQuantity input missing"
    assert 'id="scanInputCalories"' in html, "#scanInputCalories input missing"
    assert 'id="scanInputProtein"' in html, "#scanInputProtein input missing"
    assert 'id="scanInputCarbs"' in html, "#scanInputCarbs input missing"
    assert 'id="scanInputFats"' in html, "#scanInputFats input missing"
    print("✓ Editable food, meal window, serving unit, quantity, and macro inputs verified.")

    # 6. Prominent Disclaimer Notice
    assert 'Nutritional Estimates Notice' in html, "Nutritional Estimates Notice missing"
    assert 'ESTIMATES' in html, "ESTIMATES capital keyword missing"
    print("✓ Prominent Nutritional Estimates Disclaimer verified.")

    # 7. Required Action Buttons
    assert 'Add to Nutrition' in html, "'Add to Nutrition' button missing"
    assert 'Retake Photo' in html, "'Retake Photo' button missing"
    assert '✎ Edit' in html or 'Edit' in html, "'Edit' button missing"
    print("✓ 'Add to Nutrition', 'Edit', and 'Retake Photo' buttons verified.")

def test_api_endpoints():
    print("\n--- 5. Testing Food Scanner API Endpoints ---")
    client.get('/login/demo', follow_redirects=True)

    # 1. Status endpoint
    res_status = client.get('/nutrition/scan/status')
    assert res_status.status_code == 200
    status_json = res_status.get_json()
    assert 'configured' in status_json
    assert 'provider' in status_json
    assert 'disclaimer' in status_json
    print(f"✓ GET /nutrition/scan/status returned: {status_json}")

    # 2. Estimate endpoint
    res_est = client.get('/nutrition/food-estimate?query=Rice%20%2B%20Dal')
    assert res_est.status_code == 200
    est_json = res_est.get_json()
    assert est_json['success']
    assert est_json['estimate']['calories'] == 375
    print(f"✓ GET /nutrition/food-estimate returned correct combo estimate: {est_json['estimate']['food_name']}")

    # 3. Scan food endpoint with missing payload
    res_bad_scan = client.post('/nutrition/scan-food', json={})
    assert res_bad_scan.status_code == 400
    print("✓ POST /nutrition/scan-food handles missing payload with HTTP 400.")

    # 4. Scan food endpoint with valid JPEG base64 payload
    fake_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/" + "A"*200
    res_scan = client.post('/nutrition/scan-food', json={'image_data': fake_b64})
    assert res_scan.status_code == 200
    scan_json = res_scan.get_json()
    assert not scan_json['configured'], "Should report configured=False"
    assert scan_json['status'] == 'ai_unconfigured'
    assert 'ESTIMATES' in scan_json['disclaimer']
    print(f"✓ POST /nutrition/scan-food processed valid capture cleanly: {scan_json['status']}")

def test_logging_scanned_meal_and_manual_compatibility():
    print("\n--- 6. Testing Camera Logging & Manual Compatibility ---")
    client.get('/login/demo', follow_redirects=True)
    today_str = "2026-10-05"

    # Log a meal via camera scan (AJAX request)
    scan_payload = {
        "date": today_str,
        "meal_type": "Lunch",
        "food_name": "Rice + Dal (Scanned Bowl)",
        "quantity": 1.5,
        "serving_unit": "cups",
        "calories": 560,
        "protein_g": 20.0,
        "carbs_g": 105.0,
        "fats_g": 5.2,
        "logged_via": "camera",
        "is_estimate": 1
    }

    res_add = client.post('/nutrition/add', json=scan_payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_add.status_code == 200, f"Expected 200, got {res_add.status_code}"
    add_json = res_add.get_json()
    assert add_json['success']
    log_id = add_json['log_id']
    print(f"✓ Scanned meal logged successfully with ID: {log_id}")

    # Verify database persistence
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nutrition_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row['food_name'] == "Rice + Dal (Scanned Bowl)"
    assert row['calories'] == 560
    assert row['logged_via'] == 'camera'
    assert row['is_estimate'] == 1
    print(f"✓ SQLite database verified: food='{row['food_name']}', logged_via='{row['logged_via']}', is_estimate={row['is_estimate']}")
    conn.close()

    # Verify UI reflects the scanned meal and badge
    res_page = client.get(f'/nutrition?date={today_str}')
    assert res_page.status_code == 200
    page_html = res_page.get_data(as_text=True)
    assert "Rice + Dal (Scanned Bowl)" in page_html
    assert "📷 Est" in page_html, "Camera estimate badge missing from nutrition table"
    print("✓ /nutrition page renders scanned meal with '📷 Est' badge.")

    # Verify manual entry system remains 100% operational
    manual_form = {
        "date": today_str,
        "meal_type": "Breakfast",
        "food_name": "Eggs (Boiled / Whole)",
        "quantity": 2.0,
        "serving_unit": "servings (2 eggs)"
    }
    # Form post (manual staple from library)
    res_manual = client.post('/nutrition/add', data=manual_form, follow_redirects=True)
    assert res_manual.status_code == 200
    manual_html = res_manual.get_data(as_text=True)
    assert "Eggs (Boiled / Whole)" in manual_html
    print("✓ Manual food logging via library and form post verified operational.")

    # Clean up test entries
    client.post(f'/nutrition/delete/{log_id}', data={'date': today_str})
    print("✓ Cleanup completed.")

if __name__ == "__main__":
    print("==================================================")
    print("  PHASE 5: CAMERA-BASED FOOD TRACKING VERIFICATION")
    print("==================================================")
    test_database_migration()
    test_food_recognition_module_integrity()
    test_macro_estimation_helper()
    test_nutrition_ui_elements()
    test_api_endpoints()
    test_logging_scanned_meal_and_manual_compatibility()
    print("\n==================================================")
    print("  ALL PHASE 5 TESTS PASSED SUCCESSFULLY! (100%)")
    print("==================================================")
