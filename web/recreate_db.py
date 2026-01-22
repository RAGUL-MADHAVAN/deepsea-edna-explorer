from app import app, db
import os

# Remove existing database if it exists
db_path = 'deepsea.db'
if os.path.exists(db_path):
    print(f"Removing existing database: {db_path}")
    os.remove(db_path)

# Create all tables
with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully!")