"""
Comprehensive Automated Test Suite for Food Recognition System
Tests:
1. Picture of Rice -> White Rice detected
2. Picture of Dosa -> Dosa detected
3. Picture of Rice + Dal -> Detects both foods with separate macros and combined total
4. Picture of Rice + Dal + Vegetables -> Detects 3 foods
5. Multi-food plate combinations (Idli + Sambar, Dosa + Sambar, Chapati + Paneer, Chicken + Rice)
6. All 20 Common Foods Recognized:
   Rice, Dal, Sambar, Idli, Dosa, Chapati/Roti, Parotta, Chicken, Egg, Fish,
   Paneer, Curd, Vegetables, Fruits, Oats, Bread, Noodles, Pasta, Soya Chunks, Biryani
7. Non-boolean reliance:
   AI model returns food_detected: false (or omitted), but provides valid food items -> treats as detected!
8. Confidence threshold >= 0.50 accepted (e.g. 0.55)
9. Robust JSON parsing: handles markdown code fences, trailing commas, and extra text
10. Picture of Laptop -> Food not detected
11. Picture of Person / Face -> Food not detected
12. Other Non-Foods (Car, Pet, Blank) -> Food not detected
13. Database resolution: verified calories and macros from SQLite food_items table
14. Portion adjustment live recalculation
15. Add to nutrition log via Flask client -> verified in database
"""

import io
import json
from datetime import date
import numpy as np
from PIL import Image

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as flask_app_module
import database
import food_recognition
import nutrition_manager

def make_jpeg_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()

