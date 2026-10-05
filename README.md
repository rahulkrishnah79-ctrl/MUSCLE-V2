# IronPulse - Muscle Building & Fitness Tracking Web App

A professional, responsive, dark fitness-themed web application built with **Python Flask**, **SQLite**, and vanilla **HTML5 / CSS3 / JavaScript** with **Chart.js** data visualizations.

---

## 📌 Project Description

**IronPulse** is an end-to-end physique engineering and muscle-building application designed for lifters, bodybuilders, and fitness enthusiasts. It bridges the gap between workout tracking, nutritional intake, circumferential body anthropometrics, and personalized AI coaching.

The application calculates physiological targets based on scientific formulas (Mifflin-St Jeor BMR, TDEE, macronutrient distributions), schedules workout splits tailored to experience and available equipment, tracks daily meals across four dining windows, charts multi-month transformation progressions, and features an interactive context-aware AI Fitness Coach.

---

## ✨ Features Overview

### 0. 🌐 Two Clearly Separated Experiences (Public Homepage & Authenticated SaaS App)
- **Public Homepage (`/`)**:
  - High-converting modern dark fitness landing page with branded logo, hero pill badge, and bold headline (*"Build Serious Muscle. Track With Precision"*).
  - Short description highlighting hypertrophy engineering and progressive overload.
  - Call-to-action buttons: **"Get Started Free"**, **"Athlete Login"**, and **"Instant Demo Login"**.
  - Interactive hero dashboard mockup with live biometrics preview.
  - Animated stat counter ticker highlighting scientific equations, 8 muscle categories, and context AI.
  - Comprehensive feature showcase grid covering: Workout Tracking, Nutrition & Macros, Anthropometrics Progress, AI Assistant, and Searchable Exercise Library.
  - Clean public footer with platform links, copyright, and technology badges.
  - **Zero Authenticated Clutter**: The authenticated application sidebar is strictly hidden from unauthenticated visitors.
- **Authenticated SaaS Fitness Application (`/dashboard`, `/workouts`, etc.)**:
  - Fixed, collapsible desktop sidebar with smooth width transitions (expanded 260px $\leftrightarrow$ collapsed 72px rail).
  - Smooth mobile slide-out drawer with backdrop blur and hamburger button.
  - Persistent user preference storage (`localStorage`) for sidebar collapse state.
  - Complete navigation suite:
    1. **Dashboard**
    2. **Workouts**
    3. **Nutrition**
    4. **Progress**
    5. **Exercises**
    6. **AI Assistant**
    7. **Profile**
    8. **Settings**
  - Active page indicator, section headings, athlete quick profile card, and one-click exit in sidebar.
  - SaaS application topbar with real-time breadcrumbs, fitness goal pill, quick "Ask AI" trigger, and avatar.

### 1. 🔐 User Authentication & Dual Sign-In (Local + Google OAuth 2.0)
- **Google OAuth 2.0 Integration**:
  - One-click **"Continue with Google"** sign-in and registration button styled seamlessly with the dark fitness aesthetic.
  - Standard OAuth 2.0 flow (`https://accounts.google.com/o/oauth2/v2/auth` and `https://oauth2.googleapis.com/token`).
  - Fetches verified athlete profile info (Full Name, Email, Profile Picture via `googleapis.com/oauth2/v3/userinfo`).
  - Automatic account provisioning for new athletes with baseline biometrics.
  - Intelligent account linking: automatically connects Google accounts to existing email/password user accounts.
  - Profile picture display in navbar and athlete profile biometrics with "Google Connected" badge.
  - Robust error handling (cancellation, access denial, missing credentials alert, CSRF state verification).
- **Secure Local Registration**: Full Name, Username, Email, Password verification with password hashing via `werkzeug.security` (PBKDF2/scrypt).
- **Session Protection**: Encrypted HTTP cookie sessions with a 7-day persistent lifespan.
- **Route Guarding**: Custom `@login_required` decorator protecting all user data routes.
- **Data Isolation**: Strict user-level multi-tenancy (`user_id = g.user['id']`) across all database queries.
- **Instant Demo Login**: 1-click evaluation access pre-populated with training sessions, meal logs, and transformation checkpoints.

