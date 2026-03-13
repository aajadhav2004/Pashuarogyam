"""
Chatbot Utilities
Helper functions for chatbot service including translation and fallback responses
"""
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = [
    {'code': 'en', 'name': 'English'},
    {'code': 'hi', 'name': 'Hindi'},
    {'code': 'mr', 'name': 'Marathi'},
    {'code': 'gu', 'name': 'Gujarati'},
    {'code': 'ta', 'name': 'Tamil'},
    {'code': 'te', 'name': 'Telugu'},
    {'code': 'kn', 'name': 'Kannada'},
    {'code': 'ml', 'name': 'Malayalam'},
    {'code': 'pa', 'name': 'Punjabi'},
    {'code': 'bn', 'name': 'Bengali'},
    {'code': 'or', 'name': 'Odia'},
    {'code': 'as', 'name': 'Assamese'},
]


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text between languages - optimized for speed
    
    Args:
        text: Text to translate
        source_lang: Source language code
        target_lang: Target language code
    
    Returns:
        Translated text or original if translation fails
    """
    try:
        # Quick checks to avoid unnecessary translation
        if source_lang == target_lang:
            return text
        
        if not text or not text.strip() or len(text.strip()) < 3:
            return text
        
        # Try to import translator
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            logger.warning("deep_translator not available, returning original text")
            return text
        
        # For Indian languages, allow longer text translation
        max_length = 2000 if target_lang in ['mr', 'hi', 'ta', 'te', 'gu', 'kn', 'ml', 'pa', 'bn'] else 1000
        
        # Skip translation for very long texts to save time
        if len(text) > max_length:
            logger.info(f"Skipping translation for long text ({len(text)} chars > {max_length})")
            return text
        
        # Translate with timeout
        import threading
        result = {'translated': None, 'error': None}
        
        def translate_with_timeout():
            try:
                # Use 'source' and 'target' parameters (not source_language/target_language)
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                result['translated'] = translator.translate(text)
            except Exception as e:
                result['error'] = str(e)
        
        # Run translation with 5 second timeout
        translation_thread = threading.Thread(target=translate_with_timeout)
        translation_thread.daemon = True
        translation_thread.start()
        translation_thread.join(timeout=5)
        
        if translation_thread.is_alive():
            logger.warning("Translation timed out, using original text")
            return text
        
        if result['error']:
            logger.warning(f"Translation failed ({source_lang} → {target_lang}): {result['error']}")
            return text
        
        if result['translated']:
            logger.info(f"Translated from {source_lang} to {target_lang}")
            return result['translated']
        else:
            return text
    
    except Exception as e:
        logger.warning(f"Translation failed: {e}, returning original text")
        return text


def get_fallback_response(user_input: str = "") -> str:
    """
    Provide helpful fallback response when AI is unavailable
    
    Args:
        user_input: User's input message
    
    Returns:
        Fallback response text
    """
    user_lower = user_input.lower() if user_input else ""
    
    # Animal-specific responses
    if any(word in user_lower for word in ['cow', 'cattle', 'bull', 'calf', 'bovine']):
        if 'fever' in user_lower:
            return """🐄 **Cow Fever Management**
**Normal Temperature**: 101.5-103.5°F (38.6-39.7°C)
**Action Steps**:
• Provide shade and cool, fresh water
• Check for respiratory distress
• Monitor appetite and milk production
• Contact vet if fever >104°F or persists >24h
• Consider electrolyte solutions"""
        elif 'mastitis' in user_lower:
            return """🥛 **Mastitis in Cows**
**Signs**: Hot, swollen udder quarters, abnormal milk
**Immediate Care**:
• Frequent milking every 2-3 hours
• Apply warm compresses before milking
• Strip affected quarters completely
• **Veterinary consultation required for antibiotics**
• Monitor for systemic illness"""
    
    elif any(word in user_lower for word in ['dog', 'puppy', 'canine']):
        if 'fever' in user_lower:
            return """🐕 **Dog Fever Care**
**Normal Temperature**: 101-102.5°F (38.3-39.2°C)
**Action Steps**:
• Ensure adequate water intake
• Cool environment, avoid overheating
• Monitor for lethargy, loss of appetite
• **Emergency if fever >104°F**
• Consider wet towels on paws and belly"""
    
    elif any(word in user_lower for word in ['cat', 'kitten', 'feline']):
        if 'fever' in user_lower:
            return """🐱 **Cat Fever Management**
**Normal Temperature**: 100.5-102.5°F (38.1-39.2°C)
**Action Steps**:
• Quiet, cool environment
• Encourage water intake
• Monitor breathing and appetite
• **Emergency if fever >104°F or lethargic**
• Wet food may help hydration"""
    
    # General responses by symptom
    if 'emergency' in user_lower or 'urgent' in user_lower:
        return """🚨 **EMERGENCY SIGNS - Contact Veterinarian IMMEDIATELY**
• **Breathing difficulties** - Open mouth breathing, gasping
• **Severe bleeding** - Continuous, won't stop with pressure
• **Cannot stand or walk** - Paralysis, extreme weakness
• **High fever** - >104°F (40°C) for most animals
• **Seizures or convulsions**
• **Severe pain** - Crying, restlessness, rigid posture
• **Bloated abdomen** - Especially in ruminants
• **Eye injuries** - Any trauma to eyes"""
    
    elif 'fever' in user_lower:
        return """🌡️ **General Fever Management**
**Recognition**: Lethargy, warm nose/ears, shivering
**Immediate Care**:
• Cool, quiet environment with good ventilation
• Fresh water access - encourage drinking
• Light, easily digestible food
• Monitor temperature if possible
• **Call vet if fever >104°F or lasts >24h**"""
    
    # Default response
    return """🩺 **PashuAarogyam - Animal Health Guidance**

I'm currently unable to provide AI-powered responses. Here's some general guidance:

**Emergency Signs - Contact Veterinarian Immediately:**
• Difficulty breathing, severe bleeding, unable to stand
• High fever (>104°F/40°C), seizures, severe pain

**General Care Tips:**
• Monitor appetite, behavior, and vital signs daily
• Ensure clean water and appropriate nutrition
• Maintain clean, dry living conditions
• Isolate sick animals to prevent spread

**Common Treatments:**
• **Fever**: Cool water, shade, electrolytes
• **Minor cuts**: Clean, disinfect, monitor healing
• **Digestive issues**: Withhold food briefly, provide water

Always consult a qualified veterinarian for proper diagnosis and treatment."""


def get_supported_languages() -> List[Dict[str, str]]:
    """
    Get list of supported languages
    
    Returns:
        List of language dictionaries with code and name
    """
    return SUPPORTED_LANGUAGES


def format_response(response: str, language: str = 'en') -> Dict:
    """
    Format response for API output
    
    Args:
        response: Response text
        language: Language code
    
    Returns:
        Formatted response dictionary
    """
    return {
        'success': True,
        'response': response,
        'language': language,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
    }


def format_error_response(error: str, error_code: str = 'ERROR') -> Dict:
    """
    Format error response for API output
    
    Args:
        error: Error message
        error_code: Error code
    
    Returns:
        Formatted error response dictionary
    """
    return {
        'success': False,
        'error': error,
        'error_code': error_code,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
    }
