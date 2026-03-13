"""
Authentication routes for PashuAarogyam application
Handles user login, signup, and logout with role-based access control
"""
from flask import render_template, request, jsonify, redirect, url_for, session
from src.utils.helpers import validate_email, validate_password, hash_password, check_password
from src.services.database import users_collection, consultants_collection, get_db_status
from bson import ObjectId
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_auth_routes(app):
    """Register all authentication routes"""
    
    # ==================== FARMER ROUTES ====================
    
    @app.route('/farmer/login')
    def farmer_login_page():
        """Farmer login page"""
        if 'user_id' in session and session.get('role') == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        return render_template('farmer_login.html')
    
    
    @app.route('/farmer/signup')
    def farmer_signup_page():
        """Farmer signup page"""
        if 'user_id' in session and session.get('role') == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        return render_template('farmer_signup.html')
    
    
    @app.route('/auth/farmer/login', methods=['POST'])
    def farmer_login():
        """Handle farmer login"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({'success': False, 'message': 'Email and password are required'}), 400
            
            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Find farmer user
            user = users_collection.find_one({'email': email.lower(), 'role': 'farmer'})
            
            if not user:
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            if not check_password(password, user['password']):
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            # Set session
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['name'] = user.get('name', 'Farmer')
            session['role'] = 'farmer'
            
            return jsonify({'success': True, 'message': 'Login successful', 'redirect': url_for('farmer_dashboard')})
        
        except Exception as e:
            logger.error(f"Farmer login error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during login'}), 500
    
    
    @app.route('/auth/farmer/signup', methods=['POST'])
    def farmer_signup():
        """Handle farmer signup"""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')
            
            if not all([name, email, password, confirm_password]):
                return jsonify({'success': False, 'message': 'All fields are required'}), 400
            
            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            if password != confirm_password:
                return jsonify({'success': False, 'message': 'Passwords do not match'}), 400
            
            is_valid, message = validate_password(password)
            if not is_valid:
                return jsonify({'success': False, 'message': message}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            if users_collection.find_one({'email': email.lower()}):
                return jsonify({'success': False, 'message': 'Email already registered'}), 409
            
            hashed_password = hash_password(password)
            user_data = {
                'name': name,
                'email': email.lower(),
                'password': hashed_password,
                'role': 'farmer',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = users_collection.insert_one(user_data)
            
            session['user_id'] = str(result.inserted_id)
            session['email'] = email.lower()
            session['name'] = name
            session['role'] = 'farmer'
            
            return jsonify({'success': True, 'message': 'Signup successful', 'redirect': url_for('farmer_dashboard')})
        
        except Exception as e:
            logger.error(f"Farmer signup error: {str(e)}")
            return jsonify({'success': False, 'message': f'An error occurred during signup: {str(e)}'}), 500
    
    
    # ==================== CONSULTANT ROUTES ====================
    
    @app.route('/consultant/login')
    def consultant_login_page():
        """Consultant login page"""
        if 'user_id' in session and session.get('role') == 'consultant':
            return redirect(url_for('consultant_dashboard'))
        return render_template('consultant_login.html')
    
    
    @app.route('/auth/consultant/login', methods=['POST'])
    def consultant_login():
        """Handle consultant login"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({'success': False, 'message': 'Email and password are required'}), 400
            
            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Find consultant
            consultant = consultants_collection.find_one({'email': email.lower()})
            
            if not consultant:
                logger.warning(f"Consultant not found: {email}")
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            # Check if consultant has password field (for backward compatibility)
            if 'password' not in consultant:
                logger.warning(f"Consultant has no password field: {email}")
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            # Debug: Log password info
            stored_password = consultant['password']
            logger.info(f"Stored password type: {type(stored_password)}, length: {len(str(stored_password))}")
            logger.info(f"Input password length: {len(password)}")
            
            if not check_password(password, stored_password):
                logger.warning(f"Password check failed for: {email}")
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            logger.info(f"Consultant login successful: {email}")
            session['user_id'] = str(consultant['_id'])
            session['email'] = consultant['email']
            session['name'] = consultant.get('name', 'Consultant')
            session['role'] = 'consultant'
            
            return jsonify({'success': True, 'message': 'Login successful', 'redirect': url_for('consultant_dashboard')})
        
        except Exception as e:
            logger.error(f"Consultant login error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'An error occurred during login'}), 500
    
    
    # ==================== ADMIN ROUTES ====================
    
    @app.route('/admin/login')
    def admin_login_page():
        """Admin login page"""
        if 'user_id' in session and session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html')
    
    
    @app.route('/auth/admin/login', methods=['POST'])
    def admin_login():
        """Handle admin login"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({'success': False, 'message': 'Email and password are required'}), 400
            
            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Find admin user
            user = users_collection.find_one({'email': email.lower(), 'role': 'admin'})
            
            if not user:
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            if not check_password(password, user['password']):
                return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['name'] = user.get('name', 'Admin')
            session['role'] = 'admin'
            
            return jsonify({'success': True, 'message': 'Login successful', 'redirect': url_for('admin_dashboard')})
        
        except Exception as e:
            logger.error(f"Admin login error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during login'}), 500
    
    
    @app.route('/admin/signup')
    def admin_signup_page():
        """Admin signup page (only for initial setup)"""
        if 'user_id' in session and session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_signup.html')
    
    
    @app.route('/auth/admin/signup', methods=['POST'])
    def admin_signup():
        """Handle admin signup (restricted)"""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')
            
            if not all([name, email, password, confirm_password]):
                return jsonify({'success': False, 'message': 'All fields are required'}), 400
            
            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            if password != confirm_password:
                return jsonify({'success': False, 'message': 'Passwords do not match'}), 400
            
            is_valid, message = validate_password(password)
            if not is_valid:
                return jsonify({'success': False, 'message': message}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Check if admin already exists
            if users_collection.find_one({'role': 'admin'}):
                return jsonify({'success': False, 'message': 'Admin account already exists'}), 409
            
            if users_collection.find_one({'email': email.lower()}):
                return jsonify({'success': False, 'message': 'Email already registered'}), 409
            
            hashed_password = hash_password(password)
            user_data = {
                'name': name,
                'email': email.lower(),
                'password': hashed_password,
                'role': 'admin',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = users_collection.insert_one(user_data)
            
            session['user_id'] = str(result.inserted_id)
            session['email'] = email.lower()
            session['name'] = name
            session['role'] = 'admin'
            
            return jsonify({'success': True, 'message': 'Admin account created', 'redirect': url_for('admin_dashboard')})
        
        except Exception as e:
            logger.error(f"Admin signup error: {str(e)}")
            return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
    
    
    # ==================== LOGOUT ====================
    
    @app.route('/auth/logout')
    def logout():
        """Handle logout for all roles"""
        session.clear()
        return redirect(url_for('index'))
