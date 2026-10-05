"""
Phase 6: Professional Loading Experience Verification Suite
Tests Initial Application Loader, Page Transitions, AI Response Skeleton,
Workout Generation Loading, Camera/Food Scan Loading, Form Button Loading,
and Skeleton Loader System.
"""

import unittest
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import get_db

class TestPhase6LoadingExperience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

        # Ensure demo user exists
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = 'alex@ironpulse.fit'").fetchone()
        conn.close()
        cls.user_id = user['id'] if user else None

    def login_demo(self):
        return self.client.get('/login/demo', follow_redirects=True)

    # -------------------------------------------------------------
    # 1. Initial Application Loader Verification
    # -------------------------------------------------------------
    def test_01_initial_application_loader_markup(self):
        """Test initial loader element, logo, fitness animation, loading indicator and tagline."""
        # Test on public landing page
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="appInitialLoader"', html, "appInitialLoader element must be present in body")
        self.assertIn('Iron<span class="text-gradient">Pulse</span>', html, "App brand name must be present in loader")
        self.assertIn('class="loader-fitness-anim"', html, "Fitness animation container must be present")
        self.assertIn('class="loader-barbell-svg"', html, "Barbell fitness SVG animation must be present")
        self.assertIn('class="loader-progress-track"', html, "Loading indicator track must be present")
        self.assertIn('class="loader-progress-bar"', html, "Loading indicator progress bar must be present")
        self.assertIn('Building a stronger you.', html, "Exact tagline 'Building a stronger you.' must be present")

        # Test prompt dismissal logic is present
        self.assertIn('dismissInitialLoader', html, "Inline dismiss logic must be present for immediate non-blocking experience")

    def test_02_initial_loader_authenticated(self):
        """Test initial loader is present and configured on authenticated routes."""
        self.login_demo()
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="appInitialLoader"', html)
        self.assertIn('Building a stronger you.', html)
        self.assertIn('id="pageTransitionBar"', html)

    # -------------------------------------------------------------
    # 2. Page Transitions Progress Bar
    # -------------------------------------------------------------
    def test_03_page_transition_bar_markup_and_css(self):
        """Test page transition bar exists in templates and CSS."""
        resp = self.client.get('/', follow_redirects=True)
        html = resp.get_data(as_text=True)
        self.assertIn('id="pageTransitionBar"', html)

        # Check CSS
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('#pageTransitionBar', css)
        self.assertIn('linear-gradient(90deg, var(--primary)', css)
        self.assertIn('#pageTransitionBar.active', css)
        self.assertIn('#pageTransitionBar.done', css)

        # Check JS implementation
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('initPageTransitions', js)
        self.assertIn('pageTransitionBar', js)

    # -------------------------------------------------------------
    # 3. Skeleton Loading System in CSS
    # -------------------------------------------------------------
    def test_04_skeleton_classes_and_shimmer_animation(self):
        """Verify skeleton loader classes and @keyframes skeletonShimmer."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('@keyframes skeletonShimmer', css)
        self.assertIn('.skeleton', css)
        self.assertIn('.skeleton-text', css)
        self.assertIn('.skeleton-title', css)
        self.assertIn('.skeleton-card', css)
        self.assertIn('.skeleton-circle', css)
        self.assertIn('.skeleton-rect', css)
        # Theme awareness
        self.assertIn('[data-theme="light"] .skeleton', css)

    # -------------------------------------------------------------
    # 4. Dashboard Skeleton Placeholders
    # -------------------------------------------------------------
    def test_05_dashboard_chart_skeleton_placeholder(self):
        """Verify dashboard chart skeleton loader placeholder and dismissal."""
        self.login_demo()
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="dashboardChartSkeleton"', html)
        self.assertIn('LOADING TRAJECTORY METRICS...', html)
        self.assertIn('dashboardChartSkeleton', html)

    # -------------------------------------------------------------
    # 5. AI Assistant Loading Experience
    # -------------------------------------------------------------
    def test_06_ai_typing_skeleton_card(self):
        """Verify AI response typing indicator skeleton card."""
        self.login_demo()
        resp = self.client.get('/assistant')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="typingIndicator"', html)
        self.assertIn('class="ai-typing-skeleton"', html)
        self.assertIn('class="ai-typing-box"', html)
        self.assertIn('AI Coach is analyzing biometrics &amp; crafting advice...', html)
        self.assertIn('class="skeleton-text long"', html)
        self.assertIn('data-no-loader="true"', html)

    # -------------------------------------------------------------
    # 6. Workout Generation Loading States
    # -------------------------------------------------------------
    def test_07_workout_generation_loading_attributes(self):
        """Verify workout plan generation and split activation have loading states."""
        self.login_demo()
        resp = self.client.get('/workouts')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('data-loading-text="Generating Periodized Split..."', html)
        self.assertIn('data-loading-text="Activating Split..."', html)

    # -------------------------------------------------------------
    # 7. Nutrition Food Image Analysis & Camera Loading
    # -------------------------------------------------------------
    def test_08_nutrition_scan_loading_indicators(self):
        """Verify food image analysis and camera loading indicators."""
        self.login_demo()
        resp = self.client.get('/nutrition')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="scanStageAnalyzing"', html)
        self.assertIn('Analyzing Food Image...', html)
        self.assertIn('id="cameraLoadingMsg"', html)
        self.assertIn('Accessing camera...', html)

    # -------------------------------------------------------------
    # 8. Button Loading State and Accessibility
    # -------------------------------------------------------------
    def test_09_button_loading_state_and_accessibility(self):
        """Verify button loading state (.is-loading, .btn-spinner) and reduced motion support."""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('.btn.is-loading', css)
        self.assertIn('.btn-spinner', css)
        self.assertIn('cursor: wait', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)

        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('initFormLoadingStates', js)
        self.assertIn('setButtonLoading', js)
        self.assertIn('btn-spinner', js)

    def test_10_progress_charts_skeletons(self):
        """Verify analytics charts in progress.html have skeleton placeholders."""
        self.login_demo()
        resp = self.client.get('/progress')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        self.assertIn('id="weightChartSkeleton"', html)
        self.assertIn('id="consistencyChartSkeleton"', html)
        self.assertIn('id="torsoChartSkeleton"', html)
        self.assertIn('id="limbsChartSkeleton"', html)

    def test_11_form_buttons_loading_text(self):
        """Verify login, register, profile, and active workout have explicit data-loading-text."""
        self.client.get('/logout')
        login_html = self.client.get('/login').get_data(as_text=True)
        self.assertIn('data-loading-text="Authenticating..."', login_html)

        reg_html = self.client.get('/register').get_data(as_text=True)
        self.assertIn('data-loading-text="Creating Account..."', reg_html)

        self.login_demo()
        prof_html = self.client.get('/profile').get_data(as_text=True)
        self.assertIn('data-loading-text="Saving Biometrics..."', prof_html)

if __name__ == '__main__':
    unittest.main()

