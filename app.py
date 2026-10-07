import os
import re
import json
import secrets
import urllib.parse
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import requests
import logging

# Load environment variables from .env
load_dotenv()

# Logging configuration for OAuth and application events
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("ironpulse.auth")

import database
import workout_manager
import nutrition_manager
import progress_manager
import ai_assistant
import food_recognition

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static'
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Environment and HTTPS/Vercel Production Detection
is_vercel = bool(os.environ.get('VERCEL') == '1' or os.environ.get('VERCEL_ENV') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
is_production = is_vercel or os.environ.get('FLASK_ENV') == 'production' or os.environ.get('ENV') == 'production'

# SECRET_KEY Configuration
# In production/Vercel: SECRET_KEY must be provided via environment variables, otherwise fail clearly.
# In local development: use env var if present, or fall back to clearly dev-only insecure key.
raw_secret = os.environ.get('SECRET_KEY', '').strip()
if is_production:
    if not raw_secret:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is missing or empty. "
            "A secure SECRET_KEY must be configured in your production/Vercel environment variables."
        )
    app.secret_key = raw_secret
else:
    app.secret_key = raw_secret if raw_secret else 'dev-only-insecure-secret-key-for-local-development'

# Dynamic SESSION_COOKIE_SECURE:
# Must be True in production/Vercel (HTTPS) so modern browsers persist the cookie.
# Must be False on localhost (HTTP) so cookies work over non-SSL local dev servers.
cookie_secure_override = os.environ.get('SESSION_COOKIE_SECURE')
if cookie_secure_override is not None:
    session_cookie_secure = cookie_secure_override.lower() in ('true', '1', 'yes')
else:
    session_cookie_secure = is_production

app.config.update(
    SECRET_KEY=app.secret_key,
    SESSION_COOKIE_NAME='ironpulse_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=session_cookie_secure,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    PREFERRED_URL_SCHEME='https' if is_production else 'http',
)
app.permanent_session_lifetime = timedelta(days=7)

# Google OAuth 2.0 Configuration Endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Profile Picture (PFP) Upload Configuration
if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    UPLOAD_AVATAR_DIR = '/tmp/uploads/avatars'
else:
    UPLOAD_AVATAR_DIR = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')

try:
    os.makedirs(UPLOAD_AVATAR_DIR, exist_ok=True)
except Exception as _dir_err:
    logger.warning(f"Could not create upload directory {UPLOAD_AVATAR_DIR}: {_dir_err}")

ALLOWED_AVATAR_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MAX_AVATAR_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def get_user_initials(name):
    """Generates 1 or 2 uppercase initials from a user's full name."""
    if not name:
        return 'A'
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    elif len(parts) == 1 and len(parts[0]) > 0:
        return parts[0][:2].upper() if len(parts[0]) > 1 else parts[0][0].upper()
    return 'A'

@app.template_filter('initials')
def initials_filter(name):
    """Jinja filter to render athlete initials."""
    return get_user_initials(name)


