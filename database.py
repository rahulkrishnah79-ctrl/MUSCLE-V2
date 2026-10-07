import sqlite3
import os
import shutil
import re
import logging
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

logger = logging.getLogger("ironpulse.database")

# Try importing modern psycopg 3
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None
    PSYCOPG_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')
SCHEMA_PG_PATH = os.path.join(BASE_DIR, 'schema_pg.sql')

# Tracks whether PostgreSQL schema has been verified/initialized in this process
_pg_initialized = False


def is_postgres_configured() -> bool:
    """
    Check if a PostgreSQL connection URL is configured in environment variables.
    Checks DATABASE_URL (standard) and POSTGRES_URL (Vercel Postgres default).
    Never logs or prints the URL value.
    """
    raw_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or ''
    clean_url = raw_url.strip()
    return bool(clean_url.startswith(('postgres://', 'postgresql://')))


def get_postgres_url() -> str:
    """
    Retrieves and normalizes the PostgreSQL connection URL.
    Normalizes legacy 'postgres://' prefix to modern 'postgresql://'.
    Never logs or exposes credentials.
    """
    raw_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or ''
    clean_url = raw_url.strip()
    if clean_url.startswith('postgres://'):
        clean_url = 'postgresql://' + clean_url[len('postgres://'):]
    return clean_url


def get_database_path():
    """
    Resolves the SQLite database path for local development.
    In Vercel serverless environment (detected via VERCEL env var or AWS_LAMBDA_FUNCTION_NAME),
    copies or creates the database in writable /tmp to allow read-write operations ONLY if DATABASE_URL is NOT set.
    In local development, uses fitness_tracker.db in the project directory.
    Can be explicitly overridden via the DATABASE_PATH environment variable.
    """
    configured_path = os.environ.get('DATABASE_PATH')
    if configured_path:
        return configured_path

    # If running on Vercel without PostgreSQL DATABASE_URL configured
    if not is_postgres_configured() and (os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or os.environ.get('VERCEL_ENV')):
        tmp_db = '/tmp/fitness_tracker.db'
        repo_db = os.path.join(BASE_DIR, 'fitness_tracker.db')
        if not os.path.exists(tmp_db):
            if os.path.exists(repo_db) and os.path.getsize(repo_db) > 0:
                try:
                    shutil.copyfile(repo_db, tmp_db)
                except Exception:
                    pass
        return tmp_db

    return os.path.join(BASE_DIR, 'fitness_tracker.db')


DATABASE_PATH = get_database_path()


# =============================================================================
# COMPATIBILITY LAYER: DUAL-ACCESS ROW & SQL TRANSLATION
# =============================================================================

