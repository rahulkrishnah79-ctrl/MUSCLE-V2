"""
Vercel Serverless Function Entry Point for IronPulse Flask Application.
Exposes the WSGI `app` callable for the Vercel Python runtime (@vercel/python).
"""
import os
import sys

# Ensure the root project directory is on sys.path so modules (app, database, etc.) resolve properly
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

# Export the Flask application instance for Vercel's serverless handler
app = app
