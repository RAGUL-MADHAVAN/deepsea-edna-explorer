#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSea eDNA Explorer - Web Application

This is the main application file for the DeepSea eDNA Explorer web interface.
"""

import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_wtf import CSRFProtect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import json
import sys

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import pipeline components - commented out for simplified demo
# from src.pipeline import run_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DeepSeaEDNA.web')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'deep-sea-edna-explorer-demo-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///deepsea_edna.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Enable CSRF protection
csrf = CSRFProtect(app)

# Provide csrf_token() to Jinja templates (for explicit hidden inputs)
@app.context_processor
def inject_csrf_token():
    try:
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    except Exception:
        # In case CSRF is disabled in some environments
        return dict(csrf_token=lambda: '')

# Import db from models to avoid circular imports
from models import db

# Initialize database with app
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add custom Jinja2 filters
@app.template_filter('nl2br')
def nl2br(value):
    if value:
        return value.replace('\n', '<br>')
    return ''

# Import User model for Flask-Login
from models import User

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes will be registered in the main block to avoid circular imports

if __name__ == '__main__':
    # Import routes here to avoid circular imports
    from routes import register_routes
    register_routes(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)