"""
Application Factory for PashuAarogyam
Follows Flask best practices for application creation and configuration
"""
from flask import Flask
import os
import logging
from config import (
    FLASK_SECRET_KEY, FLASK_HOST, FLASK_PORT, FLASK_DEBUG,
    UPLOAD_FOLDER, MAX_CONTENT_LENGTH
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config=None):
    """
    Application factory function
    Creates and configures Flask application
    
    Args:
        config (dict): Optional configuration dictionary
    
    Returns:
        Flask: Configured Flask application
    """
    
    # Get project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(project_root, 'templates')
    static_folder = os.path.join(project_root, 'static')
    
    # Create Flask app with absolute paths
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder)
    
    # Load configuration
    app.config['SECRET_KEY'] = FLASK_SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    
    # Session configuration - MongoDB for production & local consistency
    from config import MONGODB_URI
    from pymongo import MongoClient
    
    try:
        # Create MongoClient instance for Flask-Session
        mongo_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000
        )
        # Test connection
        mongo_client.admin.command('ping')
        logger.info("✓ MongoDB connection successful for sessions")
        
        app.config['SESSION_TYPE'] = 'mongodb'
        app.config['SESSION_MONGODB'] = mongo_client
        app.config['SESSION_MONGODB_DB'] = 'pashudb'
        app.config['SESSION_MONGODB_COLLECT'] = 'sessions'
        app.config['SESSION_PERMANENT'] = True
        app.config['SESSION_USE_SIGNER'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
        
    except Exception as e:
        logger.error(f"✗ MongoDB session connection failed: {e}")
        logger.warning("Falling back to filesystem sessions")
        # Fallback to filesystem sessions
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
        app.config['SESSION_PERMANENT'] = True
        app.config['SESSION_USE_SIGNER'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = 86400
    
    # Apply custom config if provided
    if config:
        app.config.update(config)
    
    # Create upload directory
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize Flask-Session
    from flask_session import Session
    Session(app)
    
    logger.info("Flask application created")
    
    return app


def register_services(app):
    """
    Register and initialize services
    
    Args:
        app (Flask): Flask application instance
    """
    from src.services.database import initialize_mongodb
    from src.services.chatbot_service import AnimalDiseaseChatbot
    
    logger.info("Initializing services...")
    
    # Initialize database
    db_connected = initialize_mongodb()
    if db_connected:
        logger.info("✓ Database connection established")
        app.db_connected = True
    else:
        logger.warning("✗ Database connection failed")
        app.db_connected = False
    
    # Initialize chatbot
    try:
        from config import GEMINI_API_KEY_CHATBOT
        if GEMINI_API_KEY_CHATBOT:
            chatbot = AnimalDiseaseChatbot(GEMINI_API_KEY_CHATBOT)
            app.chatbot = chatbot
            logger.info("✓ Chatbot service initialized")
        else:
            logger.warning("✗ Chatbot API key not configured")
            app.chatbot = None
    except Exception as e:
        logger.warning(f"✗ Chatbot initialization failed: {e}")
        app.chatbot = None


def register_routes(app):
    """
    Register all application routes
    
    Args:
        app (Flask): Flask application instance
    """
    from src.routes.auth_routes import register_auth_routes
    from src.routes.prediction_routes import register_prediction_routes
    from src.routes.admin_routes import register_admin_routes
    from src.routes.chatbot_routes import register_chatbot_routes
    
    logger.info("Registering routes...")
    
    # Register route blueprints
    register_auth_routes(app)
    logger.info("✓ Auth routes registered")
    
    register_prediction_routes(app, app.config)
    logger.info("✓ Prediction routes registered")
    
    register_admin_routes(app)
    logger.info("✓ Admin routes registered")
    
    register_chatbot_routes(app)
    logger.info("✓ Chatbot routes registered")
    
    # Register basic routes
    register_basic_routes(app)
    logger.info("✓ Basic routes registered")


def register_basic_routes(app):
    """
    Register basic application routes
    
    Args:
        app (Flask): Flask application instance
    """
    from flask import render_template, redirect, url_for, session, jsonify
    from src.services.database import get_db_status
    
    @app.route('/')
    def index():
        """Main landing page"""
        return render_template('index.html')
    
    @app.route('/dashboard')
    def dashboard():
        """Main dashboard - redirects based on role"""
        if 'user_id' not in session:
            return redirect(url_for('index'))
        
        role = session.get('role', 'farmer')
        
        if role == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif role == 'consultant':
            return redirect(url_for('consultant_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('index'))
    
    @app.route('/farmer/dashboard')
    def farmer_dashboard():
        """Farmer dashboard"""
        if 'user_id' not in session or session.get('role') != 'farmer':
            return redirect(url_for('farmer_login_page'))
        
        return render_template('farmer_dashboard.html', user={'name': session.get('name', 'Farmer')})
    
    @app.route('/consultant/dashboard')
    def consultant_dashboard():
        """Consultant dashboard"""
        if 'user_id' not in session or session.get('role') != 'consultant':
            return redirect(url_for('consultant_login_page'))
        
        return render_template('consultant_dashboard.html', user={'name': session.get('name', 'Consultant')})
    
    @app.route('/test-db')
    def test_db():
        """Test database connection"""
        db_available, message = get_db_status()
        return jsonify({
            'database_connected': db_available,
            'message': message
        })
    
    @app.route('/about')
    def about():
        """About page"""
        return render_template('about.html')
    
    @app.route('/contact')
    def contact():
        """Contact page"""
        return render_template('contact.html')
    
    @app.route('/chatbot')
    def chatbot():
        """Chatbot page"""
        if 'user_id' not in session:
            return redirect(url_for('farmer_login_page'))
        return render_template('chatbot.html')
    
    @app.route('/disease-detection')
    def disease_detection():
        """Disease detection animal selection page"""
        if 'user_id' not in session:
            return redirect(url_for('farmer_login_page'))
        return render_template('disease_detection.html')
    
    @app.route('/chatbot-page')
    def chatbot_page():
        """Chatbot page (alias for /chatbot)"""
        if 'user_id' not in session:
            return redirect(url_for('farmer_login_page'))
        return render_template('chatbot.html')
    
    @app.route('/consultation-form')
    def consultation_form():
        """Consultation request form"""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('consultation_form.html')
    
    @app.route('/ai-disease-prediction')
    def ai_disease_prediction():
        """Enhanced AI disease prediction page"""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('integrated_prediction.html')
    
    @app.route('/consultation-request')
    def consultation_request_page():
        """Consultation request page"""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('consultation_request.html')


def register_error_handlers(app):
    """
    Register error handlers
    
    Args:
        app (Flask): Flask application instance
    """
    from flask import render_template, jsonify
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        logger.error(f"Internal server error: {error}")
        return render_template('500.html'), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 errors"""
        return render_template('403.html'), 403


def register_context_processors(app):
    """
    Register context processors for templates
    
    Args:
        app (Flask): Flask application instance
    """
    
    @app.context_processor
    def inject_config():
        """Inject configuration into templates"""
        return {
            'app_name': 'PashuAarogyam',
            'app_version': '1.0.0'
        }


def create_app_with_services(config=None):
    """
    Create Flask app with all services and routes registered
    
    Args:
        config (dict): Optional configuration dictionary
    
    Returns:
        Flask: Fully configured Flask application
    """
    
    logger.info("=" * 80)
    logger.info("Starting PashuAarogyam Application (Modular Version)")
    logger.info("=" * 80)
    
    # Create app
    app = create_app(config)
    
    # Register services
    register_services(app)
    
    # Register routes
    register_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register context processors
    register_context_processors(app)
    
    logger.info("=" * 80)
    logger.info("Application initialization complete")
    logger.info("=" * 80)
    
    return app