### 2. 📊 Comprehensive Athlete Profile & Diagnostics
- **Biometric Attributes**: Age, Gender, Height, Weight, Target Weight, Experience Level, Primary Fitness Goal, Training Days Per Week, Available Equipment, and Dietary Preference.
- **Calculated Diagnostics**:
  - **Body Mass Index (BMI)** with WHO categorization (Underweight, Normal/Athletic, Overweight/Muscular, Obese).
  - **Basal Metabolic Rate (BMR)** via the Mifflin-St Jeor formula.
  - **Total Daily Energy Expenditure (TDEE)** scaled by weekly workout frequency multipliers (1.375× to 1.9×).
  - **Target Daily Caloric Requirement** calibrated for Hypertrophy (+350 kcal surplus), Cutting (-450 kcal deficit), Strength (+250 kcal), or Recomposition (maintenance).
  - **Recommended Protein Intake** (1.9 g/kg to 2.3 g/kg depending on goal).
- **1-Click Sync**: Apply scientific recommendations instantly to daily dashboard targets.

### 3. 📈 Professional Unified Dashboard
- **Current Weight Card**: Scale weight with target comparison.
- **BMI Diagnostic Card**: Live BMI value and health status badge.
- **Daily Calorie Target**: Dynamic progress bar comparing consumed vs. target calories with surplus/deficit feedback.
- **Daily Protein Target**: Dedicated hypertrophy protein fulfillment tracker.
- **Today's Calories & Today's Protein**: Live aggregation of today's nutrition logs.
- **Today's Scheduled Workout**: Session status (`Scheduled`, `In Progress`, `Completed`), target muscle focus, and 1-click start/resume buttons.
- **Workout Consistency Streak**: Real-time consecutive training day counter.
- **Weekly Workout Completion**: Interactive weekly goal fulfillment metric.
- **Interactive Weight Progress Chart**: Chart.js time-series graph displaying scale weight trajectory against target goal lines.

### 4. 🏋️ Workout Programming & Management System
- **Pre-Built Science-Backed Splits**:
  - 4-Day Upper / Lower Hypertrophy Split
  - 5-Day Push / Pull / Legs (PPL) Power Hypertrophy Split
  - 3-Day Full Body Foundational Split
  - 4-Day Dumbbells & Bench Split
- **Custom Plan Generator**: Formulates personalized periodized splits for any training frequency (3 to 6 days/week) and muscle specialization.
- **Active Workout Execution Mode (`/workouts/active/<id>`)**:
  - Live session stopwatch timer.
  - Real-time set completion toggles with weight (kg) and reps logging.
  - Interactive rest interval countdown timer (30s, 60s, 90s, 120s, 180s) with audio bell notifications.
  - Automatic calculation of cumulative training volume load (kg).
- **Historical Workout Logs**: Chronological log of past workouts, volume lifted, intensity ratings, and reflection notes.

### 5. 🥗 Comprehensive Nutrition & Macronutrient Tracker
- **Meal Windows**: Breakfast, Lunch, Dinner, and Snacks/Post-Workout.
- **Real-Time Food Library**: Instant modal search with common muscle-building foods (Eggs, Milk, Curd, Paneer, Soy chunks, Dal, Peanuts, Oats, Rice, Chicken breast, Salmon, Greek yogurt, Whey protein).
- **Custom Food Entries**: Option to log custom foods with tailored serving sizes.
- **Macro Tracking**: Total calories, protein, carbohydrates, and dietary fats with remaining target counters.
- **📷 Camera-Based Food Tracking ("Scan Your Food" - Phase 5)**:
  - **Live Viewfinder & Capture**: Modern in-browser camera integration using `getUserMedia` with animated scanning reticle, mobile front/rear camera flip toggle, and photo upload fallback.
  - **AI Vision Recognition Engine**: Pluggable backend architecture supporting real Google Gemini or OpenAI vision inference (`GEMINI_API_KEY` / `OPENAI_API_KEY`).
  - **Strict No-Fake-AI Policy**: When an external API key is unconfigured, the system transparently reports unconfigured state and provides instant baseline macro lookup without generating fake AI guesses.
  - **Prominent Estimation Disclaimers**: Explicit alerts that visual scans provide nutritional *ESTIMATES* and cannot determine exact cooking oils or microscopic gram weights.
  - **Full User Control & Editing**: Users can edit detected food names, meal windows, serving units, quantities, calories, and macros with dynamic scaling.
  - **Seamless Flow**: "Add to Nutrition", "Edit", and "Retake Photo" controls with direct SQLite persistence (`logged_via='camera'`, `is_estimate=1`) and `📷 Est` meal badges.
  - **Zero Regression**: Existing manual search and custom food logging systems remain completely intact and functional.