def is_google_oauth_configured():
    """Checks whether valid, non-placeholder Google OAuth credentials are present in the environment."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

    if not client_id or not client_secret:
        return False

    placeholder_indicators = [
        'your_google_client_id',
        'your_google_client_secret',
        'your-google-client-id',
        'your-google-client-secret',
        'placeholder',
        'enter_here',
        'change_me',
        '<client_id>',
        '<client_secret>',
    ]
    for indicator in placeholder_indicators:
        if indicator in client_id.lower() or indicator in client_secret.lower():
            return False

    return True

def get_google_redirect_uri():
    """
    Determines the exact Google OAuth 2.0 redirect URI:
    1. If GOOGLE_REDIRECT_URI is defined in .env and non-empty, use that.
    2. Otherwise, fall back to dynamic host URL: {request.host_url.rstrip('/')}/auth/google/callback
    """
    configured_uri = os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
    if configured_uri:
        return configured_uri
    return f"{request.host_url.rstrip('/')}/auth/google/callback"


def calculate_fitness_metrics(user):
    """Calculates BMI, BMR, TDEE, Calorie Requirement, and Recommended Protein for a user row."""
    if not user:
        return {}
    age = int(user['age'] if user['age'] is not None else 25)
    gender = (user['gender'] or 'Male').strip()
    height_cm = float(user['height_cm'] if user['height_cm'] is not None else 178.0)
    weight_kg = float(user['weight_kg'] if user['weight_kg'] is not None else 75.0)
    training_days = int(user['training_days_per_week'] if user['training_days_per_week'] is not None else 4)
    fitness_goal = (user['fitness_goal'] or 'Muscle Hypertrophy & Strength').strip()

    return calculate_fitness_metrics_values(age, gender, height_cm, weight_kg, training_days, fitness_goal)

def calculate_fitness_metrics_values(age, gender, height_cm, weight_kg, training_days, fitness_goal):
    """Core calculation logic implementing Mifflin-St Jeor and exercise science recommendations."""
    # 1. BMI Calculation
    height_m = height_cm / 100.0 if height_cm > 0 else 1.75
    bmi = round(weight_kg / (height_m * height_m), 1) if height_m > 0 else 22.0
    
    if bmi < 18.5:
        bmi_status = "Underweight"
        bmi_badge_class = "badge-amber"
    elif bmi < 25.0:
        bmi_status = "Normal / Athletic"
        bmi_badge_class = "badge-green"
    elif bmi < 30.0:
        bmi_status = "Overweight / Muscular"
        bmi_badge_class = "badge-primary"
    else:
        bmi_status = "Obese"
        bmi_badge_class = "badge-danger"

    # 2. Basal Metabolic Rate (BMR) - Mifflin-St Jeor Equation
    # Men: 10 * weight(kg) + 6.25 * height(cm) - 5 * age + 5
    # Women: 10 * weight(kg) + 6.25 * height(cm) - 5 * age - 161
    if gender.lower() == 'female':
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    elif gender.lower() == 'male':
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 78

    # 3. Total Daily Energy Expenditure (TDEE) based on Training Days per week
    if training_days <= 2:
        activity_multiplier = 1.375
        activity_level_desc = "Light Activity (1-2 Training Days/Week)"
    elif training_days <= 4:
        activity_multiplier = 1.55
        activity_level_desc = "Moderate Activity (3-4 Training Days/Week)"
    elif training_days <= 6:
        activity_multiplier = 1.725
        activity_level_desc = "High Activity (5-6 Training Days/Week)"
    else:
        activity_multiplier = 1.9
        activity_level_desc = "Extreme Activity (Daily Intense Training)"

    tdee = bmr * activity_multiplier

    # 4. Estimated Daily Calorie Requirement (adjusted for Hypertrophy surplus, Deficit, etc.)
    goal_lower = fitness_goal.lower()
    if 'hypertrophy' in goal_lower or 'bulk' in goal_lower:
        cal_surplus = 350
        calorie_req = int(round(tdee + cal_surplus))
        goal_adjustment_desc = "+350 kcal Anabolic Surplus for Hypertrophy"
        protein_multiplier = 2.1
    elif 'cut' in goal_lower or 'fat loss' in goal_lower:
        cal_deficit = 450
        calorie_req = int(round(max(1400, tdee - cal_deficit)))
        goal_adjustment_desc = "-450 kcal Caloric Deficit for Fat Loss"
        protein_multiplier = 2.3
    elif 'strength' in goal_lower or 'power' in goal_lower:
        cal_surplus = 250
        calorie_req = int(round(tdee + cal_surplus))
        goal_adjustment_desc = "+250 kcal Power Surplus for CNS Recovery"
        protein_multiplier = 2.0
    else:
        calorie_req = int(round(tdee))
        goal_adjustment_desc = "Maintenance Level (0 kcal delta) for Recomposition"
        protein_multiplier = 1.9

    # 5. Recommended Protein Intake (grams per day)
    recommended_protein = int(round(weight_kg * protein_multiplier))

    # Balanced Carbs & Fats macro distribution
    rec_fats = int(round((calorie_req * 0.25) / 9.0))
    rec_carbs = int(round((calorie_req - (recommended_protein * 4) - (rec_fats * 9)) / 4.0))

    return {
        'bmi': bmi,
        'bmi_status': bmi_status,
        'bmi_badge_class': bmi_badge_class,
        'bmr': int(round(bmr)),
        'tdee': int(round(tdee)),
        'activity_multiplier': activity_multiplier,
        'activity_level_desc': activity_level_desc,
        'calorie_req': calorie_req,
        'goal_adjustment_desc': goal_adjustment_desc,
        'recommended_protein': recommended_protein,
        'protein_multiplier': protein_multiplier,
        'rec_carbs': max(50, rec_carbs),
        'rec_fats': max(30, rec_fats)
    }

@app.before_request
def load_logged_in_user():
    """Load logged-in user into flask.g before every request."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        g.user = cursor.fetchone()
        conn.close()
        if g.user is None:
            logger.warning(f"Session user_id={user_id} not found in database, clearing session")
            session.clear()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash("Please sign in or use Demo Login to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- ROUTES ----------------- #

@app.route('/')
def index():
    """Public Landing Page (or redirect to Dashboard if already logged in)."""
    if g.user:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/settings')
@login_required
def settings():
    """Athlete application settings, units, and preferences."""
    return render_template('settings.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        raw_identifier = request.form.get('username', '')
        # Do not modify passwords before verification (preserve spaces, do not strip)
        password = request.form.get('password', '')

        identifier = raw_identifier.strip()
        if not identifier or not password:
            flash("Please enter your username/email and password", "danger")
            return render_template('login.html')

        clean_identifier = identifier.lower()

        logger.info(f"Login attempt initiated for: {clean_identifier}")

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
            (clean_identifier, clean_identifier)
        )
        user = cursor.fetchone()
        conn.close()

        if not user:
            logger.info(f"Login failed: Account not found for '{clean_identifier}'")
            flash("Account not found", "danger")
            return render_template('login.html')

        if not check_password_hash(user['password_hash'], password):
            logger.info(f"Login failed: Invalid password for user_id={user['id']}")
            flash("Invalid username/email or password", "danger")
            return render_template('login.html')

        # Authentication successful
        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        logger.info(f"Login successful: user_id={user['id']} (session established)")
        flash(f"Welcome back, {user['full_name']}! Ready to crush today's session?", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/login/demo')
def login_demo():
    """One-click instant login as demo user for reviewing."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = 'alex_pulse'")
    demo_user = cursor.fetchone()
    conn.close()

    if demo_user:
        session.clear()
        session.permanent = True
        session['user_id'] = demo_user['id']
        flash("Logged in successfully as Demo User (Alex Mercer)!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Demo user not found. Re-initializing database...", "warning")
        database.init_db()
        return redirect(url_for('login'))

@app.route('/auth/google')
def auth_google():
    """Initiates Google OAuth 2.0 Authorization Flow."""
    logger.info("Google login started")
    if g.user:
        logger.info("User already authenticated, redirecting to /dashboard")
        return redirect(url_for('dashboard'))

    # Check for credentials
    if not is_google_oauth_configured():
        logger.warning("Google login aborted: credentials are not configured or are placeholder values.")
        flash("Google Login is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", "warning")
        return redirect(url_for('login'))

    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    redirect_uri = get_google_redirect_uri()
    logger.info(f"Google redirect URI: {redirect_uri}")

    # Generate cryptographic state and nonce for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account'
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    logger.info("OAuth authorization URL generated")
    return redirect(auth_url)

@app.route('/auth/google/callback')
def auth_google_callback():
    """Handles Google OAuth 2.0 Authorization Callback."""
    logger.info("Callback received")
    redirect_uri = get_google_redirect_uri()
    logger.info(f"Google redirect URI: {redirect_uri}")

    # Check credentials
    if not is_google_oauth_configured():
        logger.warning("Google callback aborted: credentials are not configured or are placeholder values.")
        flash("Google Login is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", "warning")
        return redirect(url_for('login'))

    # 1. Check for cancellation or error returned by Google
    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', '')
        logger.warning(f"Google OAuth callback error: {error} - {error_description}")
        if error == 'access_denied':
            flash("User cancelled Google login.", "warning")
        else:
            flash(f"Google login failed: {error_description or error}", "danger")
        return redirect(url_for('login'))

    # 2. Verify state token against CSRF
    state = request.args.get('state')
    saved_state = session.pop('oauth_state', None)
    if not state or not saved_state or state != saved_state:
        logger.warning("Invalid OAuth state token. Possible CSRF attack detected.")
        flash("Invalid OAuth state token. Possible CSRF attack detected. Please try signing in again.", "danger")
        return redirect(url_for('login'))

    # 3. Retrieve authorization code
    code = request.args.get('code')
    if not code:
        logger.warning("Missing authorization code from Google OAuth response.")
        flash("Missing authorization code from Google OAuth response.", "danger")
        return redirect(url_for('login'))

    logger.info("Authorization code received")

    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

    # 4. Exchange authorization code for access token
    try:
        token_response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            },
            headers={'Accept': 'application/json'},
            timeout=10
        )
        token_data = token_response.json()
    except Exception as e:
        logger.error(f"Error communicating with Google OAuth token server: {str(e)}")
        flash(f"Error communicating with Google OAuth token server: {str(e)}", "danger")
        return redirect(url_for('login'))

    if token_response.status_code != 200 or 'access_token' not in token_data:
        err_type = token_data.get('error', 'unknown_error')
        err_desc = token_data.get('error_description', '')
        logger.error(f"Token exchange failed: {err_type} - {err_desc}")

        if err_type == 'redirect_uri_mismatch':
            flash(
                f"Google OAuth redirect URI mismatch. "
                f"Ensure this redirect URI is added to 'Authorized redirect URIs' in Google Cloud Console: {redirect_uri}",
                "danger"
            )
        elif err_type == 'invalid_client':
            flash("Google OAuth authentication failed: Invalid Client ID or Client Secret.", "danger")
        elif err_type == 'invalid_grant':
            flash("Google authorization code has expired or was already used. Please try logging in again.", "danger")
        else:
            flash(f"Google OAuth token exchange failed: {err_desc or err_type}", "danger")
        return redirect(url_for('login'))

    logger.info("Token exchange successful")
    access_token = token_data['access_token']

    # 5. Retrieve Google User Profile Info (Name, Email, Picture, Sub/ID)
    try:
        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f"Bearer {access_token}"},
            timeout=10
        )
        user_info = userinfo_response.json()
    except Exception as e:
        logger.error(f"Error retrieving user profile from Google: {str(e)}")
        flash(f"Error retrieving user profile from Google: {str(e)}", "danger")
        return redirect(url_for('login'))

    if userinfo_response.status_code != 200 or not user_info.get('email'):
        logger.error("Could not retrieve verified profile information from Google account.")
        flash("Could not retrieve verified profile information from Google account.", "danger")
        return redirect(url_for('login'))

    logger.info("Google profile received")

    google_sub = str(user_info.get('sub', '')).strip()
    email = user_info.get('email', '').lower().strip()
    full_name = (user_info.get('name') or user_info.get('given_name') or email.split('@')[0]).strip()
    profile_picture = user_info.get('picture', '').strip()

    # 6. Database lookup & Account Creation / Linking
    conn = database.get_db()
    cursor = conn.cursor()

    # Priority A: Check if existing user with matching google_id
    cursor.execute("SELECT * FROM users WHERE google_id = ?", (google_sub,))
    user = cursor.fetchone()

    if user:
        user_id = user['id']
        if profile_picture and profile_picture != user['profile_picture']:
            cursor.execute("UPDATE users SET profile_picture = ? WHERE id = ?", (profile_picture, user_id))
            conn.commit()
        welcome_msg = f"Welcome back, {user['full_name']}! Logged in via Google."
        logger.info(f"User found/created: user_id={user_id}")
    else:
        # Priority B: Check if existing user with matching email
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),))
        user = cursor.fetchone()

        if user:
            user_id = user['id']
            # Link Google account to existing email user
            cursor.execute("""
                UPDATE users SET
                    google_id = ?,
                    profile_picture = COALESCE(?, profile_picture),
                    auth_provider = CASE WHEN auth_provider = 'local' THEN 'google_linked' ELSE auth_provider END
                WHERE id = ?
            """, (google_sub, profile_picture if profile_picture else None, user_id))
            conn.commit()
            welcome_msg = f"Welcome back, {user['full_name']}! Successfully connected your Google Account."
            logger.info(f"User found/created: user_id={user_id}")
        else:
            # Priority C: Create brand new athlete account from Google
            base_user = re.sub(r'[^a-z0-9_]', '', email.split('@')[0])
            username = base_user if len(base_user) >= 3 else f"athlete_{base_user}"

            # Ensure unique username
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                username = f"{username}_{secrets.token_hex(2)}"

            # Compute initial baseline fitness metrics for 75kg athlete
            initial_metrics = calculate_fitness_metrics_values(
                age=26,
                gender='Male',
                height_cm=178.0,
                weight_kg=75.0,
                training_days=4,
                fitness_goal='Muscle Hypertrophy & Strength'
            )

            # Generate random password hash since authentication is handled via Google OAuth
            dummy_password_hash = generate_password_hash(secrets.token_urlsafe(32))

            cursor.execute("""
                INSERT INTO users (
                    full_name, username, email, password_hash, age, gender,
                    height_cm, weight_kg, experience_level, fitness_goal,
                    training_days_per_week, available_equipment, dietary_preference,
                    target_weight_kg, daily_calorie_target, daily_protein_target,
                    daily_carbs_target, daily_fats_target, google_id, profile_picture, auth_provider
                ) VALUES (?, ?, ?, ?, 26, 'Male', 178.0, 75.0, 'Intermediate (1-3 Years)',
                          'Muscle Hypertrophy & Strength', 4, 'Full Commercial Gym', 'High Protein Omnivore',
                          78.0, ?, ?, ?, ?, ?, ?, 'google')
            """, (
                full_name, username, email, dummy_password_hash,
                initial_metrics['calorie_req'], initial_metrics['recommended_protein'],
                initial_metrics['rec_carbs'], initial_metrics['rec_fats'],
                google_sub, profile_picture if profile_picture else None
            ))
            user_id = cursor.lastrowid
            conn.commit()
            welcome_msg = f"Welcome to IronPulse, {full_name}! Your athlete profile has been initialized with Google."
            logger.info(f"User found/created: user_id={user_id}")

    conn.close()

    # 7. Secure Session Initialization
    session.clear()
    session.permanent = True
    session['user_id'] = user_id
    logger.info(f"Session created for user_id={user_id}")

    flash(welcome_msg, "success")
    logger.info("Redirecting to /dashboard")
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        username = request.form.get('username', '').strip().lower()

        # Validation
        if not full_name or len(full_name) < 2:
            flash("Full name must be at least 2 characters long.", "danger")
            return render_template('register.html')

        if not email or '@' not in email or '.' not in email or len(email) < 5:
            flash("Please enter a valid email address.", "danger")
            return render_template('register.html')

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        # Auto-create username if omitted
        if not username:
            base_user = re.sub(r'[^a-z0-9_]', '', email.split('@')[0])
            username = base_user if len(base_user) >= 3 else f"athlete_{base_user}"

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (username, email))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            flash("An account with that email or username already exists. Please sign in.", "danger")
            return render_template('register.html')

        # Initial fitness profile inputs or defaults
        fitness_goal = request.form.get('fitness_goal', 'Muscle Hypertrophy & Strength').strip()
        experience_level = request.form.get('experience_level', 'Intermediate (1-3 Years)').strip()
        age = int(request.form.get('age', 25) or 25)
        gender = request.form.get('gender', 'Male').strip()
        height_cm = float(request.form.get('height_cm', 178.0) or 178.0)
        weight_kg = float(request.form.get('weight_kg', 75.0) or 75.0)
        training_days = int(request.form.get('training_days_per_week', 4) or 4)
        available_equipment = request.form.get('available_equipment', 'Full Commercial Gym').strip()
        dietary_preference = request.form.get('dietary_preference', 'High Protein Omnivore').strip()

        # Compute initial scientifically backed caloric and protein targets
        metrics = calculate_fitness_metrics_values(age, gender, height_cm, weight_kg, training_days, fitness_goal)

        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (
                full_name, username, email, password_hash, age, gender,
                height_cm, weight_kg, experience_level, fitness_goal,
                training_days_per_week, available_equipment, dietary_preference,
                target_weight_kg, daily_calorie_target, daily_protein_target,
                daily_carbs_target, daily_fats_target, auth_provider
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local')
        """, (
            full_name, username, email, password_hash, age, gender,
            height_cm, weight_kg, experience_level, fitness_goal,
            training_days, available_equipment, dietary_preference,
            round(weight_kg + 3.0, 1), metrics['calorie_req'], metrics['recommended_protein'],
            metrics['rec_carbs'], metrics['rec_fats']
        ))
        new_user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"New local user registered: user_id={new_user_id}, username={username}")

        session.clear()
        session.permanent = True
        session['user_id'] = new_user_id
        flash("Account created successfully! Your personalized fitness targets have been generated.", "success")
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out. Keep up the consistency!", "info")
    return redirect(url_for('login'))

