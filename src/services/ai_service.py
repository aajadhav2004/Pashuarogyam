"""
AI Service for PashuAarogyam application
Handles Gemini API calls and disease prediction
"""
import google.generativeai as genai
from config import GEMINI_API_KEY_DISEASE, GEMINI_API_KEY_CHATBOT
import time
import logging

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """Rate limiter for Gemini API calls"""
    def __init__(self, min_interval=2.0, max_retries=3, base_backoff=5.0, max_backoff=300.0):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.last_call_time = 0
        self.quota_exceeded_until = 0
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()
        
        # Check if quota is exceeded
        if current_time < self.quota_exceeded_until:
            wait_time = self.quota_exceeded_until - current_time
            logger.warning(f"Quota exceeded. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            self.quota_exceeded_until = 0
        
        # Check minimum interval between calls
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.min_interval:
            wait_time = self.min_interval - time_since_last_call
            time.sleep(wait_time)
        
        self.last_call_time = time.time()
    
    def handle_quota_exceeded(self):
        """Handle quota exceeded error"""
        self.quota_exceeded_until = time.time() + self.base_backoff


gemini_rate_limiter = GeminiRateLimiter()


def call_gemini_with_retry(model_name, prompt, image_parts=None, max_retries=2, api_key=None):
    """
    Call Gemini API with proper error handling, rate limiting, and quota management
    """
    if api_key is None:
        api_key = GEMINI_API_KEY_DISEASE
    
    if not api_key:
        return None, "API key not configured"
    
    # Define fallback models in order of preference
    models_to_try = [model_name, 'gemini-2.5-flash', 'gemini-flash-latest', 'gemini-pro-latest']
    models_to_try = list(dict.fromkeys(models_to_try))
    
    for attempt in range(max_retries):
        try:
            gemini_rate_limiter.wait_if_needed()
            
            for current_model in models_to_try:
                try:
                    # Configure with the specific API key for this request
                    genai.configure(api_key=api_key)
                    
                    # Create model and make request
                    model = genai.GenerativeModel(current_model)
                    
                    if image_parts:
                        response = model.generate_content(image_parts + [prompt])
                    else:
                        response = model.generate_content(prompt)
                    
                    return response.text, None
                
                except Exception as model_error:
                    logger.warning(f"Model {current_model} failed: {str(model_error)}")
                    continue
            
            return None, "All models failed"
        
        except Exception as e:
            error_str = str(e)
            
            if "429" in error_str or "quota" in error_str.lower():
                gemini_rate_limiter.handle_quota_exceeded()
                logger.warning(f"Quota exceeded. Attempt {attempt + 1}/{max_retries}")
                
                if attempt < max_retries - 1:
                    wait_time = min(gemini_rate_limiter.base_backoff * (2 ** attempt), gemini_rate_limiter.max_backoff)
                    time.sleep(wait_time)
                    continue
            
            return None, f"API Error: {error_str}"
    
    return None, "Max retries exceeded"


def get_treatment_suggestions(animal_type, disease):
    """Get treatment suggestions for a specific animal and disease"""
    # This would be populated with actual treatment data
    # For now, returning a placeholder
    try:
        # Treatment database would be here
        return {
            'disease': disease,
            'animal_type': animal_type,
            'suggestions': 'Consult a veterinarian for proper treatment'
        }
    except Exception as e:
        logger.error(f"Error getting treatment suggestions: {str(e)}")
        return None
