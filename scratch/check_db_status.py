import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database

conn = database.get_db()
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in database:", tables)
for t in tables:
    if t != 'sqlite_sequence':
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt} rows")

users = conn.execute("SELECT id, username, email FROM users").fetchall()
print("\nUsers in database:")
for u in users:
    print(f"  ID {u['id']}: {u['username']} ({u['email']})")

conn.close()
