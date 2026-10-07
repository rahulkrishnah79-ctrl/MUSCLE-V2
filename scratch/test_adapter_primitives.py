"""
Unit test for database adapter primitives:
- CompatibleRow dual index/key access
- adapt_sql_for_postgres placeholder and PRAGMA translation
- INSERT RETURNING id and lastrowid capture logic
"""

import re

class CompatibleRow(dict):
    """
    Dual-access row wrapper that supports:
    1. Integer indexing: row[0], row[1]
    2. String key lookup: row['username'], row['id']
    3. Iteration, len(row), dict(row), .keys(), .values(), .items()
    """
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = tuple(values)
        self._keys = list(keys)
        self._lower_map = {k.lower(): k for k in keys if isinstance(k, str)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        if key in self:
            return super().__getitem__(key)
        if isinstance(key, str):
            lower_key = key.lower()
            if lower_key in self._lower_map:
                return super().__getitem__(self._lower_map[lower_key])
        return super().__getitem__(key)

    def keys(self):
        return self._keys

    def values(self):
        return self._values

    def items(self):
        return [(k, self[k]) for k in self._keys]


def replace_placeholders(sql: str) -> str:
    """Replaces ? with %s outside of quoted strings."""
    out = []
    in_single = False
    in_double = False
    escape = False
    for ch in sql:
        if ch == "'" and not in_double:
            if not escape:
                in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            if not escape:
                in_double = not in_double
            out.append(ch)
        elif ch == '?' and not in_single and not in_double:
            out.append('%s')
        else:
            out.append(ch)
    return "".join(out)


def adapt_sql_for_postgres(sql: str) -> tuple[str, bool]:
    """
    Translates SQLite SQL query for PostgreSQL.
    Returns: (adapted_sql, is_auto_returning_insert)
    """
    s = sql.strip()

    # 1. PRAGMA foreign_keys = ON -> no-op
    if re.match(r"^PRAGMA\s+foreign_keys\b", s, re.IGNORECASE):
        return ("SELECT 1", False)

    # 2. PRAGMA table_info(table_name)
    m_info = re.match(r"^PRAGMA\s+table_info\s*\(\s*['\"]?(\w+)['\"]?\s*\)", s, re.IGNORECASE)
    if m_info:
        tbl = m_info.group(1).lower()
        adapted = (
            f"SELECT ordinal_position as cid, column_name as name, data_type as type, "
            f"CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END as notnull, "
            f"column_default as dflt_value, 0 as pk "
            f"FROM information_schema.columns WHERE LOWER(table_name) = '{tbl}' "
            f"ORDER BY ordinal_position"
        )
        return (adapted, False)

    # 3. INSERT OR REPLACE INTO user_active_plans
    if re.match(r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_active_plans\b", s, re.IGNORECASE):
        s = re.sub(
            r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_active_plans\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
            r"INSERT INTO user_active_plans (\1) VALUES (\2) ON CONFLICT (user_id) DO UPDATE SET plan_id = EXCLUDED.plan_id, started_at = EXCLUDED.started_at",
            s,
            flags=re.IGNORECASE
        )

    # 4. Replace ? placeholders with %s
    s = replace_placeholders(s)

    # 5. Handle INSERT RETURNING id for lastrowid
    is_auto_returning = False
    if re.match(r"^INSERT\s+INTO\b", s, re.IGNORECASE):
        if not re.search(r"\bRETURNING\b", s, re.IGNORECASE):
            s = s.rstrip(';') + " RETURNING id"
            is_auto_returning = True

    return (s, is_auto_returning)


def test_primitives():
    # Test CompatibleRow
    row = CompatibleRow(['id', 'username', 'email'], [42, 'alex_pulse', 'alex@ironpulse.fit'])
    assert row[0] == 42
    assert row[1] == 'alex_pulse'
    assert row['id'] == 42
    assert row['username'] == 'alex_pulse'
    assert row['EMAIL'] == 'alex@ironpulse.fit'
    assert dict(row) == {'id': 42, 'username': 'alex_pulse', 'email': 'alex@ironpulse.fit'}
    assert list(row.keys()) == ['id', 'username', 'email']
    print("[PASS] CompatibleRow passed all assertions!")

    # Test adapt_sql_for_postgres
    q1 = "SELECT * FROM users WHERE id = ?"
    a1, r1 = adapt_sql_for_postgres(q1)
    assert a1 == "SELECT * FROM users WHERE id = %s"
    assert not r1

    q2 = "INSERT INTO workouts (user_id, title) VALUES (?, ?)"
    a2, r2 = adapt_sql_for_postgres(q2)
    assert a2 == "INSERT INTO workouts (user_id, title) VALUES (%s, %s) RETURNING id"
    assert r2

    q3 = "INSERT INTO users (id, name) VALUES (?, ?) RETURNING id"
    a3, r3 = adapt_sql_for_postgres(q3)
    assert a3 == "INSERT INTO users (id, name) VALUES (%s, %s) RETURNING id"
    assert not r3

    q4 = "PRAGMA foreign_keys = ON"
    a4, r4 = adapt_sql_for_postgres(q4)
    assert a4 == "SELECT 1"

    q5 = "PRAGMA table_info(users)"
    a5, r5 = adapt_sql_for_postgres(q5)
    assert "information_schema.columns" in a5
    assert "'users'" in a5

    q6 = "INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at) VALUES (?, ?, ?)"
    a6, r6 = adapt_sql_for_postgres(q6)
    assert "ON CONFLICT (user_id) DO UPDATE" in a6
    assert "%s, %s, %s" in a6
    assert a6.endswith("RETURNING id")
    assert r6

    print("[PASS] adapt_sql_for_postgres passed all assertions!")

if __name__ == '__main__':
    test_primitives()