import workout_manager

@app.route('/dashboard')
@login_required
def dashboard():
    conn = database.get_db()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    user_id = g.user['id']

    # 1. Today's Nutrition stats
    cursor.execute("""
        SELECT 
            COALESCE(SUM(calories), 0) as total_calories,
            COALESCE(SUM(protein_g), 0) as total_protein,
            COALESCE(SUM(carbs_g), 0) as total_carbs,
            COALESCE(SUM(fats_g), 0) as total_fats,
            COUNT(*) as meal_count
        FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """, (user_id, today_str))
    nutrition_today = cursor.fetchone()

    # 2. Workout statistics & Consistency streak
    workout_stats = workout_manager.calculate_dashboard_workout_stats(user_id, g.user['training_days_per_week'])

    # 3. Today's Workout Details
    todays_workout_info = workout_manager.get_todays_workout_details(user_id, g.user)

    # 4. Recent 4 workouts
    cursor.execute("""
        SELECT * FROM workouts
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 4
    """, (user_id,))
    recent_workouts = cursor.fetchall()

    # 5. Latest progress log
    cursor.execute("""
        SELECT * FROM progress_logs
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 2
    """, (user_id,))
    progress_records = cursor.fetchall()

    latest_progress = progress_records[0] if len(progress_records) > 0 else None
    prev_progress = progress_records[1] if len(progress_records) > 1 else None

    # Calculate weight delta
    weight_delta = 0.0
    if latest_progress and prev_progress:
        weight_delta = round(latest_progress['weight_kg'] - prev_progress['weight_kg'], 1)

    # 6. Today's logged meals
    cursor.execute("""
        SELECT * FROM nutrition_logs
        WHERE user_id = ? AND date = ?
        ORDER BY created_at ASC
    """, (user_id, today_str))
    today_meals = cursor.fetchall()

    conn.close()

    # Goal weight progress calculation
    current_weight = latest_progress['weight_kg'] if latest_progress else g.user['weight_kg']
    target_weight = g.user['target_weight_kg']
    weight_progress_pct = min(100, max(10, int((current_weight / target_weight) * 100))) if target_weight else 75

    # Nutrition percentages and remaining
    cal_target = g.user['daily_calorie_target'] or 2800
    protein_target = g.user['daily_protein_target'] or 180
    carbs_target = g.user['daily_carbs_target'] or 320
    fats_target = g.user['daily_fats_target'] or 75

    remaining_calories = cal_target - nutrition_today['total_calories']
    remaining_protein = round(protein_target - nutrition_today['total_protein'], 1)

    cal_pct = min(100, int((nutrition_today['total_calories'] / cal_target) * 100)) if cal_target else 0
    protein_pct = min(100, int((nutrition_today['total_protein'] / protein_target) * 100)) if protein_target else 0
    carbs_pct = min(100, int((nutrition_today['total_carbs'] / carbs_target) * 100)) if carbs_target else 0
    fats_pct = min(100, int((nutrition_today['total_fats'] / fats_target) * 100)) if fats_target else 0

    # 7. Fitness Biometric Diagnostics (BMI, BMR, etc.)
    user_metrics = calculate_fitness_metrics(g.user)
    bmi = user_metrics.get('bmi', 22.0)
    bmi_status = user_metrics.get('bmi_status', 'Normal / Athletic')
    bmi_badge_class = user_metrics.get('bmi_badge_class', 'badge-green')

    # 8. Weight Progression Dataset for Dashboard Chart
    conn = database.get_db()
    progress_chart_data = progress_manager.get_progress_dashboard_data(conn, user_id, g.user)

    # 9. Load exercise library and routines for editing today's schedule
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, category, muscle_group, equipment, difficulty, rest_seconds, default_sets, default_reps, instructions, youtube_id, youtube_url
        FROM exercises
        ORDER BY category, name
    """)
    all_exercises = [dict(r) for r in cursor.fetchall()]

    detailed_plans = workout_manager.get_all_plans_with_details(conn)
    all_plan_routines = []
    for p in detailed_plans:
        for d in p['days']:
            all_plan_routines.append({
                'day_id': d['id'],
                'plan_name': p['name'],
                'day_title': d['day_title'],
                'focus_category': d['focus_category'],
                'exercise_count': len(d['exercises']),
                'exercises': [
                    {
                        'exercise_id': ex['exercise_id'],
                        'exercise_name': ex['exercise_name'],
                        'category': ex.get('category', ''),
                        'target_muscle': ex.get('muscle_group', ''),
                        'sets': ex['sets'],
                        'reps': ex['reps'],
                        'rest_time': ex.get('rest_seconds') or 90,
                        'notes': ex.get('notes', ''),
                        'youtube_id': ex.get('youtube_id', ''),
                        'youtube_url': ex.get('youtube_url', '')
                    }
                    for ex in d['exercises']
                ]
            })
    conn.close()

    return render_template(
        'dashboard.html',
        today=date.today().strftime("%B %d, %Y"),
        today_date=today_str,
        nutrition_today=nutrition_today,
        workout_stats=workout_stats,
        todays_workout_info=todays_workout_info,
        recent_workouts=recent_workouts,
        latest_progress=latest_progress,
        weight_delta=weight_delta,
        today_meals=today_meals,
        current_weight=current_weight,
        target_weight=target_weight,
        weight_progress_pct=weight_progress_pct,
        cal_pct=cal_pct,
        protein_pct=protein_pct,
        carbs_pct=carbs_pct,
        fats_pct=fats_pct,
        cal_target=cal_target,
        protein_target=protein_target,
        carbs_target=carbs_target,
        fats_target=fats_target,
        remaining_calories=remaining_calories,
        remaining_protein=remaining_protein,
        bmi=bmi,
        bmi_status=bmi_status,
        bmi_badge_class=bmi_badge_class,
        progress_charts=progress_chart_data['charts'],
        progress_summary=progress_chart_data['summary'],
        all_exercises=all_exercises,
        all_plan_routines=all_plan_routines
    )

@app.route('/workouts')
@login_required
def workouts():
    conn = database.get_db()
    cursor = conn.cursor()
    user_id = g.user['id']

    # 1. Fetch Today's Workout Status
    todays_workout_info = workout_manager.get_todays_workout_details(user_id, g.user)

    # 2. Fetch User Active Plan
    cursor.execute("""
        SELECT wp.* FROM user_active_plans uap
        JOIN workout_plans wp ON uap.plan_id = wp.id
        WHERE uap.user_id = ?
    """, (user_id,))
    active_plan = cursor.fetchone()

    # 3. Fetch All Available Workout Plans
    cursor.execute("SELECT * FROM workout_plans ORDER BY is_default DESC, id ASC")
    all_plans = cursor.fetchall()

    # 4. Fetch Completed & In-Progress Workouts History
    cursor.execute("""
        SELECT w.*, 
               (SELECT COUNT(*) FROM workout_exercises we WHERE we.workout_id = w.id) as exercise_count,
               (SELECT COUNT(*) FROM workout_exercises we WHERE we.workout_id = w.id AND we.completed = 1) as completed_exercise_count
        FROM workouts w
        WHERE w.user_id = ?
        ORDER BY w.date DESC, w.id DESC
    """, (user_id,))
    workout_list = cursor.fetchall()

    # 5. Fetch exercise library for modal dropdown
    cursor.execute("SELECT id, name, category, muscle_group, equipment, difficulty FROM exercises ORDER BY category, name")
    exercise_options = cursor.fetchall()

    # 6. Fetch detailed exercises for all workouts
    cursor.execute("""
        SELECT we.*, e.name as exercise_name, e.category as exercise_category,
               e.muscle_group, e.instructions, e.youtube_id, e.youtube_url
        FROM workout_exercises we
        JOIN exercises e ON we.exercise_id = e.id
        JOIN workouts w ON we.workout_id = w.id
        WHERE w.user_id = ?
        ORDER BY we.order_idx ASC, we.id ASC
    """, (user_id,))
    all_workout_exercises = cursor.fetchall()

    # Group exercises by workout_id
    exercises_by_workout = {}
    for item in all_workout_exercises:
        wid = item['workout_id']
        if wid not in exercises_by_workout:
            exercises_by_workout[wid] = []
        exercises_by_workout[wid].append(item)

    # 7. Workout Consistency Statistics & Streaks
    workout_stats = workout_manager.calculate_dashboard_workout_stats(user_id, g.user['training_days_per_week'])

    # 8. Fetch detailed plans with days & exercises for the workout catalog
    detailed_plans = workout_manager.get_all_plans_with_details(conn)

    # Flatten all available plan days for dropdown selection in replace/schedule modals
    all_plan_routines = []
    for p in detailed_plans:
        for d in p['days']:
            all_plan_routines.append({
                'day_id': d['id'],
                'plan_name': p['name'],
                'day_title': d['day_title'],
                'focus_category': d['focus_category'],
                'exercise_count': len(d['exercises'])
            })

    # Enrich workouts with all matched categories and details
    enriched_workout_list = []
    for w in workout_list:
        w_dict = dict(w)
        w_ex = exercises_by_workout.get(w_dict['id'], [])
        cats = workout_manager.compute_workout_categories(w_dict, w_ex)
        w_dict['categories'] = cats
        w_dict['categories_csv'] = ",".join(cats)
        enriched_workout_list.append(w_dict)
    workout_list = enriched_workout_list

    selected_category = request.args.get('category', 'All').strip()

    conn.close()

    return render_template(
        'workout.html',
        todays_workout_info=todays_workout_info,
        active_plan=active_plan,
        all_plans=all_plans,
        detailed_plans=detailed_plans,
        all_plan_routines=all_plan_routines,
        workouts=workout_list,
        exercises_by_workout=exercises_by_workout,
        exercise_options=exercise_options,
        stats=workout_stats,
        today_date=date.today().isoformat(),
        selected_category=selected_category
    )

@app.route('/api/workouts/history')
@login_required
def api_workout_history():
    """
    User-specific workout history API.
    Supports optional category query parameter: ?category=Chest
    Returns user-only records with categories, exercises, sets, reps, duration, and status.
    """
    category = request.args.get('category', 'All').strip()
    conn = database.get_db()
    cursor = conn.cursor()
    user_id = g.user['id']

    cursor.execute("""
        SELECT w.*, 
               (SELECT COUNT(*) FROM workout_exercises we WHERE we.workout_id = w.id) as exercise_count,
               (SELECT COUNT(*) FROM workout_exercises we WHERE we.workout_id = w.id AND we.completed = 1) as completed_exercise_count
        FROM workouts w
        WHERE w.user_id = ?
        ORDER BY w.date DESC, w.id DESC
    """, (user_id,))
    workout_rows = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT we.*, e.name as exercise_name, e.category as exercise_category,
               e.muscle_group, e.instructions, e.youtube_id, e.youtube_url
        FROM workout_exercises we
        JOIN exercises e ON we.exercise_id = e.id
        JOIN workouts w ON we.workout_id = w.id
        WHERE w.user_id = ?
        ORDER BY we.order_idx ASC, we.id ASC
    """, (user_id,))
    all_workout_exercises = cursor.fetchall()
    conn.close()

    exercises_by_workout = {}
    for item in all_workout_exercises:
        wid = item['workout_id']
        exercises_by_workout.setdefault(wid, []).append(dict(item))

    matched_workouts = []
    for w in workout_rows:
        w_ex = exercises_by_workout.get(w['id'], [])
        cats = workout_manager.compute_workout_categories(w, w_ex)
        w['categories'] = cats
        w['categories_csv'] = ",".join(cats)
        w['exercises'] = w_ex
        if workout_manager.category_matches(cats, category):
            matched_workouts.append(w)

    return jsonify({
        "success": True,
        "category": category,
        "count": len(matched_workouts),
        "total_recorded": len(matched_workouts),
        "workouts": matched_workouts
    })

