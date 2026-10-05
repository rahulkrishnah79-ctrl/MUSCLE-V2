"""
Progress Manager Module for IronPulse Fitness Tracker
Calculates physique progression, starting weight, current weight, weight deltas,
workout consistency rates, and prepares time-series chart data for Chart.js.
"""

from datetime import date, datetime, timedelta
import sqlite3
import database

def get_progress_dashboard_data(conn, user_id, user_profile):
    """
    Computes all statistics and chart datasets needed for the Progress Dashboard:
    - Current weight, Starting weight, Total weight change
    - Chest, Waist, Arm, Thigh measurements and deltas
    - Workout completion percentage and consistency metrics
    - Time-series progression datasets for Chart.js
    """
    cursor = conn.cursor()

    # 1. Fetch all progress logs ordered by date ascending for charts
    cursor.execute("""
        SELECT * FROM progress_logs
        WHERE user_id = ?
        ORDER BY date ASC, id ASC
    """, (user_id,))
    asc_entries = [dict(r) for r in cursor.fetchall()]

    # Reverse list for recent history table
    desc_entries = list(reversed(asc_entries))

    # Fallback user baseline weight
    user_weight_baseline = float(user_profile['weight_kg'] or 75.0) if user_profile else 75.0
    user_target_weight = float(user_profile['target_weight_kg'] or 82.0) if user_profile else 82.0

    # 2. Starting weight, Current weight, Total weight change
    if asc_entries:
        starting_weight = float(asc_entries[0]['weight_kg'])
        current_weight = float(asc_entries[-1]['weight_kg'])
        latest_entry = asc_entries[-1]
    else:
        starting_weight = user_weight_baseline
        current_weight = user_weight_baseline
        latest_entry = None

    total_weight_change = round(current_weight - starting_weight, 1)

    # 3. Measurement specifics (Chest, Waist, Arm, Thigh)
    current_chest = latest_entry['chest_cm'] if latest_entry and latest_entry.get('chest_cm') else None
    current_waist = latest_entry['waist_cm'] if latest_entry and latest_entry.get('waist_cm') else None
    current_arm = latest_entry['arms_cm'] if latest_entry and latest_entry.get('arms_cm') else None
    current_thigh = latest_entry['thighs_cm'] if latest_entry and latest_entry.get('thighs_cm') else None
    current_body_fat = latest_entry['body_fat_pct'] if latest_entry and latest_entry.get('body_fat_pct') else None

    # Calculate measurement changes from starting to latest
    first_chest = next((e['chest_cm'] for e in asc_entries if e.get('chest_cm')), None)
    first_waist = next((e['waist_cm'] for e in asc_entries if e.get('waist_cm')), None)
    first_arm = next((e['arms_cm'] for e in asc_entries if e.get('arms_cm')), None)
    first_thigh = next((e['thighs_cm'] for e in asc_entries if e.get('thighs_cm')), None)

    total_chest_change = round(current_chest - first_chest, 1) if (current_chest and first_chest) else 0.0
    total_waist_change = round(current_waist - first_waist, 1) if (current_waist and first_waist) else 0.0
    total_arm_change = round(current_arm - first_arm, 1) if (current_arm and first_arm) else 0.0
    total_thigh_change = round(current_thigh - first_thigh, 1) if (current_thigh and first_thigh) else 0.0

    # 4. Workout Consistency & Overall Workout Completion Percentage
    cursor.execute("""
        SELECT COUNT(*) as total_logged,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as total_completed,
               AVG(completion_rate) as avg_completion_rate,
               SUM(total_volume_kg) as cumulative_volume
        FROM workouts
        WHERE user_id = ?
    """, (user_id,))
    w_stats = cursor.fetchone()
    total_logged_workouts = w_stats['total_logged'] or 0
    total_completed_workouts = w_stats['total_completed'] or 0
    cumulative_volume = round(w_stats['cumulative_volume'] or 0.0, 1)

    # Workout Completion Percentage
    if total_logged_workouts > 0:
        overall_completion_pct = int(round((total_completed_workouts / total_logged_workouts) * 100))
    else:
        overall_completion_pct = 100 if total_completed_workouts > 0 else 0

    # 5. Weekly Workout Consistency (Last 8 Weeks)
    today = date.today()
    consistency_weeks = []
    consistency_rates = []
    
    # Target days per week from user profile
    weekly_target = int(user_profile['training_days_per_week'] or 4) if user_profile else 4

    for i in range(7, -1, -1):
        week_end = today - timedelta(days=i * 7)
        week_start = week_end - timedelta(days=6)
        cursor.execute("""
            SELECT COUNT(*) FROM workouts
            WHERE user_id = ? AND date >= ? AND date <= ? AND status = 'completed'
        """, (user_id, week_start.isoformat(), week_end.isoformat()))
        done_count = cursor.fetchone()[0]
        pct = min(100, int(round((done_count / weekly_target) * 100)))
        
        consistency_weeks.append(f"{week_start.strftime('%b %d')}")
        consistency_rates.append(pct)

    # 6. Prepare Clean Datasets for Chart.js
    chart_dates = []
    weight_points = []
    chest_points = []
    waist_points = []
    arm_points = []
    thigh_points = []

    for entry in asc_entries:
        d_str = entry['date']
        # Short format e.g. "Oct 04"
        try:
            d_fmt = datetime.strptime(d_str, "%Y-%m-%d").strftime("%b %d")
        except Exception:
            d_fmt = d_str

        chart_dates.append(d_fmt)
        weight_points.append(entry.get('weight_kg'))
        chest_points.append(entry.get('chest_cm'))
        waist_points.append(entry.get('waist_cm'))
        arm_points.append(entry.get('arms_cm'))
        thigh_points.append(entry.get('thighs_cm'))

    # If no progress entries exist, supply baseline so charts render cleanly
    if not chart_dates:
        chart_dates = [today.strftime("%b %d")]
        weight_points = [user_weight_baseline]
        chest_points = [None]
        waist_points = [None]
        arm_points = [None]
        thigh_points = [None]

    # Target milestone percentage
    if user_target_weight and starting_weight:
        if user_target_weight != starting_weight:
            milestone_pct = int(min(100, max(0, ((current_weight - starting_weight) / (user_target_weight - starting_weight)) * 100)))
        else:
            milestone_pct = 100
    else:
        milestone_pct = 85

    return {
        'summary': {
            'starting_weight': starting_weight,
            'current_weight': current_weight,
            'target_weight': user_target_weight,
            'total_weight_change': total_weight_change,
            'current_chest': current_chest,
            'current_waist': current_waist,
            'current_arm': current_arm,
            'current_thigh': current_thigh,
            'current_body_fat': current_body_fat,
            'total_chest_change': total_chest_change,
            'total_waist_change': total_waist_change,
            'total_arm_change': total_arm_change,
            'total_thigh_change': total_thigh_change,
            'total_completed_workouts': total_completed_workouts,
            'total_logged_workouts': total_logged_workouts,
            'overall_completion_pct': overall_completion_pct,
            'cumulative_volume': cumulative_volume,
            'milestone_pct': milestone_pct
        },
        'charts': {
            'dates': chart_dates,
            'weight': weight_points,
            'chest': chest_points,
            'waist': waist_points,
            'arm': arm_points,
            'thigh': thigh_points,
            'consistency_weeks': consistency_weeks,
            'consistency_rates': consistency_rates
        },
        'entries': desc_entries
    }

def reset_user_progress(conn, user_id):
    """
    Permanently deletes saved body measurements and progress records in progress_logs for the user.
    Preserves user account, workouts, nutrition logs, and exercise library.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM progress_logs WHERE user_id = ?", (user_id,))
    conn.commit()
    return True
