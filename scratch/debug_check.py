import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import date
from app import app

client = app.test_client()
with client.session_transaction() as sess:
    sess['user_id'] = 1

today = date.today().isoformat()
res = client.get(f'/nutrition?date={today}')
html = res.get_data(as_text=True)

checks = [
    'Nutrition & Macros',
    'Nutrition &amp; Macros',
    'id="searchFoodModal"',
    'id="editFoodLogModal"',
    'id="addSelectedFoodForm"',
    'openEditFoodModal',
    'name="protein_g"',
    'Essential Muscle-Building Foods'
]

for c in checks:
    print(c, '-->', c in html)