@app.route('/workouts/start', methods=['POST'])
@login_required
def start_workout():
    plan_day_id = request.form.get('plan_day_id')
    plan_day_id = int(plan_day_id) if plan_day_id else None
    workout_id = workout_manager.start_or_get_workout_session(g.user['id'], g.user, plan_day_id)
    return redirect(url_for('active_workout', workout_id=workout_id))

@app.route('/workouts/active/<int:workout_id>')
@login_required
def active_workout(workout_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE id = ? AND user_id = ?", (workout_id, g.user['id']))
    workout = cursor.fetchone()

    if not workout:
        conn.close()
        flash("Workout session not found.", "danger")
        return redirect(url_for('workouts'))

    cursor.execute("""
        SELECT we.*, e.name as exercise_name, e.category, e.muscle_group as target_muscle,
               e.difficulty, e.instructions, e.youtube_id, e.youtube_url
        FROM workout_exercises we
        JOIN exercises e ON we.exercise_id = e.id
        WHERE we.workout_id = ?
        ORDER BY we.order_idx ASC, we.id ASC
    """, (workout_id,))
    workout_exercises = cursor.fetchall()

    cursor.execute("SELECT id, name, category, muscle_group, equipment, difficulty, rest_seconds FROM exercises ORDER BY category, name")
    exercise_options = cursor.fetchall()

    conn.close()

    total_ex = len(workout_exercises)
    completed_ex = sum(1 for we in workout_exercises if we['completed'] == 1)
    rate = int((completed_ex / total_ex * 100)) if total_ex > 0 else 0

    return render_template(
        'active_workout.html',
        workout=workout,
        exercises=workout_exercises,
        total_exercises=total_ex,
        completed_exercises=completed_ex,
        completion_rate=rate,
        exercise_options=exercise_options
    )

@app.route('/workouts/exercise/toggle/<int:we_id>', methods=['POST'])
@login_required
def toggle_exercise(we_id):
    completed = int(request.form.get('completed', 1))
    weight_kg = float(request.form.get('weight_kg', 0) or 0)
    reps = request.form.get('reps')
    reps = int(reps) if reps else None
    workout_id = int(request.form.get('workout_id', 0))

    rate = workout_manager.toggle_exercise_completion_status(workout_id, we_id, completed, weight_kg, reps)

    # Check if AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'success': True, 'completion_rate': rate}

    return redirect(url_for('active_workout', workout_id=workout_id))

@app.route('/workouts/finish/<int:workout_id>', methods=['POST'])
@login_required
def finish_workout(workout_id):
    duration = int(request.form.get('duration_minutes', 60) or 60)
    intensity = int(request.form.get('intensity_rating', 8) or 8)
    notes = request.form.get('notes', '').strip()

    conn = database.get_db()
    cursor = conn.cursor()

    # Recalculate total volume
    cursor.execute("SELECT sets, reps, weight_kg, completed FROM workout_exercises WHERE workout_id = ?", (workout_id,))
    rows = cursor.fetchall()
    total_volume = sum(r['sets'] * r['reps'] * r['weight_kg'] for r in rows if r['completed'] == 1)

    cursor.execute("""
        UPDATE workouts SET
            status = 'completed',
            duration_minutes = ?,
            intensity_rating = ?,
            total_volume_kg = ?,
            completion_rate = 100,
            notes = ?
        WHERE id = ? AND user_id = ?
    """, (duration, intensity, round(total_volume, 1), notes, workout_id, g.user['id']))
    conn.commit()
    conn.close()

    flash(f"Workout finished! {round(total_volume, 1)} kg total volume recorded. Keep the momentum going!", "success")
    return redirect(url_for('workouts'))

@app.route('/workouts/plan/select', methods=['POST'])
@login_required
def select_plan():
    plan_id = int(request.form.get('plan_id', 1))
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at)
        VALUES (?, ?, ?)
    """, (g.user['id'], plan_id, date.today().isoformat()))
    conn.commit()
    conn.close()

    flash("Workout plan successfully activated!", "success")
    return redirect(url_for('workouts'))

@app.route('/workouts/plan/generate', methods=['POST'])
@app.route('/workout-plan/generate', methods=['POST'])
@login_required
def generate_custom_plan():
    goal = request.form.get('fitness_goal', g.user['fitness_goal'])
    experience = request.form.get('experience_level', g.user['experience_level'])
    days_per_week = int(request.form.get('days_per_week', g.user['training_days_per_week'] or 4))
    equipment = request.form.get('available_equipment', g.user['available_equipment'])
    target_muscle = request.form.get('target_muscle_group', 'All').strip()

    conn = database.get_db()
    cursor = conn.cursor()

    plan_name = f"Custom {days_per_week}-Day {target_muscle} {goal} Split"
    plan_desc = f"Tailored {days_per_week}-day split for {experience} level targeting {target_muscle} using {equipment}."

    cursor.execute("""
        INSERT INTO workout_plans (name, description, fitness_goal, experience_level, days_per_week, available_equipment, target_muscle_group, is_default)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (plan_name, plan_desc, goal, experience, days_per_week, equipment, target_muscle))
    new_plan_id = cursor.lastrowid

    # Create plan days matching categories
    categories_to_schedule = []
    if target_muscle != 'All' and target_muscle in workout_manager.CATEGORIES:
        categories_to_schedule = [target_muscle]
    else:
        categories_to_schedule = ['Chest', 'Back', 'Legs', 'Shoulders', 'Biceps', 'Triceps', 'Core'][:days_per_week]

    for day_num in range(1, days_per_week + 1):
        cat = categories_to_schedule[(day_num - 1) % len(categories_to_schedule)]
        day_title = f"Day {day_num}: {cat} Overload & Hypertrophy"
        cursor.execute("""
            INSERT INTO workout_plan_days (plan_id, day_number, day_title, focus_category)
            VALUES (?, ?, ?, ?)
        """, (new_plan_id, day_num, day_title, cat))
        day_id = cursor.lastrowid

        # Attach matching exercises from library
        cursor.execute("SELECT id, default_sets, default_reps, rest_seconds FROM exercises WHERE category = ? LIMIT 5", (cat,))
        ex_list = cursor.fetchall()
        for idx, ex in enumerate(ex_list, start=1):
            cursor.execute("""
                INSERT INTO workout_plan_exercises (plan_day_id, exercise_id, sets, reps, rest_seconds, order_idx, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'Targeted muscle execution')
            """, (day_id, ex['id'], ex['default_sets'], ex['default_reps'], ex['rest_seconds'], idx))

    # Activate new plan for user
    cursor.execute("""
        INSERT OR REPLACE INTO user_active_plans (user_id, plan_id, started_at)
        VALUES (?, ?, ?)
    """, (g.user['id'], new_plan_id, date.today().isoformat()))

    conn.commit()
    conn.close()

    flash(f"Generated and activated '{plan_name}'!", "success")
    return redirect(url_for('workouts'))

