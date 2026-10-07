import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tempfile
import shutil
import database

tmp_dir = tempfile.mkdtemp()
db_path = os.path.join(tmp_dir, 'fresh_test.db')
os.environ['DATABASE_PATH'] = db_path

# Monkey patch database.seed_demo_user_and_data to fix Tricep Pushdown
orig_code = open('database.py', 'r', encoding='utf-8').read()
assert "WHERE name = 'Tricep Rope Pushdown'" in orig_code

fixed_code = orig_code.replace(
    "WHERE name = 'Tricep Rope Pushdown'",
    "WHERE name = 'Tricep Pushdown (Cable Rope)'"
)

exec(compile(fixed_code, 'database.py', 'exec'), database.__dict__)

conn = database.get_db()
conn.close()

conn2 = database.get_db()
cursor = conn2.cursor()
cursor.execute("SELECT COUNT(*) FROM users")
print("User count:", cursor.fetchone()[0])
cursor.execute("SELECT id, username, email FROM users")
for row in cursor.fetchall():
    print("User:", dict(row))
cursor.execute("SELECT COUNT(*) FROM workouts")
print("Workouts count:", cursor.fetchone()[0])
conn2.close()

shutil.rmtree(tmp_dir, ignore_errors=True)
