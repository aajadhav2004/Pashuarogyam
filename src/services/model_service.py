"""
Model Service for PashuAarogyam application
Handles YOLO model loading and management
"""
from ultralytics import YOLO
from huggingface_hub import hf_hub_download
from config import HF_REPO_ID, HF_MODEL_CACHE_DIR
import os
import logging

logger = logging.getLogger(__name__)

# Initialize YOLO models dictionary (lazy loading)
models = {
    'cat': None,
    'cow': None,
    'dog': None,
    'sheep': None
}

MODEL_FILES = {
    'cat': 'cat_disease_best.pt',
    'cow': 'lumpy_disease_best.pt',
    'dog': 'dog_disease_best.pt',
    'sheep': 'sheep_disease_model.pt'
}


def load_model(animal_type):
    """
    Lazy load YOLO model from Hugging Face on first use.
    This prevents timeout during deployment by deferring model download.
    Automatically unloads other models to save RAM (important for Render's 512MB limit).
    """
    global models
    
    if animal_type not in models:
        raise ValueError(f"Unknown animal type: {animal_type}")
    
    # Return cached model if already loaded
    if models[animal_type] is not None:
        logger.info(f"Using cached {animal_type} model")
        return models[animal_type]
    
    # MEMORY OPTIMIZATION: Clear other models before loading new one
    # This ensures only 1 model is in memory at a time (critical for Render's RAM limit)
    for key in models:
        if key != animal_type and models[key] is not None:
            logger.info(f"Clearing {key} model from memory to free RAM")
            models[key] = None
    
    # Force garbage collection to free memory immediately
    import gc
    gc.collect()
    logger.info(f"Memory cleared, now loading {animal_type} model")
    
    try:
        # Get the model filename
        model_filename = MODEL_FILES.get(animal_type)
        
        if not model_filename:
            raise ValueError(f"Unknown animal type: {animal_type}")
        
        try:
            print(f"Downloading {model_filename} from Hugging Face...")
            model_path = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=f"models/{model_filename}",
                cache_dir=HF_MODEL_CACHE_DIR
            )
            print(f"Downloaded to: {model_path}")
        except Exception as hf_error:
            print(f"Hugging Face download failed: {hf_error}")
            # Fallback to local path
            model_path = f'models/{model_filename}'
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model not found locally: {model_path}")
        else:
            # Use local path if Hugging Face Hub is not available
            model_path = f'models/{model_filename}'
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model not found and Hugging Face Hub not available: {model_path}")
        
        # Load the YOLO model
        models[animal_type] = YOLO(model_path)
        
        print(f"✓ {animal_type.capitalize()} disease model loaded successfully!")
        
        return models[animal_type]
    
    except Exception as e:
        logger.error(f"Error loading {animal_type} model: {str(e)}")
        raise


def get_model(animal_type):
    """Get a loaded model or load it if not already loaded"""
    return load_model(animal_type)


def clear_models():
    """Clear all loaded models from memory"""
    global models
    for animal_type in models:
        if models[animal_type] is not None:
            logger.info(f"Clearing {animal_type} model from memory")
            models[animal_type] = None
    
    # Force garbage collection
    import gc
    gc.collect()
    logger.info("All models cleared from memory and garbage collected")


def unload_model_after_prediction(animal_type):
    """
    Unload a specific model after prediction to free memory.
    Use this after prediction is complete to minimize RAM usage.
    """
    global models
    if animal_type in models and models[animal_type] is not None:
        logger.info(f"Unloading {animal_type} model after prediction")
        models[animal_type] = None
        
        # Force garbage collection
        import gc
        gc.collect()
        logger.info(f"{animal_type} model unloaded and memory freed")
