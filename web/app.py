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
from flask_pymongo import PyMongo

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import pipeline components - commented out for simplified demo
# from src.pipeline import run_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DeepSeaEDNA.web')

# Initialize Flask app (enable instance config)
app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = 'deep-sea-edna-explorer-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///deepsea_edna.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size
# MongoDB configuration (use environment variable if available)
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/deepsea_edna')
# Initialize Mongo client
mongo = PyMongo(app)

# Load instance config if present (instance/config.py, ignored by git)
try:
    app.config.from_pyfile('config.py', silent=True)
except Exception:
    pass

# Ensure upload and instance directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
try:
    os.makedirs(app.instance_path, exist_ok=True)
except Exception:
    pass

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

@app.template_filter('datetimeformat')
def datetimeformat(value, fmt='%Y-%m-%d'):
    try:
        import datetime as _dt
        if value is None:
            return ''
        if isinstance(value, (_dt.datetime, _dt.date)):
            return value.strftime(fmt)
        if isinstance(value, (int, float)):
            dt = _dt.datetime.fromtimestamp(value)
            return dt.strftime(fmt)
        if isinstance(value, str):
            try:
                dt = _dt.datetime.fromisoformat(value)
                return dt.strftime(fmt)
            except Exception:
                return value
    except Exception:
        return ''

@app.template_filter('timeago')
def timeago(value):
    try:
        import datetime as _dt
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = _dt.datetime.fromisoformat(value)
            except Exception:
                return value
        if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
            value = _dt.datetime.combine(value, _dt.time.min)
        now = _dt.datetime.utcnow()
        if isinstance(value, _dt.datetime) and value.tzinfo:
            now = _dt.datetime.now(value.tzinfo)
        delta = now - value
        seconds = int(delta.total_seconds())
        intervals = (
            ('year', 31536000),
            ('month', 2592000),
            ('week', 604800),
            ('day', 86400),
            ('hour', 3600),
            ('minute', 60),
            ('second', 1),
        )
        for name, count in intervals:
            value_count = seconds // count
            if value_count:
                return f"{value_count} {name}{'' if value_count == 1 else 's'} ago"
        return 'just now'
    except Exception:
        return ''

@app.template_filter('numberformat')
def numberformat(value, decimals=None):
    try:
        if value is None:
            return ''
        if isinstance(value, (int, float)):
            if decimals is None:
                return f"{value:,}"
            try:
                decimals_int = int(decimals)
            except Exception:
                decimals_int = 0
            return f"{value:,.{decimals_int}f}"
        # Try casting strings that represent numbers
        if isinstance(value, str):
            try:
                if '.' in value:
                    num = float(value)
                    if decimals is None:
                        return f"{num:,}"
                    return f"{num:,.{int(decimals)}f}"
                else:
                    num = int(value)
                    return f"{num:,}"
            except Exception:
                return value
        return str(value)
    except Exception:
        return str(value)
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