@app.route('/workouts/add', methods=['POST'])
@login_required
def add_workout():
    title = request.form.get('title', '').strip()
    workout_date = request.form.get('date', date.today().isoformat())
    duration = int(request.form.get('duration_minutes', 60) or 60)
    intensity = int(request.form.get('intensity_rating', 8) or 8)
    notes = request.form.get('notes', '').strip()

    # Selected exercises & sets
    exercise_id = request.form.get('exercise_id')
    sets = int(request.form.get('sets', 3) or 3)
    reps = int(request.form.get('reps', 10) or 10)
    weight_kg = float(request.form.get('weight_kg', 0) or 0)
    calculated_volume = round(sets * reps * weight_kg, 1)

    if not title:
        flash("Workout title is required.", "danger")
        return redirect(url_for('workouts'))

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, completion_rate, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'completed', 'General', 100, ?)
    """, (g.user['id'], title, workout_date, duration, calculated_volume, intensity, notes))
    workout_id = cursor.lastrowid

    if exercise_id:
        cursor.execute("""
            INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes)
            VALUES (?, ?, ?, ?, ?, 90, 1, 'Manual logged set')
        """, (workout_id, exercise_id, sets, reps, weight_kg))

    conn.commit()
    conn.close()

    flash(f"Workout '{title}' logged successfully! Total volume: {calculated_volume} kg.", "success")
    return redirect(url_for('workouts'))

@app.route('/workouts/add-exercise', methods=['POST'])
@login_required
def add_exercise_to_workout():
    exercise_id = request.form.get('exercise_id')
    workout_id = request.form.get('workout_id')
    sets = int(request.form.get('sets', 3) or 3)
    reps = int(request.form.get('reps', 10) or 10)
    weight_kg = float(request.form.get('weight_kg', 0) or 0)

    if not exercise_id:
        flash("Please select an exercise movement.", "danger")
        return redirect(url_for('exercises'))

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,))
    ex = cursor.fetchone()
    if not ex:
        conn.close()
        flash("Exercise not found.", "warning")
        return redirect(url_for('exercises'))

    # If no workout_id specified, find or create an active workout session today
    if not workout_id:
        today_str = date.today().isoformat()
        cursor.execute("""
            SELECT id FROM workouts
            WHERE user_id = ? AND date = ? AND status = 'in_progress'
            ORDER BY id DESC LIMIT 1
        """, (g.user['id'], today_str))
        w_row = cursor.fetchone()
        if w_row:
            workout_id = w_row['id']
        else:
            # Create a new active session
            cursor.execute("""
                INSERT INTO workouts (user_id, title, date, duration_minutes, total_volume_kg, intensity_rating, status, target_muscle_group, completion_rate, notes)
                VALUES (?, ?, ?, 45, 0, 8, 'in_progress', ?, 0, 'Training session launched from Exercise Library')
            """, (g.user['id'], f"{ex['category']} Hypertrophy Session", today_str, ex['category']))
            workout_id = cursor.lastrowid

    # Append exercise to the workout
    cursor.execute("""
        INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, completed, notes)
        VALUES (?, ?, ?, ?, ?, ?, 0, 'Added from Exercise Library')
    """, (workout_id, exercise_id, sets, reps, weight_kg, ex['rest_seconds'] or 90))

    conn.commit()
    conn.close()

    flash(f"Added {ex['name']} ({sets}x{reps}) to active workout session!", "success")
    return redirect(url_for('active_workout', workout_id=workout_id))

@app.route('/workouts/add-to-plan', methods=['POST'])
@login_required
def add_to_plan():
    plan_day_id = request.form.get('plan_day_id')
    workout_date = request.form.get('date', date.today().isoformat())
    status = request.form.get('status', 'scheduled')

    if not plan_day_id:
        flash("Please select a workout routine to add.", "warning")
        return redirect(url_for('workouts'))

    workout_id = workout_manager.add_routine_to_user_schedule(
        user_id=g.user['id'],
        plan_day_id=int(plan_day_id),
        workout_date=workout_date,
        status=status
    )
    if workout_id:
        flash("Workout successfully added to your personal schedule!", "success")
    else:
        flash("Unable to add workout routine. Please check your selection.", "danger")
    return redirect(url_for('workouts'))

@app.route('/workouts/delete/<int:workout_id>', methods=['POST'])
@login_required
def delete_workout(workout_id):
    success = workout_manager.delete_user_workout(g.user['id'], workout_id)
    if success:
        flash("Workout successfully removed from your plan.", "success")
    else:
        flash("Workout could not be removed or was not found.", "danger")
    return redirect(url_for('workouts'))

@app.route('/workouts/replace/<int:workout_id>', methods=['POST'])
@login_required
def replace_workout(workout_id):
    plan_day_id = request.form.get('plan_day_id')
    if not plan_day_id:
        flash("Please select a replacement routine.", "warning")
        return redirect(url_for('workouts'))

    success = workout_manager.replace_user_workout(g.user['id'], workout_id, int(plan_day_id))
    if success:
        flash("Workout successfully replaced with the selected routine!", "success")
    else:
        flash("Failed to replace workout. Workout or routine not found.", "danger")
    return redirect(url_for('workouts'))

@app.route('/workouts/edit/<int:workout_id>', methods=['POST'])
@login_required
def edit_workout(workout_id):
    title = request.form.get('title', '').strip()
    workout_date = request.form.get('date', date.today().isoformat())
    duration = int(request.form.get('duration_minutes', 60) or 60)
    intensity = int(request.form.get('intensity_rating', 8) or 8)
    target_muscle = request.form.get('target_muscle_group', 'General').strip()
    notes = request.form.get('notes', '').strip()

    if not title:
        flash("Workout title cannot be empty.", "warning")
        return redirect(url_for('workouts'))

    success = workout_manager.edit_workout_details(
        g.user['id'], workout_id, title, workout_date, duration, intensity, target_muscle, notes
    )
    if success:
        flash("Workout details successfully updated!", "success")
    else:
        flash("Failed to update workout details.", "danger")
    return redirect(url_for('workouts'))

@app.route('/workouts/complete/<int:workout_id>', methods=['POST'])
@login_required
def complete_workout(workout_id):
    duration = request.form.get('duration_minutes')
    duration = int(duration) if duration else None
    intensity = request.form.get('intensity_rating')
    intensity = int(intensity) if intensity else None
    notes = request.form.get('notes')

    success = workout_manager.mark_workout_completed(
        g.user['id'], workout_id, duration, intensity, notes
    )
    if success:
        flash("Workout marked as completed! Consistency streak updated.", "success")
    else:
        flash("Could not mark workout as completed.", "danger")

    ref = request.referrer
    if ref and ('active' in ref or 'dashboard' in ref):
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/workouts/exercise/add', methods=['POST'])
@login_required
def add_exercise():
    workout_id = int(request.form.get('workout_id', 0))
    exercise_id = int(request.form.get('exercise_id', 0))
    sets = int(request.form.get('sets', 3) or 3)
    reps = int(request.form.get('reps', 10) or 10)
    weight_kg = float(request.form.get('weight_kg', 0) or 0)
    rest_seconds = int(request.form.get('rest_seconds', 90) or 90)
    notes = request.form.get('notes', '').strip()

    if not workout_id or not exercise_id:
        flash("Invalid exercise or workout selection.", "warning")
        return redirect(url_for('workouts'))

    we_id = workout_manager.add_exercise_to_workout(
        g.user['id'], workout_id, exercise_id, sets, reps, weight_kg, rest_seconds, notes
    )
    if we_id:
        flash("Exercise successfully added to your workout!", "success")
    else:
        flash("Failed to add exercise. Please verify the workout exists.", "danger")

    ref = request.referrer
    if ref and 'active' in ref:
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/workouts/exercise/delete/<int:we_id>', methods=['POST'])
@login_required
def delete_exercise(we_id):
    success = workout_manager.remove_exercise_from_workout(g.user['id'], we_id)
    if success:
        flash("Exercise removed from workout.", "success")
    else:
        flash("Failed to remove exercise.", "danger")

    ref = request.referrer
    if ref and 'active' in ref:
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/workouts/exercise/edit/<int:we_id>', methods=['POST'])
@login_required
def edit_exercise(we_id):
    sets = int(request.form.get('sets', 3) or 3)
    reps = int(request.form.get('reps', 10) or 10)
    rest_seconds = int(request.form.get('rest_seconds', 90) or 90)
    weight_kg = float(request.form.get('weight_kg', 0) or 0)
    notes = request.form.get('notes', '').strip()

    success = workout_manager.update_exercise_in_workout(
        g.user['id'], we_id, sets, reps, rest_seconds, weight_kg, notes
    )
    if success:
        flash("Exercise updated successfully.", "success")
    else:
        flash("Failed to update exercise.", "danger")

    ref = request.referrer
    if ref and 'active' in ref:
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/workouts/exercise/reorder/<int:we_id>', methods=['POST'])
@login_required
def reorder_exercise(we_id):
    direction = request.form.get('direction', 'up').lower()
    success = workout_manager.reorder_workout_exercise(g.user['id'], we_id, direction)
    if not success:
        flash("Could not change exercise position.", "warning")

    ref = request.referrer
    if ref and 'active' in ref:
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/api/schedule/today', methods=['GET'])
@login_required
def api_get_today_schedule():
    target_date = request.args.get('date', date.today().isoformat())
    conn = database.get_db()
    sched = workout_manager.get_user_daily_schedule(g.user['id'], target_date, conn=conn)
    
    # If no custom schedule, fetch default routine details for today
    if not sched:
        todays_details = workout_manager.get_todays_workout_details(g.user['id'], g.user)
        workout_meta = todays_details.get('workout') or {}
        exercises = todays_details.get('exercises') or []
        res = {
            'is_custom': False,
            'date': target_date,
            'workout_title': workout_meta.get('title') or "Today's Workout",
            'target_muscle_group': workout_meta.get('target_muscle_group') or "General",
            'duration_minutes': workout_meta.get('duration_minutes') or 60,
            'notes': workout_meta.get('notes') or '',
            'workout_id': workout_meta.get('workout_id'),
            'exercises': [
                {
                    'exercise_id': ex.get('exercise_id') or ex.get('id'),
                    'name': ex.get('exercise_name') or ex.get('name'),
                    'category': ex.get('category', ''),
                    'target_muscle': ex.get('target_muscle') or ex.get('muscle_group', ''),
                    'sets': ex.get('sets') or 3,
                    'reps': ex.get('reps') or 10,
                    'rest_time': ex.get('rest_time') or ex.get('rest_seconds') or 90,
                    'exercise_order': ex.get('exercise_order') or (idx + 1),
                    'notes': ex.get('notes') or '',
                    'youtube_id': ex.get('youtube_id') or '',
                    'youtube_url': ex.get('youtube_url') or ''
                }
                for idx, ex in enumerate(exercises)
            ]
        }
        conn.close()
        return jsonify(res)
        
    first = sched[0]
    res = {
        'is_custom': True,
        'date': target_date,
        'workout_title': first.get('workout_title') or "Today's Custom Workout",
        'target_muscle_group': first.get('target_muscle_group') or "General",
        'duration_minutes': first.get('duration_minutes') or 60,
        'notes': first.get('notes') or '',
        'workout_id': first.get('workout_id'),
        'exercises': [
            {
                'exercise_id': ex.get('exercise_id'),
                'name': ex.get('exercise_name'),
                'category': ex.get('category', ''),
                'target_muscle': ex.get('target_muscle') or ex.get('muscle_group', ''),
                'sets': ex.get('sets') or 3,
                'reps': ex.get('reps') or 10,
                'rest_time': ex.get('rest_time') or ex.get('rest_seconds') or 90,
                'exercise_order': ex.get('exercise_order') or (idx + 1),
                'notes': ex.get('notes') or '',
                'youtube_id': ex.get('youtube_id') or '',
                'youtube_url': ex.get('youtube_url') or ''
            }
            for idx, ex in enumerate(sched)
        ]
    }
    conn.close()
    return jsonify(res)


@app.route('/schedule/today/save', methods=['POST'])
@app.route('/workouts/schedule/today/save', methods=['POST'])
@login_required
def save_today_schedule_route():
    # Supports JSON payload or form data
    if request.is_json:
        payload = request.get_json() or {}
    else:
        data_raw = request.form.get('schedule_data')
        if data_raw:
            try:
                payload = json.loads(data_raw)
            except Exception:
                payload = {}
        else:
            payload = request.form.to_dict()

    target_date = payload.get('date') or date.today().isoformat()
    workout_title = (payload.get('workout_title') or "Today's Workout").strip()
    workout_id = payload.get('workout_id')
    try:
        workout_id = int(workout_id) if workout_id is not None and str(workout_id).strip() != '' else None
    except (ValueError, TypeError):
        workout_id = None

    target_muscle_group = (payload.get('target_muscle_group') or "General").strip()
    try:
        duration_minutes = int(payload.get('duration_minutes') or 60)
    except (ValueError, TypeError):
        duration_minutes = 60
    notes = (payload.get('notes') or '').strip()
    exercises = payload.get('exercises') or []

    if isinstance(exercises, str):
        try:
            exercises = json.loads(exercises)
        except Exception:
            exercises = []

    success = workout_manager.save_user_daily_schedule(
        user_id=g.user['id'],
        date_str=target_date,
        workout_title=workout_title,
        workout_id=workout_id,
        target_muscle_group=target_muscle_group,
        duration_minutes=duration_minutes,
        notes=notes,
        exercises=exercises
    )

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': bool(success),
            'message': "Today's schedule updated successfully." if success else "Failed to update today's schedule."
        })

    if success:
        flash("Today's schedule updated successfully.", "success")
    else:
        flash("Failed to update today's schedule.", "danger")

    return redirect(url_for('dashboard'))

@app.route('/workouts/reset-today', methods=['POST'])
@login_required
def reset_workout_route():
    try:
        success = workout_manager.reset_todays_workout(g.user['id'])
        if success:
            msg = "Today's workout has been reset."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': msg})
            flash(msg, "success")
        else:
            err = "Unable to reset. Please try again."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': err}), 400
            flash(err, "danger")
    except Exception as e:
        err = "Unable to reset. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")

    ref = request.referrer
    if ref and ('workout' in ref or 'dashboard' in ref):
        return redirect(ref)
    return redirect(url_for('workouts'))

@app.route('/nutrition')
@login_required
def nutrition():
    selected_date = request.args.get('date', date.today().isoformat())
    conn = database.get_db()
    
    # Calculate detailed summary & grouped meals using nutrition_manager
    nutrition_data = nutrition_manager.get_daily_nutrition_summary(conn, g.user['id'], selected_date, g.user)
    
    # Load food library items for instant search and quick selection
    food_library = nutrition_manager.search_foods(conn)
    
    conn.close()

    return render_template(
        'nutrition.html',
        selected_date=selected_date,
        data=nutrition_data,
        meals=nutrition_data['all_meals'],
        grouped_meals=nutrition_data['grouped_meals'],
        meal_subtotals=nutrition_data['meal_subtotals'],
        totals=nutrition_data['totals'],
        targets=nutrition_data['targets'],
        remaining=nutrition_data['remaining'],
        percentages=nutrition_data['percentages'],
        food_library=food_library,
        today_date=date.today().isoformat()
    )

@app.route('/nutrition/add', methods=['POST'])
@login_required
def add_nutrition():
    # Support both JSON payload and Form data
    data = request.get_json(silent=True) or request.form
    meal_date = data.get('date', date.today().isoformat())
    meal_type = data.get('meal_type', 'Lunch')
    food_id = data.get('food_id')
    food_name = (data.get('food_name') or '').strip()
    logged_via = data.get('logged_via', 'manual')

    conn = database.get_db()
    cursor = conn.cursor()

    # Batch insertion for multi-food scanned items
    if data.get('items') and isinstance(data.get('items'), list):
        items = data.get('items')
        added_entries = []
        total_cals = 0
        total_prot = 0.0
        for it in items:
            it_name = (it.get('food_name') or it.get('name') or '').strip()
            if not it_name:
                continue
            it_qty = float(it.get('quantity', 1.0) or 1.0)
            it_unit = (it.get('serving_unit') or 'serving').strip()
            it_cals = int(float(it.get('calories', 0) or 0))
            it_prot = float(it.get('protein_g', 0) or 0)
            it_carbs = float(it.get('carbs_g', 0) or 0)
            it_fats = float(it.get('fats_g', 0) or 0)
            it_est = int(it.get('is_estimate', 0) or 0)

            cursor.execute("""
                INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, quantity, serving_unit, calories, protein_g, carbs_g, fats_g, logged_via, is_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (g.user['id'], meal_date, meal_type, it_name, it_qty, it_unit, it_cals, it_prot, it_carbs, it_fats, logged_via, it_est))
            new_id = cursor.lastrowid
            total_cals += it_cals
            total_prot += it_prot
            added_entries.append({
                'id': new_id,
                'meal_type': meal_type,
                'food_name': it_name,
                'quantity': it_qty,
                'serving_unit': it_unit,
                'calories': it_cals,
                'protein_g': it_prot
            })

        conn.commit()
        conn.close()
        success_msg = "Food added to today's log"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': success_msg,
                'entries': added_entries,
                'total_calories': total_cals,
                'total_protein': round(total_prot, 1)
            })
        flash(success_msg, "success")
        return redirect(url_for('nutrition', date=meal_date))

    try:
        quantity = float(data.get('quantity', 1.0) or 1.0)
    except (ValueError, TypeError):
        quantity = 1.0

    if quantity <= 0:
        conn.close()
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Serving quantity must be greater than zero.'}), 400
        flash("Serving quantity must be greater than zero.", "danger")
        return redirect(url_for('nutrition', date=meal_date))

    serving_unit = (data.get('serving_unit') or 'serving').strip()
    try:
        is_estimate = int(data.get('is_estimate', 0) or 0)
    except (ValueError, TypeError):
        is_estimate = 0

    food_item = None
    if food_id and str(food_id).strip():
        try:
            food_item = nutrition_manager.get_food_by_id(conn, int(food_id))
        except (ValueError, TypeError):
            food_item = None

    # If food was selected from library by ID, compute scaled macros
    if food_item:
        food_name = food_item['name']
        serving_unit = food_item['serving_unit']
        calories = int(round(food_item['calories'] * quantity))
        protein_g = round(food_item['protein_g'] * quantity, 1)
        carbs_g = round(food_item['carbs_g'] * quantity, 1)
        fats_g = round(food_item['fats_g'] * quantity, 1)
    else:
        # Manual, custom or search entry
        try:
            calories = int(float(data.get('calories', 0) or 0))
        except (ValueError, TypeError):
            calories = 0
        try:
            protein_g = float(data.get('protein_g', 0) or 0)
        except (ValueError, TypeError):
            protein_g = 0.0
        try:
            carbs_g = float(data.get('carbs_g', 0) or 0)
        except (ValueError, TypeError):
            carbs_g = 0.0
        try:
            fats_g = float(data.get('fats_g', 0) or 0)
        except (ValueError, TypeError):
            fats_g = 0.0

        # If food_name was given but calories were 0, try baseline lookup from library
        if food_name and calories <= 0:
            est = nutrition_manager.estimate_food_macros_by_query(conn, food_name, quantity)
            if est:
                calories = est['calories']
                protein_g = est['protein_g']
                carbs_g = est['carbs_g']
                fats_g = est['fats_g']
                if not serving_unit or serving_unit == 'serving':
                    serving_unit = est['serving_unit']

    if not food_name or calories <= 0:
        conn.close()
        msg = 'Please specify a valid food item and caloric value greater than 0.'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('nutrition', date=meal_date))

    cursor.execute("""
        INSERT INTO nutrition_logs (user_id, date, meal_type, food_name, quantity, serving_unit, calories, protein_g, carbs_g, fats_g, logged_via, is_estimate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], meal_date, meal_type, food_name, quantity, serving_unit, calories, protein_g, carbs_g, fats_g, logged_via, is_estimate))
    new_log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = f"Added {quantity:g}x {food_name} to {meal_type} (+{calories} kcal, {protein_g}g protein)."
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': msg,
            'log_id': new_log_id,
            'entry': {
                'id': new_log_id,
                'meal_type': meal_type,
                'food_name': food_name,
                'quantity': quantity,
                'serving_unit': serving_unit,
                'calories': calories,
                'protein_g': protein_g,
                'carbs_g': carbs_g,
                'fats_g': fats_g,
                'logged_via': logged_via,
                'is_estimate': is_estimate
            }
        })

    flash(msg, "success")
    return redirect(url_for('nutrition', date=meal_date))

@app.route('/nutrition/edit/<int:log_id>', methods=['POST'])
@login_required
def edit_nutrition(log_id):
    data = request.get_json(silent=True) or request.form
    meal_date = data.get('date', date.today().isoformat())
    
    try:
        new_quantity = float(data.get('quantity', 1.0) or 1.0)
    except (ValueError, TypeError):
        new_quantity = 1.0

    if new_quantity <= 0:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Serving quantity must be greater than zero.'}), 400
        flash("Serving quantity must be greater than zero.", "danger")
        return redirect(url_for('nutrition', date=meal_date))

    meal_type = data.get('meal_type')
    calories = data.get('calories')
    protein_g = data.get('protein_g')
    carbs_g = data.get('carbs_g')
    fats_g = data.get('fats_g')

    cals_val = None
    if calories is not None and str(calories).strip() != '':
        try:
            cals_val = int(float(calories))
        except (ValueError, TypeError):
            cals_val = None

    p_val = None
    if protein_g is not None and str(protein_g).strip() != '':
        try:
            p_val = float(protein_g)
        except (ValueError, TypeError):
            p_val = None

    c_val = None
    if carbs_g is not None and str(carbs_g).strip() != '':
        try:
            c_val = float(carbs_g)
        except (ValueError, TypeError):
            c_val = None

    f_val = None
    if fats_g is not None and str(fats_g).strip() != '':
        try:
            f_val = float(fats_g)
        except (ValueError, TypeError):
            f_val = None

    conn = database.get_db()
    updated = nutrition_manager.update_nutrition_log(
        conn,
        user_id=g.user['id'],
        log_id=log_id,
        new_quantity=new_quantity,
        calories=cals_val,
        protein_g=p_val,
        carbs_g=c_val,
        fats_g=f_val,
        meal_type=meal_type
    )
    conn.close()

    if not updated:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Food log entry not found or unauthorized.'}), 404
        flash("Food entry not found.", "warning")
        return redirect(url_for('nutrition', date=meal_date))

    msg = f"Updated '{updated['food_name']}' ({new_quantity:g}x: {updated['calories']} kcal, {updated['protein_g']}g protein)."
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': msg, 'entry': updated})
    flash(msg, "success")
    return redirect(url_for('nutrition', date=meal_date))

@app.route('/nutrition/scan/status', methods=['GET'])
@login_required
def scan_food_status():
    """Returns whether AI food-recognition model is configured and active provider."""
    return jsonify({
        "configured": food_recognition.is_ai_configured(),
        "provider": food_recognition.get_configured_provider(),
        "disclaimer": food_recognition.ESTIMATES_DISCLAIMER
    })

@app.route('/nutrition/scan-food', methods=['POST'])
@login_required
def scan_food():
    """
    Receives food image from camera or file upload, validates image,
    and analyzes with AI food-recognition system if configured.
    Never returns fake results.
    """
    image_input = None
    filename_hint = None
    if request.is_json:
        image_input = request.json.get('image_data') or request.json.get('image')
        filename_hint = request.json.get('filename')
    elif 'food_image' in request.files:
        file = request.files['food_image']
        if file and file.filename != '':
            image_input = file.read()
            filename_hint = file.filename
    elif 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            image_input = file.read()
            filename_hint = file.filename
    elif 'image_data' in request.form:
        image_input = request.form['image_data']
        filename_hint = request.form.get('filename')

    if not image_input:
        return jsonify({
            "success": False,
            "configured": food_recognition.is_ai_configured(),
            "status": "invalid_image",
            "message": "No image data was provided. Please capture or select a photo.",
            "disclaimer": food_recognition.ESTIMATES_DISCLAIMER
        }), 400

    conn = database.get_db()
    result = food_recognition.analyze_food_image(image_input, filename_hint=filename_hint, conn=conn)
    conn.close()
    return jsonify(result)

@app.route('/nutrition/food-estimate', methods=['GET', 'POST'])
@login_required
def food_estimate():
    """Returns baseline macro estimates for a food item from the database."""
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        query = (data.get('query') or '').strip()
        try:
            qty = float(data.get('quantity', 1.0) or 1.0)
        except (ValueError, TypeError):
            qty = 1.0
    else:
        query = request.args.get('query', '').strip()
        try:
            qty = float(request.args.get('quantity', 1.0))
        except (ValueError, TypeError):
            qty = 1.0

    conn = database.get_db()
    estimate = nutrition_manager.estimate_food_macros_by_query(conn, query, qty)
    conn.close()

    if estimate:
        return jsonify({
            "success": True,
            "estimate": estimate,
            "disclaimer": food_recognition.ESTIMATES_DISCLAIMER
        })
    return jsonify({
        "success": False,
        "message": f"No baseline match found for '{query}'. Please adjust values manually.",
        "disclaimer": food_recognition.ESTIMATES_DISCLAIMER
    })

@app.route('/nutrition/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_nutrition(log_id):
    data = request.get_json(silent=True) or request.form
    meal_date = data.get('date', date.today().isoformat())
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT food_name, meal_type FROM nutrition_logs WHERE id = ? AND user_id = ?", (log_id, g.user['id']))
    entry = cursor.fetchone()
    if entry:
        cursor.execute("DELETE FROM nutrition_logs WHERE id = ? AND user_id = ?", (log_id, g.user['id']))
        conn.commit()
        msg = f"Removed '{entry['food_name']}' from {entry['meal_type']}."
        conn.close()
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg})
        flash(msg, "info")
    else:
        conn.close()
        msg = "Food entry not found."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 404
        flash(msg, "warning")
    return redirect(url_for('nutrition', date=meal_date))

@app.route('/api/foods/search')
@app.route('/nutrition/search')
@login_required
def api_search_foods():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    conn = database.get_db()
    results = nutrition_manager.search_foods(conn, query=q, category=category)
    conn.close()
    return jsonify(results)

@app.route('/nutrition/reset-today', methods=['POST'])
@login_required
def reset_nutrition_today():
    target_date = request.form.get('date') or request.args.get('date') or date.today().isoformat()
    try:
        conn = database.get_db()
        success = nutrition_manager.reset_daily_nutrition(conn, g.user['id'], target_date)
        conn.close()
        if success:
            msg = "Today's nutrition has been reset."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': msg})
            flash(msg, "success")
        else:
            err = "Unable to reset. Please try again."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': err}), 400
            flash(err, "danger")
    except Exception as e:
        err = "Unable to reset. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")

    return redirect(url_for('nutrition', date=target_date))

@app.route('/progress')
@login_required
def progress():
    conn = database.get_db()
    progress_data = progress_manager.get_progress_dashboard_data(conn, g.user['id'], g.user)
    conn.close()

    return render_template(
        'progress.html',
        summary=progress_data['summary'],
        charts=progress_data['charts'],
        entries=progress_data['entries'],
        latest=progress_data['entries'][0] if progress_data['entries'] else None,
        today_date=date.today().isoformat()
    )

@app.route('/progress/add', methods=['POST'])
@login_required
def add_progress():
    log_date = request.form.get('date', date.today().isoformat())
    weight_kg = float(request.form.get('weight_kg', 0) or 0)
    body_fat_pct = request.form.get('body_fat_pct')
    body_fat_pct = float(body_fat_pct) if body_fat_pct else None
    chest_cm = request.form.get('chest_cm')
    chest_cm = float(chest_cm) if chest_cm else None
    arms_cm = request.form.get('arms_cm')
    arms_cm = float(arms_cm) if arms_cm else None
    waist_cm = request.form.get('waist_cm')
    waist_cm = float(waist_cm) if waist_cm else None
    thighs_cm = request.form.get('thighs_cm')
    thighs_cm = float(thighs_cm) if thighs_cm else None
    notes = request.form.get('notes', '').strip()

    if weight_kg <= 0:
        flash("Please enter a valid body weight.", "danger")
        return redirect(url_for('progress'))

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO progress_logs (user_id, date, weight_kg, body_fat_pct, chest_cm, arms_cm, waist_cm, thighs_cm, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (g.user['id'], log_date, weight_kg, body_fat_pct, chest_cm, arms_cm, waist_cm, thighs_cm, notes))

    # Also update user current weight in users table
    cursor.execute("UPDATE users SET weight_kg = ? WHERE id = ?", (weight_kg, g.user['id']))
    conn.commit()
    conn.close()

    flash(f"Progress check-in logged for {log_date} ({weight_kg} kg). Data synced successfully!", "success")
    return redirect(url_for('progress'))

@app.route('/progress/reset', methods=['POST'])
@login_required
def reset_progress_route():
    try:
        conn = database.get_db()
        success = progress_manager.reset_user_progress(conn, g.user['id'])
        conn.close()
        if success:
            msg = "Progress data has been reset."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': msg})
            flash(msg, "success")
        else:
            err = "Unable to reset. Please try again."
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': err}), 400
            flash(err, "danger")
    except Exception as e:
        err = "Unable to reset. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")

    return redirect(url_for('progress'))

@app.route('/exercises')
def exercises():
    """Exercise library page accessible to all users, with category and equipment filtering."""
    category = request.args.get('category', 'All')
    muscle_group = request.args.get('muscle', 'All')
    equipment = request.args.get('equipment', 'All')
    difficulty = request.args.get('difficulty', 'All')
    search = request.args.get('q', '').strip()

    conn = database.get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM exercises WHERE 1=1"
    params = []

    if category != 'All' and category:
        query += " AND category = ?"
        params.append(category)

    if muscle_group != 'All' and muscle_group:
        query += " AND muscle_group LIKE ?"
        params.append(f"%{muscle_group}%")

    if equipment != 'All' and equipment:
        query += " AND equipment = ?"
        params.append(equipment)

    if difficulty != 'All' and difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)

    if search:
        query += " AND (name LIKE ? OR muscle_group LIKE ? OR description LIKE ? OR instructions LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    query += " ORDER BY category, name"
    cursor.execute(query, params)
    exercise_list = [dict(r) for r in cursor.fetchall()]

    # Ordered categories: Chest, Back, Shoulders, Biceps, Triceps, Legs, Core, Abs
    categories = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Core', 'Abs']

    cursor.execute("SELECT DISTINCT equipment FROM exercises ORDER BY equipment")
    equipment_list = [row['equipment'] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT difficulty FROM exercises ORDER BY difficulty")
    difficulty_list = [row['difficulty'] for row in cursor.fetchall()]

    # Check if logged-in user has an active workout session in progress
    active_workout_session = None
    if g.user:
        cursor.execute("""
            SELECT * FROM workouts
            WHERE user_id = ? AND status = 'in_progress'
            ORDER BY date DESC, id DESC LIMIT 1
        """, (g.user['id'],))
        row = cursor.fetchone()
        if row:
            active_workout_session = dict(row)

    conn.close()

    return render_template(
        'exercises.html',
        exercises=exercise_list,
        categories=categories,
        equipment_list=equipment_list,
        difficulty_list=difficulty_list,
        current_category=category,
        current_muscle=muscle_group,
        current_equipment=equipment,
        current_difficulty=difficulty,
        search_query=search,
        active_workout_session=active_workout_session
    )

@app.route('/exercises/reset-filters', methods=['GET', 'POST'])
def reset_exercise_filters():
    flash("Exercise filters cleared.", "success")
    return redirect(url_for('exercises'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        age_str = request.form.get('age', '').strip()
        gender = request.form.get('gender', 'Male').strip()
        height_str = request.form.get('height_cm', '').strip()
        weight_str = request.form.get('weight_kg', '').strip()
        target_weight_str = request.form.get('target_weight_kg', '').strip()
        experience_level = request.form.get('experience_level', '').strip()
        fitness_goal = request.form.get('fitness_goal', '').strip()
        training_days_str = request.form.get('training_days_per_week', '').strip()
        available_equipment = request.form.get('available_equipment', '').strip()
        dietary_preference = request.form.get('dietary_preference', '').strip()

        daily_calorie_target_str = request.form.get('daily_calorie_target', '').strip()
        daily_protein_target_str = request.form.get('daily_protein_target', '').strip()
        daily_carbs_target_str = request.form.get('daily_carbs_target', '').strip()
        daily_fats_target_str = request.form.get('daily_fats_target', '').strip()

        # Validation
        if not full_name or len(full_name) < 2:
            flash("Full name must be at least 2 characters.", "danger")
            return redirect(url_for('profile'))

        try:
            age = int(age_str)
            if not (12 <= age <= 100):
                flash("Age must be between 12 and 100.", "danger")
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            flash("Please enter a valid age.", "danger")
            return redirect(url_for('profile'))

        try:
            height_cm = float(height_str)
            if not (100.0 <= height_cm <= 250.0):
                flash("Height must be between 100 cm and 250 cm.", "danger")
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            flash("Please enter a valid height.", "danger")
            return redirect(url_for('profile'))

        try:
            weight_kg = float(weight_str)
            if not (30.0 <= weight_kg <= 300.0):
                flash("Weight must be between 30 kg and 300 kg.", "danger")
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            flash("Please enter a valid weight.", "danger")
            return redirect(url_for('profile'))

        try:
            target_weight_kg = float(target_weight_str) if target_weight_str else weight_kg
            if not (30.0 <= target_weight_kg <= 300.0):
                flash("Target weight must be between 30 kg and 300 kg.", "danger")
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            target_weight_kg = weight_kg

        try:
            training_days = int(training_days_str)
            if not (1 <= training_days <= 7):
                flash("Training days per week must be between 1 and 7.", "danger")
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            training_days = 4

        try:
            daily_calorie_target = max(1000, int(daily_calorie_target_str or 2800))
            daily_protein_target = max(30, int(daily_protein_target_str or 180))
            daily_carbs_target = max(20, int(daily_carbs_target_str or 320))
            daily_fats_target = max(15, int(daily_fats_target_str or 75))
        except (ValueError, TypeError):
            flash("Nutrition targets must be valid positive numbers.", "danger")
            return redirect(url_for('profile'))

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET
                full_name = ?,
                age = ?,
                gender = ?,
                height_cm = ?,
                weight_kg = ?,
                target_weight_kg = ?,
                experience_level = ?,
                fitness_goal = ?,
                training_days_per_week = ?,
                available_equipment = ?,
                dietary_preference = ?,
                daily_calorie_target = ?,
                daily_protein_target = ?,
                daily_carbs_target = ?,
                daily_fats_target = ?
            WHERE id = ?
        """, (
            full_name, age, gender, height_cm, weight_kg, target_weight_kg,
            experience_level or 'Intermediate (1-3 Years)',
            fitness_goal or 'Muscle Hypertrophy & Strength',
            training_days,
            available_equipment or 'Full Commercial Gym',
            dietary_preference or 'High Protein Omnivore',
            daily_calorie_target, daily_protein_target,
            daily_carbs_target, daily_fats_target, g.user['id']
        ))
        conn.commit()
        conn.close()

        flash("Fitness profile, biometrics, and nutrition targets successfully updated!", "success")
        return redirect(url_for('profile'))

    metrics = calculate_fitness_metrics(g.user)
    return render_template('profile.html', metrics=metrics)

