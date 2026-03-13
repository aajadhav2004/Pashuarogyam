"""
Database service for PashuAarogyam application
Handles MongoDB connection and initialization
"""
from pymongo import MongoClient
from config import MONGODB_URI
import logging

logger = logging.getLogger(__name__)

# Global database variables
client = None
db = None
users_collection = None
predictions_collection = None
consultants_collection = None
consultation_requests_collection = None
messages_collection = None


def initialize_mongodb():
    """Initialize MongoDB connection with the correct credentials"""
    global client, db, users_collection, predictions_collection, consultants_collection, consultation_requests_collection, messages_collection
    
    print("Initializing MongoDB connection...")
    
    try:
        # Create MongoDB client with proper configuration
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=30000,  
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
            maxPoolSize=50,
            retryWrites=True
        )
        
        # Test the connection by pinging the admin database
        client.admin.command('ping')
        print("MongoDB ping successful!")
        
        # Initialize database and collections
        # The database name is already in the MONGODB_URI (e.g., /pashudb)
        # MongoDB will use the database specified in the connection string
        db = client.get_default_database()
        users_collection = db['users']
        predictions_collection = db['predictions']
        consultants_collection = db['consultants']
        consultation_requests_collection = db['consultation_requests']
        messages_collection = db['messages']
        
        print(f"Collections initialized:")
        print(f"   - users_collection: {users_collection is not None}")
        print(f"   - consultants_collection: {consultants_collection is not None}")
        print(f"   - consultation_requests_collection: {consultation_requests_collection is not None}")
        print(f"   - messages_collection: {messages_collection is not None}")
        
        # Create indexes for better performance
        try:
            users_collection.create_index("email", unique=True)
            predictions_collection.create_index("user_id")
            predictions_collection.create_index("created_at")
            predictions_collection.create_index("animal_type")
            predictions_collection.create_index("prediction")
            consultants_collection.create_index("email", unique=True)
            consultation_requests_collection.create_index("status")
            consultation_requests_collection.create_index("created_at")
            messages_collection.create_index("consultation_id")
            messages_collection.create_index("created_at")
            print("Database indexes created successfully!")
        except Exception as idx_error:
            print(f"Index creation warning: {str(idx_error)}")
        
        # Test collections access
        user_count = users_collection.count_documents({})
        print(f"Users collection accessible. Current user count: {user_count}")
        
        print("MongoDB connected successfully!")
        return True
        
    except Exception as e:
        print(f"MongoDB connection failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print("Starting without database - authentication will not work")
        
        # Set globals to None on failure
        client = None
        db = None
        users_collection = None
        predictions_collection = None
        consultants_collection = None
        consultation_requests_collection = None
        messages_collection = None
        
        return False


def get_db_status():
    """Check if database is connected and available"""
    try:
        if client is None or db is None:
            return False, "Database not initialized"
        
        # Test connection
        client.admin.command('ping')
        return True, "Database connected"
    
    except Exception as e:
        return False, f"Database error: {str(e)}"


def get_collections():
    """Get all database collections"""
    return {
        'users': users_collection,
        'predictions': predictions_collection,
        'consultants': consultants_collection,
        'consultation_requests': consultation_requests_collection,
        'messages': messages_collection
    }
