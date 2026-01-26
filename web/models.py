#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Database models for DeepSea eDNA Explorer
"""

from flask_sqlalchemy import SQLAlchemy
from flask import current_app
import os

# Create database instance
db = SQLAlchemy()
from flask_login import UserMixin
from datetime import datetime
import json

# Association tables for many-to-many relationships
project_collaborators = db.Table('project_collaborators',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True)
)

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100))
    institution = db.Column(db.String(200))
    research_interests = db.Column(db.Text)
    profile_picture = db.Column(db.String(200))  # Path to profile picture
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    projects = db.relationship('Project', backref='owner', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    badges = db.relationship('UserBadge', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
        
    def get_total_samples(self):
        """Return the total number of samples across all user's projects"""
        total = 0
        for project in self.projects:
            total += len(project.samples)
        return total
            
    def get_total_analyses(self):
        """Return the total number of analyses across all user's samples"""
        total = 0
        for project in self.projects:
            for sample in project.samples:
                total += len(sample.analyses)
        return total

    # Template helpers/aliases expected by some pages
    def get_samples_count(self):
        return self.get_total_samples()

    def get_analyses_count(self):
        return self.get_total_analyses()

    def get_recent_analyses(self, limit=5):
        """Return most recent analyses across all projects/samples owned by the user."""
        items = []
        for project in self.projects:
            for sample in project.samples:
                items.extend(sample.analyses)
        # sort by created_at desc
        items.sort(key=lambda a: a.created_at or datetime.min, reverse=True)
        return items[:limit]

    def get_badges_count(self):
        try:
            return len(self.badges)
        except Exception:
            return 0

# Project model
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False)
    project_metadata = db.Column(db.Text)  # JSON string with additional project metadata
    
    # Relationships
    samples = db.relationship('Sample', backref='project', lazy=True, cascade='all, delete-orphan')
    collaborators = db.relationship('User', secondary=project_collaborators, lazy='subquery',
                                   backref=db.backref('collaborative_projects', lazy=True))
    
    def __repr__(self):
        return f'<Project {self.title}>'
        
    def get_metadata(self):
        """Parse and return metadata as a dictionary"""
        if self.project_metadata:
            return json.loads(self.project_metadata)
        return {}

    # Template convenience properties
    @property
    def location(self):
        return self.get_metadata().get('location')

    @property
    def depth_min(self):
        return self.get_metadata().get('depth_min')

    @property
    def depth_max(self):
        return self.get_metadata().get('depth_max')

    @property
    def tags(self):
        return self.get_metadata().get('tags')

    @property
    def user(self):
        # Some templates expect project.user; alias to owner
        return self.owner

# Sample model
class Sample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Path to the uploaded file
    file_type = db.Column(db.String(20))  # FASTQ, FASTA, etc.
    sample_metadata = db.Column(db.Text)  # JSON string with metadata (location, depth, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    analyses = db.relationship('Analysis', backref='sample', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Sample {self.name}>'
    
    def get_metadata(self):
        """Parse and return metadata as a dictionary"""
        if self.sample_metadata:
            return json.loads(self.sample_metadata)
        return {}

    # Template convenience properties
    @property
    def collection_date(self):
        return self.get_metadata().get('collection_date')

    @property
    def depth(self):
        return self.get_metadata().get('depth')

    @property
    def status(self):
        # Basic derived status: if any completed analyses exist
        try:
            if any(a.status == 'completed' for a in self.analyses):
                return 'processed'
            if any(a.status == 'processing' for a in self.analyses):
                return 'processing'
            if any(a.status == 'failed' for a in self.analyses):
                return 'error'
        except Exception:
            pass
        return 'uploaded'

    # UI helper methods
    def _absolute_file_path(self):
        """Return absolute path to the stored sample file, if possible."""
        try:
            upload_root = current_app.config.get('UPLOAD_FOLDER')
            if upload_root and self.file_path:
                return os.path.join(upload_root, self.file_path)
        except Exception:
            pass
        return None

    def get_file_size_display(self):
        """Return a human-readable file size (e.g., '1.2 MB')."""
        abspath = self._absolute_file_path()
        try:
            if abspath and os.path.exists(abspath):
                size = os.path.getsize(abspath)
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024.0 or unit == 'GB':
                        return f"{size:.0f} {unit}" if unit == 'B' else f"{size/1024.0:.1f} {unit}"
                    size /= 1024.0
        except Exception:
            pass
        return 'N/A'

    def get_file_name(self):
        """Return just the filename of the uploaded sample."""
        try:
            return os.path.basename(self.file_path) if self.file_path else ''
        except Exception:
            return ''

    def get_file_extension(self):
        """Return the file extension (e.g., 'fastq')."""
        try:
            name = self.get_file_name()
            if '.' in name:
                return name.rsplit('.', 1)[1].lower()
        except Exception:
            pass
        return ''

# Analysis model
class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sample_id = db.Column(db.Integer, db.ForeignKey('sample.id'), nullable=False)
    analysis_type = db.Column(db.String(50), nullable=False)  # Standard, Novel Discovery, Fast Mode
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    result_path = db.Column(db.String(500))  # Path to results directory
    results_json = db.Column(db.Text)  # JSON summary of pipeline outputs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Analysis {self.id} - {self.analysis_type}>'

    def get_duration_display(self):
        """Return a human-readable duration from created_at to completed_at (or now)."""
        try:
            start = self.created_at
            end = self.completed_at or datetime.utcnow()
            if not start or not end:
                return '—'
            delta = end - start
            # Format as H:MM:SS or M:SS
            seconds = int(delta.total_seconds())
            hours, rem = divmod(seconds, 3600)
            minutes, secs = divmod(rem, 60)
            if hours:
                return f"{hours:d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:d}:{secs:02d}"
        except Exception:
            return '—'

# Notification model
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))  # Optional link to related resource
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.id}>'

# Badge model for gamification
class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(200))  # Path to badge icon
    
    # Relationships
    users = db.relationship('UserBadge', backref='badge', lazy=True)
    
    def __repr__(self):
        return f'<Badge {self.name}>'

# UserBadge association model
class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserBadge {self.user_id} - {self.badge_id}>'

# Comment model for collaboration
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='comments')
    analysis = db.relationship('Analysis', backref='comments')
    project = db.relationship('Project', backref='comments')
    
    def __repr__(self):
        return f'<Comment {self.id}>'