### 6. 📏 Transformation & Physique Progress Tracking
- **Body Anthropometrics**: Scale Weight, Body Fat %, Chest, Waist, Arms, and Thigh measurements.
- **Analytical Charts (Chart.js)**:
  - Weight Progression Trajectory
  - Workout Adherence & Consistency (Last 8 Weeks)
  - Torso Circumference (Chest vs. Waist)
  - Limbs Hypertrophy (Flexed Biceps vs. Thighs)
- **Metrics Summary**: Starting weight, net weight change, milestone completion percentage, and check-in history table.

### 7. 📚 Searchable Exercise Movement Library & YouTube Video References
- **8 Dedicated Muscle Categories**: Chest, Back, Shoulders, Biceps, Triceps, Legs, Core, and Abs.
- **Detailed Movement Metadata**: Muscle anatomy, equipment required, difficulty tier, execution instructions, recommended sets/reps, and common mistakes alert box.
- **Multi-Filter & Instant Search**: Filter by Category, Equipment (Barbell, Dumbbell, Cable, Machine, Bodyweight), Difficulty, and real-time text search.
- **Workout Integration**: Direct "Add to Workout Session" button that appends exercises to active training sessions.
- **Integrated YouTube Video Tutorial References (Phase 4)**:
  - **No Local Video Hosting**: Stores only verified YouTube IDs and canonical URLs in the SQLite database (`exercises.youtube_id`, `exercises.youtube_url`).
  - **Evidence-Based Tutorial Library**: High-quality form guides from verified educators for key movements:
    - *Bench Press* & *Incline Bench Press*
    - *Squat* & *Deadlift* (including Romanian Deadlift)
    - *Lat Pulldown* & *Bent-Over Barbell Row*
    - *Overhead Barbell Press* & *Dumbbell Shoulder Press*
    - *Dumbbell Lateral Raise*
    - *Barbell Bicep Curl* & *Incline Dumbbell Curl*
    - *Tricep Pushdown* & *Skull Crushers*
    - *Leg Press*, *Lying Leg Curl*, *Leg Extension*, and *Standing Calf Raise*
    - *Abdominal Plank*
  - **Responsive 16:9 Thumbnail Cards**: Lazy-loaded 16:9 thumbnail cards with animated play button overlays.
  - **Responsive Embed Modal Player**: In-app modal video player utilizing privacy-enhanced `youtube-nocookie.com/embed/<id>` with auto-stop on close and external "Open on YouTube" link.
  - **Clean Fallback State**: Displays an elegant "Tutorial unavailable" pill if a tutorial is unassigned rather than broken links.
  - **Ubiquitous Access**: Watch Tutorial controls available across the Exercise Catalog, Workout Management routine tables, and the Active Training Session interface.

### 8. 🤖 Context-Aware AI Fitness Assistant
- **Athlete Context Injection**: Considers weight, height, age, goal, experience, available equipment, dietary preferences, today's logged calories/protein, and recent workout history.
- **Supported Query Intents**:
  - *"Create a chest workout"*
  - *"How much protein should I eat?"*
  - *"What should I eat after my workout?"*
  - *"Create a 4-day workout plan"*
  - *"How can I improve my bench press?"*
  - *"Give me a cheap high-protein meal"*