@app.route('/static/uploads/avatars/<path:filename>')
def serve_uploaded_avatar(filename):
    """Serves uploaded avatars from writable UPLOAD_AVATAR_DIR (e.g. /tmp on Vercel) or bundled static fallback."""
    if os.path.exists(os.path.join(UPLOAD_AVATAR_DIR, filename)):
        return send_from_directory(UPLOAD_AVATAR_DIR, filename)
    fallback_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
    if os.path.exists(os.path.join(fallback_dir, filename)):
        return send_from_directory(fallback_dir, filename)
    return ("Avatar image not found", 404)

@app.route('/profile/picture/upload', methods=['POST'])
@login_required
def upload_profile_picture():
    """Uploads, validates, crops, and updates the user's custom profile picture."""
    file = None
    for key in ['profile_picture', 'file', 'image', 'avatar']:
        if key in request.files and request.files[key].filename:
            file = request.files[key]
            break

    if not file or not file.filename:
        err = "Please select a valid image"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 400
        flash(err, "danger")
        return redirect(url_for('profile'))

    original_filename = file.filename
    ext = os.path.splitext(original_filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        err = "Please select a valid image"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 400
        flash(err, "danger")
        return redirect(url_for('profile'))

    # Check file size (max 5 MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_AVATAR_FILE_SIZE:
        err = "Image must be smaller than 5 MB"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 400
        flash(err, "danger")
        return redirect(url_for('profile'))

    if file_size == 0:
        err = "Please select a valid image"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 400
        flash(err, "danger")
        return redirect(url_for('profile'))

    # Validate image content with Pillow
    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()
        file.seek(0)
        img = Image.open(file)
        img_format = (img.format or '').upper()
        if img_format not in {'JPEG', 'JPG', 'PNG', 'WEBP'}:
            raise ValueError(f"Invalid format {img_format}")
    except Exception as e:
        logger.warning(f"Corrupted or invalid image upload attempted: {e}")
        err = "Please select a valid image"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 400
        flash(err, "danger")
        return redirect(url_for('profile'))

    user_id = g.user['id']

    # Process and crop square
    try:
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        cropped = img.crop((left, top, right, bottom))
        if min_dim > 512:
            cropped = cropped.resize((512, 512), Image.Resampling.LANCZOS)

        # Decide output format & extension
        if cropped.mode in ('RGBA', 'LA') or (cropped.mode == 'P' and 'transparency' in cropped.info):
            save_format = 'WEBP'
            save_ext = '.webp'
        else:
            cropped = cropped.convert('RGB')
            save_format = 'JPEG'
            save_ext = '.jpg'

        # Generate secure unique filename
        unique_token = secrets.token_hex(8)
        new_filename = f"avatar_u{user_id}_{int(datetime.now().timestamp())}_{unique_token}{save_ext}"
        destination_path = os.path.join(UPLOAD_AVATAR_DIR, new_filename)
        cropped.save(destination_path, format=save_format, quality=90, optimize=True)

        web_path = f"/static/uploads/avatars/{new_filename}"

        # Clean up old uploaded image file if present in static/uploads/avatars/
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT profile_picture FROM users WHERE id = ?", (user_id,))
        current_row = cursor.fetchone()
        if current_row and current_row['profile_picture']:
            old_pic = current_row['profile_picture']
            if old_pic.startswith('/static/uploads/avatars/'):
                old_file = os.path.join(UPLOAD_AVATAR_DIR, os.path.basename(old_pic))
                if os.path.exists(old_file) and os.path.isfile(old_file) and old_file != destination_path:
                    try:
                        os.remove(old_file)
                    except Exception as ex:
                        logger.warning(f"Could not remove old avatar {old_file}: {ex}")

        # Update database
        cursor.execute("UPDATE users SET profile_picture = ? WHERE id = ?", (web_path, user_id))
        conn.commit()
        conn.close()

        logger.info(f"Profile picture updated successfully for user_id={user_id}: {web_path}")
        msg = "Profile picture updated successfully"
        initials = get_user_initials(g.user['full_name'] if g.user else '')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg, 'avatar_url': web_path, 'initials': initials})
        flash(msg, "success")
        return redirect(url_for('profile'))

    except Exception as e:
        logger.error(f"Error processing profile picture upload: {e}")
        err = "An error occurred while uploading your profile picture. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")
        return redirect(url_for('profile'))

