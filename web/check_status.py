
import sys
import os
from app import app, db
from models import Analysis

with app.app_context():
    print(f"Instance Path: {app.instance_path}")
    print(f"DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    analyses = Analysis.query.order_by(Analysis.created_at.desc()).all()
    for a in analyses:
        print(f"ID: {a.id}, Status: {a.status}, Created: {a.created_at}")
