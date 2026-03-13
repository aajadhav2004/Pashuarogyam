"""
Admin routes for PashuAarogyam application
Handles admin dashboard and administrative functions
Note: Admin login is handled in auth_routes.py
"""
from flask import render_template, request, jsonify, session, redirect, url_for
from src.services.database import (
    users_collection, predictions_collection, 
    consultants_collection, get_db_status
)
from src.utils.helpers import hash_password, validate_password
from bson import ObjectId
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_admin_routes(app):
    """Register all admin routes"""
    
    @app.route('/admin-dashboard')
    def admin_dashboard():
        """Admin dashboard"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('admin_login_page'))
        
        try:
            db_available, db_message = get_db_status()
            
            if db_available:
                # Get statistics - count only farmers (exclude admins)
                total_users = users_collection.count_documents({'role': 'farmer'})
                total_predictions = predictions_collection.count_documents({})
                total_consultants = consultants_collection.count_documents({})
                total_consultation_requests = 0  # Placeholder
                
                # Get recent predictions
                recent_predictions = list(
                    predictions_collection.find()
                    .sort('created_at', -1)
                    .limit(10)
                )
                
                # Convert ObjectId to string for JSON serialization
                for pred in recent_predictions:
                    pred['_id'] = str(pred['_id'])
                    pred['user_id'] = str(pred['user_id'])
                    pred['created_at'] = pred['created_at'].isoformat()
                
                # Get recent users (only farmers)
                recent_users = list(
                    users_collection.find({'role': 'farmer'})
                    .sort('created_at', -1)
                    .limit(10)
                )
                
                for user in recent_users:
                    user['_id'] = str(user['_id'])
                    if 'created_at' in user:
                        user['created_at'] = user['created_at'].isoformat()
                
                # Get recent consultations
                recent_consultations = []
                
                # Create stats dictionary
                stats = {
                    'total_users': total_users,
                    'total_predictions': total_predictions,
                    'total_consultants': total_consultants,
                    'total_consultation_requests': total_consultation_requests,
                    'recent_predictions': recent_predictions,
                    'recent_users': recent_users,
                    'recent_consultations': recent_consultations
                }
                
                return render_template(
                    'admin_dashboard.html',
                    stats=stats,
                    db_available=True
                )
            else:
                # Create empty stats dictionary
                stats = {
                    'total_users': 0,
                    'total_predictions': 0,
                    'total_consultants': 0,
                    'total_consultation_requests': 0,
                    'recent_predictions': [],
                    'recent_users': [],
                    'recent_consultations': []
                }
                
                return render_template(
                    'admin_dashboard.html',
                    stats=stats,
                    db_available=False,
                    db_message=db_message
                )
        
        except Exception as e:
            logger.error(f"Admin dashboard error: {str(e)}")
            
            # Create empty stats dictionary for error case
            stats = {
                'total_users': 0,
                'total_predictions': 0,
                'total_consultants': 0,
                'total_consultation_requests': 0,
                'recent_predictions': [],
                'recent_users': [],
                'recent_consultations': []
            }
            
            return render_template(
                'admin_dashboard.html',
                stats=stats,
                error=str(e),
                db_available=False
            ), 500
    
    
    @app.route('/admin/api/stats')
    def admin_api_stats():
        """API endpoint for admin statistics"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        try:
            db_available, _ = get_db_status()
            
            if not db_available:
                return jsonify({'success': False, 'message': 'Database not available'}), 503
            
            # Get statistics
            stats = {
                'total_users': users_collection.count_documents({}),
                'total_predictions': predictions_collection.count_documents({}),
                'total_consultants': consultants_collection.count_documents({}),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return jsonify({'success': True, 'data': stats})
        
        except Exception as e:
            logger.error(f"Admin stats error: {str(e)}")
            return jsonify({'success': False, 'message': 'Error fetching statistics'}), 500
    
    
    @app.route('/admin/users')
    def admin_users():
        """List all users"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('admin_login_page'))
        
        try:
            db_available, _ = get_db_status()
            
            if not db_available:
                return render_template('admin_users.html', users=[], error='Database not available')
            
            users = list(users_collection.find().limit(100))
            
            # Convert ObjectId to string
            for user in users:
                user['_id'] = str(user['_id'])
                if 'created_at' in user:
                    user['created_at'] = user['created_at'].isoformat()
            
            return render_template('admin_users.html', users=users)
        
        except Exception as e:
            logger.error(f"Admin users error: {str(e)}")
            return render_template('admin_users.html', users=[], error=str(e)), 500
    
    
    @app.route('/admin/predictions')
    def admin_predictions():
        """List all predictions"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('admin_login_page'))
        
        try:
            db_available, _ = get_db_status()
            
            if not db_available:
                return render_template('admin_predictions.html', predictions=[], error='Database not available')
            
            predictions = list(predictions_collection.find().sort('created_at', -1).limit(100))
            
            # Convert ObjectId to string
            for pred in predictions:
                pred['_id'] = str(pred['_id'])
                pred['user_id'] = str(pred['user_id'])
                if 'created_at' in pred:
                    pred['created_at'] = pred['created_at'].isoformat()
            
            return render_template('admin_predictions.html', predictions=predictions)
        
        except Exception as e:
            logger.error(f"Admin predictions error: {str(e)}")
            return render_template('admin_predictions.html', predictions=[], error=str(e)), 500

    
    @app.route('/admin/consultants')
    def manage_consultants():
        """Manage consultants page - displays all consultants"""
        logger.info("=== Manage consultants route accessed ===")
        
        if 'user_id' not in session or session.get('role') != 'admin':
            logger.warning("Unauthorized access attempt to manage consultants")
            return redirect(url_for('admin_login_page'))
        
        try:
            db_available, _ = get_db_status()
            logger.info(f"Database available: {db_available}")
            
            if db_available:
                # Get all consultants
                consultants = list(consultants_collection.find().sort('created_at', -1))
                logger.info(f"Found {len(consultants)} consultants")
                
                # Convert ObjectId to string
                for consultant in consultants:
                    consultant['_id'] = str(consultant['_id'])
                    if 'created_at' in consultant:
                        consultant['created_at'] = consultant['created_at'].isoformat()
                    if 'updated_at' in consultant:
                        consultant['updated_at'] = consultant['updated_at'].isoformat()
                
                logger.info("Rendering manage_consultants.html template")
                return render_template('manage_consultants.html', consultants=consultants, db_available=True)
            else:
                logger.warning("Database not available")
                return render_template('manage_consultants.html', consultants=[], db_available=False)
        
        except Exception as e:
            logger.error(f"Manage consultants error: {str(e)}", exc_info=True)
            return render_template('manage_consultants.html', consultants=[], db_available=False, error=str(e))
    
    
    @app.route('/admin/test-route')
    def test_route():
        """Test route to verify routing is working"""
        return "Test route is working! Admin routes are registered correctly."
    
    
    @app.route('/admin/add-consultant')
    def add_consultant_page():
        """Add consultant page"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('admin_login_page'))
        
        return render_template('add_consultant.html')
    
    
    @app.route('/admin/add-consultant', methods=['POST'])
    def add_consultant():
        """Handle adding new consultant"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        try:
            # Get raw request data
            raw_data = request.get_data(as_text=True)
            logger.info(f"Raw request body length: {len(raw_data)}")
            
            data = request.get_json()
            logger.info(f"Raw request data keys: {list(data.keys()) if data else 'None'}")
            logger.info(f"Full request data: {data}")
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            phone = data.get('phone', '').strip()
            specialization = data.get('specialization', '').strip()
            experience = data.get('experience', 0)
            qualification = data.get('qualification', '').strip()
            password = data.get('password', '').strip()
            bio = data.get('bio', '').strip()
            
            logger.info(f"Parsed values - Name: {name}, Email: {email}, Password present: {bool(password)}, Password length: {len(password) if password else 0}")
            
            # Validation
            if not name or not email or not specialization:
                return jsonify({'success': False, 'message': 'Name, email, and specialization are required'}), 400
            
            if not password:
                logger.error("Password is empty after parsing")
                return jsonify({'success': False, 'message': 'Password is required'}), 400
            
            # Validate email format
            if '@' not in email or '.' not in email:
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            
            # Validate password strength
            is_valid, message = validate_password(password)
            if not is_valid:
                logger.error(f"Password validation failed: {message}")
                return jsonify({'success': False, 'message': message}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Check if email already exists
            if consultants_collection.find_one({'email': email.lower()}):
                return jsonify({'success': False, 'message': 'Email already registered'}), 409
            
            # Hash password
            hashed_password = hash_password(password)
            logger.info(f"Password hashed. Hash type: {type(hashed_password)}, Hash length: {len(hashed_password)}, First 20 chars: {hashed_password[:20]}")
            
            # Create consultant record
            consultant_data = {
                'name': name,
                'email': email.lower(),
                'phone': phone,
                'specialization': specialization,
                'experience': int(experience),
                'qualification': qualification,
                'password': hashed_password,
                'bio': bio,
                'status': 'active',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'created_by': session.get('user_id')
            }
            
            logger.info(f"Consultant data prepared. Keys: {list(consultant_data.keys())}")
            logger.info(f"Password in data: {'password' in consultant_data}, Password value type: {type(consultant_data.get('password'))}")
            
            result = consultants_collection.insert_one(consultant_data)
            logger.info(f"Insert result ID: {result.inserted_id}")
            
            # Verify insertion
            inserted_doc = consultants_collection.find_one({'_id': result.inserted_id})
            if inserted_doc:
                logger.info(f"Document retrieved after insert. Keys: {list(inserted_doc.keys())}")
                logger.info(f"Password field in retrieved doc: {'password' in inserted_doc}")
                if 'password' in inserted_doc:
                    logger.info(f"Password value type: {type(inserted_doc['password'])}, Length: {len(str(inserted_doc['password']))}")
            else:
                logger.error("Document not found after insert!")
            
            logger.info(f"New consultant added: {email} by admin {session.get('user_id')}")
            
            return jsonify({
                'success': True,
                'message': f'Consultant {name} added successfully',
                'consultant_id': str(result.inserted_id)
            })
        
        except Exception as e:
            logger.error(f"Add consultant error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
    
    
    @app.route('/admin/edit-consultant/<consultant_id>')
    def edit_consultant_page(consultant_id):
        """Edit consultant page"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('admin_login_page'))
        
        try:
            db_available, _ = get_db_status()
            if not db_available:
                return "Database connection error", 503
            
            # Get consultant details
            consultant = consultants_collection.find_one({'_id': ObjectId(consultant_id)})
            
            if not consultant:
                return "Consultant not found", 404
            
            # Convert ObjectId to string
            consultant['_id'] = str(consultant['_id'])
            if 'created_at' in consultant:
                consultant['created_at'] = consultant['created_at'].isoformat()
            if 'updated_at' in consultant:
                consultant['updated_at'] = consultant['updated_at'].isoformat()
            
            return render_template('edit_consultant.html', consultant=consultant)
        
        except Exception as e:
            logger.error(f"Edit consultant page error: {str(e)}", exc_info=True)
            return f"Error loading consultant: {str(e)}", 500
    
    
    @app.route('/admin/edit-consultant/<consultant_id>', methods=['POST'])
    def update_consultant(consultant_id):
        """Update consultant details"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        try:
            data = request.get_json()
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            phone = data.get('phone', '').strip()
            specialization = data.get('specialization', '').strip()
            experience = data.get('experience', 0)
            qualification = data.get('qualification', '').strip()
            bio = data.get('bio', '').strip()
            status = data.get('status', 'active')
            
            # Validation
            if not name or not email or not specialization:
                return jsonify({'success': False, 'message': 'Name, email, and specialization are required'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Check if consultant exists
            consultant = consultants_collection.find_one({'_id': ObjectId(consultant_id)})
            if not consultant:
                return jsonify({'success': False, 'message': 'Consultant not found'}), 404
            
            # Check if email is taken by another consultant
            existing = consultants_collection.find_one({
                'email': email.lower(),
                '_id': {'$ne': ObjectId(consultant_id)}
            })
            if existing:
                return jsonify({'success': False, 'message': 'Email already registered to another consultant'}), 409
            
            # Update consultant record
            update_data = {
                'name': name,
                'email': email.lower(),
                'phone': phone,
                'specialization': specialization,
                'experience': int(experience),
                'qualification': qualification,
                'bio': bio,
                'status': status,
                'updated_at': datetime.utcnow()
            }
            
            # If password is provided, update it
            new_password = data.get('password', '').strip()
            if new_password:
                is_valid, message = validate_password(new_password)
                if not is_valid:
                    return jsonify({'success': False, 'message': message}), 400
                update_data['password'] = hash_password(new_password)
            
            consultants_collection.update_one(
                {'_id': ObjectId(consultant_id)},
                {'$set': update_data}
            )
            
            logger.info(f"Consultant updated: {consultant_id} by admin {session.get('user_id')}")
            
            return jsonify({
                'success': True,
                'message': f'Consultant {name} updated successfully'
            })
        
        except Exception as e:
            logger.error(f"Update consultant error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
    
    
    @app.route('/admin/delete-consultant/<consultant_id>', methods=['DELETE'])
    def delete_consultant(consultant_id):
        """Delete a consultant"""
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        
        try:
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Check if consultant exists
            consultant = consultants_collection.find_one({'_id': ObjectId(consultant_id)})
            if not consultant:
                return jsonify({'success': False, 'message': 'Consultant not found'}), 404
            
            # Delete the consultant
            result = consultants_collection.delete_one({'_id': ObjectId(consultant_id)})
            
            if result.deleted_count > 0:
                logger.info(f"Consultant deleted: {consultant_id} by admin {session.get('user_id')}")
                return jsonify({
                    'success': True,
                    'message': f'Consultant {consultant.get("name", "Unknown")} deleted successfully'
                })
            else:
                return jsonify({'success': False, 'message': 'Failed to delete consultant'}), 500
        
        except Exception as e:
            logger.error(f"Delete consultant error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
