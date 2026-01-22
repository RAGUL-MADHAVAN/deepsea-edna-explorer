#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to migrate the comment table to add project_id column
"""

import os
import sqlite3
from app import app

# Run this script from the command line to migrate the comment table
db_path = os.path.join('instance', 'deepsea_edna.db')

if os.path.exists(db_path):
    print(f"Migrating database: {db_path}")
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Check if project_id column exists
    cursor.execute("PRAGMA table_info(comment)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    if 'project_id' not in column_names:
        print("Adding project_id column to comment table...")
        cursor.execute("ALTER TABLE comment ADD COLUMN project_id INTEGER REFERENCES project(id)")
        conn.commit()
        print("Migration completed successfully!")
    else:
        print("project_id column already exists in comment table.")
    conn.close()
else:
    print(f"Database file not found: {db_path}")