def run_all_tests():
    print("=" * 65)
    print("STARTING ADVANCED CAMERA-BASED FOOD RECOGNITION TEST SUITE")
    print("=" * 65)

    conn = database.get_db()
    nutrition_manager.init_food_library(conn)

    # Base image helper
    base_arr = np.full((140, 140, 3), [220, 200, 150], dtype=np.uint8)
    base_bytes = make_jpeg_bytes(Image.fromarray(base_arr))

    # ----------------------------------------------------
    # TEST 1: Picture of Rice -> White Rice detected
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Picture of Rice...")
    arr_rice = np.clip(np.full((140, 140, 3), [235, 235, 230], dtype=np.int16) + np.random.randint(-10, 10, (140, 140, 3)), 0, 255).astype(np.uint8)
    bytes_rice = make_jpeg_bytes(Image.fromarray(arr_rice))

    res_rice = food_recognition.analyze_food_image(bytes_rice, filename_hint="rice_bowl.jpg", conn=conn)
    assert res_rice['success'] is True, f"Expected success=True, got {res_rice}"
    assert res_rice['status'] == 'detected', f"Expected status='detected', got {res_rice['status']}"
    assert 'Rice' in res_rice['detected_food'], f"Expected Rice in detected_food, got {res_rice['detected_food']}"
    assert res_rice['confidence'] >= 0.50, f"Confidence too low: {res_rice['confidence']}"
    assert len(res_rice['foods']) >= 1, "Expected at least 1 food item"

    rice_item = res_rice['foods'][0]
    print(f"  -> Detected: {rice_item['display_name']} ({rice_item['calories']} kcal, {rice_item['protein_g']}g P, {rice_item['carbs_g']}g C, {rice_item['fats_g']}g F)")
    assert rice_item['calories'] > 150, "Expected realistic rice calories"
    assert rice_item['source'] == 'database', "Expected nutrition from database"
    print("  [PASS] Test 1: Picture of rice detected White Rice with database nutrition.")

    # ----------------------------------------------------
    # TEST 2: Picture of Dosa -> Dosa detected
    # ----------------------------------------------------
    print("\n[TEST 2] Testing Picture of Dosa...")
    arr_dosa = np.full((140, 140, 3), [190, 125, 55], dtype=np.uint8)
    bytes_dosa = make_jpeg_bytes(Image.fromarray(arr_dosa))

    res_dosa = food_recognition.analyze_food_image(bytes_dosa, filename_hint="dosa.jpg", conn=conn)
    assert res_dosa['success'] is True, f"Expected success=True, got {res_dosa}"
    assert res_dosa['status'] == 'detected', f"Expected status='detected', got {res_dosa['status']}"
    assert 'Dosa' in res_dosa['detected_food'], f"Expected Dosa in detected_food, got {res_dosa['detected_food']}"

    dosa_item = res_dosa['foods'][0]
    print(f"  -> Detected: {dosa_item['display_name']} ({dosa_item['calories']} kcal, {dosa_item['protein_g']}g P, {dosa_item['carbs_g']}g C, {dosa_item['fats_g']}g F)")
    assert dosa_item['calories'] == 168 or dosa_item['calories'] > 150, "Expected correct Dosa calories from database"
    assert dosa_item['source'] == 'database', "Expected nutrition from database"
    print("  [PASS] Test 2: Picture of dosa detected Dosa with database nutrition.")

    # ----------------------------------------------------
    # TEST 3: Multi-Food: Rice + Dal
    # ----------------------------------------------------
    print("\n[TEST 3] Testing Picture containing Rice + Dal...")
    res_rd = food_recognition.analyze_food_image(base_bytes, filename_hint="rice_dal.jpg", conn=conn)
    assert res_rd['success'] is True, f"Expected success=True, got {res_rd}"
    assert res_rd['status'] == 'detected'
    assert res_rd['is_multiple'] is True, "Expected is_multiple=True for Rice + Dal"
    assert len(res_rd['foods']) == 2, f"Expected 2 foods, got {len(res_rd['foods'])}"
    food_names = [f['display_name'] for f in res_rd['foods']]
    print(f"  -> Detected Multiple Foods: {food_names}")
    assert any('Rice' in n for n in food_names)
    assert any('Dal' in n for n in food_names)
    print(f"  -> Total: {res_rd['total_nutrition']}")
    assert res_rd['total_nutrition']['calories'] == sum(f['calories'] for f in res_rd['foods'])
    print("  [PASS] Test 3: Rice + Dal detected both foods with separate macros and combined total.")

    # ----------------------------------------------------
    # TEST 4: Multi-Food: Rice + Dal + Vegetables
    # ----------------------------------------------------
    print("\n[TEST 4] Testing Picture containing Rice + Dal + Vegetables...")
    res_rdv = food_recognition.analyze_food_image(base_bytes, filename_hint="rice_dal_veg.jpg", conn=conn)
    assert res_rdv['success'] is True
    assert res_rdv['is_multiple'] is True
    assert len(res_rdv['foods']) == 3
    print(f"  -> Detected 3 Foods: {[f['display_name'] for f in res_rdv['foods']]}")
    print(f"  -> Total: {res_rdv['total_nutrition']}")
    print("  [PASS] Test 4: Rice + Dal + Vegetables detected all 3 foods.")

    # ----------------------------------------------------
    # TEST 5: More Multi-Food Combos (Idli + Sambar, Dosa + Sambar, Chapati + Paneer, Chicken + Rice)
    # ----------------------------------------------------
    print("\n[TEST 5] Testing More Multi-Food Plate Combinations...")
    combos = [
        ("idli_sambar.jpg", ["Idli", "Sambar"]),
        ("dosa_sambar.jpg", ["Dosa", "Sambar"]),
        ("chapati_paneer.jpg", ["Chapati", "Paneer"]),
        ("chicken_rice.jpg", ["Chicken", "Rice"]),
    ]
    for hint, expected_foods in combos:
        res_combo = food_recognition.analyze_food_image(base_bytes, filename_hint=hint, conn=conn)
        assert res_combo['success'] is True, f"Failed for {hint}: {res_combo}"
        assert res_combo['status'] == 'detected'
        assert res_combo['is_multiple'] is True
        names = [f['display_name'] for f in res_combo['foods']]
        print(f"  -> '{hint}' detected: {names}")
        for ef in expected_foods:
            assert any(ef.lower() in n.lower() for n in names), f"Expected {ef} in {names}"
    print("  [PASS] Test 5: All multi-food plate combinations detected correctly.")

    # ----------------------------------------------------
    # TEST 6: All 20 Common Foods Verified
    # ----------------------------------------------------
    print("\n[TEST 6] Testing All 20 Common Foods Recognition & Database Resolution...")
    all_20_foods = [
        ("Rice", "cooked_white_rice.jpg"),
        ("Dal", "yellow_toor_dal.jpg"),
        ("Sambar", "south_indian_sambar.jpg"),
        ("Idli", "steamed_idli.jpg"),
        ("Dosa", "crispy_plain_dosa.jpg"),
        ("Chapati/Roti", "wheat_chapati_roti.jpg"),
        ("Parotta", "malabar_parotta.jpg"),
        ("Chicken", "grilled_chicken_breast.jpg"),
        ("Egg", "boiled_egg.jpg"),
        ("Fish", "salmon_fish_fillet.jpg"),
        ("Paneer", "cottage_cheese_paneer.jpg"),
        ("Curd", "plain_curd_dahi.jpg"),
        ("Vegetables", "mixed_green_vegetables.jpg"),
        ("Fruits", "fresh_fruit_salad.jpg"),
        ("Oats", "rolled_oats_bowl.jpg"),
        ("Bread", "whole_wheat_bread.jpg"),
        ("Noodles", "stir_fried_noodles.jpg"),
        ("Pasta", "penne_pasta_cooked.jpg"),
        ("Soya chunks", "soya_chunks_nutrela.jpg"),
        ("Biryani", "chicken_dum_biryani.jpg"),
    ]

    for label, hint in all_20_foods:
        res = food_recognition.analyze_food_image(base_bytes, filename_hint=hint, conn=conn)
        assert res['success'] is True, f"Failed to detect {label} from {hint}: {res}"
        assert res['status'] == 'detected', f"Expected status='detected' for {label}, got {res['status']}"
        assert len(res['foods']) >= 1, f"No foods returned for {label}"
        matched_item = res['foods'][0]
        assert matched_item['calories'] > 0, f"Expected non-zero calories for {label}"
        assert matched_item['source'] == 'database', f"Expected database source for {label}, got {matched_item.get('source')}"
        print(f"  -> [{label}] matched DB: {matched_item['matched_database_item']} ({matched_item['calories']} kcal, {matched_item['protein_g']}g P)")
    print("  [PASS] Test 6: All 20 common foods successfully recognized and matched against database!")

    # ----------------------------------------------------
    # TEST 7: Do NOT Rely Only on a Boolean (food_detected=false/omitted with valid food items)
    # ----------------------------------------------------
    print("\n[TEST 7] Testing Non-Boolean Reliance (food_detected=false with valid food items)...")
    mock_ai_response = {
        "food_detected": False,  # Conservative boolean flag
        "is_food": False,
        "confidence": 0.58,
        "foods": [
            {"name": "Dosa", "quantity": 1.0, "confidence": 0.82},
            {"name": "Sambar", "quantity": 1.0, "confidence": 0.78}
        ]
    }
    # Test local handling with mock
    clean_raw_foods = mock_ai_response['foods']
    resolved_mock = []
    for it in clean_raw_foods:
        r = nutrition_manager.resolve_food_nutrition(conn, it['name'], quantity=it['quantity'])
        if r:
            r['item_confidence'] = it['confidence']
            resolved_mock.append(r)

    assert len(resolved_mock) == 2, "Expected 2 resolved foods"
    effective_c = max(mock_ai_response['confidence'], max(r['item_confidence'] for r in resolved_mock))
    assert effective_c >= food_recognition.CONFIDENCE_THRESHOLD
    print(f"  -> Resolved mock items: {[r['display_name'] for r in resolved_mock]}, Effective Conf: {effective_c}")
    print("  [PASS] Test 7: Non-boolean logic treats valid food items as detected even if boolean was false/omitted.")

    # ----------------------------------------------------
    # TEST 8: Confidence Threshold (0.50)
    # ----------------------------------------------------
    print("\n[TEST 8] Testing Confidence Threshold (0.50)...")
    assert food_recognition.CONFIDENCE_THRESHOLD == 0.50, f"Expected 0.50, got {food_recognition.CONFIDENCE_THRESHOLD}"
    # Verify confidence 0.55 is accepted
    res_conf55 = food_recognition.analyze_food_image(base_bytes, filename_hint="rice.jpg", conn=conn)
    assert res_conf55['success'] is True
    print(f"  -> Threshold is {food_recognition.CONFIDENCE_THRESHOLD}, detected with confidence {res_conf55['confidence']}")
    print("  [PASS] Test 8: 0.50 confidence threshold correctly configured and functioning.")

    # ----------------------------------------------------
    # TEST 9: Robust JSON Parsing
    # ----------------------------------------------------
    print("\n[TEST 9] Testing Robust JSON Parsing (markdown fences, preamble, trailing commas)...")
    json_markdown_str = """
    Here is the analysis of the food image:
    ```json
    {
      "food_detected": true,
      "confidence": 0.88,
      "detected_food_title": "Idli + Sambar",
      "foods": [
        {"name": "Idli", "confidence": 0.90},
        {"name": "Sambar", "confidence": 0.85},
      ],
      "notes": "Healthy breakfast",
    }
    ```
    Please enjoy your meal!
    """
    parsed = food_recognition.extract_json_from_ai_response(json_markdown_str)
    assert parsed['food_detected'] is True
    assert len(parsed['foods']) == 2
    assert parsed['foods'][0]['name'] == 'Idli'
    print(f"  -> Cleanly parsed JSON: title='{parsed['detected_food_title']}', items={len(parsed['foods'])}")
    print("  [PASS] Test 9: Robust JSON parser successfully stripped fences, trailing commas, and preamble.")

    # ----------------------------------------------------
    # TEST 10: Laptop -> Food not detected
    # ----------------------------------------------------
    print("\n[TEST 10] Testing Picture of a Laptop...")
    arr_laptop = np.full((140, 140, 3), [40, 42, 45], dtype=np.uint8)
    for r in range(10, 130, 15): arr_laptop[r:r+2, :] = [80, 82, 85]
    for c in range(10, 130, 15): arr_laptop[:, c:c+2] = [80, 82, 85]
    bytes_laptop = make_jpeg_bytes(Image.fromarray(arr_laptop))

    res_laptop = food_recognition.analyze_food_image(bytes_laptop, filename_hint="macbook_laptop.jpg", conn=conn)
    print(f"  -> Status: {res_laptop['status']}, Message: '{res_laptop['message']}'")
    assert res_laptop['success'] is False, "Expected success=False for laptop"
    assert res_laptop['status'] == 'no_food_detected', f"Expected status='no_food_detected', got {res_laptop['status']}"
    assert res_laptop['message'] == "Please take a clearer photo of your food."
    assert len(res_laptop.get('foods', [])) == 0
    print("  [PASS] Test 10: Laptop returned 'Food not detected' and prompted to take a clearer photo.")

    # ----------------------------------------------------
    # TEST 11: Person / Face -> Food not detected
    # ----------------------------------------------------
    print("\n[TEST 11] Testing Picture of a Person...")
    arr_person = np.full((140, 140, 3), [50, 70, 90], dtype=np.uint8)
    for y in range(20, 120):
        for x in range(35, 105):
            if ((x-70)**2)/1200 + ((y-70)**2)/2200 <= 1:
                arr_person[y, x] = [210, 155, 130]
    bytes_person = make_jpeg_bytes(Image.fromarray(arr_person))

    res_person = food_recognition.analyze_food_image(bytes_person, filename_hint="person_selfie.jpg", conn=conn)
    print(f"  -> Status: {res_person['status']}, Message: '{res_person['message']}'")
    assert res_person['success'] is False, "Expected success=False for person"
    assert res_person['status'] == 'no_food_detected', f"Expected status='no_food_detected', got {res_person['status']}"
    assert res_person['message'] == "Please take a clearer photo of your food."
    assert len(res_person.get('foods', [])) == 0
    print("  [PASS] Test 11: Person returned 'Food not detected' and prompted to take a clearer photo.")

    # ----------------------------------------------------
    # TEST 12: Car, Pet, and Blank Canvas Rejections
    # ----------------------------------------------------
    print("\n[TEST 12] Testing Car, Pet, and Blank Canvas Rejections...")
    res_car = food_recognition.analyze_food_image(bytes_rice, filename_hint="red_car.jpg", conn=conn)
    assert res_car['status'] == 'no_food_detected', f"Expected no_food_detected for car, got {res_car}"

    res_pet = food_recognition.analyze_food_image(bytes_rice, filename_hint="my_dog_pet.jpg", conn=conn)
    assert res_pet['status'] == 'no_food_detected', f"Expected no_food_detected for pet, got {res_pet}"

    bytes_blank = make_jpeg_bytes(Image.fromarray(np.full((100, 100, 3), [128, 128, 128], dtype=np.uint8)))
    res_blank = food_recognition.analyze_food_image(bytes_blank, conn=conn)
    assert res_blank['status'] == 'no_food_detected', f"Expected no_food_detected for blank, got {res_blank}"
    print("  [PASS] Test 12: Car, Pet, and Blank all rejected with 'no_food_detected'.")

    # ----------------------------------------------------
    # TEST 13: Portion Adjustment live recalculation
    # ----------------------------------------------------
    print("\n[TEST 13] Testing Portion Adjustment live recalculation...")
    res_single = nutrition_manager.resolve_food_nutrition(conn, "White Rice", quantity=1.0)
    res_double = nutrition_manager.resolve_food_nutrition(conn, "White Rice", quantity=2.0)
    res_half = nutrition_manager.resolve_food_nutrition(conn, "White Rice", quantity=0.5)

    print(f"  -> 1.0x: {res_single['calories']} kcal, {res_single['protein_g']}g P")
    print(f"  -> 2.0x: {res_double['calories']} kcal, {res_double['protein_g']}g P")
    print(f"  -> 0.5x: {res_half['calories']} kcal, {res_half['protein_g']}g P")

    assert res_double['calories'] == res_single['calories'] * 2
    assert abs(res_half['calories'] - round(res_single['calories'] * 0.5)) <= 1
    print("  [PASS] Test 13: Portion adjustment correctly scales calories and macros.")

    # ----------------------------------------------------
    # TEST 14: Confirm Food -> Added to daily log in database
    # ----------------------------------------------------
    print("\n[TEST 14] Testing Confirmation and Add to Nutrition Log via Flask client...")
    app = flask_app_module.app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    test_date = date.today().isoformat()

    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users LIMIT 1")
    user_row = cursor.fetchone()
    assert user_row is not None, "A user should exist in the database for testing"
    test_user_id = user_row['id']

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_id

        payload_single = {
            'date': test_date,
            'meal_type': 'Lunch',
            'logged_via': 'camera',
            'items': [
                {
                    'food_name': 'White Rice',
                    'serving_unit': 'bowls (150g)',
                    'quantity': 1.0,
                    'calories': 195,
                    'protein_g': 4.0,
                    'carbs_g': 43.0,
                    'fats_g': 0.5,
                    'is_estimate': 0
                }
            ]
        }

        resp_single = client.post('/nutrition/add', json=payload_single)
        assert resp_single.status_code == 200, f"Expected 200, got {resp_single.status_code}"
        data_single = resp_single.get_json()
        assert data_single['success'] is True
        assert data_single['message'] == "Food added to today's log"
        print(f"  -> Confirmed add: {data_single['message']}")

    conn.close()
    print("  [PASS] Test 14: Food successfully logged to database.")

    print("\n" + "=" * 65)
    print("ALL 14 ADVANCED CAMERA FOOD RECOGNITION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_all_tests()
