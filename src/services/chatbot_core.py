"""
Chatbot Core Service
Main chatbot logic for processing queries and managing conversations
"""
import os
import logging
import google.generativeai as genai
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from src.services.chatbot_rate_limiter import GeminiRateLimiter
from src.services.chatbot_utils import translate_text, get_fallback_response, format_response, format_error_response

logger = logging.getLogger(__name__)


class AnimalDiseaseChatbot:
    """Main chatbot class for animal disease consultation"""
    
    def __init__(self, api_key: str):
        """
        Initialize the chatbot with comprehensive error handling
        
        Args:
            api_key: Gemini API key
        """
        try:
            self.api_key = api_key or os.getenv('GEMINI_API_KEY')
            self.offline_mode = os.getenv('CHATBOT_OFFLINE_MODE', 'false').lower() == 'true'
            self.enable_fallback = os.getenv('CHATBOT_ENABLE_FALLBACK', 'true').lower() == 'true'
            
            self.model = None
            self.vision_model = None
            self.conversation_history = []
            self.session_histories = {}
            self.current_session = 'default'
            
            # Initialize rate limiter
            self.rate_limiter = GeminiRateLimiter()
            
            # Initialize Gemini AI
            if not self.offline_mode:
                self._initialize_genai()
            else:
                logger.info("Chatbot running in offline mode")
        
        except Exception as e:
            logger.error(f"Chatbot initialization error: {e}")
    
    def _initialize_genai(self) -> bool:
        """
        Initialize Google Generative AI
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not self.api_key or self.api_key.strip() == "":
                logger.error("API key is empty or not provided")
                return False
            
            # Configure the API key
            genai.configure(api_key=self.api_key)
            logger.info("Gemini AI configured with API key")
            
            # Try to initialize text model with newer model
            try:
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Text model initialized successfully with gemini-2.5-flash")
            except Exception as e:
                logger.error(f"Failed to initialize gemini-2.5-flash: {e}")
                try:
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    logger.info("Text model initialized with gemini-1.5-flash fallback")
                except Exception as e2:
                    logger.error(f"Failed to initialize fallback model: {e2}")
                    try:
                        self.model = genai.GenerativeModel('gemini-pro')
                        logger.info("Text model initialized with gemini-pro (legacy)")
                    except Exception as e3:
                        logger.error(f"All text model initialization failed: {e3}")
                        return False
            
            # Try to initialize vision model with newer model
            try:
                self.vision_model = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Vision model initialized successfully with gemini-2.5-flash")
            except Exception as e:
                logger.error(f"Failed to initialize vision model: {e}")
                self.vision_model = self.model
            
            return True
        
        except Exception as e:
            logger.error(f"Gemini AI initialization failed: {e}")
            return False
    
    def test_model_health(self, skip_api_test: bool = False) -> Tuple[bool, str]:
        """
        Test if the model is working properly with graceful quota handling
        
        Args:
            skip_api_test: Skip API test to preserve quota
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if self.offline_mode:
                return True, "Chatbot running in offline mode"
            
            if not self.model:
                return False, "Model not initialized"
            
            if skip_api_test:
                logger.info("Skipping API test to preserve quota")
                return True, "Model initialized (API test skipped)"
            
            # Test with a simple prompt
            test_prompt = "Say 'OK' if you can understand this."
            response = self.model.generate_content(test_prompt)
            
            if response and response.text:
                logger.info("Model health check passed")
                return True, "Model is healthy"
            else:
                return False, "Model returned empty response"
        
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "429" in error_str:
                logger.warning("Quota exceeded during health check")
                return False, "Model health check error: Quota exceeded"
            
            logger.error(f"Model health check error: {e}")
            return False, f"Model health check error: {str(e)}"
    
    def process_text_query(self, user_input: str, language: str = 'en', session_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Process text-based queries about animal diseases with session context
        
        Args:
            user_input: User's question
            language: Language code
            session_key: Session identifier
        
        Returns:
            Response dictionary
        """
        try:
            if not user_input or not user_input.strip():
                return format_error_response("Please provide a question")
            
            # Set session
            if session_key:
                self.current_session = session_key
                if session_key not in self.session_histories:
                    self.session_histories[session_key] = []
            
            # Check if offline or model not available
            if self.offline_mode or not self.model:
                if self.enable_fallback:
                    response = get_fallback_response(user_input)
                    return format_response(response, language)
                else:
                    return format_error_response("Chatbot is currently offline")
            
            # Check rate limiting
            if self.rate_limiter.wait_if_needed():
                if self.rate_limiter.is_quota_exceeded():
                    if self.enable_fallback:
                        response = get_fallback_response(user_input)
                        return format_response(response, language)
                    else:
                        return format_error_response("API quota exceeded")
            
            # Check cache
            cached_response = self.rate_limiter.get_cached_response(user_input, has_image=False)
            if cached_response:
                if language != 'en':
                    cached_response = translate_text(cached_response, 'en', language)
                return format_response(cached_response, language)
            
            # Build prompt with context
            system_prompt = """You are an expert veterinary consultant specializing in animal diseases. 
Provide accurate, helpful information about animal health and diseases.
Always recommend consulting a qualified veterinarian for serious conditions.
Be concise but thorough in your responses."""
            
            # Get response from model
            try:
                response = self.model.generate_content(f"{system_prompt}\n\nUser: {user_input}")
                
                if response and response.text:
                    response_text = response.text.strip()
                    
                    # Cache the response
                    self.rate_limiter.cache_response(user_input, response_text, has_image=False)
                    self.rate_limiter.reset_on_success()
                    
                    # Add to conversation history
                    self.conversation_history.append({'role': 'user', 'content': user_input})
                    self.conversation_history.append({'role': 'assistant', 'content': response_text})
                    
                    # Add to session history if using sessions
                    if session_key and session_key in self.session_histories:
                        self.session_histories[session_key].append({'role': 'user', 'content': user_input})
                        self.session_histories[session_key].append({'role': 'assistant', 'content': response_text})
                    
                    # Translate if needed
                    if language != 'en':
                        response_text = translate_text(response_text, 'en', language)
                    
                    return format_response(response_text, language)
                else:
                    return format_error_response("Model returned empty response")
            
            except Exception as api_error:
                error_str = str(api_error).lower()
                if "quota" in error_str or "429" in error_str:
                    self.rate_limiter.handle_rate_limit_error(str(api_error))
                    if self.enable_fallback:
                        response = get_fallback_response(user_input)
                        return format_response(response, language)
                    else:
                        return format_error_response("API quota exceeded")
                
                logger.error(f"API error: {api_error}")
                if self.enable_fallback:
                    response = get_fallback_response(user_input)
                    return format_response(response, language)
                else:
                    return format_error_response(f"API error: {str(api_error)}")
        
        except Exception as e:
            logger.error(f"Error processing text query: {e}")
            return format_error_response(f"Error: {str(e)}")
    
    def clear_conversation(self, session_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear conversation history for a specific session or current session
        
        Args:
            session_key: Session identifier
        
        Returns:
            Status dictionary
        """
        try:
            if session_key:
                if session_key in self.session_histories:
                    self.session_histories[session_key] = []
                    logger.info(f"Cleared conversation for session: {session_key}")
            else:
                self.conversation_history = []
                logger.info("Cleared main conversation history")
            
            return {'success': True, 'message': 'Conversation cleared'}
        
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_conversation_history(self, session_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get conversation history for a specific session or current session
        
        Args:
            session_key: Session identifier
        
        Returns:
            Conversation history dictionary
        """
        try:
            if session_key and session_key in self.session_histories:
                history = self.session_histories[session_key]
            else:
                history = self.conversation_history
            
            return {
                'success': True,
                'history': history,
                'session_key': session_key or 'default'
            }
        
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {'success': False, 'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the chatbot service
        
        Returns:
            Health status dictionary
        """
        return {
            'status': 'healthy' if self.model else 'degraded',
            'model_initialized': self.model is not None,
            'vision_model_initialized': self.vision_model is not None,
            'offline_mode': self.offline_mode,
            'fallback_enabled': self.enable_fallback,
            'quota_exceeded': self.rate_limiter.is_quota_exceeded(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get list of supported languages
        
        Returns:
            List of language dictionaries with code and name
        """
        return [
            {'code': 'en', 'name': 'English'},
            {'code': 'hi', 'name': 'Hindi'},
            {'code': 'mr', 'name': 'Marathi'},
            {'code': 'te', 'name': 'Telugu'},
            {'code': 'ta', 'name': 'Tamil'},
            {'code': 'bn', 'name': 'Bengali'},
            {'code': 'gu', 'name': 'Gujarati'},
            {'code': 'kn', 'name': 'Kannada'},
            {'code': 'ml', 'name': 'Malayalam'},
            {'code': 'pa', 'name': 'Punjabi'},
            {'code': 'es', 'name': 'Spanish'},
            {'code': 'fr', 'name': 'French'},
            {'code': 'de', 'name': 'German'}
        ]