@app.route('/profile/picture/remove', methods=['POST'])
@login_required
def remove_profile_picture():
    """Removes the custom profile picture and restores the default avatar."""
    user_id = g.user['id']
    try:
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT profile_picture, full_name FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()

        if user_row and user_row['profile_picture']:
            old_pic = user_row['profile_picture']
            if old_pic.startswith('/static/uploads/avatars/'):
                old_file = os.path.join(UPLOAD_AVATAR_DIR, os.path.basename(old_pic))
                if os.path.exists(old_file) and os.path.isfile(old_file):
                    try:
                        os.remove(old_file)
                    except Exception as ex:
                        logger.warning(f"Could not delete avatar file {old_file}: {ex}")

            cursor.execute("UPDATE users SET profile_picture = NULL WHERE id = ?", (user_id,))
            conn.commit()

        initials = get_user_initials(user_row['full_name'] if user_row else g.user['full_name'])
        conn.close()

        logger.info(f"Profile picture removed for user_id={user_id}")
        msg = "Profile picture removed"
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg, 'initials': initials})
        flash(msg, "info")
        return redirect(url_for('profile'))

    except Exception as e:
        logger.error(f"Error removing profile picture: {e}")
        err = "Could not remove profile picture. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")
        return redirect(url_for('profile'))