class CompatibleRow(dict):
    """
    Dual-access row wrapper that provides:
    1. Integer indexing: row[0], row[1]
    2. String key lookup: row['username'], row['id']
    3. Case-insensitive column key access
    4. dict(row), .keys(), .values(), .items(), len(row)
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

    def __repr__(self):
        return f"<CompatibleRow {dict(self.items())}>"


def _replace_placeholders_outside_quotes(sql: str) -> str:
    """Replaces SQLite '?' parameter placeholders with PostgreSQL '%s' outside quotes."""
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
    Translates SQLite SQL query for PostgreSQL:
    1. PRAGMA foreign_keys = ON -> safe no-op ("SELECT 1")
    2. PRAGMA table_info(tbl) -> queries information_schema.columns
    3. INSERT OR REPLACE INTO user_active_plans -> ON CONFLICT (user_id) DO UPDATE ...
    4. Replaces ? placeholders with %s
    5. Appends RETURNING id to INSERT statements lacking RETURNING clause
    Returns: (adapted_sql, is_auto_returning_insert)
    """
    s = sql.strip()

    # 1. PRAGMA foreign_keys = ON -> no-op
    if re.match(r"^PRAGMA\s+foreign_keys\b", s, re.IGNORECASE):
        return ("SELECT 1", False)

    # 2. PRAGMA table_info(table_name) -> information_schema.columns
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

    # 3. Translate INSERT OR REPLACE INTO user_active_plans
    if re.match(r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_active_plans\b", s, re.IGNORECASE):
        s = re.sub(
            r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_active_plans\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
            r"INSERT INTO user_active_plans (\1) VALUES (\2) ON CONFLICT (user_id) DO UPDATE SET plan_id = EXCLUDED.plan_id, started_at = EXCLUDED.started_at",
            s,
            flags=re.IGNORECASE
        )

    # Translate generic INSERT OR REPLACE INTO user_daily_schedules
    if re.match(r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_daily_schedules\b", s, re.IGNORECASE):
        s = re.sub(
            r"^INSERT\s+OR\s+REPLACE\s+INTO\s+user_daily_schedules\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
            r"INSERT INTO user_daily_schedules (\1) VALUES (\2) ON CONFLICT (user_id, date) DO UPDATE SET workout_title = EXCLUDED.workout_title, notes = EXCLUDED.notes",
            s,
            flags=re.IGNORECASE
        )

    # 4. Translate SQLite AUTOINCREMENT in DDL if present
    if "AUTOINCREMENT" in s.upper():
        s = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
            s,
            flags=re.IGNORECASE
        )

    # 5. Replace ? parameter placeholders with %s
    s = _replace_placeholders_outside_quotes(s)

    # 6. Handle lastrowid via RETURNING id on INSERT
    is_auto_returning = False
    if re.match(r"^INSERT\s+INTO\b", s, re.IGNORECASE):
        if not re.search(r"\bRETURNING\b", s, re.IGNORECASE):
            s = s.rstrip(';') + " RETURNING id"
            is_auto_returning = True

    return (s, is_auto_returning)


class PostgresCursorWrapper:
    """
    Wraps a Psycopg 3 cursor to provide SQLite-compatible semantics:
    - Automatically adapts query syntax (? -> %s, PRAGMA, UPSERT)
    - Emulates cursor.lastrowid via RETURNING id
    - Returns CompatibleRow objects from fetchone/fetchall/fetchmany
    """
    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self.lastrowid = None
        self._closed = False

    def execute(self, query, params=None):
        sql_adapted, is_auto_returning = adapt_sql_for_postgres(query)
        if sql_adapted == "SELECT 1" and query.strip().upper().startswith("PRAGMA FOREIGN_KEYS"):
            return self

        if params is not None:
            # Psycopg expects tuple or list
            self._cur.execute(sql_adapted, tuple(params) if not isinstance(params, (tuple, list, dict)) else params)
        else:
            self._cur.execute(sql_adapted)

        if is_auto_returning:
            row = self._cur.fetchone()
            if row:
                self.lastrowid = row[0]

        return self

    def executemany(self, query, params_seq):
        sql_adapted, _ = adapt_sql_for_postgres(query)
        self._cur.executemany(sql_adapted, params_seq)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        col_names = [desc[0] for desc in self._cur.description]
        return CompatibleRow(col_names, row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        col_names = [desc[0] for desc in self._cur.description]
        return [CompatibleRow(col_names, r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        if not rows:
            return []
        col_names = [desc[0] for desc in self._cur.description]
        return [CompatibleRow(col_names, r) for r in rows]

    def __iter__(self):
        if not self._cur.description:
            return iter([])
        col_names = [desc[0] for desc in self._cur.description]
        for row in self._cur:
            yield CompatibleRow(col_names, row)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        if not self._closed:
            self._cur.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PostgresConnectionWrapper:
    """
    Wraps a Psycopg 3 connection to provide SQLite-compatible semantics:
    - conn.cursor() returns PostgresCursorWrapper
    - conn.execute(...) shortcut
    - conn.executescript(script) for multi-statement DDL
    - conn.commit(), conn.rollback(), conn.close()
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self.row_factory = None  # CompatibleRow is handled directly by cursor

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def executescript(self, script):
        with self._conn.cursor() as cur:
            cur.execute(script)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self.close()


# =============================================================================
# DATABASE CONNECTION & INITIALIZATION
# =============================================================================

def get_db():
    """
    Establishes connection to the database.
    - If DATABASE_URL / POSTGRES_URL is configured: connects to PostgreSQL via Psycopg 3.
    - If DATABASE_URL is not configured: connects to SQLite (local fitness_tracker.db).
    Rest of the application calls get_db() without needing to know backend dialect.
    """
    global _pg_initialized

    if is_postgres_configured():
        if not PSYCOPG_AVAILABLE:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: DATABASE_URL is set for PostgreSQL, "
                "but psycopg is not installed. Please install psycopg[binary]."
            )
        pg_url = get_postgres_url()
        raw_conn = psycopg.connect(pg_url)
        conn = PostgresConnectionWrapper(raw_conn)

        # Ensure PostgreSQL tables and seed data exist on initial run
        if not _pg_initialized:
            ensure_postgres_initialized(conn)
            _pg_initialized = True

        return conn

    # ------------------ SQLite Local Fallback ------------------
    db_path = get_database_path()
    db_existed = os.path.exists(db_path) and os.path.getsize(db_path) > 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # If the database was newly created in a serverless environment like /tmp, initialize it
    if not db_existed:
        try:
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.commit()
                migrate_tables(conn)
                import exercise_catalog
                exercise_catalog.seed_exercise_catalog(conn)
                import workout_manager
                workout_manager.get_or_create_default_plans(conn)
                import nutrition_manager
                nutrition_manager.init_food_library(conn)
                import ai_assistant
                ai_assistant.init_chat_tables(conn)
                seed_demo_user_and_data(conn)
        except Exception as e:
            logger.error(f"Error during SQLite database initialization: {e}", exc_info=True)
    else:
        # Check if users table is empty and seed demo user if needed
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                seed_demo_user_and_data(conn)
        except Exception:
            pass

    return conn


def ensure_postgres_initialized(conn: PostgresConnectionWrapper):
    """
    Checks if PostgreSQL schema is initialized; if tables are missing,
    executes schema_pg.sql and populates baseline catalog & demo data.
    Logs errors clearly without silently rolling back.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            logger.info("Initializing PostgreSQL database schema from schema_pg.sql...")
            if not os.path.exists(SCHEMA_PG_PATH):
                raise FileNotFoundError(f"PostgreSQL schema file not found at {SCHEMA_PG_PATH}")

            with open(SCHEMA_PG_PATH, 'r', encoding='utf-8') as f:
                ddl = f.read()

            conn.executescript(ddl)
            logger.info("PostgreSQL schema created successfully. Seeding initial data...")

            # Run standard catalog seeders
            import exercise_catalog
            exercise_catalog.seed_exercise_catalog(conn)

            import workout_manager
            workout_manager.get_or_create_default_plans(conn)

            import nutrition_manager
            nutrition_manager.init_food_library(conn)

            import ai_assistant
            ai_assistant.init_chat_tables(conn)

            seed_demo_user_and_data(conn)
            logger.info("PostgreSQL catalog and demo user seeded successfully.")
        else:
            # Check if demo user exists in PostgreSQL, seed if users table is empty
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                seed_demo_user_and_data(conn)

    except Exception as e:
        logger.error(f"CRITICAL ERROR during PostgreSQL database initialization: {e}", exc_info=True)
        conn.rollback()
        raise


def migrate_tables(conn):
    """Ensures existing tables have all columns and creates any new tables."""
    cursor = conn.cursor()

    # 1. Users table migration
    cursor.execute("PRAGMA table_info(users)")
    existing_user_cols = [row[1] for row in cursor.fetchall()]
    needed_user_cols = [
        ("age", "INTEGER DEFAULT 26"),
        ("gender", "TEXT DEFAULT 'Male'"),
        ("training_days_per_week", "INTEGER DEFAULT 4"),
        ("available_equipment", "TEXT DEFAULT 'Full Commercial Gym'"),
        ("dietary_preference", "TEXT DEFAULT 'High Protein Omnivore'"),
        ("google_id", "TEXT"),
        ("profile_picture", "TEXT"),
        ("auth_provider", "TEXT DEFAULT 'local'")
    ]
    for col_name, col_def in needed_user_cols:
        if col_name not in existing_user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id) WHERE google_id IS NOT NULL")

    # 2. Exercises table migration
    cursor.execute("PRAGMA table_info(exercises)")
    existing_ex_cols = [row[1] for row in cursor.fetchall()]
    needed_ex_cols = [
        ("default_sets", "INTEGER DEFAULT 3"),
        ("default_reps", "INTEGER DEFAULT 10"),
        ("rest_seconds", "INTEGER DEFAULT 90"),
        ("recommended_sets", "TEXT DEFAULT '3-4 sets'"),
        ("recommended_reps", "TEXT DEFAULT '8-12 reps'"),
        ("common_mistakes", "TEXT"),
        ("youtube_id", "TEXT"),
        ("youtube_url", "TEXT")
    ]
    for col_name, col_def in needed_ex_cols:
        if col_name not in existing_ex_cols:
            cursor.execute(f"ALTER TABLE exercises ADD COLUMN {col_name} {col_def}")

    # 3. Workouts table migration
    cursor.execute("PRAGMA table_info(workouts)")
    existing_w_cols = [row[1] for row in cursor.fetchall()]
    needed_w_cols = [
        ("status", "TEXT DEFAULT 'completed'"),
        ("target_muscle_group", "TEXT DEFAULT 'General'"),
        ("completion_rate", "INTEGER DEFAULT 100"),
        ("intensity_rating", "INTEGER DEFAULT 8")
    ]
    for col_name, col_def in needed_w_cols:
        if col_name not in existing_w_cols:
            cursor.execute(f"ALTER TABLE workouts ADD COLUMN {col_name} {col_def}")

    # 4. Workout exercises table migration
    cursor.execute("PRAGMA table_info(workout_exercises)")
    existing_we_cols = [row[1] for row in cursor.fetchall()]
    needed_we_cols = [
        ("completed", "INTEGER DEFAULT 1"),
        ("notes", "TEXT")
    ]
    for col_name, col_def in needed_we_cols:
        if col_name not in existing_we_cols:
            cursor.execute(f"ALTER TABLE workout_exercises ADD COLUMN {col_name} {col_def}")

    # 5. Progress logs table migration
    cursor.execute("PRAGMA table_info(progress_logs)")
    existing_p_cols = [row[1] for row in cursor.fetchall()]
    needed_p_cols = [
        ("body_fat_pct", "REAL"),
        ("chest_cm", "REAL"),
        ("arms_cm", "REAL"),
        ("waist_cm", "REAL"),
        ("thighs_cm", "REAL"),
        ("notes", "TEXT")
    ]
    for col_name, col_def in needed_p_cols:
        if col_name not in existing_p_cols:
            cursor.execute(f"ALTER TABLE progress_logs ADD COLUMN {col_name} {col_def}")

    # 6. Workout plans table migration
    cursor.execute("PRAGMA table_info(workout_plans)")
    existing_wp_cols = [row[1] for row in cursor.fetchall()]
    needed_wp_cols = [
        ("target_muscle_group", "TEXT DEFAULT 'All'"),
        ("is_default", "INTEGER DEFAULT 0")
    ]
    for col_name, col_def in needed_wp_cols:
        if col_name not in existing_wp_cols:
            cursor.execute(f"ALTER TABLE workout_plans ADD COLUMN {col_name} {col_def}")

    # 7. Nutrition logs table migration
    cursor.execute("PRAGMA table_info(nutrition_logs)")
    existing_n_cols = [row[1] for row in cursor.fetchall()]
    needed_n_cols = [
        ("logged_via", "TEXT DEFAULT 'manual'"),
        ("is_estimate", "INTEGER DEFAULT 0"),
        ("image_path", "TEXT")
    ]
    for col_name, col_def in needed_n_cols:
        if col_name not in existing_n_cols:
            cursor.execute(f"ALTER TABLE nutrition_logs ADD COLUMN {col_name} {col_def}")

    # Migrate any legacy 'Arms' exercises into Biceps / Triceps
    cursor.execute("UPDATE exercises SET category = 'Biceps' WHERE category = 'Arms' AND name LIKE '%Curl%'")
    cursor.execute("UPDATE exercises SET category = 'Triceps' WHERE category = 'Arms'")

    # 8. User daily schedules table for editable daily workout schedules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            workout_id INTEGER,
            workout_title TEXT,
            target_muscle_group TEXT DEFAULT 'General',
            duration_minutes INTEGER DEFAULT 60,
            exercise_id INTEGER NOT NULL,
            sets INTEGER NOT NULL DEFAULT 3,
            reps INTEGER NOT NULL DEFAULT 10,
            rest_time INTEGER NOT NULL DEFAULT 90,
            exercise_order INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (exercise_id) REFERENCES exercises (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_daily_schedules ON user_daily_schedules (user_id, date)")

    conn.commit()


def init_db():
    """Initializes tables and populates seed data if empty."""
    conn = get_db()
    if is_postgres_configured():
        ensure_postgres_initialized(conn)
        conn.close()
        return

    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

    migrate_tables(conn)

    # Seed comprehensive exercise catalog with all 8 categories
    import exercise_catalog
    exercise_catalog.seed_exercise_catalog(conn)

    # Initialize workout plans
    import workout_manager
    workout_manager.get_or_create_default_plans(conn)

    # Initialize food items library
    import nutrition_manager
    nutrition_manager.init_food_library(conn)

    # Initialize AI assistant chat tables
    import ai_assistant
    ai_assistant.init_chat_tables(conn)

    # Check if demo user exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_demo_user_and_data(conn)

    conn.close()


def seed_exercises(conn):
    """Seeds comprehensive exercises across Chest, Back, Shoulders, Biceps, Triceps, Legs, Core."""
    exercises = [
        # Chest
        ("Barbell Bench Press", "Chest", "Pectoralis Major, Anterior Deltoid, Triceps", "Barbell", "Intermediate",
         "The fundamental compound movement for building upper body pushing strength and chest mass.",
         "Lie flat on the bench with eyes under the bar. Grip slightly wider than shoulder width. Lower bar smoothly to mid-chest, press upward driving through the feet.",
         4, 8, 90),
        ("Incline Dumbbell Press", "Chest", "Clavicular Pectoral Head (Upper Chest), Front Delts", "Dumbbell", "Intermediate",
         "Isolates the upper chest fibers while allowing a natural wrist rotation and deep stretch.",
         "Set bench to 30-45 degrees. Press dumbbells upward together while maintaining engaged shoulder blades.",
         3, 10, 90),
        ("Cable Chest Fly", "Chest", "Sternal Pectoral Head, Inner Chest Squeeze", "Cable", "Beginner",
         "Provides continuous tension across the entire chest muscle range of motion.",
         "Set pulleys at chest height. Step forward, keep slight bend in elbows, and bring hands together in a hugging motion.",
         3, 12, 60),
        ("Dips", "Chest", "Lower Pectorals, Anterior Deltoid, Triceps", "Bodyweight", "Intermediate",
         "High-intensity compound push for chest lower head and pushing strength.",
         "Grip parallel bars. Lean torso forward ~30 degrees, descend until upper arms are parallel to floor, drive back up.",
         3, 10, 75),
        ("Push-Ups", "Chest", "Pectorals, Anterior Delts, Triceps, Core", "Bodyweight", "Beginner",
         "Classic horizontal pressing foundation for endurance and joint stability.",
         "Hands slightly wider than shoulders, core tightly braced. Lower chest to floor and press through palms.",
         3, 15, 60),

        # Back
        ("Barbell Deadlift", "Back", "Erector Spinae, Latissimus Dorsi, Traps, Glutes, Hamstrings", "Barbell", "Advanced",
         "The king of posterior chain movements for full-body power and dense back thickness.",
         "Stand with mid-foot under barbell. Hinge at hips, grip bar firmly outside knees. Brace core, engage lats, drive hips forward to stand tall.",
         4, 5, 120),
        ("Pull-Ups", "Back", "Latissimus Dorsi, Teres Major, Biceps Brachii", "Bodyweight", "Intermediate",
         "The gold standard vertical pull for building wide V-taper lats.",
         "Pronated grip slightly wider than shoulders. Pull chest towards the bar by driving elbows down and back. Lower with full control.",
         4, 8, 90),
        ("Barbell Bent-Over Row", "Back", "Latissimus Dorsi, Rhomboids, Middle Trapezius", "Barbell", "Intermediate",
         "Heavy horizontal pulling compound for upper and mid-back density.",
         "Hinge hips to 45 degrees, spine neutral. Pull barbell into lower ribs/navel driving through elbows. Squeeze scapulae at top.",
         4, 8, 90),
        ("Lat Pulldown", "Back", "Latissimus Dorsi, Upper Back, Biceps", "Cable", "Beginner",
         "Controlled vertical pulling isolation to master lat recruitment without fatigue.",
         "Grip wide bar, sit with thighs secure under pads. Lean torso slightly back (~10 deg) and draw bar smoothly to upper clavicles.",
         3, 12, 60),
        ("Seated Cable Row", "Back", "Rhomboids, Lats, Lower Trapezius", "Cable", "Beginner",
         "Continuous tension horizontal pulling for posture and mid-back thickness.",
         "Sit upright with knees slightly bent. Pull handle into stomach while retracting shoulder blades. Control eccentric stretch.",
         3, 12, 60),

        # Shoulders
        ("Overhead Barbell Press", "Shoulders", "Anterior & Lateral Deltoid, Triceps, Upper Chest", "Barbell", "Intermediate",
         "The pinnacle compound movement for complete vertical pushing power and boulder shoulders.",
         "Bar resting across front delts. Brace core and glutes. Press bar straight up, tilting head back slightly, lock out overhead.",
         4, 6, 90),
        ("Dumbbell Lateral Raise", "Shoulders", "Lateral Deltoid (Side Delt)", "Dumbbell", "Beginner",
         "Essential isolation movement for capped side delts and upper-body width.",
         "Stand with slight forward torso lean. Raise dumbbells out to sides until elbows reach shoulder height. Pour pitch slightly at peak.",
         4, 15, 60),
        ("Face Pulls", "Shoulders", "Posterior Deltoid, Infraspinatus, Traps, Rhomboids", "Cable", "Beginner",
         "Crucial bulletproofing movement for rear delts and rotator cuff health.",
         "Rope attachment at eye level. Pull rope towards bridge of nose while externally rotating hands back and apart.",
         3, 15, 60),
        ("Dumbbell Arnold Press", "Shoulders", "Anterior & Lateral Delts, Triceps", "Dumbbell", "Intermediate",
         "Dynamic pressing motion taking deltoids through full rotational range of motion.",
         "Start dumbbells in front of chest palms facing in. Press upward while rotating palms forward at top lockout.",
         3, 10, 75),

        # Biceps
        ("Barbell Bicep Curl", "Biceps", "Biceps Brachii (Short & Long Head), Brachialis", "Barbell", "Beginner",
         "Classic mass-builder for heavy loading and bicep peak development.",
         "Shoulder-width underhand grip. Pin elbows to sides, curl barbell up smoothly contracting biceps. Lower under full control.",
         4, 10, 60),
        ("Dumbbell Incline Curl", "Biceps", "Biceps Brachii Long Head (Outer Head Peak)", "Dumbbell", "Intermediate",
         "Deep stretch isolation emphasizing the outer long head for a taller bicep peak.",
         "Bench set to 45-60 degrees. Let arms hang vertically, curl dumbbells up supinating wrists at top for maximum contraction.",
         3, 12, 60),
        ("Hammer Curl", "Biceps", "Brachialis, Brachioradialis, Forearms", "Dumbbell", "Beginner",
         "Neutral grip curl targeting the muscle beneath the bicep to push the arm wider.",
         "Neutral grip (palms facing each other). Curl dumbbells upward keeping wrists rigid. Squeeze forearms and brachialis hard.",
         3, 12, 60),
        ("Preacher Curl", "Biceps", "Biceps Brachii Short Head (Inner Head Thickness)", "Barbell", "Intermediate",
         "Strict isolation preventing shoulder momentum for concentrated bicep tension.",
         "Rest upper arms firmly on preacher pad. Curl EZ-bar or barbell upward without lifting elbows off pad.",
         3, 10, 60),

        # Triceps
        ("Tricep Pushdown (Cable Rope)", "Triceps", "Lateral & Medial Tricep Head", "Cable", "Beginner",
         "Fundamental isolation movement for horseshoe tricep definition.",
         "Attach rope to high pulley. Keep upper arms glued to sides, push hands down and spread rope apart at bottom lockout.",
         4, 12, 60),
        ("Skull Crushers (Lying Triceps Extension)", "Triceps", "Long Head Triceps", "Barbell", "Intermediate",
         "Overhead stretch extension key for maximal long-head tricep size and arm girth.",
         "Lie on flat bench with EZ-bar above chest. Bend elbows to lower bar towards forehead/behind head, extend back to lockout.",
         3, 10, 75),
        ("Overhead Dumbbell Tricep Extension", "Triceps", "Long Head Triceps", "Dumbbell", "Intermediate",
         "Deep vertical stretch isolating the tricep long head throughout full stretch.",
         "Hold heavy dumbbell overhead with both hands forming a diamond grip. Lower dumbbell behind neck, extend fully upward.",
         3, 12, 60),
        ("Bench Tricep Dips", "Triceps", "Triceps Brachii, Anterior Delts", "Bodyweight", "Beginner",
         "Accessible compound bodyweight exercise for high-rep pump and tricep endurance.",
         "Hands behind back on edge of bench, legs extended forward. Lower hips towards floor bending elbows to 90 degrees, press up.",
         3, 15, 60),

        # Legs
        ("Barbell Back Squat", "Legs", "Quadriceps, Gluteus Maximus, Adductors, Core", "Barbell", "Intermediate",
         "The indisputable foundational movement for lower-body power and quad hypertrophy.",
         "Bar placed on upper traps. Feet shoulder-width apart, toes flared slightly. Break at hips and knees simultaneously, descend below parallel, drive up explosively.",
         4, 8, 120),
        ("Romanian Deadlift (RDL)", "Legs", "Hamstrings, Gluteus Maximus, Lower Back", "Barbell", "Intermediate",
         "Premier hip-hinge exercise for lengthening hamstring mass and strengthening hips.",
         "Hold bar with overhand grip. Soft bend in knees, push hips backward maintaining flat back until deep hamstring stretch. Squeeze glutes forward to stand.",
         4, 10, 90),
        ("Leg Press", "Legs", "Quadriceps, Glutes", "Machine", "Beginner",
         "High-volume machine compound allowing safe, heavy quad overload without spinal loading.",
         "Feet shoulder-width on carriage platform. Release safety handles, lower weight until knees are at 90 degrees, press through mid-foot without locking knees.",
         3, 12, 90),
        ("Lying Leg Curl", "Legs", "Hamstrings (Biceps Femoris, Semitendinosus)", "Machine", "Beginner",
         "Direct knee-flexion isolation targeting the posterior leg sweep.",
         "Lie face down on machine with pad against lower calves. Curl legs upward towards glutes, hold peak squeeze for 1 second, lower smoothly.",
         3, 12, 60),
        ("Standing Calf Raise", "Legs", "Gastrocnemius, Soleus", "Machine", "Beginner",
         "Straight-knee calf exercise delivering full vertical ankle flexion overload.",
         "Pads on shoulders, balls of feet on step edge. Lower heels down for deep stretch, rise onto balls of feet contracting calves hard.",
         4, 15, 60),

        # Core / Abs
        ("Hanging Leg Raise", "Core", "Rectus Abdominis (Lower Region), Hip Flexors, Obliques", "Bodyweight", "Intermediate",
         "Dynamic calisthenic core movement demanding pelvic rotation and abdominal contraction.",
         "Hang from pull-up bar with overhand grip. Without swinging, lift knees or straight legs up towards chest by curling pelvis up.",
         3, 12, 60),
        ("Cable Woodchopper", "Core", "Internal & External Obliques, Transverse Abdominis", "Cable", "Beginner",
         "Rotational athletic movement forging rotational power and defined waistline.",
         "Set pulley to high position. Grip handle with both hands, pivot back foot and chop diagonally down across torso towards opposite hip.",
         3, 12, 60),
        ("Ab Roller Wheel", "Core", "Entire Rectus Abdominis, Transverse Abdominis, Lats", "Bodyweight", "Advanced",
         "Elite anti-extension core builder producing maximal eccentric tension.",
         "Kneel with wheel under shoulders. Roll forward extending arms and hips until torso is just above floor, pull back squeezing abs.",
         3, 10, 75),
        ("Cable Crunch", "Core", "Rectus Abdominis", "Cable", "Beginner",
         "Direct weighted abdominal loading to build defined six-pack brick density.",
         "Adjust seat so chest pad contacts upper torso. Crunch forward flexing spine, hold peak contraction for 1 second.",
         3, 15, 60)
    ]

    for ex in exercises:
        name, cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec = ex
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM exercises WHERE name = ?", (name,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE exercises SET
                    category = ?, muscle_group = ?, equipment = ?, difficulty = ?,
                    description = ?, instructions = ?, default_sets = ?, default_reps = ?, rest_seconds = ?
                WHERE id = ?
            """, (cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO exercises (name, category, muscle_group, equipment, difficulty, description, instructions, default_sets, default_reps, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, cat, muscles, equip, diff, desc, instr, sets, reps, rest_sec))
    conn.commit()


def seed_demo_user_and_data(conn):
    """
    Seeds default demo athlete ('alex_pulse') and initial workout, nutrition, and progress records.
    Safely commits demo user first and handles exercise lookups robustly.
    """
    demo_password = generate_password_hash("fitness123")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = 'alex_pulse'")
    existing_demo = cursor.fetchone()
    if existing_demo:
        user_id = existing_demo[0]
    else:
        cursor.execute("""
            INSERT INTO users (
                username, email, password_hash, full_name, age, gender,
                height_cm, weight_kg, experience_level, fitness_goal,
                training_days_per_week, available_equipment, dietary_preference,
                target_weight_kg, daily_calorie_target, daily_protein_target,
                daily_carbs_target, daily_fats_target
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'alex_pulse',
            'alex@ironpulse.fit',
            demo_password,
            'Alex Mercer',
            26,
            'Male',
            181.0,
            78.5,
            'Intermediate (1-3 Years)',
            'Muscle Hypertrophy & Strength',
            5,
            'Full Commercial Gym',
            'High Protein Omnivore',
            82.0,
            2850,
            185,
            320,
            75
        ))
        conn.commit()
        user_id = cursor.lastrowid

    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    three_days_ago = today - timedelta(days=3)

    # Workouts for demo user
    workouts_data = [
        (user_id, "Heavy Push Session: Chest, Shoulders & Triceps", today.isoformat(), 65, 8420.0, 9, "completed", "Chest & Triceps", 100, "Hit a new PR on Bench Press! Pump was incredible."),
        (user_id, "Power Pull Session: Lats, Biceps & Rear Delts", two_days_ago.isoformat(), 70, 9150.0, 8, "completed", "Back & Biceps", 100, "Great focus on mind-muscle connection during Deadlifts."),
        (user_id, "Leg Hypertrophy: Quads, Hamstrings & Calves", three_days_ago.isoformat(), 75, 11200.0, 9, "completed", "Legs", 100, "Brutal leg day. 4 hard working sets of back squats.")
    ]

    for w in workouts_data:
        cursor.execute("""
            INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, completion_rate, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, w)
        w_id = cursor.lastrowid

        if "Push" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Bench Press'")
            r1 = cursor.fetchone()
            cursor.execute("SELECT id FROM exercises WHERE name = 'Incline Dumbbell Press'")
            r2 = cursor.fetchone()
            cursor.execute("SELECT id FROM exercises WHERE name = 'Tricep Pushdown (Cable Rope)' OR name LIKE '%Tricep%Pushdown%'")
            r3 = cursor.fetchone()

            if r1 and r2 and r3:
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 8, 90.0, 90, 1, 'RPE 8.5')", (w_id, r1[0]))
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 3, 10, 32.0, 90, 1, 'Clean stretch')", (w_id, r2[0]))
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 12, 35.0, 60, 1, 'Drop set on last set')", (w_id, r3[0]))
        elif "Pull" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Deadlift'")
            r1 = cursor.fetchone()
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Bicep Curl'")
            r2 = cursor.fetchone()
            if r1 and r2:
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 5, 150.0, 150, 1, 'Conventional stance')", (w_id, r1[0]))
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 3, 12, 35.0, 60, 1, 'Strict form')", (w_id, r2[0]))
        elif "Leg" in w[1]:
            cursor.execute("SELECT id FROM exercises WHERE name = 'Barbell Back Squat'")
            r1 = cursor.fetchone()
            cursor.execute("SELECT id FROM exercises WHERE name = 'Standing Calf Raise'")
            r2 = cursor.fetchone()
            if r1 and r2:
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 8, 120.0, 120, 1, 'Deep below parallel')", (w_id, r1[0]))
                cursor.execute("INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes) VALUES (?, ?, 4, 15, 60.0, 60, 1, '1-sec squeeze')", (w_id, r2[0]))

    # Link demo user to default plan
    cursor.execute("SELECT id FROM workout_plans LIMIT 1")
    plan_row = cursor.fetchone()
    if plan_row:
        cursor.execute("INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at) VALUES (?, ?, ?)", (user_id, plan_row[0], today.isoformat()))

    # Nutrition data
    nutrition_data = [
        (user_id, today.isoformat(), "Breakfast", "Oatmeal with Blueberries, Chia Seeds & Whey Protein", 580, 42.0, 72.0, 12.0),
        (user_id, today.isoformat(), "Lunch", "Grilled Chicken Breast, Brown Jasmine Rice & Broccoli", 720, 58.0, 78.0, 14.0),
        (user_id, today.isoformat(), "Post-Workout", "Whey Protein Isolate Shake & Large Banana", 340, 32.0, 45.0, 3.0),
        (user_id, today.isoformat(), "Dinner", "Wild Salmon Fillet, Roasted Sweet Potatoes & Asparagus", 690, 46.0, 58.0, 24.0),
        (user_id, today.isoformat(), "Snack", "Greek Yogurt (0% Fat) with Honey & Almonds", 280, 22.0, 25.0, 9.0)
    ]
    for meal in nutrition_data:
        cursor.execute("INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, calories, protein_g, carbs_g, fats_g) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", meal)

    # Progress data (date, weight, body_fat, chest, arms, waist, thighs, notes)
    progress_data = [
        (user_id, (today - timedelta(days=28)).isoformat(), 76.8, 14.8, 104.0, 38.0, 83.0, 58.0, "Starting hypertrophy training block."),
        (user_id, (today - timedelta(days=21)).isoformat(), 77.2, 14.6, 104.5, 38.2, 83.0, 58.5, "Weight steadily climbing, feeling energetic."),
        (user_id, (today - timedelta(days=14)).isoformat(), 77.8, 14.5, 105.2, 38.5, 82.8, 59.0, "Deload completed, strength restored."),
        (user_id, (today - timedelta(days=7)).isoformat(), 78.1, 14.4, 105.8, 38.8, 82.5, 59.8, "Good vascularity, recovery is on point."),
        (user_id, today.isoformat(), 78.5, 14.2, 106.4, 39.1, 82.3, 60.5, "Hit 78.5kg milestone! Arms up +1.1cm, Thighs +2.5cm.")
    ]
    for p in progress_data:
        cursor.execute("INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, arms_cm, waist_cm, thighs_cm, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", p)

    conn.commit()
