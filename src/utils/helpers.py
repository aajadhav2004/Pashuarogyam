"""
Helper functions for PashuAarogyam application
Includes validation, password hashing, and utility functions
"""
import re
import bcrypt
import logging
from config import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)


def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"
    return True, "Password is valid"


def hash_password(password):
    """Hash password using bcrypt and return as string for MongoDB storage"""
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Convert bytes to string for MongoDB storage
    return hashed.decode('utf-8')


def check_password(password, hashed):
    """Check password against hash"""
    try:
        # Handle case where hashed might be bytes or string
        if isinstance(hashed, str):
            hashed = hashed.encode('utf-8')
        elif not isinstance(hashed, bytes):
            return False
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except Exception as e:
        logger.error(f"Password check error: {str(e)}")
        return False
