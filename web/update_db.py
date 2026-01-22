from app import app, db
from models import Project
from sqlalchemy import text

with app.app_context():
    db.session.execute(text('ALTER TABLE project ADD COLUMN project_metadata TEXT'))
    db.session.commit()
    print("Database updated successfully!")