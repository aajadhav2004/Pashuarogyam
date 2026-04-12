"""
Helper functions for PashuAarogyam application
Includes validation, password hashing, and utility functions
"""
import re
import bcrypt
import logging
import os
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


def cleanup_previous_upload(session, upload_folder, animal_type):
    """
    Delete previous uploaded image for this animal type from this user's session.
    This saves disk space by removing old images when user uploads a new one.
    
    Args:
        session: Flask session object
        upload_folder: Path to upload folder
        animal_type: Type of animal (cat, dog, cow, sheep)
    
    Returns:
        bool: True if cleanup was successful or no file to clean, False on error
    """
    try:
        # Create session key for this animal type
        session_key = f'last_upload_{animal_type}'
        
        # Check if there's a previous upload for this animal type
        if session_key in session:
            previous_file = session[session_key]
            file_path = os.path.join(upload_folder, previous_file)
            
            # Delete the file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted previous upload: {previous_file}")
            
            # Remove from session
            session.pop(session_key, None)
        
        return True
    
    except Exception as e:
        logger.error(f"Error cleaning up previous upload: {str(e)}")
        return False


def save_upload_to_session(session, animal_type, filename):
    """
    Save the uploaded filename to session for later cleanup.
    
    Args:
        session: Flask session object
        animal_type: Type of animal (cat, dog, cow, sheep)
        filename: Name of the uploaded file
    """
    session_key = f'last_upload_{animal_type}'
    session[session_key] = filename
    logger.info(f"Saved upload to session: {filename} for {animal_type}")
