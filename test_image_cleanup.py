"""
Quick test script to verify image cleanup functionality
Run this to test if old images are being deleted properly
"""
import os
from flask import Flask, session
from src.utils.helpers import cleanup_previous_upload, save_upload_to_session

# Create test Flask app
app = Flask(__name__)
app.secret_key = 'test-secret-key'

def test_image_cleanup():
    """Test the image cleanup functionality"""
    
    print("=" * 60)
    print("Testing Image Cleanup Functionality")
    print("=" * 60)
    
    upload_folder = 'static/uploads'
    
    # Ensure upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    with app.test_request_context():
        # Simulate user session
        session['user_id'] = 'test_user_123'
        
        print("\n1. Creating test image files...")
        test_files = {
            'cat': 'test_cat_image_1.jpg',
            'dog': 'test_dog_image_1.jpg',
            'cow': 'test_cow_image_1.jpg',
            'sheep': 'test_sheep_image_1.jpg'
        }
        
        # Create dummy files
        for animal, filename in test_files.items():
            filepath = os.path.join(upload_folder, filename)
            with open(filepath, 'w') as f:
                f.write(f"Test {animal} image content")
            print(f"   ✓ Created: {filename}")
            
            # Save to session
            save_upload_to_session(session, animal, filename)
            print(f"   ✓ Saved to session: {animal} -> {filename}")
        
        print("\n2. Simulating new uploads (should delete old ones)...")
        
        # Simulate uploading new cat image
        print("\n   Testing CAT image replacement:")
        new_cat_file = 'test_cat_image_2.jpg'
        new_cat_path = os.path.join(upload_folder, new_cat_file)
        
        # Create new file
        with open(new_cat_path, 'w') as f:
            f.write("New cat image content")
        print(f"   ✓ Created new file: {new_cat_file}")
        
        # Cleanup should delete old cat image
        cleanup_previous_upload(session, upload_folder, 'cat')
        
        # Check if old file was deleted
        old_cat_path = os.path.join(upload_folder, test_files['cat'])
        if not os.path.exists(old_cat_path):
            print(f"   ✅ SUCCESS: Old cat image deleted!")
        else:
            print(f"   ❌ FAILED: Old cat image still exists!")
        
        # Save new cat file to session
        save_upload_to_session(session, 'cat', new_cat_file)
        print(f"   ✓ Saved new cat image to session")
        
        # Verify other animal images still exist
        print("\n3. Verifying other animal images are NOT deleted:")
        for animal in ['dog', 'cow', 'sheep']:
            filepath = os.path.join(upload_folder, test_files[animal])
            if os.path.exists(filepath):
                print(f"   ✅ {animal.upper()}: Still exists (correct!)")
            else:
                print(f"   ❌ {animal.upper()}: Was deleted (wrong!)")
        
        print("\n4. Cleanup test files...")
        # Clean up all test files
        for filename in [new_cat_file] + list(test_files.values()):
            filepath = os.path.join(upload_folder, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"   ✓ Removed: {filename}")
        
        print("\n" + "=" * 60)
        print("Test Complete!")
        print("=" * 60)
        print("\nExpected behavior:")
        print("✓ Old cat image should be deleted when new one is uploaded")
        print("✓ Other animal images should remain untouched")
        print("✓ Each animal type tracks its own last upload")
        print("=" * 60)

if __name__ == '__main__':
    test_image_cleanup()
