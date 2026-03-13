"""
Chatbot Service - Main Entry Point
Imports and re-exports chatbot components for backward compatibility
"""

# Import all components from modularized services
from src.services.chatbot_rate_limiter import GeminiRateLimiter
from src.services.chatbot_core import AnimalDiseaseChatbot
from src.services.chatbot_utils import (
    translate_text,
    get_fallback_response,
    get_supported_languages,
    format_response,
    format_error_response,
    SUPPORTED_LANGUAGES
)

# Export for backward compatibility
__all__ = [
    'GeminiRateLimiter',
    'AnimalDiseaseChatbot',
    'translate_text',
    'get_fallback_response',
    'get_supported_languages',
    'format_response',
    'format_error_response',
    'SUPPORTED_LANGUAGES'
]
