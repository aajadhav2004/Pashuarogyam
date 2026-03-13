"""
Configuration module for PashuAarogyam application
Loads all environment variables and sets up application configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =================== API KEYS ===================
GEMINI_API_KEY_DISEASE = os.getenv('GEMINI_API_KEY_DISEASE')
GEMINI_API_KEY_CHATBOT = os.getenv('GEMINI_API_KEY_CHATBOT')

# =================== DATABASE CONFIGURATION ===================
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://localhost:27017/gorakshaai')

# =================== FLASK CONFIGURATION ===================
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-in-production')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))

# =================== UPLOAD CONFIGURATION ===================
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
MAX_CONTENT_LENGTH_MB = int(os.getenv('MAX_CONTENT_LENGTH_MB', 16))
MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# =================== HUGGINGFACE CONFIGURATION ===================
HF_REPO_ID = os.getenv('HF_REPO_ID', 'gangurde/cattle_disease_model')
HF_MODEL_CACHE_DIR = os.getenv('HF_MODEL_CACHE_DIR', 'models_cache')

# =================== CHATBOT CONFIGURATION ===================
CHATBOT_OFFLINE_MODE = os.getenv('CHATBOT_OFFLINE_MODE', 'false').lower() == 'true'
CHATBOT_ENABLE_FALLBACK = os.getenv('CHATBOT_ENABLE_FALLBACK', 'true').lower() == 'true'
RUN_GEMINI_HEALTH_CHECK = os.getenv('RUN_GEMINI_HEALTH_CHECK', 'false').lower() == 'true'

# =================== RATE LIMITING ===================
GEMINI_MIN_INTERVAL = float(os.getenv('GEMINI_MIN_INTERVAL', 2.0))
GEMINI_MAX_RETRIES = int(os.getenv('GEMINI_MAX_RETRIES', 3))
GEMINI_BASE_BACKOFF = float(os.getenv('GEMINI_BASE_BACKOFF', 5.0))
GEMINI_MAX_BACKOFF = float(os.getenv('GEMINI_MAX_BACKOFF', 300.0))

# =================== CACHING ===================
GEMINI_ENABLE_CACHE = os.getenv('GEMINI_ENABLE_CACHE', 'true').lower() == 'true'
GEMINI_CACHE_TTL = int(os.getenv('GEMINI_CACHE_TTL', 3600))
GEMINI_MAX_CACHE_SIZE = int(os.getenv('GEMINI_MAX_CACHE_SIZE', 100))

# =================== VOICE & SPEECH SETTINGS ===================
DEFAULT_VOICE_LANGUAGE = os.getenv('DEFAULT_VOICE_LANGUAGE', 'en-US')
DEFAULT_TEXT_LANGUAGE = os.getenv('DEFAULT_TEXT_LANGUAGE', 'en')

# =================== SECURITY SETTINGS ===================
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 1440))  # 24 hours in minutes
