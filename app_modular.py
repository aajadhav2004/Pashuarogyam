"""
PashuAarogyam - Animal Disease Detection and Consultation System
Modular Flask Application Entry Point

This is the new modular version using application factory pattern.
Follows Flask best practices and industry standards.
"""

import os
import sys
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Import configuration
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG

# Import application factory
from src.app_factory import create_app_with_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create application with all services and routes
app = create_app_with_services()


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info(f"Running on http://{FLASK_HOST}:{FLASK_PORT}")
    logger.info("=" * 80)
    
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT, use_reloader=False)