- **Chat Experience**: Modern split-view chat interface, suggested question chips, asynchronous AJAX responses with typing indicator, and persistent chat history in SQLite (`ai_chat_messages`).
- **Prominent Medical Disclaimer**: Explicit notice regarding general fitness guidance vs. clinical advice.

### 9. ⚡ Professional Loading Experience & Skeleton System (Phase 6)
- **Initial Application Loader**:
  - Branded startup overlay featuring the IronPulse logo, animated barbell lifting SVG, sleek progress bar, and the official tagline: *"Building a stronger you."*
  - Non-blocking design: smoothly fades out on `window.onload` or `DOMContentLoaded` with a safety timeout, never holding the user unnecessarily.
  - Universal theme support: uses CSS theme variables for dark obsidian and clean light modes with zero flash of unstyled content.
- **Page Transitions**:
  - Slim top progress bar (`#pageTransitionBar`) with gradient glow that triggers immediately on navigation link clicks to eliminate blank screen perception.
- **Universal Form & Database Request Feedback**:
  - Universal `.is-loading` button states with spinning indicator (`.btn-spinner`) and duplicate-submission prevention on all POST forms.
  - Contextual action feedback: *"Generating Periodized Split..."*, *"Activating Split..."*, *"Starting..."*, and *"Saving Session..."*.
- **AI Coach Response Skeleton**:
  - Animated thinking card featuring coach avatar, pulsating status dots, and multi-line shimmering skeleton bars before reply delivery.
- **Nutrition Scanner & Camera Processing**:
  - Real-time camera viewfinder initialization spinner, reticle overlay, and analyzing stage with visual inference spinner and skeleton shimmer lines.
- **Dashboard Skeleton Placeholders**:
  - Smooth skeleton placeholders for metrics and time-series charts preventing layout shifts or blank screens before data renders.
- **Accessibility**:
  - Fully compliant with `prefers-reduced-motion` to disable animations for users requesting reduced motion.

---

## 🛠️ Technologies Used

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.10+ / Flask | Web server, routing, authentication, business logic |
| **Database** | SQLite 3 | Relational data persistence with foreign keys |
| **Frontend** | HTML5 / CSS3 / Vanilla JS | Responsive, modern dark fitness interface |
| **Visualization** | Chart.js 4.4.1 | Responsive time-series and bar charts |
| **Fonts & Icons** | Plus Jakarta Sans / Inline SVG | Crisp typography and vector icons |
| **Security** | Werkzeug Security | Salted password hashing (PBKDF2/scrypt) |

---

## 💾 Database Information

The database is powered by **SQLite** (`fitness_tracker.db`). Foreign keys are enforced via `PRAGMA foreign_keys = ON`.

### Relational Schema Tables:
1. `users`: Stores athlete credentials, biometrics, training parameters, and caloric/macro targets.
2. `exercises`: Catalog of movements with execution steps, sets, reps, equipment, and form warnings.
3. `workout_plans`: Structured training programs (e.g. 4-Day Upper/Lower, 5-Day PPL).
4. `workout_plan_days`: Individual days belonging to a workout plan.
5. `workout_plan_exercises`: Prescribed movements, order, sets, and reps for each plan day.
6. `user_active_plans`: Links users to their currently assigned workout split.
7. `workouts`: Logs of scheduled, in-progress, and completed training sessions.
8. `workout_exercises`: Exercise records within specific sessions (weight lifted, reps, completion flag).
9. `food_items`: Seeded library of muscle-building foods with per-serving macronutrient profiles.
10. `nutrition_logs`: Daily meal entries logged by users.
11. `progress_logs`: Anthropometric check-ins (weight, body fat, chest, waist, arms, thighs).
12. `ai_chat_messages`: Stored conversation history between athletes and the AI Coach.

---

## 📂 Project Structure

