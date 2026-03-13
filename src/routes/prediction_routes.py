"""
Prediction routes for PashuAarogyam application
Handles disease prediction endpoints for different animals
"""
from flask import render_template, request, jsonify, session, redirect, url_for
from src.services.database import predictions_collection, consultants_collection, get_db_status
from src.services.ai_service import call_gemini_with_retry
from src.services.model_service import load_model
from src.utils.helpers import allowed_file
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def register_prediction_routes(app, config):
    """Register all prediction routes"""
    
    @app.route('/api/available-consultants')
    def available_consultants():
        """Get list of available consultants"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Get all active consultants
            consultants = list(consultants_collection.find(
                {'status': 'active'},
                {'password': 0}  # Exclude password field
            ).sort('name', 1))
            
            # Convert ObjectId to string and add id field for frontend compatibility
            for consultant in consultants:
                consultant['id'] = str(consultant['_id'])
                consultant['_id'] = str(consultant['_id'])
                if 'created_at' in consultant:
                    consultant['created_at'] = consultant['created_at'].isoformat()
                if 'updated_at' in consultant:
                    consultant['updated_at'] = consultant['updated_at'].isoformat()
            
            return jsonify({
                'success': True,
                'consultants': consultants
            })
        
        except Exception as e:
            logger.error(f"Available consultants error: {str(e)}")
            return jsonify({'success': False, 'message': 'Error fetching consultants'}), 500
    
    
    @app.route('/api/consultation-request', methods=['POST'])
    def create_consultation_request():
        """Create a new consultation request"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            data = request.get_json()
            consultant_id = data.get('assigned_to') or data.get('consultant_id') or data.get('selected_consultant')
            
            logger.info(f"Creating consultation request - data keys: {data.keys()}")
            logger.info(f"Consultant ID extracted: {consultant_id}")
            
            # Get other form data
            farmer_name = data.get('farmer_name', '')
            contact_phone = data.get('contact_phone', '')
            farm_name = data.get('farm_name', '')
            farmer_email = data.get('farmer_email', '')
            location = data.get('location', '')
            animal_type = data.get('animal_type', '')
            animal_breed = data.get('animal_breed', '')
            animal_age = data.get('animal_age', '')
            symptoms = data.get('symptoms', '')
            duration = data.get('duration', '')
            urgency = data.get('urgency', 'Medium')
            additional_notes = data.get('additional_notes', '')
            
            # Validate required fields
            if not farmer_name or not contact_phone or not farm_name or not animal_type or not symptoms:
                return jsonify({'success': False, 'message': 'Please fill in all required fields'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Create consultation request
            from src.services.database import consultation_requests_collection
            
            # Determine initial status based on consultant assignment
            if consultant_id:
                initial_status = 'Assigned'  # Consultant pre-selected, waiting for acceptance
                logger.info(f"Setting status to 'Assigned' - consultant_id: {consultant_id}")
            else:
                initial_status = 'Pending'  # No consultant selected, available for any consultant
                logger.info(f"Setting status to 'Pending' - no consultant selected")
            
            request_data = {
                'farmer_id': ObjectId(session['user_id']),
                'consultant_id': ObjectId(consultant_id) if consultant_id else None,
                'farmer_name': farmer_name,
                'contact_phone': contact_phone,
                'farm_name': farm_name,
                'farmer_email': farmer_email,
                'location': location,
                'animal_type': animal_type,
                'animal_breed': animal_breed,
                'animal_age': animal_age,
                'symptoms': symptoms,
                'duration': duration,
                'urgency': urgency,
                'additional_notes': additional_notes,
                'status': initial_status,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = consultation_requests_collection.insert_one(request_data)
            
            logger.info(f"Consultation request created: {result.inserted_id} by farmer {session['user_id']} "
                       f"with status '{initial_status}' and consultant_id: {consultant_id}")
            
            return jsonify({
                'success': True,
                'message': 'Consultation request created successfully',
                'request_id': str(result.inserted_id)
            })
        
        except Exception as e:
            logger.error(f"Create consultation request error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error creating consultation request: {str(e)}'}), 500
    
    
    @app.route('/api/consultation-requests')
    def get_consultation_requests():
        """Get consultation requests for consultant"""
        try:
            if 'user_id' not in session or session.get('role') != 'consultant':
                return jsonify({'success': False, 'message': 'Not authorized'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import consultation_requests_collection
            
            # Get requests:
            # 1. Unassigned requests (consultant_id = None) - available for any consultant
            # 2. Requests assigned to this consultant that are not yet accepted (status = Pending or Assigned)
            consultant_id = ObjectId(session['user_id'])
            
            requests = list(consultation_requests_collection.find({
                '$or': [
                    # Unassigned requests - any consultant can see
                    {'consultant_id': None},
                    # Requests assigned to this consultant (all statuses)
                    {'consultant_id': consultant_id}
                ]
            }).sort('created_at', -1))
            
            logger.info(f"Found {len(requests)} total requests for consultant {session['user_id']}")
            
            # Convert ObjectId to string and add id field for frontend compatibility
            pending_count = 0
            assigned_count = 0
            progress_count = 0
            completed_count = 0
            
            for req in requests:
                req['id'] = str(req['_id'])
                req['_id'] = str(req['_id'])
                
                # Handle farmer_id - might be missing in old records
                if 'farmer_id' in req and req['farmer_id']:
                    req['farmer_id'] = str(req['farmer_id'])
                else:
                    req['farmer_id'] = None
                
                # Handle consultant_id - might be None
                if req.get('consultant_id'):
                    req['consultant_id'] = str(req['consultant_id'])
                else:
                    req['consultant_id'] = None
                
                # Convert dates
                if 'created_at' in req:
                    req['created_at'] = req['created_at'].isoformat()
                if 'updated_at' in req:
                    req['updated_at'] = req['updated_at'].isoformat()
                
                # Set default status if not present
                if 'status' not in req or not req['status']:
                    req['status'] = 'Pending'
                
                # Count by status for logging
                status = req['status']
                if status == 'Pending':
                    pending_count += 1
                elif status == 'Assigned':
                    assigned_count += 1
                elif status == 'In Progress':
                    progress_count += 1
                elif status == 'Completed':
                    completed_count += 1
            
            logger.info(f"Returning {len(requests)} consultation requests for consultant {session['user_id']}: "
                       f"Pending={pending_count}, Assigned={assigned_count}, In Progress={progress_count}, Completed={completed_count}")
            
            return jsonify({
                'success': True,
                'requests': requests
            })
        
        except Exception as e:
            logger.error(f"Get consultation requests error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error fetching requests'}), 500
    
    
    @app.route('/api/consultation-requests/<request_id>/accept', methods=['POST'])
    def accept_consultation_request(request_id):
        """Accept a consultation request"""
        try:
            if 'user_id' not in session or session.get('role') != 'consultant':
                return jsonify({'success': False, 'message': 'Not authorized'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import consultation_requests_collection
            
            # Find the request
            request_doc = consultation_requests_collection.find_one({'_id': ObjectId(request_id)})
            
            if not request_doc:
                return jsonify({'success': False, 'message': 'Request not found'}), 404
            
            # Check if request is unassigned or assigned to this consultant
            if request_doc.get('consultant_id') and str(request_doc['consultant_id']) != session['user_id']:
                return jsonify({'success': False, 'message': 'Request is assigned to another consultant'}), 403
            
            # Update request: assign consultant and change status
            result = consultation_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'consultant_id': ObjectId(session['user_id']),
                    'status': 'In Progress',
                    'updated_at': datetime.utcnow()
                }}
            )
            
            if result.matched_count == 0:
                return jsonify({'success': False, 'message': 'Request not found'}), 404
            
            logger.info(f"Consultation request {request_id} accepted by consultant {session['user_id']}")
            
            return jsonify({
                'success': True,
                'message': 'Consultation request accepted successfully'
            })
        
        except Exception as e:
            logger.error(f"Accept consultation request error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error accepting request'}), 500
    
    
    @app.route('/api/consultation-requests/<request_id>/complete', methods=['POST'])
    def complete_consultation_request(request_id):
        """Mark a consultation request as completed"""
        try:
            if 'user_id' not in session or session.get('role') != 'consultant':
                return jsonify({'success': False, 'message': 'Not authorized'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import consultation_requests_collection
            
            # Find the request
            request_doc = consultation_requests_collection.find_one({'_id': ObjectId(request_id)})
            
            if not request_doc:
                return jsonify({'success': False, 'message': 'Request not found'}), 404
            
            # Check if request is assigned to this consultant
            if str(request_doc.get('consultant_id')) != session['user_id']:
                return jsonify({'success': False, 'message': 'You can only complete your own consultations'}), 403
            
            # Update request status to Completed
            result = consultation_requests_collection.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': 'Completed',
                    'completed_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }}
            )
            
            if result.matched_count == 0:
                return jsonify({'success': False, 'message': 'Request not found'}), 404
            
            logger.info(f"Consultation request {request_id} marked as completed by consultant {session['user_id']}")
            
            return jsonify({
                'success': True,
                'message': 'Consultation marked as completed successfully'
            })
        
        except Exception as e:
            logger.error(f"Complete consultation request error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error marking as completed'}), 500
    
    
    @app.route('/consultation-chat/<consultation_id>')
    def consultation_chat(consultation_id):
        """Consultation chat page"""
        logger.info(f"Consultation chat requested for ID: {consultation_id}")
        
        if 'user_id' not in session:
            logger.warning("User not logged in, redirecting to index")
            return redirect(url_for('index'))
        
        try:
            db_available, _ = get_db_status()
            if not db_available:
                logger.error("Database not available")
                return "Database connection error", 503
            
            from src.services.database import consultation_requests_collection, users_collection, consultants_collection
            
            # Fetch consultation details
            logger.info(f"Fetching consultation from database: {consultation_id}")
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            
            if not consultation:
                logger.error(f"Consultation not found: {consultation_id}")
                return "Consultation not found", 404
            
            logger.info(f"Consultation found: {consultation.get('farmer_name', 'Unknown')}")
            
            # Determine if user is farmer or consultant
            user_id = session.get('user_id')
            is_farmer = session.get('role') == 'farmer' or str(consultation.get('farmer_id')) == user_id
            is_consultant = session.get('role') == 'consultant' or str(consultation.get('consultant_id')) == user_id
            
            # Fetch additional user details based on role
            other_user_details = None
            
            if is_consultant and consultation.get('farmer_id'):
                # Consultant viewing - fetch farmer details
                farmer = users_collection.find_one({'_id': consultation['farmer_id']})
                if farmer:
                    other_user_details = {
                        'type': 'farmer',
                        'name': farmer.get('name', consultation.get('farmer_name', 'Unknown Farmer')),
                        'email': farmer.get('email', consultation.get('farmer_email', 'N/A')),
                        'phone': consultation.get('contact_phone', 'N/A'),
                        'farm_name': consultation.get('farm_name', 'N/A'),
                        'location': consultation.get('location', 'N/A'),
                        'avatar': '🌾'
                    }
            
            elif is_farmer and consultation.get('consultant_id'):
                # Farmer viewing - fetch consultant details
                consultant = consultants_collection.find_one({'_id': consultation['consultant_id']})
                if consultant:
                    other_user_details = {
                        'type': 'consultant',
                        'name': consultant.get('name', 'Unknown Consultant'),
                        'email': consultant.get('email', 'N/A'),
                        'phone': consultant.get('phone', 'N/A'),
                        'specialization': consultant.get('specialization', 'Veterinary Consultant'),
                        'experience': consultant.get('experience', 'N/A'),
                        'qualifications': consultant.get('qualifications', 'N/A'),
                        'avatar': '👨‍⚕️'
                    }
                    # Add consultant name to consultation object for display
                    consultation['consultant_name'] = consultant.get('name', 'Unknown Consultant')
            
            # Convert ObjectId to string
            consultation['id'] = str(consultation['_id'])
            consultation['_id'] = str(consultation['_id'])
            if consultation.get('farmer_id'):
                consultation['farmer_id'] = str(consultation['farmer_id'])
            if consultation.get('consultant_id'):
                consultation['consultant_id'] = str(consultation['consultant_id'])
            
            # Convert dates
            if 'created_at' in consultation:
                consultation['created_at'] = consultation['created_at'].isoformat()
            if 'updated_at' in consultation:
                consultation['updated_at'] = consultation['updated_at'].isoformat()
            
            # Set default values for missing fields
            consultation.setdefault('farmer_name', 'Unknown Farmer')
            consultation.setdefault('farm_name', 'Unknown Farm')
            consultation.setdefault('animal_type', 'Unknown Animal')
            consultation.setdefault('symptoms', 'No symptoms provided')
            consultation.setdefault('status', 'Pending')
            consultation.setdefault('urgency', 'Medium')
            consultation.setdefault('consultant_name', 'Consultant')  # Default if not assigned yet
            
            logger.info(f"Rendering template with consultation ID: {consultation['id']}, is_farmer: {is_farmer}")
            return render_template(
                'consultation_chat.html', 
                consultation=consultation, 
                is_farmer=is_farmer,
                other_user=other_user_details
            )
        
        except Exception as e:
            logger.error(f"Consultation chat error: {str(e)}", exc_info=True)
            return f"Error loading consultation: {str(e)}", 500
    
    
    @app.route('/api/consultation-requests/<consultation_id>')
    def get_consultation_details(consultation_id):
        """Get consultation details by ID"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import consultation_requests_collection, consultants_collection
            
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            
            if not consultation:
                return jsonify({'success': False, 'message': 'Consultation not found'}), 404
            
            # Check authorization
            user_id = session.get('user_id')
            role = session.get('role')
            
            # Allow access if user is the farmer, the assigned consultant, or an admin
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            is_admin = role == 'admin'
            
            if not (is_farmer or is_consultant or is_admin):
                return jsonify({'success': False, 'message': 'Access denied'}), 403
            
            # Fetch consultant name if consultant is assigned
            if consultation.get('consultant_id'):
                consultant = consultants_collection.find_one({'_id': consultation['consultant_id']})
                if consultant:
                    consultation['consultant_name'] = consultant.get('name', 'Consultant')
            
            # Convert ObjectId to string
            consultation['id'] = str(consultation['_id'])
            consultation['_id'] = str(consultation['_id'])
            if consultation.get('farmer_id'):
                consultation['farmer_id'] = str(consultation['farmer_id'])
            if consultation.get('consultant_id'):
                consultation['consultant_id'] = str(consultation['consultant_id'])
            
            # Convert dates
            if 'created_at' in consultation:
                consultation['created_at'] = consultation['created_at'].isoformat()
            if 'updated_at' in consultation:
                consultation['updated_at'] = consultation['updated_at'].isoformat()
            
            return jsonify({'success': True, 'consultation': consultation})
        
        except Exception as e:
            logger.error(f"Get consultation details error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error fetching consultation details'}), 500
    
    
    @app.route('/api/consultation/<consultation_id>/messages', methods=['GET'])
    def get_consultation_messages(consultation_id):
        """Get messages for a consultation"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import messages_collection, consultation_requests_collection
            
            # Verify consultation exists and user has access
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            if not consultation:
                return jsonify({'success': False, 'message': 'Consultation not found'}), 404
            
            # Check authorization
            user_id = session.get('user_id')
            role = session.get('role')
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            is_admin = role == 'admin'
            
            if not (is_farmer or is_consultant or is_admin):
                return jsonify({'success': False, 'message': 'Access denied'}), 403
            
            # Get messages for this consultation
            messages = list(messages_collection.find(
                {'consultation_id': ObjectId(consultation_id)}
            ).sort('timestamp', 1))
            
            # Convert ObjectId to string
            for msg in messages:
                msg['id'] = str(msg['_id'])
                msg['_id'] = str(msg['_id'])
                msg['consultation_id'] = str(msg['consultation_id'])
                if msg.get('sender_id'):
                    msg['sender_id'] = str(msg['sender_id'])
                if 'timestamp' in msg:
                    msg['timestamp'] = msg['timestamp'].isoformat()
            
            return jsonify({'success': True, 'messages': messages})
        
        except Exception as e:
            logger.error(f"Get messages error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error fetching messages'}), 500
    
    
    @app.route('/api/consultation/<consultation_id>/messages', methods=['POST'])
    def send_consultation_message(consultation_id):
        """Send a message in a consultation"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
            data = request.get_json()
            message_text = data.get('message', '').strip()
            
            if not message_text:
                return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import messages_collection, consultation_requests_collection, users_collection, consultants_collection
            
            # Verify consultation exists and user has access
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            if not consultation:
                return jsonify({'success': False, 'message': 'Consultation not found'}), 404
            
            # Check authorization and determine sender type
            user_id = session.get('user_id')
            role = session.get('role')
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            
            if not (is_farmer or is_consultant):
                return jsonify({'success': False, 'message': 'Access denied'}), 403
            
            # Determine sender type and name
            if is_farmer:
                sender_type = 'farmer'
                user = users_collection.find_one({'_id': ObjectId(user_id)})
                sender_name = user.get('name', 'Farmer') if user else 'Farmer'
            else:
                sender_type = 'consultant'
                consultant = consultants_collection.find_one({'_id': ObjectId(user_id)})
                sender_name = consultant.get('name', 'Consultant') if consultant else 'Consultant'
            
            # Create message
            message_data = {
                'consultation_id': ObjectId(consultation_id),
                'sender_id': ObjectId(user_id),
                'sender_type': sender_type,
                'sender_name': sender_name,
                'message': message_text,
                'timestamp': datetime.utcnow()
            }
            
            result = messages_collection.insert_one(message_data)
            
            # Update consultation updated_at
            consultation_requests_collection.update_one(
                {'_id': ObjectId(consultation_id)},
                {'$set': {'updated_at': datetime.utcnow()}}
            )
            
            # Convert for response
            message_data['id'] = str(result.inserted_id)
            message_data['_id'] = str(result.inserted_id)
            message_data['consultation_id'] = str(message_data['consultation_id'])
            message_data['sender_id'] = str(message_data['sender_id'])
            message_data['timestamp'] = message_data['timestamp'].isoformat()
            
            logger.info(f"Message sent in consultation {consultation_id} by {sender_type} {user_id}")
            
            return jsonify({'success': True, 'message': message_data})
        
        except Exception as e:
            logger.error(f"Send message error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error sending message'}), 500
    
    
    @app.route('/api/consultation/<consultation_id>/upload', methods=['POST'])
    def upload_consultation_file(consultation_id):
        """Upload a file to a consultation"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'}), 400
            
            message_text = request.form.get('message', '').strip()
            
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import messages_collection, consultation_requests_collection, users_collection, consultants_collection
            import gridfs
            
            # Verify consultation exists and user has access
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            if not consultation:
                return jsonify({'success': False, 'message': 'Consultation not found'}), 404
            
            # Check authorization
            user_id = session.get('user_id')
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            
            if not (is_farmer or is_consultant):
                return jsonify({'success': False, 'message': 'Access denied'}), 403
            
            # Determine sender type and name
            if is_farmer:
                sender_type = 'farmer'
                user = users_collection.find_one({'_id': ObjectId(user_id)})
                sender_name = user.get('name', 'Farmer') if user else 'Farmer'
            else:
                sender_type = 'consultant'
                consultant = consultants_collection.find_one({'_id': ObjectId(user_id)})
                sender_name = consultant.get('name', 'Consultant') if consultant else 'Consultant'
            
            # Save file using GridFS
            from src.services.database import db
            fs = gridfs.GridFS(db)
            
            file_id = fs.put(
                file.read(),
                filename=secure_filename(file.filename),
                content_type=file.content_type,
                consultation_id=consultation_id,
                uploaded_by=user_id,
                uploaded_at=datetime.utcnow()
            )
            
            # Create message with file attachment
            message_data = {
                'consultation_id': ObjectId(consultation_id),
                'sender_id': ObjectId(user_id),
                'sender_type': sender_type,
                'sender_name': sender_name,
                'message': message_text if message_text else None,
                'file_info': {
                    'file_id': str(file_id),
                    'filename': secure_filename(file.filename),
                    'content_type': file.content_type,
                    'size': file.content_length or 0
                },
                'timestamp': datetime.utcnow()
            }
            
            result = messages_collection.insert_one(message_data)
            
            # Update consultation updated_at
            consultation_requests_collection.update_one(
                {'_id': ObjectId(consultation_id)},
                {'$set': {'updated_at': datetime.utcnow()}}
            )
            
            # Convert for response
            message_data['id'] = str(result.inserted_id)
            message_data['_id'] = str(result.inserted_id)
            message_data['consultation_id'] = str(message_data['consultation_id'])
            message_data['sender_id'] = str(message_data['sender_id'])
            message_data['timestamp'] = message_data['timestamp'].isoformat()
            
            logger.info(f"File uploaded in consultation {consultation_id} by {sender_type} {user_id}")
            
            return jsonify({'success': True, 'message': message_data})
        
        except Exception as e:
            logger.error(f"Upload file error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'Error uploading file'}), 500
    
    
    @app.route('/api/consultation/<consultation_id>/download/<file_id>')
    def download_consultation_file(consultation_id, file_id):
        """Download a file from a consultation"""
        try:
            if 'user_id' not in session:
                return "Not authenticated", 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return "Database connection error", 503
            
            from src.services.database import consultation_requests_collection, db
            import gridfs
            from flask import send_file
            import io
            
            # Verify consultation exists and user has access
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            if not consultation:
                return "Consultation not found", 404
            
            # Check authorization
            user_id = session.get('user_id')
            role = session.get('role')
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            is_admin = role == 'admin'
            
            if not (is_farmer or is_consultant or is_admin):
                return "Access denied", 403
            
            # Get file from GridFS
            fs = gridfs.GridFS(db)
            try:
                file_data = fs.get(ObjectId(file_id))
                
                return send_file(
                    io.BytesIO(file_data.read()),
                    mimetype=file_data.content_type,
                    as_attachment=True,
                    download_name=file_data.filename
                )
            except gridfs.errors.NoFile:
                return "File not found", 404
        
        except Exception as e:
            logger.error(f"Download file error: {str(e)}", exc_info=True)
            return f"Error downloading file: {str(e)}", 500
    
    
    @app.route('/api/consultation/<consultation_id>/view/<file_id>')
    def view_consultation_file(consultation_id, file_id):
        """View a file from a consultation (inline, not as download)"""
        try:
            if 'user_id' not in session:
                return "Not authenticated", 401
            
            db_available, _ = get_db_status()
            if not db_available:
                return "Database connection error", 503
            
            from src.services.database import consultation_requests_collection, db
            import gridfs
            from flask import send_file
            import io
            
            # Verify consultation exists and user has access
            consultation = consultation_requests_collection.find_one({'_id': ObjectId(consultation_id)})
            if not consultation:
                return "Consultation not found", 404
            
            # Check authorization
            user_id = session.get('user_id')
            role = session.get('role')
            is_farmer = str(consultation.get('farmer_id')) == user_id
            is_consultant = str(consultation.get('consultant_id')) == user_id
            is_admin = role == 'admin'
            
            if not (is_farmer or is_consultant or is_admin):
                return "Access denied", 403
            
            # Get file from GridFS
            fs = gridfs.GridFS(db)
            try:
                file_data = fs.get(ObjectId(file_id))
                
                # Send file inline (for viewing in browser) instead of as attachment
                return send_file(
                    io.BytesIO(file_data.read()),
                    mimetype=file_data.content_type,
                    as_attachment=False,  # This makes it display inline
                    download_name=file_data.filename
                )
            except gridfs.errors.NoFile:
                return "File not found", 404
        
        except Exception as e:
            logger.error(f"View file error: {str(e)}", exc_info=True)
            return f"Error viewing file: {str(e)}", 500
    
    
    @app.route('/api/user-consultation-messages')
    def get_user_consultation_messages():
        """Get farmer's consultations with messages for chat modal"""
        try:
            logger.info("=== User Consultation Messages API Called ===")
            logger.info(f"Session data: {dict(session)}")
            
            if 'user_id' not in session:
                logger.warning("User not authenticated - no user_id in session")
                return jsonify({'success': False, 'message': 'Not authenticated'}), 401
            
            db_available, _ = get_db_status()
            if not db_available:
                logger.error("Database not available")
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            from src.services.database import consultation_requests_collection, messages_collection
            
            user_id = session.get('user_id')
            logger.info(f"Fetching consultations for farmer: {user_id}")
            
            # Get all consultations for this farmer
            consultations = list(consultation_requests_collection.find(
                {'farmer_id': ObjectId(user_id)}
            ).sort('created_at', -1))
            
            logger.info(f"Found {len(consultations)} consultations for farmer {user_id}")
            
            # For each consultation, get messages
            for consultation in consultations:
                consultation_id = consultation['_id']
                logger.info(f"Processing consultation: {consultation_id}")
                
                # Convert ObjectId to string
                consultation['id'] = str(consultation['_id'])
                consultation['_id'] = str(consultation['_id'])
                if consultation.get('farmer_id'):
                    consultation['farmer_id'] = str(consultation['farmer_id'])
                if consultation.get('consultant_id'):
                    consultation['consultant_id'] = str(consultation['consultant_id'])
                
                # Convert dates
                if 'created_at' in consultation:
                    consultation['created_at'] = consultation['created_at'].isoformat()
                if 'updated_at' in consultation:
                    consultation['updated_at'] = consultation['updated_at'].isoformat()
                
                # Get messages for this consultation
                messages = list(messages_collection.find(
                    {'consultation_id': consultation_id}
                ).sort('timestamp', 1))
                
                logger.info(f"Found {len(messages)} messages for consultation {consultation_id}")
                
                # Convert message ObjectIds
                for msg in messages:
                    msg['id'] = str(msg['_id'])
                    msg['_id'] = str(msg['_id'])
                    msg['consultation_id'] = str(msg['consultation_id'])
                    if msg.get('sender_id'):
                        msg['sender_id'] = str(msg['sender_id'])
                    if 'timestamp' in msg:
                        msg['timestamp'] = msg['timestamp'].isoformat()
                
                consultation['messages'] = messages
            
            logger.info(f"Returning {len(consultations)} consultations with messages")
            
            return jsonify({
                'success': True,
                'consultations': consultations
            })
        
        except Exception as e:
            logger.error(f"Get user consultation messages error: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error fetching consultations: {str(e)}'}), 500
    
    
    @app.route('/api/session-check')
    def session_check():
        """Check session status for debugging"""
        return jsonify({
            'success': True,
            'session_info': {
                'has_user_id': 'user_id' in session,
                'has_consultant_id': 'consultant_id' in session,
                'role': session.get('role'),
                'user_id': session.get('user_id')
            }
        })
    
    
    @app.route('/predict_disease', methods=['POST'])
    def predict_disease():
        """Handle disease prediction requests"""
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            # Debug: Log all form data
            logger.info(f"Form data received: {dict(request.form)}")
            logger.info(f"Files received: {list(request.files.keys())}")
            
            # Get form data
            animal_type = request.form.get('animal_type', '').lower()
            
            # Handle symptoms array
            symptoms_list = request.form.getlist('symptoms[]')
            symptoms = ', '.join(symptoms_list) if symptoms_list else ''
            
            # Get other form data with correct field names
            age = request.form.get('animal_age', '')
            weight = request.form.get('animal_weight', '')
            duration = request.form.get('duration', '')
            severity = request.form.get('severity', '')
            additional_info = request.form.get('additional_symptoms', '')
            
            logger.info(f"Processed data - Animal: {animal_type}, Symptoms: {symptoms}, Age: {age}")
            
            # Validate input
            if not animal_type:
                return jsonify({'success': False, 'message': 'Animal type is required'}), 400
            
            if not symptoms and not additional_info:
                return jsonify({'success': False, 'message': 'Please select symptoms or provide additional information'}), 400
            
            # Check database availability
            db_available, _ = get_db_status()
            if not db_available:
                return jsonify({'success': False, 'message': 'Database connection error'}), 503
            
            # Mock disease prediction logic
            prediction_result = mock_disease_prediction(
                animal_type, symptoms, age, weight, duration, severity, additional_info
            )
            
            # Save prediction to database
            prediction_data = {
                'user_id': ObjectId(session['user_id']),
                'animal_type': animal_type,
                'symptoms': symptoms,
                'age': age,
                'weight': weight,
                'duration': duration,
                'severity': severity,
                'additional_info': additional_info,
                'prediction': prediction_result,
                'created_at': datetime.utcnow()
            }
            
            result = predictions_collection.insert_one(prediction_data)
            
            return jsonify({
                'success': True,
                'prediction': prediction_result,
                'prediction_id': str(result.inserted_id)
            })
        
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred during prediction'}), 500
    
    
    @app.route('/cat-detection', methods=['GET', 'POST'])
    def cat_detection():
        """Cat disease detection"""
        if request.method == 'GET':
            if 'user_id' not in session:
                return redirect(url_for('farmer_login_page'))
            return render_template('cat_detection.html')
        
        # POST request - handle image upload
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No image uploaded'}), 400
            
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No image selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
            # Process image and make prediction
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Load model and make prediction
            model = load_model('cat')
            results = model.predict(file_path)
            
            # Process YOLO results
            predictions = []
            if results and len(results) > 0:
                result = results[0]  # First result
                if result.boxes is not None and len(result.boxes) > 0:
                    # Process detected boxes
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        class_name = result.names[class_id] if hasattr(result, 'names') else f"Class_{class_id}"
                        
                        predictions.append({
                            'class': class_name,
                            'confidence': confidence,
                            'quality_warning': confidence < 0.7
                        })
                else:
                    # No detections found
                    predictions.append({
                        'class': 'Healthy',
                        'confidence': 0.8,
                        'quality_warning': False
                    })
            else:
                # No results
                predictions.append({
                    'class': 'Unable to analyze',
                    'confidence': 0.5,
                    'quality_warning': True
                })
            
            # Sort by confidence (highest first)
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return jsonify({
                'success': True,
                'predictions': predictions,
                'image_path': unique_filename
            })
        
        except Exception as e:
            logger.error(f"Cat detection error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/cow-detection', methods=['GET', 'POST'])
    def cow_detection():
        """Cow disease detection"""
        if request.method == 'GET':
            if 'user_id' not in session:
                return redirect(url_for('farmer_login_page'))
            return render_template('cow_detection.html')
        
        # POST request - handle image upload
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No image uploaded'}), 400
            
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No image selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
            # Process image and make prediction
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Load model and make prediction
            model = load_model('cow')
            results = model.predict(file_path)
            
            # Process YOLO results
            predictions = []
            if results and len(results) > 0:
                result = results[0]  # First result
                if result.boxes is not None and len(result.boxes) > 0:
                    # Process detected boxes
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        class_name = result.names[class_id] if hasattr(result, 'names') else f"Class_{class_id}"
                        
                        predictions.append({
                            'class': class_name,
                            'confidence': confidence,
                            'quality_warning': confidence < 0.7
                        })
                else:
                    # No detections found
                    predictions.append({
                        'class': 'Healthy',
                        'confidence': 0.8,
                        'quality_warning': False
                    })
            else:
                # No results
                predictions.append({
                    'class': 'Unable to analyze',
                    'confidence': 0.5,
                    'quality_warning': True
                })
            
            # Sort by confidence (highest first)
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return jsonify({
                'success': True,
                'predictions': predictions,
                'image_path': unique_filename
            })
        
        except Exception as e:
            logger.error(f"Cow detection error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/dog-detection', methods=['GET', 'POST'])
    def dog_detection():
        """Dog disease detection"""
        if request.method == 'GET':
            if 'user_id' not in session:
                return redirect(url_for('farmer_login_page'))
            return render_template('dog_detection.html')
        
        # POST request - handle image upload
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No image uploaded'}), 400
            
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No image selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
            # Process image and make prediction
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Load model and make prediction
            model = load_model('dog')
            results = model.predict(file_path)
            
            # Process YOLO results
            predictions = []
            if results and len(results) > 0:
                result = results[0]  # First result
                if result.boxes is not None and len(result.boxes) > 0:
                    # Process detected boxes
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        class_name = result.names[class_id] if hasattr(result, 'names') else f"Class_{class_id}"
                        
                        predictions.append({
                            'class': class_name,
                            'confidence': confidence,
                            'quality_warning': confidence < 0.7
                        })
                else:
                    # No detections found
                    predictions.append({
                        'class': 'Healthy',
                        'confidence': 0.8,
                        'quality_warning': False
                    })
            else:
                # No results
                predictions.append({
                    'class': 'Unable to analyze',
                    'confidence': 0.5,
                    'quality_warning': True
                })
            
            # Sort by confidence (highest first)
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return jsonify({
                'success': True,
                'predictions': predictions,
                'image_path': unique_filename
            })
        
        except Exception as e:
            logger.error(f"Dog detection error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/sheep-detection', methods=['GET', 'POST'])
    def sheep_detection():
        """Sheep disease detection"""
        if request.method == 'GET':
            if 'user_id' not in session:
                return redirect(url_for('farmer_login_page'))
            return render_template('sheep_detection.html')
        
        # POST request - handle image upload
        try:
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'User not logged in'}), 401
            
            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No image uploaded'}), 400
            
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No image selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400
            
            # Process image and make prediction
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Load model and make prediction
            model = load_model('sheep')
            results = model.predict(file_path)
            
            # Process YOLO results
            predictions = []
            if results and len(results) > 0:
                result = results[0]  # First result
                if result.boxes is not None and len(result.boxes) > 0:
                    # Process detected boxes
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        class_name = result.names[class_id] if hasattr(result, 'names') else f"Class_{class_id}"
                        
                        predictions.append({
                            'class': class_name,
                            'confidence': confidence,
                            'quality_warning': confidence < 0.7
                        })
                else:
                    # No detections found
                    predictions.append({
                        'class': 'Healthy',
                        'confidence': 0.8,
                        'quality_warning': False
                    })
            else:
                # No results
                predictions.append({
                    'class': 'Unable to analyze',
                    'confidence': 0.5,
                    'quality_warning': True
                })
            
            # Sort by confidence (highest first)
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return jsonify({
                'success': True,
                'predictions': predictions,
                'image_path': unique_filename
            })
        
        except Exception as e:
            logger.error(f"Sheep detection error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500


def mock_disease_prediction(animal_type, symptoms, age, weight, duration, severity, additional_info):
    """Mock disease prediction function"""
    
    # Create a more realistic prediction based on inputs
    diseases = {
        'cow': ['Mastitis', 'Foot and Mouth Disease', 'Bloat', 'Milk Fever'],
        'cat': ['Upper Respiratory Infection', 'Feline Leukemia', 'Urinary Tract Infection'],
        'dog': ['Parvovirus', 'Kennel Cough', 'Hip Dysplasia', 'Skin Allergies'],
        'sheep': ['Foot Rot', 'Internal Parasites', 'Pneumonia', 'Scrapie']
    }
    
    # Select disease based on animal type
    animal_diseases = diseases.get(animal_type, ['Unknown Disease'])
    selected_disease = animal_diseases[0]  # For simplicity, pick first one
    
    # Determine confidence based on symptom count
    symptom_count = len(symptoms.split(',')) if symptoms else 0
    base_confidence = 0.6 + (symptom_count * 0.1)
    confidence = min(base_confidence, 0.95)
    
    # Determine severity
    severity_level = severity if severity else 'Moderate'
    
    return {
        'disease': selected_disease,
        'confidence': confidence,
        'recommendations': f'Consult a veterinarian for {selected_disease.lower()} treatment',
        'severity': severity_level,
        'symptoms_analyzed': symptoms,
        'duration': duration,
        'additional_notes': additional_info
    }
