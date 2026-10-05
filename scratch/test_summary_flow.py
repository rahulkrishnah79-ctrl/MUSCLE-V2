import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import date
from app import app
import database
import nutrition_manager

def run_summary_lifecycle_test():
    client = app.test_client()
    user_id = 1
    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    today_str = date.today().isoformat()
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_row = dict(cursor.fetchone())

    # 1. Initial summary
    initial = nutrition_manager.get_daily_nutrition_summary(conn, user_id, today_str, user_row)
    init_cals = initial['totals']['calories']
    init_p = initial['totals']['protein']
    print(f"Initial: {init_cals} kcal, {init_p}g protein. Remaining: {initial['remaining']['calories']} kcal, {initial['remaining']['protein']}g P")

    # 2. Add 2 servings of Soy Chunks (id lookup)
    cursor.execute("SELECT * FROM food_items WHERE name LIKE '%Soy Chunks%' LIMIT 1")
    soy = dict(cursor.fetchone())
    conn.close()

    res = client.post('/nutrition/add', data={
        'date': today_str,
        'meal_type': 'Lunch',
        'food_id': soy['id'],
        'quantity': 2.0
    }, follow_redirects=True)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nutrition_logs WHERE user_id = ? AND date = ? AND food_name = ? ORDER BY id DESC LIMIT 1", (user_id, today_str, soy['name']))
    new_entry = dict(cursor.fetchone())
    log_id = new_entry['id']
    print(f"Inserted log_id: {log_id}, qty: {new_entry['quantity']}, cals: {new_entry['calories']}, p: {new_entry['protein_g']}")

    # Check updated summary
    updated = nutrition_manager.get_daily_nutrition_summary(conn, user_id, today_str, user_row)
    expected_cals = init_cals + int(round(soy['calories'] * 2.0))
    expected_p = round(init_p + soy['protein_g'] * 2.0, 1)
    assert updated['totals']['calories'] == expected_cals, f"{updated['totals']['calories']} != {expected_cals}"
    assert updated['totals']['protein'] == expected_p, f"{updated['totals']['protein']} != {expected_p}"
    print(f"After Add: {updated['totals']['calories']} kcal, {updated['totals']['protein']}g protein. Remaining: {updated['remaining']['calories']} kcal")

    # 3. Edit to 3.0 servings
    res_edit = client.post(f'/nutrition/edit/{log_id}', data={
        'date': today_str,
        'meal_type': 'Lunch',
        'quantity': 3.0
    }, follow_redirects=True)
    assert res_edit.status_code == 200

    edited_summary = nutrition_manager.get_daily_nutrition_summary(conn, user_id, today_str, user_row)
    expected_edit_cals = init_cals + int(round(soy['calories'] * 3.0))
    expected_edit_p = round(init_p + soy['protein_g'] * 3.0, 1)
    assert edited_summary['totals']['calories'] == expected_edit_cals
    assert edited_summary['totals']['protein'] == expected_edit_p
    print(f"After Edit (3 servings): {edited_summary['totals']['calories']} kcal, {edited_summary['totals']['protein']}g protein")

    # 4. Remove entry
    res_del = client.post(f'/nutrition/delete/{log_id}', data={'date': today_str}, follow_redirects=True)
    assert res_del.status_code == 200

    reverted = nutrition_manager.get_daily_nutrition_summary(conn, user_id, today_str, user_row)
    assert reverted['totals']['calories'] == init_cals
    assert reverted['totals']['protein'] == init_p
    print(f"After Delete: {reverted['totals']['calories']} kcal, {reverted['totals']['protein']}g protein. Successfully reverted!")
    conn.close()
    print("ALL SUMMARY LIFECYCLE CHECKS PASSED!")

if __name__ == '__main__':
    run_summary_lifecycle_test()