```text
MentorConnect/
│
├── app.py                     # Main Flask application, routes, and error handlers
├── database.py                # Database connection, migrations, and demo data seeder
├── schema.sql                 # Complete SQLite schema definitions
├── workout_manager.py         # Workout plans, session execution, volume calculations
├── nutrition_manager.py       # Food library, meal logs, daily macro aggregations
├── progress_manager.py        # Transformation metrics and Chart.js datasets
├── exercise_catalog.py        # Comprehensive 8-category exercise movement catalog
├── ai_assistant.py            # Context-aware AI coach engine, query intents, and disclaimer
├── requirements.txt           # Python dependencies
├── README.md                  # Comprehensive project documentation
│
├── static/
│   ├── css/
│   │   └── style.css          # Dark fitness theme, responsive grids, modals, components
│   └── js/
│       └── main.js            # Mobile nav toggle, modal system, alert dismissal, search
│
└── templates/
    ├── base.html              # Base layout with navbar, flash messages, and footer
    ├── dashboard.html         # Unified dashboard with 6 stat cards, BMI, and weight chart
    ├── login.html             # Secure login page and 1-click demo access
    ├── register.html          # Registration form with initial biometrics inputs
    ├── profile.html           # Athlete profile, BMR/TDEE calculations, target sync
    ├── workout.html           # Workout plans, generator, and training history
    ├── active_workout.html    # Live session tracker with stopwatch and rest timers
    ├── nutrition.html         # Nutrition tracker, food library search, and meal windows
    ├── progress.html          # Progress dashboard with 4 Chart.js charts and logs table
    ├── exercises.html         # Searchable 8-category exercise library with filters
    └── assistant.html         # AI Fitness Coach chat interface with suggested chips
```

---

## 🚀 Installation & Setup Steps

### 1. Prerequisites
- **Python 3.10+** (Python 3.11, 3.12, 3.13, or 3.14 supported)
- **pip** (Python package manager)

### 2. Clone or Navigate to Directory
```powershell
cd d:\Projects\MentorConnect
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```
*(Dependencies: `Flask>=3.0.0`, `Werkzeug>=3.0.0`, `requests>=2.31.0`, `python-dotenv>=1.0.0`)*

### 4. Configure Google OAuth 2.0 & Environment Variables
The application reads configuration from a local `.env` file (which is included in `.gitignore` to prevent leaking credentials).

1. Open or create `.env` in the project root:
```env
SECRET_KEY=your-random-production-secret-key-here
GOOGLE_CLIENT_ID=your_google_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

2. **To obtain Google OAuth 2.0 credentials:**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project (e.g., "IronPulse Fitness").
   - Navigate to **APIs & Services** > **OAuth consent screen** and select **External**. Configure the app name and user support email.
   - Under **Scopes**, add `openid`, `.../auth/userinfo.email`, and `.../auth/userinfo.profile`.
   - Navigate to **APIs & Services** > **Credentials** > **Create Credentials** > **OAuth client ID**.
   - Select application type: **Web application**.
   - Under **Authorized redirect URIs**, add:
     - `http://127.0.0.1:5000/auth/google/callback`
     - `http://localhost:5000/auth/google/callback`
   - Copy the generated **Client ID** and **Client Secret** into your `.env` file.

> [!NOTE]
> If Google OAuth credentials are not configured or left as placeholders, the application will gracefully inform the user via a friendly flash alert and guide them to use standard email/password or instant demo login.

### 5. Initialize Database (Automatic)
The database will automatically initialize and seed sample data on first run. To manually verify initialization:
```powershell
py -c "import database; database.init_db(); print('Database ready!')"
```

---

## 🏃 How to Run the Application

```powershell
py app.py
```
*(or `python app.py`)*

Once running, access the application in your browser:
```text
http://127.0.0.1:5000
```

### Demo Credentials:
- **Username / Email**: `alex_pulse` (or `alex@ironpulse.fit`)
- **Password**: `fitness123`
- Or click **"Instant Demo Login"** on the login page for immediate access to pre-populated workouts, nutrition logs, and progress charts.