@app.route('/profile/apply-recommendations', methods=['POST'])
@login_required
def apply_profile_recommendations():
    metrics = calculate_fitness_metrics(g.user)
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET
            daily_calorie_target = ?,
            daily_protein_target = ?,
            daily_carbs_target = ?,
            daily_fats_target = ?
        WHERE id = ?
    """, (
        metrics['calorie_req'],
        metrics['recommended_protein'],
        metrics['rec_carbs'],
        metrics['rec_fats'],
        g.user['id']
    ))
    conn.commit()
    conn.close()

    flash(f"Successfully applied recommended targets: {metrics['calorie_req']} kcal/day and {metrics['recommended_protein']}g protein!", "success")
    return redirect(url_for('profile'))

@app.route('/profile/reset-preferences', methods=['POST'])
@login_required
def reset_fitness_preferences():
    try:
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET
                fitness_goal = ?,
                training_days_per_week = ?,
                available_equipment = ?,
                dietary_preference = ?,
                experience_level = ?
            WHERE id = ?
        """, (
            "Muscle Hypertrophy & Strength",
            4,
            "Full Commercial Gym",
            "High Protein Omnivore",
            "Intermediate (1-3 Years)",
            g.user['id']
        ))
        conn.commit()
        conn.close()
        msg = "Fitness preferences have been reset."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
    except Exception as e:
        err = "Unable to reset. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")

    ref = request.referrer
    if ref and ('settings' in ref or 'profile' in ref):
        return redirect(ref)
    return redirect(url_for('profile'))

@app.route('/assistant')
@login_required
def ai_assistant_page():
    conn = database.get_db()
    context = ai_assistant.get_user_fitness_context(conn, g.user['id'], g.user)
    chat_history = ai_assistant.get_chat_history(conn, g.user['id'], limit=50)
    conn.close()

    return render_template(
        'assistant.html',
        context=context,
        chat_history=chat_history,
        suggested_questions=ai_assistant.SUGGESTED_QUESTIONS,
        disclaimer=ai_assistant.DISCLAIMER_TEXT
    )

@app.route('/assistant/chat', methods=['POST'])
@login_required
def ai_assistant_chat():
    message = request.form.get('message', '').strip()
    if not message:
        # Check json body
        data = request.get_json(silent=True)
        if data:
            message = data.get('message', '').strip()

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    conn = database.get_db()
    # 1. Save user message
    ai_assistant.save_chat_message(conn, g.user['id'], 'user', message)

    # 2. Get user full context
    context = ai_assistant.get_user_fitness_context(conn, g.user['id'], g.user)

    # 3. Generate response
    ai_reply = ai_assistant.generate_ai_response(message, context)

    # 4. Save AI reply
    ai_assistant.save_chat_message(conn, g.user['id'], 'ai', ai_reply)
    conn.close()

    if request.is_json:
        return jsonify({
            'reply': ai_reply,
            'disclaimer': ai_assistant.DISCLAIMER_TEXT
        })

    flash("Response received!", "info")
    return redirect(url_for('ai_assistant_page'))

@app.route('/assistant/clear', methods=['POST'])
@login_required
def ai_assistant_clear():
    try:
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_chat_messages WHERE user_id = ?", (g.user['id'],))
        conn.commit()
        conn.close()
        msg = "AI conversation cleared."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
    except Exception as e:
        err = "Unable to reset. Please try again."
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err}), 500
        flash(err, "danger")
    return redirect(url_for('ai_assistant_page'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', not_found=True), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html', server_error=True), 500

if __name__ == '__main__':
    database.init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
