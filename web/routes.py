#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Routes for DeepSea eDNA Explorer web application
"""

import os
import shutil
import json
import pandas as pd
import uuid
import subprocess
import sys
import threading
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file, send_from_directory
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from Bio import SeqIO

# Mongo client
from app import mongo

# Import models
from models import db, User, Project, Sample, Analysis, Notification, Comment

# Import pipeline components
# from src.pipeline import run_pipeline

def register_routes(app):
    # Helper functions
    def allowed_file(filename, allowed=None):
        default_allowed = {'fastq', 'fq', 'fasta', 'fa', 'csv', 'xlsx', 'xls'}
        exts = allowed if allowed is not None else default_allowed
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in exts

    def run_pipeline_async(app_instance, analysis_id, project_id, user_id, sample_id, input_file_path, output_dir_path):
        """
        Background worker to run the pipeline asynchronously.
        """
        with app_instance.app_context():
            print(f"Starting async pipeline for analysis {analysis_id}", flush=True)
            try:
                # Re-fetch objects to ensure they are attached to this session
                analysis = Analysis.query.get(analysis_id)
                project = Project.query.get(project_id)
                sample = Sample.query.get(sample_id)
                # user = User.query.get(user_id) # Not strictly needed if we just use user_id for Notification

                if not analysis:
                    print(f"Analysis {analysis_id} not found in worker", flush=True)
                    return

                # Convert CSV/Excel or FASTQ to FASTA for downstream processing
                final_input_file = input_file_path
                
                try:
                    ext = os.path.splitext(input_file_path)[1].lower().lstrip('.')
                    converted_dir = os.path.join(output_dir_path, 'converted')
                    os.makedirs(converted_dir, exist_ok=True)
                    
                    if ext in ['csv', 'xlsx', 'xls']:
                        # Read sequences from CSV/Excel
                        if ext == 'csv':
                            df = pd.read_csv(input_file_path)
                        else:
                            df = pd.read_excel(input_file_path)
                        col = None
                        for candidate in ['sequence', 'seq', 'dna', 'Sequence', 'Seq']:
                            if candidate in df.columns:
                                col = candidate
                                break
                        if col is None:
                            col = df.columns[0]
                        sequences = df[col].astype(str).tolist()
                        out_fasta = os.path.join(converted_dir, 'input_converted.fasta')
                        with open(out_fasta, 'w') as f:
                            for i, s in enumerate(sequences):
                                s_clean = ''.join(ch for ch in s.upper() if ch in 'ACGTN')
                                if not s_clean:
                                    continue
                                f.write(f'>seq_{i}\n{s_clean}\n')
                        final_input_file = out_fasta
                    elif ext in ['fastq', 'fq']:
                        # Simple fastq -> fasta conversion
                        out_fasta = os.path.join(converted_dir, 'input_converted.fasta')
                        count = 0
                        with open(out_fasta, 'w') as out_handle:
                            for record in SeqIO.parse(input_file_path, 'fastq'):
                                seq_str = str(record.seq).upper()
                                if len(seq_str) >= 50:
                                    rid = record.id or f'read_{count}'
                                    out_handle.write(f'>{rid}\n{seq_str}\n')
                                    count += 1
                        if count > 0:
                            final_input_file = out_fasta
                except Exception as e:
                    print(f"Conversion warning: {e}", flush=True)

                # Build pipeline command
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                pipeline_script = os.path.join(project_root, 'src', 'pipeline.py')
                
                # Extract data type from sample metadata
                sample_meta = json.loads(sample.sample_metadata or '{}')
                data_type = sample_meta.get('data_type', 'amplicon')
                
                cmd = [sys.executable or 'python', pipeline_script, '--input', final_input_file, '--output', output_dir_path, '--data-type', data_type]

                print(f"Executing pipeline command: {cmd}", flush=True)
                
                # Execute pipeline via subprocess
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
                    print(f"Pipeline finished with return code: {result.returncode}", flush=True)
                except subprocess.TimeoutExpired:
                    print("Pipeline timed out!", flush=True)
                    analysis.status = 'failed'
                    analysis.error_message = 'Pipeline timed out (limit: 1h)'
                    db.session.commit()
                    return
                except Exception as e:
                    print(f"Pipeline execution error: {e}", flush=True)
                    raise e

                # Capture logs
                stage_header = (
                    'Pipeline stages (Real-Time):\n'
                    f'- Data Type: {data_type.title()}\n'
                    '- QC / Preprocessing – fastp (Real)\n'
                    '- DNA Embedding – DNABERT-2 (Real)\n'
                    '- Clustering – Unsupervised HDBSCAN (Real)\n'
                    '- Taxonomy – BLAST (Local/Remote) (Real)\n'
                    '- Phylogeny & Assembly – Real Modules\n'
                    '- Abundance & Diversity – Real Calculation\n'
                    '- Report Generation – Dynamic\n\n'
                )
                pipeline_log = stage_header + '=== STDOUT ===\n' + (result.stdout or '') + '\n=== STDERR ===\n' + (result.stderr or '')
                analysis.pipeline_log = pipeline_log

                if result.returncode != 0:
                    analysis.status = 'failed'
                    analysis.error_message = f'Pipeline exited with code {result.returncode}'
                    analysis.completed_at = datetime.utcnow()
                    db.session.commit()
                    return

                # Expected output paths (New Pipeline)
                rel_base = os.path.join(str(user_id), str(project_id), 'analysis', str(analysis_id))
                final_csv_rel = os.path.join(rel_base, 'results', 'final_results.csv')
                
                # Check for final results
                abs_final_csv = os.path.join(app_instance.config['UPLOAD_FOLDER'], final_csv_rel)
                
                if os.path.exists(abs_final_csv):
                    analysis.status = 'completed'
                    analysis.completed_at = datetime.utcnow()
                    analysis.result_path = rel_base
                    # Store main result file in a suitable field (reusing abundance_path or similar if needed, 
                    # but result_path pointing to dir is enough for now)
                else:
                    analysis.status = 'failed'
                    analysis.error_message = f'Missing final output: {final_csv_rel}'

                db.session.commit()

                # Store output paths in MongoDB
                try:
                    mongo.db.projects.update_one(
                        {'project_id': project.id},
                        {'$set': {
                            'project_title': project.title,
                            f'analyses.{analysis.id}': {
                                'result_path': rel_base,
                                'status': analysis.status,
                                'completed_at': (analysis.completed_at.isoformat() if analysis.completed_at else None),
                            }
                        }},
                        upsert=True
                    )
                except Exception as e:
                    print(f"MongoDB update failed: {e}", flush=True)

                # Create notification
                # notification = Notification(
                #     user_id=user_id,
                #     message=f'Analysis of {sample.name} {"completed" if analysis.status=="completed" else "finished with issues"}',
                #     link=f"/analyses/{analysis.id}/results"
                # )
                # db.session.add(notification)
                # db.session.commit()

            except Exception as e:
                print(f"Async pipeline unhandled error: {e}", flush=True)
                if analysis:
                    analysis.status = 'failed'
                    analysis.error_message = str(e)
                    analysis.completed_at = datetime.utcnow()
                    db.session.commit()

    # Example file download endpoint for templates (e.g., upload_sample.html)
    @app.route('/download-example/<path:filename>')
    @login_required
    def download_example_file(filename):
        # Resolve to project root then data/raw for bundled examples
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        example_dir = os.path.join(project_root, 'data', 'raw')
        try:
            return send_from_directory(example_dir, filename, as_attachment=True)
        except Exception:
            flash('Example file not found', 'danger')
            return redirect(url_for('projects'))

    @app.route('/files/<path:filename>')
    @login_required
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # 1. Entry Point (login/signup)
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Authenticate against MongoDB
            user_doc = mongo.db.users.find_one({'email': email})
            
            if user_doc and check_password_hash(user_doc.get('password_hash', ''), password):
                # Ensure SQLAlchemy user exists for relationships and session
                user = User.query.filter_by(email=email).first()
                if not user:
                    user = User(
                        name=user_doc.get('name'),
                        email=user_doc.get('email'),
                        username=user_doc.get('username'),
                        institution=user_doc.get('institution'),
                        password_hash=user_doc.get('password_hash', '')
                    )
                    db.session.add(user)
                    db.session.commit()
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password', 'danger')
                
        return render_template('login.html')
    
    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
            
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            username = request.form.get('username')
            institution = request.form.get('institution')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            # Validation
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('signup.html')
                
            # Check uniqueness using MongoDB
            existing_user = mongo.db.users.find_one({'$or': [{'email': email}, {'username': username}]})
            if existing_user:
                flash('Email or username already exists', 'danger')
                return render_template('signup.html')
            
            # Hash password securely
            password_hash = generate_password_hash(password)
            
            # Store user in MongoDB (source of truth)
            mongo.db.users.insert_one({
                'name': name,
                'email': email,
                'username': username,
                'institution': institution,
                'password_hash': password_hash,
                'created_at': datetime.utcnow()
            })
            
            # Create or sync SQLAlchemy user for app relations
            sql_user = User.query.filter_by(email=email).first()
            if not sql_user:
                sql_user = User(
                    name=name,
                    email=email,
                    username=username,
                    institution=institution,
                    password_hash=password_hash
                )
                db.session.add(sql_user)
                db.session.commit()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
            
        return render_template('signup.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out', 'info')
        return redirect(url_for('index'))
        
    # AI Assistant Feature
    @app.route('/ai-assistant')
    @login_required
    def ai_assistant():
        # Get user's active projects for context selection
        user_projects = Project.query.filter_by(owner_id=current_user.id).all()
        
        # Get user's samples for context selection
        samples = Sample.query.join(Project).filter(Project.owner_id == current_user.id).all()
        
        # Get user's analyses for context selection
        analyses = Analysis.query.join(Sample).join(Project).filter(Project.owner_id == current_user.id).all()
        
        # Add current datetime for message timestamps
        now = datetime.now()
        
        return render_template('ai_assistant.html',
                              user=current_user,
                              projects=user_projects,
                              samples=samples,
                              analyses=analyses,
                              now=now)
    
    @app.route('/api/ai-assistant/query', methods=['POST'])
    @login_required
    def ai_assistant_query():
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({'success': False, 'error': 'No query provided'})
        
        query = data['query']
        context = data.get('context', {})
        
        # In a real implementation, this would call an AI service
        # For demonstration, we'll return mock responses based on keywords
        
        response = ''
        if 'species' in query.lower():
            response = "Based on the DNA sequence analysis, this appears to be a previously unidentified species of deep-sea coral. The genetic markers suggest it belongs to the Octocorallia subclass, but with several unique mutations in the mitochondrial DNA."
        elif 'method' in query.lower():
            response = "For this type of marine sample, I recommend using the Oxford Nanopore sequencing method followed by our custom OceanGenome pipeline. This approach has shown 98% accuracy for similar deep-sea samples in recent studies."
        elif 'literature' in query.lower() or 'research' in query.lower():
            response = "I found 3 recent papers related to your query: 1) 'Novel genetic markers in deep-sea corals' (Zhang et al., 2023), 2) 'Biodiversity patterns in abyssal ecosystems' (Johnson et al., 2022), and 3) 'Comparative genomics of hydrothermal vent organisms' (Patel et al., 2023)."
        elif 'analysis' in query.lower() or 'data' in query.lower():
            response = "Your current dataset shows significant clustering around three genetic markers. I recommend running a principal component analysis to better visualize the genetic diversity, followed by a BLAST comparison against the MarineGenome database."
        else:
            response = "I'm your OceanGenome AI Assistant. I can help with species identification, literature searches, data analysis, and method suggestions. Please provide more details about your research question."
        
        # In a real implementation, we would log this interaction
        
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    
    # 2. Researcher Profile Section
    @app.route('/profile')
    @login_required
    def profile():
        # Get user's publications, education, experience, and certifications
        # In a real implementation, these would be retrieved from the database
        publications = []
        education = []
        experience = []
        certifications = []
        
        return render_template('profile.html', 
                              user=current_user, 
                              publications=publications,
                              education=education,
                              experience=experience,
                              certifications=certifications)
    
    @app.route('/profile/edit', methods=['GET', 'POST'])
    @login_required
    def edit_profile():
        if request.method == 'POST':
            # Handle profile information update
            current_user.name = request.form.get('name')
            current_user.institution = request.form.get('institution')
            current_user.research_interests = request.form.get('research_interests')
            current_user.position = request.form.get('position')
            current_user.department = request.form.get('department')
            current_user.biography = request.form.get('biography')
            current_user.contact_email = request.form.get('contact_email')
            current_user.website = request.form.get('website')
            current_user.orcid = request.form.get('orcid')

            # Prepare MongoDB update payload
            user_update = {
                'name': request.form.get('name'),
                'institution': request.form.get('institution'),
                'research_interests': request.form.get('research_interests'),
                'position': request.form.get('position'),
                'department': request.form.get('department'),
                'biography': request.form.get('biography'),
                'contact_email': request.form.get('contact_email'),
                'website': request.form.get('website'),
                'orcid_id': request.form.get('orcid'),
            }
            # Handle profile picture upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    current_user.profile_picture = os.path.join('profile_pictures', filename)
                    # Also update MongoDB profile picture path
                    user_update['profile_picture'] = current_user.profile_picture
            
            # Persist non-password fields to MongoDB
            try:
                mongo.db.users.update_one({'email': current_user.email}, {'$set': user_update})
            except Exception as e:
                app.logger.error(f"MongoDB update failed: {e}")
            
            # Handle password change
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if current_password and new_password and confirm_password:
                # Verify current password against MongoDB (source of truth)
                user_doc = mongo.db.users.find_one({'email': current_user.email})
                if user_doc and check_password_hash(user_doc.get('password_hash', ''), current_password):
                    # Check if new passwords match
                    if new_password == confirm_password:
                        # Update password in both MongoDB and SQLAlchemy
                        new_hash = generate_password_hash(new_password)
                        current_user.password_hash = new_hash
                        try:
                            mongo.db.users.update_one({'email': current_user.email}, {'$set': {'password_hash': new_hash}})
                        except Exception as e:
                            app.logger.error(f"MongoDB password update failed: {e}")
                        flash('Password updated successfully', 'success')
                    else:
                        flash('New passwords do not match', 'danger')
                        return render_template('edit_profile.html', user=current_user)
                else:
                    flash('Current password is incorrect', 'danger')
                    return render_template('edit_profile.html', user=current_user)
            
            db.session.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('profile'))
            
        return render_template('edit_profile.html', user=current_user)
    
    @app.route('/profile/upload_image', methods=['POST'])
    @login_required
    def upload_profile_image():
        if 'profile_image' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'})
            
        file = request.files['profile_image']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'})
            
        if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            # Update user profile picture in database
            current_user.profile_picture = os.path.join('profile_pictures', filename)
            db.session.commit()
            
            # Also update MongoDB profile picture
            try:
                mongo.db.users.update_one({'email': current_user.email}, {'$set': {'profile_picture': current_user.profile_picture}})
            except Exception as e:
                app.logger.error(f"MongoDB profile picture update failed: {e}")
            
            # Return success with image URL
            image_url = url_for('static', filename=f'uploads/profile_pictures/{filename}')
            return jsonify({'success': True, 'image_url': image_url})
            
        return jsonify({'success': False, 'error': 'File type not allowed'})
    
    @app.route('/profile/publications', methods=['POST'])
    @login_required
    def add_publication():
        # In a real implementation, this would save to a Publication model
        title = request.form.get('title')
        authors = request.form.get('authors')
        journal = request.form.get('journal')
        year = request.form.get('year')
        doi = request.form.get('doi')
        abstract = request.form.get('abstract')
        
        # Mock response for demonstration
        return jsonify({
            'success': True,
            'publication': {
                'id': 1,  # Would be a real ID in production
                'title': title,
                'authors': authors,
                'journal': journal,
                'year': year,
                'doi': doi,
                'abstract': abstract
            }
        })
    
    @app.route('/profile/education', methods=['POST'])
    @login_required
    def add_education():
        # In a real implementation, this would save to an Education model
        institution = request.form.get('institution')
        degree = request.form.get('degree')
        field = request.form.get('field')
        start_year = request.form.get('start_year')
        end_year = request.form.get('end_year')
        description = request.form.get('description')
        
        # Mock response for demonstration
        return jsonify({
            'success': True,
            'education': {
                'id': 1,  # Would be a real ID in production
                'institution': institution,
                'degree': degree,
                'field': field,
                'start_year': start_year,
                'end_year': end_year,
                'description': description
            }
        })
    
    @app.route('/profile/experience', methods=['POST'])
    @login_required
    def add_experience():
        # In a real implementation, this would save to an Experience model
        organization = request.form.get('organization')
        position = request.form.get('position')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        description = request.form.get('description')
        
        # Mock response for demonstration
        return jsonify({
            'success': True,
            'experience': {
                'id': 1,  # Would be a real ID in production
                'organization': organization,
                'position': position,
                'start_date': start_date,
                'end_date': end_date,
                'description': description
            }
        })
    
    @app.route('/profile/certification', methods=['POST'])
    @login_required
    def add_certification():
        # In a real implementation, this would save to a Certification model
        name = request.form.get('name')
        issuer = request.form.get('issuer')
        date = request.form.get('date')
        expiration = request.form.get('expiration')
        description = request.form.get('description')
        
        # Mock response for demonstration
        return jsonify({
            'success': True,
            'certification': {
                'id': 1,  # Would be a real ID in production
                'name': name,
                'issuer': issuer,
                'date': date,
                'expiration': expiration,
                'description': description
            }
        })
    
    # 3. Researcher Dashboard (Home Screen)
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # Get recent projects
        recent_projects = Project.query.filter_by(owner_id=current_user.id).order_by(Project.updated_at.desc()).limit(5).all()
        
        # Get recent analyses
        recent_analyses = Analysis.query.join(Sample).join(Project).filter(
            Project.owner_id == current_user.id
        ).order_by(Analysis.created_at.desc()).limit(5).all()
        
        # Get unread notifications
        notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
        
        return render_template('dashboard.html', 
                              recent_projects=recent_projects, 
                              recent_analyses=recent_analyses,
                              notifications=notifications)
    
    # 4. Data Upload & Analysis
    @app.route('/projects')
    @login_required
    def projects():
        user_projects = Project.query.filter_by(owner_id=current_user.id).all()
        collaborative_projects = current_user.collaborative_projects
        
        return render_template('projects.html', 
                              user_projects=user_projects, 
                              collaborative_projects=collaborative_projects)
    
    @app.route('/projects/new', methods=['GET', 'POST'])
    @login_required
    def new_project():
        from forms import ProjectForm
        from models import User
        form = ProjectForm()
        
        if form.validate_on_submit():
            # Create project metadata dictionary for additional fields
            project_metadata = {
                'location': form.location.data,
                'depth_min': form.depth_min.data,
                'depth_max': form.depth_max.data,
                'tags': form.tags.data
            }
            
            new_project = Project(
                title=form.title.data,
                description=form.description.data,
                owner_id=current_user.id,
                is_public=form.is_public.data,
                project_metadata=json.dumps(project_metadata)
            )
            
            db.session.add(new_project)
            db.session.commit()
            
            # Process collaborators if any
            if form.collaborators.data:
                collaborator_emails = [email.strip() for email in form.collaborators.data.split(',')]
                for email in collaborator_emails:
                    user = User.query.filter_by(email=email).first()
                    if user and user != current_user:
                        new_project.collaborators.append(user)
                db.session.commit()
            
            flash('Project created successfully', 'success')
            return redirect(url_for('project_detail', project_id=new_project.id))
            
        return render_template('new_project.html', form=form)
    
    @app.route('/projects/<int:project_id>')
    @login_required
    def project_detail(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this project', 'danger')
            return redirect(url_for('projects'))
        
        # Get analyses for this project
        analyses = Analysis.query.join(Sample).filter(Sample.project_id == project_id).all()
        
        # Get comments for this project
        comments = Comment.query.filter_by(project_id=project_id).order_by(Comment.created_at.desc()).all()
        
        return render_template('project_detail.html', project=project, analyses=analyses, comments=comments)
        

    
    @app.route('/projects/<int:project_id>/delete', methods=['POST'])
    @login_required
    def delete_project(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user is the owner of the project
        if project.owner_id != current_user.id:
            flash('You do not have permission to delete this project', 'danger')
            return redirect(url_for('projects'))
        
        # Delete the project
        db.session.delete(project)
        db.session.commit()
        
        flash('Project deleted successfully', 'success')
        return redirect(url_for('projects'))
    

    
    @app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_project(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user has access to edit this project
        if project.owner_id != current_user.id:
            flash('Only the project owner can edit this project', 'danger')
            return redirect(url_for('project_detail', project_id=project_id))
            
        from forms import ProjectForm
        from models import User
        
        # Get project metadata
        project_metadata = json.loads(project.project_metadata) if project.project_metadata else {}
        
        # Pre-populate form with existing data
        form = ProjectForm()
        
        if request.method == 'GET':
            form.title.data = project.title
            form.description.data = project.description
            form.is_public.data = project.is_public
            form.location.data = project_metadata.get('location', '')
            form.depth_min.data = project_metadata.get('depth_min', '')
            form.depth_max.data = project_metadata.get('depth_max', '')
            form.tags.data = project_metadata.get('tags', '')
            
            # Get collaborator emails
            collaborator_emails = [user.email for user in project.collaborators]
            form.collaborators.data = ', '.join(collaborator_emails)
        
        if form.validate_on_submit():
            # Update project data
            project.title = form.title.data
            project.description = form.description.data
            project.is_public = form.is_public.data
            
            # Update project metadata
            project_metadata = {
                'location': form.location.data,
                'depth_min': form.depth_min.data,
                'depth_max': form.depth_max.data,
                'tags': form.tags.data
            }
            project.project_metadata = json.dumps(project_metadata)
            
            # Update collaborators
            project.collaborators = []
            if form.collaborators.data:
                collaborator_emails = [email.strip() for email in form.collaborators.data.split(',')]
                for email in collaborator_emails:
                    user = User.query.filter_by(email=email).first()
                    if user and user != current_user:
                        project.collaborators.append(user)
            
            db.session.commit()
            flash('Project updated successfully', 'success')
            return redirect(url_for('project_detail', project_id=project.id))
            
        return render_template('new_project.html', form=form, edit_mode=True, project=project)
    
    @app.route('/projects/<int:project_id>/upload', methods=['GET', 'POST'])
    @login_required
    def upload_sample(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this project', 'danger')
            return redirect(url_for('projects'))
        # WTForms form
        from forms import SampleUploadForm
        form = SampleUploadForm()

        if request.method == 'POST':
            if form.validate_on_submit():
                file = form.file.data
                if file is None or file.filename == '':
                    flash('No selected file', 'danger')
                    return redirect(request.url)

                # Validate extension (FASTA/FASTQ only)
                if not allowed_file(file.filename):
                    flash('File type not allowed. Please upload FASTA (.fasta, .fa), FASTQ (.fastq, .fq), CSV (.csv), or Excel (.xlsx, .xls) files.', 'danger')
                    return redirect(request.url)

                # Validate file size against MAX_CONTENT_LENGTH
                try:
                    file.stream.seek(0, os.SEEK_END)
                    file_size = file.stream.tell()
                    file.stream.seek(0)
                except Exception:
                    file_size = None
                max_size = app.config.get('MAX_CONTENT_LENGTH')
                if max_size and file_size and file_size > max_size:
                    flash(f'File is too large. Maximum allowed size is {int(max_size/1024/1024)} MB.', 'danger')
                    return redirect(request.url)

                # Save sequence file to structured directory: uploads/<user_id>/<project_id>/raw/
                filename = secure_filename(file.filename)
                sample_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), str(project_id), 'raw')
                os.makedirs(sample_dir, exist_ok=True)
                file_path = os.path.join(sample_dir, filename)
                file.save(file_path)

                # Optionally save metadata file
                if form.metadata_file.data and getattr(form.metadata_file.data, 'filename', ''):
                    md_file = form.metadata_file.data
                    md_filename = secure_filename(md_file.filename)
                    md_path = os.path.join(sample_dir, md_filename)
                    try:
                        md_file.save(md_path)
                    except Exception:
                        pass

                # Determine normalized file type
                ext = filename.rsplit('.', 1)[1].lower()
                file_type = 'fasta' if ext in ['fa', 'fasta'] else ('fastq' if ext in ['fq', 'fastq'] else ext)

                # Create sample record
                new_sample = Sample(
                    name=form.name.data,
                    description=form.description.data,
                    project_id=project_id,
                    file_path=os.path.join(str(current_user.id), str(project_id), 'raw', filename),
                    file_type=file_type,
                    sample_metadata=json.dumps({
                        'location': form.location.data,
                        'depth': form.depth.data,
                        'collection_date': form.collection_date.data,
                        'sample_type': form.sample_type.data,
                        'data_type': form.data_type.data
                    })
                )

                db.session.add(new_sample)
                db.session.commit()

                flash('Sample uploaded successfully', 'success')
                # Optionally auto-run analysis if requested
                if form.run_analysis.data:
                    return redirect(url_for('analyze_sample', sample_id=new_sample.id))
                return redirect(url_for('project_detail', project_id=project_id))

        return render_template('upload_sample.html', project=project, form=form)
    
    # Simple sample detail route used by templates, redirecting to analyze
    @app.route('/samples/<int:sample_id>')
    @login_required
    def sample_detail(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        # Access check
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this sample', 'danger')
            return redirect(url_for('projects'))
        # Redirect to analyze page (acts as a sample detail/entry point)
        return redirect(url_for('analyze_sample', sample_id=sample_id))

    # Backward-compatible endpoint used in templates/menus
    @app.route('/samples/<int:sample_id>/run')
    @login_required
    def run_analysis(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this sample', 'danger')
            return redirect(url_for('projects'))
        return redirect(url_for('analyze_sample', sample_id=sample_id))

    # Placeholder edit route referenced by templates
    @app.route('/samples/<int:sample_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_sample(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to edit this sample', 'danger')
            return redirect(url_for('projects'))
        # For now, redirect to analyze page as an entry point
        flash('Sample edit page is not implemented yet. Redirecting to analysis.', 'info')
        return redirect(url_for('analyze_sample', sample_id=sample_id))

    # Download the uploaded sample file
    @app.route('/samples/<int:sample_id>/download')
    @login_required
    def download_sample(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this sample', 'danger')
            return redirect(url_for('projects'))
        # Build absolute path to file
        upload_root = app.config.get('UPLOAD_FOLDER')
        if not upload_root:
            flash('Upload folder is not configured', 'danger')
            return redirect(url_for('project_detail', project_id=project.id))
        abs_path = os.path.join(upload_root, sample.file_path)
        if not os.path.exists(abs_path):
            flash('Sample file not found on server', 'danger')
            return redirect(url_for('project_detail', project_id=project.id))
        # Serve file as attachment
        directory, filename = os.path.split(abs_path)
        return send_from_directory(directory, filename, as_attachment=True)

    # Delete a sample (POST only)
    @app.route('/samples/<int:sample_id>/delete', methods=['POST'])
    @login_required
    def delete_sample(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have permission to delete this sample', 'danger')
            return redirect(url_for('project_detail', project_id=project.id))

        # Attempt to remove the file from disk
        try:
            upload_root = app.config.get('UPLOAD_FOLDER')
            if upload_root and sample.file_path:
                abs_path = os.path.join(upload_root, sample.file_path)
                if os.path.exists(abs_path):
                    os.remove(abs_path)
        except Exception:
            pass

        # Delete DB record (analyses cascade via relationship)
        db.session.delete(sample)
        db.session.commit()
        flash('Sample deleted successfully', 'success')
        return redirect(url_for('project_detail', project_id=project.id))

    @app.route('/samples/<int:sample_id>/analyze', methods=['GET', 'POST'])
    @login_required
    def analyze_sample(sample_id):
        sample = Sample.query.get_or_404(sample_id)
        project = Project.query.get(sample.project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this sample', 'danger')
            return redirect(url_for('projects'))
            
        if request.method == 'POST':
            analysis_type = request.form.get('analysis_type')
            
            # Create analysis record
            new_analysis = Analysis(
                sample_id=sample_id,
                analysis_type=analysis_type,
                status='pending'
            )
            
            db.session.add(new_analysis)
            db.session.commit()
            
            try:
                # Create output directory within structured uploads
                output_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), str(project.id), 'analysis', str(new_analysis.id))
                os.makedirs(output_dir, exist_ok=True)

                # Update analysis status
                new_analysis.status = 'processing'
                db.session.commit()
                
                # Build absolute input file path
                input_file = os.path.join(app.config['UPLOAD_FOLDER'], sample.file_path)
                # Convert CSV/Excel or FASTQ to FASTA for downstream processing
                try:
                    ext = os.path.splitext(input_file)[1].lower().lstrip('.')
                    converted_dir = os.path.join(output_dir, 'converted')
                    os.makedirs(converted_dir, exist_ok=True)
                    if ext in ['csv', 'xlsx', 'xls']:
                        # Read sequences from CSV/Excel; prefer 'sequence' column, fallback to first column
                        if ext == 'csv':
                            df = pd.read_csv(input_file)
                        else:
                            df = pd.read_excel(input_file)
                        col = None
                        for candidate in ['sequence', 'seq', 'dna', 'Sequence', 'Seq']:
                            if candidate in df.columns:
                                col = candidate
                                break
                        if col is None:
                            # fallback to first column
                            col = df.columns[0]
                        sequences = df[col].astype(str).tolist()
                        out_fasta = os.path.join(converted_dir, 'input_converted.fasta')
                        with open(out_fasta, 'w') as f:
                            for i, s in enumerate(sequences):
                                s_clean = ''.join(ch for ch in s.upper() if ch in 'ACGTN')
                                if not s_clean:
                                    continue
                                f.write(f'>seq_{i}\n{s_clean}\n')
                        input_file = out_fasta
                    elif ext in ['fastq', 'fq']:
                        # Simple fastq -> fasta conversion with basic length filter
                        out_fasta = os.path.join(converted_dir, 'input_converted.fasta')
                        count = 0
                        with open(out_fasta, 'w') as out_handle:
                            for record in SeqIO.parse(input_file, 'fastq'):
                                seq_str = str(record.seq).upper()
                                if len(seq_str) >= 50:
                                    rid = record.id or f'read_{count}'
                                    out_handle.write(f'>{rid}\n{seq_str}\n')
                                    count += 1
                        if count > 0:
                            input_file = out_fasta
                except Exception:
                    # If conversion fails, proceed with original file
                    pass
                # Start async pipeline execution
                # Note: We need to pass the real application object to the thread, not the proxy
                import flask
                real_app = flask.current_app._get_current_object()
                
                thread = threading.Thread(
                    target=run_pipeline_async,
                    args=(real_app, new_analysis.id, project.id, current_user.id, sample.id, input_file, output_dir)
                )
                thread.start()
                
                # Redirect directly to results page which will auto-refresh
                return redirect(url_for('analysis_results', analysis_id=new_analysis.id))
                
            except Exception as e:
                new_analysis.status = 'failed'
                new_analysis.error_message = str(e)
                new_analysis.completed_at = datetime.utcnow()
                db.session.commit()
                
                flash(f'Analysis failed: {str(e)}', 'danger')
                return redirect(url_for('project_detail', project_id=project.id))
            
        return render_template('analyze_sample.html', sample=sample, project=project)

    # 5. Results & Visualization
    @app.route('/analyses/<int:analysis_id>/results')
    @login_required
    def analysis_results(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to these results', 'danger')
            return redirect(url_for('projects'))
            
        # Load results data from CSV if available
        results_data = {
            'taxonomy_tree': [],
            'abundance_charts': [],
            'community_comparison': [],
            'novel_clusters': [],
            'rows': [],
            # Cluster-level summary for the results table
            'cluster_rows': []
        }
        
        try:
            if analysis.status == 'completed' and analysis.result_path:
                # Construct path to final_results.csv
                # analysis.result_path is relative to UPLOAD_FOLDER (e.g., user_id/project_id/analysis/analysis_id)
                # Check in results subdirectory first (new pipeline)
                csv_path = os.path.join(app.config['UPLOAD_FOLDER'], analysis.result_path, 'results', 'final_results.csv')
                if not os.path.exists(csv_path):
                    # Fallback to root (old pipeline)
                    csv_path = os.path.join(app.config['UPLOAD_FOLDER'], analysis.result_path, 'final_results.csv')
                
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    # Convert to list of dicts for template
                    results_data['rows'] = df.to_dict('records')

                    # Build a cluster-level table view:
                    # - One row per cluster
                    # - Taxonomy shows unique BLAST names observed in that cluster
                    # - Novelty score is average novelty in the cluster
                    # - Status is the "most severe" among sequences in that cluster
                    if 'cluster' in df.columns:
                        def _status_rank(s):
                            s = str(s or '')
                            if 'High-Novelty' in s:
                                return 4
                            if 'Potential Novel' in s:
                                return 3
                            if 'Unknown' in s:
                                return 2
                            if 'Variant' in s:
                                return 1
                            if 'Known' in s:
                                return 0
                            return 2

                        cluster_rows = []
                        for cluster_id, g in df.groupby('cluster', dropna=False):
                            taxa = []
                            if 'scientific_name' in g.columns:
                                taxa = sorted({str(x).strip() for x in g['scientific_name'].tolist() if str(x).strip()})
                            taxonomy_display = ", ".join(taxa) if taxa else "Unclassified"

                            novelty_val = None
                            if 'novelty_score' in g.columns:
                                try:
                                    novelty_val = float(g['novelty_score'].mean())
                                except Exception:
                                    novelty_val = None

                            # Determine cluster status
                            statuses = g['status'].tolist() if 'status' in g.columns else []
                            statuses = [str(s) for s in statuses if s is not None]
                            if statuses:
                                status = sorted(statuses, key=_status_rank, reverse=True)[0]
                            else:
                                status = "Unknown"

                            # Classification column mirrors status (can be refined later)
                            cluster_rows.append({
                                'cluster': int(cluster_id) if str(cluster_id).isdigit() else cluster_id,
                                'classification': status,
                                'taxonomy': taxonomy_display,
                                'novelty_score': novelty_val,
                                'status': status,
                            })

                        # Sort clusters numerically when possible
                        def _cluster_sort_key(r):
                            try:
                                return int(r.get('cluster'))
                            except Exception:
                                return 10**9
                        cluster_rows.sort(key=_cluster_sort_key)
                        results_data['cluster_rows'] = cluster_rows
                    
                    # Calculate simple stats for charts if needed
                    # e.g. novelty distribution
                    if 'final_status' in df.columns:
                         results_data['novelty_counts'] = df['final_status'].value_counts().to_dict()
        except Exception as e:
            print(f"Error loading analysis results: {e}")
            flash('Error loading analysis results.', 'warning')
        
        # Get comments for this analysis
        comments = Comment.query.filter_by(analysis_id=analysis_id).order_by(Comment.created_at).all()
        
        return render_template('analysis_results.html', 
                              analysis=analysis, 
                              sample=sample, 
                              project=project,
                              results_data=results_data,
                              comments=comments)

    # ----- Stubs for menu actions referenced in templates (only those not already defined below) -----

    @app.route('/analyses/<int:analysis_id>/report')
    @login_required
    def download_analysis_report(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to this report', 'danger')
            return redirect(url_for('projects'))
        # Serve a simple HTML report placeholder
        html = f"<html><body><h3>Analysis {analysis.id} Report (Demo)</h3><p>Type: {analysis.analysis_type}</p><p>Status: {analysis.status}</p></body></html>"
        return html

    @app.route('/analyses/<int:analysis_id>/share')
    @login_required
    def share_analysis(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to share this analysis', 'danger')
            return redirect(url_for('projects'))
        flash('Share link generated (demo): copied to clipboard (mock).', 'success')
        return redirect(url_for('analysis_results', analysis_id=analysis_id))

    @app.route('/analyses/<int:analysis_id>/delete', methods=['POST'])
    @login_required
    def delete_analysis(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have permission to delete this analysis', 'danger')
            return redirect(url_for('project_detail', project_id=project.id))
        db.session.delete(analysis)
        db.session.commit()
        flash('Analysis deleted successfully', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    
    # 6. Collaboration & Sharing
    @app.route('/collaborations')
    @login_required
    def collaborations():
        # Get all projects where the user is a collaborator
        collaborative_projects = current_user.collaborative_projects
        return render_template('collaboration.html', collaborative_projects=collaborative_projects)
        
    @app.route('/projects/<int:project_id>/collaborators', methods=['GET', 'POST'])
    @login_required
    def manage_collaborators(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Only the owner can manage collaborators
        if project.owner_id != current_user.id:
            flash('Only the project owner can manage collaborators', 'danger')
            return redirect(url_for('project_detail', project_id=project_id))
            
        if request.method == 'POST':
            collaborator_email = request.form.get('collaborator_email')
            user = User.query.filter_by(email=collaborator_email).first()
            
            if not user:
                flash('User not found', 'danger')
            elif user.id == current_user.id:
                flash('You cannot add yourself as a collaborator', 'warning')
            elif user in project.collaborators:
                flash('User is already a collaborator', 'warning')
            else:
                project.collaborators.append(user)
                db.session.commit()
                
                # Create notification for the collaborator
                notification = Notification(
                    user_id=user.id,
                    message=f'{current_user.name} added you as a collaborator on project: {project.title}',
                    link=url_for('project_detail', project_id=project_id)
                )
                db.session.add(notification)
                db.session.commit()
                
                flash('Collaborator added successfully', 'success')
                
        return render_template('manage_collaborators.html', project=project)
    
    @app.route('/projects/<int:project_id>/collaborators/<int:user_id>/remove')
    @login_required
    def remove_collaborator(project_id, user_id):
        project = Project.query.get_or_404(project_id)
        
        # Only the owner can remove collaborators
        if project.owner_id != current_user.id:
            flash('Only the project owner can remove collaborators', 'danger')
            return redirect(url_for('project_detail', project_id=project_id))
            
        user = User.query.get_or_404(user_id)
        
        if user in project.collaborators:
            project.collaborators.remove(user)
            db.session.commit()
            flash('Collaborator removed successfully', 'success')
        else:
            flash('User is not a collaborator on this project', 'warning')
            
        return redirect(url_for('manage_collaborators', project_id=project_id))
    
    @app.route('/analyses/<int:analysis_id>/comment', methods=['POST'])
    @login_required
    def add_comment(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to comment on this analysis', 'danger')
            return redirect(url_for('projects'))
            
        comment_text = request.form.get('comment_text')
        
        if comment_text:
            new_comment = Comment(
                user_id=current_user.id,
                analysis_id=analysis_id,
                text=comment_text
            )
            
            db.session.add(new_comment)
            db.session.commit()
            
            # If the commenter is not the project owner, create a notification for the owner
            if current_user.id != project.owner_id:
                notification = Notification(
                    user_id=project.owner_id,
                    message=f'{current_user.name} commented on an analysis in your project: {project.title}',
                    link=url_for('analysis_results', analysis_id=analysis_id)
                )
                db.session.add(notification)
                db.session.commit()
            
            flash('Comment added successfully', 'success')
        else:
            flash('Comment cannot be empty', 'warning')
            
        return redirect(url_for('analysis_results', analysis_id=analysis_id))
    
    # 7. Report Generation
    @app.route('/analyses/<int:analysis_id>/report')
    @login_required
    def generate_report(analysis_id):
        analysis = Analysis.query.get_or_404(analysis_id)
        sample = Sample.query.get(analysis.sample_id)
        project = Project.query.get(sample.project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to generate reports for this analysis', 'danger')
            return redirect(url_for('projects'))
            
        # Generate report (this would be customized based on your actual report generation logic)
        report_format = request.args.get('format', 'html')
        
        # For demonstration, we'll just return a template
        return render_template('report.html', 
                              analysis=analysis, 
                              sample=sample, 
                              project=project,
                              format=report_format)
    
    # 8. Admin Features
    @app.route('/admin')
    @login_required
    def admin_dashboard():
        # Check if user is an admin
        if not current_user.is_admin:
            flash('You do not have access to the admin dashboard', 'danger')
            return redirect(url_for('dashboard'))
            
        # Get all users
        users = User.query.all()
        
        # Get all projects
        projects = Project.query.all()
        
        # Get system statistics
        stats = {
            'user_count': User.query.count(),
            'project_count': Project.query.count(),
            'sample_count': Sample.query.count(),
            'analysis_count': Analysis.query.count()
        }
        
        return render_template('admin/dashboard.html', 
                              users=users, 
                              projects=projects, 
                              stats=stats)
    
    @app.route('/admin/users')
    @login_required
    def admin_users():
        # Check if user is an admin
        if not current_user.is_admin:
            flash('You do not have access to the admin dashboard', 'danger')
            return redirect(url_for('dashboard'))
            
        users = User.query.all()
        return render_template('admin/users.html', users=users)
    
    @app.route('/admin/users/<int:user_id>/toggle_admin')
    @login_required
    def toggle_admin(user_id):
        # Check if user is an admin
        if not current_user.is_admin:
            flash('You do not have access to the admin dashboard', 'danger')
            return redirect(url_for('dashboard'))
            
        user = User.query.get_or_404(user_id)
        
        # Don't allow removing admin status from yourself
        if user.id == current_user.id:
            flash('You cannot remove your own admin status', 'danger')
            return redirect(url_for('admin_users'))
            
        user.is_admin = not user.is_admin
        db.session.commit()
        
        flash(f'Admin status for {user.username} has been {"granted" if user.is_admin else "revoked"}', 'success')
        return redirect(url_for('admin_users'))
    
    # 9. Additional Features
    @app.route('/notifications')
    @login_required
    def notifications():
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        return render_template('notifications.html', notifications=notifications)
    
    @app.route('/notifications/mark_read/<int:notification_id>')
    @login_required
    def mark_notification_read(notification_id):
        notification = Notification.query.get_or_404(notification_id)
        
        # Check if notification belongs to current user
        if notification.user_id != current_user.id:
            flash('Notification not found', 'danger')
            return redirect(url_for('notifications'))
            
        notification.is_read = True
        db.session.commit()
        
        return redirect(url_for('notifications'))
    
    
    @app.route('/language/<lang>')
    def set_language(lang):
        # Store language preference in session
        session['language'] = lang
        return redirect(request.referrer or url_for('index'))
    
    # Route removed to fix duplicate endpoint error
    
    # Project comments functionality
    @app.route('/projects/<int:project_id>/comment', methods=['POST'])
    @login_required
    def add_project_comment(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to comment on this project', 'danger')
            return redirect(url_for('projects'))
        
        comment_text = request.form.get('content')
        
        if comment_text:
            new_comment = Comment(
                user_id=current_user.id,
                project_id=project_id,
                text=comment_text
            )
            
            db.session.add(new_comment)
            db.session.commit()
            
            # If the commenter is not the project owner, create a notification for the owner
            if current_user.id != project.owner_id:
                notification = Notification(
                    user_id=project.owner_id,
                    message=f'{current_user.name} commented on your project: {project.title}',
                    link=url_for('project_detail', project_id=project_id)
                )
                db.session.add(notification)
                db.session.commit()
            
            flash('Comment added successfully', 'success')
        else:
            flash('Comment cannot be empty', 'warning')
            
        return redirect(url_for('project_detail', project_id=project_id))
    
    # Export project functionality
    @app.route('/projects/<int:project_id>/export')
    @login_required
    def export_project(project_id):
        project = Project.query.get_or_404(project_id)
        
        # Check if user has access to this project
        if project.owner_id != current_user.id and current_user not in project.collaborators:
            flash('You do not have access to export this project', 'danger')
            return redirect(url_for('projects'))
            
        # For demonstration, we'll just return a template with project data
        # In a real implementation, this would generate a file for download
        samples = Sample.query.filter_by(project_id=project_id).all()
        analyses = []
        for sample in samples:
            sample_analyses = Analysis.query.filter_by(sample_id=sample.id).all()
            analyses.extend(sample_analyses)
            
        return render_template('export_project.html', 
                              project=project,
                              samples=samples,
                              analyses=analyses)
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500
