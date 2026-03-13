"""
Chatbot Routes
Handles all chatbot-related API endpoints
"""
from flask import request, jsonify, session
from datetime import datetime, timezone
import time
import logging

logger = logging.getLogger(__name__)


def register_chatbot_routes(app):
    """
    Register chatbot routes
    
    Args:
        app (Flask): Flask application instance
    """
    
    @app.route('/api/chat', methods=['POST'])
    def chat_endpoint():
        """Handle text-based chat messages with session-based history"""
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({
                'success': False, 
                'error': 'Please log in to use the chatbot'
            }), 401
        
        # Check if chatbot is available
        if not hasattr(app, 'chatbot') or app.chatbot is None:
            return jsonify({
                'success': False, 
                'error': 'Chatbot service unavailable',
                'fallback_response': """I'm currently unable to connect to the AI service. Here are some things you can try:

🔧 **For Technical Issues:**
- Refresh the page and try again
- Check your internet connection
- Contact support if the problem persists

🐄 **For Animal Health Questions:**
- Document symptoms with photos if possible
- Note the animal's behavior changes
- Contact your local veterinarian for urgent cases

🩺 **Common Animal Diseases to Watch For:**
- Fever, loss of appetite, unusual discharge
- Lameness, difficulty breathing
- Skin lesions, swelling

**Emergency:** Call your veterinarian immediately for serious symptoms!
"""
            })
        
        try:
            start_time = time.time()
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'error': 'No data received'})
                
            message = data.get('message', '').strip()
            language = data.get('language', 'en')
            session_key = data.get('session_key', None)
            
            if not message:
                return jsonify({'success': False, 'error': 'Empty message'})
            
            # Generate session key if not provided
            if not session_key:
                session_key = f"chat_{session['user_id']}_{int(time.time())}"
            
            logger.info(f"Processing message: {message[:50]}{'...' if len(message) > 50 else ''}")
            logger.info(f"Session key: {session_key}")
            
            # Process the query with session context
            response = app.chatbot.process_text_query(message, language, session_key)
            
            processing_time = time.time() - start_time
            logger.info(f"Response generated in {processing_time:.2f} seconds")
            
            # Store conversation in database if available
            if app.db_connected:
                try:
                    from src.services.database import db
                    if db is not None:
                        conversation_doc = {
                            'user_id': session['user_id'],
                            'session_key': session_key,
                            'message': message,
                            'response': response.get('response', ''),
                            'language': language,
                            'timestamp': datetime.now(timezone.utc),
                            'type': 'text',
                            'processing_time': processing_time
                        }
                        db.conversations.insert_one(conversation_doc)
                except Exception as db_error:
                    logger.error(f"Database error storing conversation: {db_error}")
            
            # Add session key to response
            response['session_key'] = session_key
            
            return jsonify(response)
        
        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False, 
                'error': f'Server error: {str(e)}',
                'fallback_response': 'I encountered an error processing your request. Please try again or contact support if the problem persists.'
            })
    
    @app.route('/api/chat/health', methods=['GET'])
    def chatbot_health_check():
        """Check chatbot service health"""
        if not hasattr(app, 'chatbot') or app.chatbot is None:
            return jsonify({
                'available': False,
                'message': 'Chatbot service not initialized'
            })
        
        try:
            # Test model health without making actual API call to preserve quota
            is_healthy, message = app.chatbot.test_model_health(skip_api_test=True)
            return jsonify({
                'available': is_healthy,
                'message': message
            })
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify({
                'available': False,
                'message': f'Health check failed: {str(e)}'
            })
    
    @app.route('/api/chat/languages', methods=['GET'])
    def get_languages():
        """Get available languages for the chatbot"""
        try:
            # Check if chatbot is available
            if not hasattr(app, 'chatbot') or app.chatbot is None:
                # Return basic language list even if chatbot is not available
                basic_languages = {
                    'en': 'English',
                    'hi': 'Hindi',
                    'mr': 'Marathi',
                    'te': 'Telugu',
                    'ta': 'Tamil'
                }
                return jsonify({'success': True, 'languages': basic_languages})
            
            # Get languages from chatbot
            languages_list = app.chatbot.get_supported_languages()
            
            # Convert list format to dict format for frontend compatibility
            languages_dict = {lang['code']: lang['name'] for lang in languages_list}
            
            return jsonify({'success': True, 'languages': languages_dict})
            
        except Exception as e:
            logger.error(f"Error getting languages: {e}")
            # Return basic language list on error
            basic_languages = {
                'en': 'English',
                'hi': 'Hindi',
                'mr': 'Marathi'
            }
            return jsonify({'success': True, 'languages': basic_languages})
    
    @app.route('/api/chat/upload', methods=['POST'])
    def upload_for_analysis():
        """Handle file uploads for analysis"""
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({
                'success': False, 
                'error': 'Please log in to use this feature'
            }), 401
        
        # Check if chatbot is available
        if not hasattr(app, 'chatbot') or app.chatbot is None:
            return jsonify({
                'success': False, 
                'error': 'Chatbot service unavailable'
            })
        
        try:
            # Check if file is present
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'})
            
            # Get additional data
            message = request.form.get('message', '').strip()
            language = request.form.get('language', 'en')
            session_key = request.form.get('session_key', None)
            
            if not session_key:
                session_key = f"chat_{session['user_id']}_{int(time.time())}"
            
            # Check if chatbot has image processing capability
            if hasattr(app.chatbot, 'analyze_image'):
                response = app.chatbot.analyze_image(file, message, language)
            elif hasattr(app.chatbot, 'process_image_query'):
                response = app.chatbot.process_image_query(file, message, language, session_key)
            else:
                # Fallback: Image processing not available
                return jsonify({
                    'success': False,
                    'error': 'Image analysis feature is currently unavailable',
                    'fallback_response': 'Please describe the symptoms or condition in text instead.'
                })
            
            # Add session key to response
            response['session_key'] = session_key
            
            return jsonify(response)
        
        except Exception as e:
            logger.error(f"Error in upload endpoint: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False, 
                'error': f'Server error: {str(e)}'
            })
    
    logger.info("✓ Chatbot routes registered")
