-- Muscle Building & Fitness Tracking Database Schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    age INTEGER DEFAULT 26,
    gender TEXT DEFAULT 'Male',
    height_cm REAL DEFAULT 180.0,
    weight_kg REAL DEFAULT 78.5,
    experience_level TEXT DEFAULT 'Intermediate (1-3 Years)',
    fitness_goal TEXT DEFAULT 'Muscle Hypertrophy & Strength',
    training_days_per_week INTEGER DEFAULT 4,
    available_equipment TEXT DEFAULT 'Full Commercial Gym',
    dietary_preference TEXT DEFAULT 'High Protein Omnivore',
    target_weight_kg REAL DEFAULT 82.0,
    daily_calorie_target INTEGER DEFAULT 2850,
    daily_protein_target INTEGER DEFAULT 185,
    daily_carbs_target INTEGER DEFAULT 320,
    daily_fats_target INTEGER DEFAULT 75,
    google_id TEXT UNIQUE,
    profile_picture TEXT,
    auth_provider TEXT DEFAULT 'local',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- Chest, Back, Shoulders, Biceps, Triceps, Legs, Core, Abs
    muscle_group TEXT NOT NULL,
    equipment TEXT NOT NULL, -- Barbell, Dumbbell, Cable, Machine, Bodyweight
    difficulty TEXT NOT NULL, -- Beginner, Intermediate, Advanced
    description TEXT,
    instructions TEXT,
    default_sets INTEGER DEFAULT 3,
    default_reps INTEGER DEFAULT 10,
    recommended_sets TEXT DEFAULT '3-4 sets',
    recommended_reps TEXT DEFAULT '8-12 reps',
    common_mistakes TEXT,
    rest_seconds INTEGER DEFAULT 90,
    youtube_id TEXT,
    youtube_url TEXT
);

CREATE TABLE IF NOT EXISTS workout_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    fitness_goal TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    days_per_week INTEGER NOT NULL,
    available_equipment TEXT NOT NULL,
    target_muscle_group TEXT DEFAULT 'All',
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workout_plan_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL, -- 1 to 7
    day_title TEXT NOT NULL,
    focus_category TEXT NOT NULL,
    is_rest_day INTEGER DEFAULT 0,
    FOREIGN KEY (plan_id) REFERENCES workout_plans (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_plan_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_day_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    sets INTEGER DEFAULT 3,
    reps INTEGER DEFAULT 10,
    rest_seconds INTEGER DEFAULT 90,
    order_idx INTEGER DEFAULT 1,
    notes TEXT,
    FOREIGN KEY (plan_day_id) REFERENCES workout_plan_days (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_active_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    plan_id INTEGER NOT NULL,
    started_at DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES workout_plans (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    date DATE NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    total_volume_kg REAL DEFAULT 0,
    intensity_rating INTEGER DEFAULT 8,
    status TEXT DEFAULT 'completed', -- 'completed', 'in_progress', 'scheduled'
    target_muscle_group TEXT DEFAULT 'General',
    completion_rate INTEGER DEFAULT 100,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    sets INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    weight_kg REAL NOT NULL,
    rest_seconds INTEGER DEFAULT 90,
    completed INTEGER DEFAULT 1, -- 1 for completed, 0 for pending
    notes TEXT,
    FOREIGN KEY (workout_id) REFERENCES workouts (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS food_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    serving_size TEXT NOT NULL,
    serving_unit TEXT NOT NULL,
    calories INTEGER NOT NULL,
    protein_g REAL DEFAULT 0,
    carbs_g REAL DEFAULT 0,
    fats_g REAL DEFAULT 0,
    is_muscle_building INTEGER DEFAULT 1,
    description TEXT
);

CREATE TABLE IF NOT EXISTS nutrition_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    meal_type TEXT NOT NULL, -- Breakfast, Lunch, Dinner, Snack
    food_name TEXT NOT NULL,
    quantity REAL DEFAULT 1.0,
    serving_unit TEXT DEFAULT 'serving',
    calories INTEGER NOT NULL,
    protein_g REAL DEFAULT 0,
    carbs_g REAL DEFAULT 0,
    fats_g REAL DEFAULT 0,
    logged_via TEXT DEFAULT 'manual', -- 'manual' or 'camera'
    is_estimate INTEGER DEFAULT 0,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS progress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    weight_kg REAL NOT NULL,
    body_fat_pct REAL,
    chest_cm REAL,
    arms_cm REAL,
    waist_cm REAL,
    thighs_cm REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sender TEXT NOT NULL, -- 'user' or 'ai'
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
