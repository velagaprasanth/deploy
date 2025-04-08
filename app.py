import os
import firebase_admin
import base64
import json
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, jsonify
from PIL import Image
from io import BytesIO
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Constants
IMAGES_PER_PAGE = 9  # Number of images to load per page
MAX_IMAGE_SIZE = (800, 800)  # Maximum image dimensions
JPEG_QUALITY = 85  # JPEG quality for compression

# Initialize Firebase
app.config['DEMO_MODE'] = False
db = None

def initialize_firebase():
    global db
    try:
        if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            # Production: Use environment variable
            cred_dict = json.loads(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info("Firebase initialized successfully from environment variable")
            return True
        else:
            # Development: Use local file
            service_account_path = "your-service-account.json"
            if os.path.exists(service_account_path):
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                db = firestore.client()
                logger.info("Firebase initialized successfully from local file")
                return True
            else:
                logger.warning("Service account file not found. Running in demo mode.")
                app.config['DEMO_MODE'] = True
                return False
    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
        app.config['DEMO_MODE'] = True
        return False

# Initialize Firebase on startup
initialize_firebase()

def optimize_image(image):
    """Optimize image size and quality."""
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    if image.size[0] > MAX_IMAGE_SIZE[0] or image.size[1] > MAX_IMAGE_SIZE[1]:
        image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
    return image

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    
    # Check if we're in demo mode
    if app.config.get('DEMO_MODE', False):
        return render_template('index.html', images=[], demo_mode=True)
    
    # Fetch images from Firestore with pagination
    images = []
    try:
        # Get total count of images
        total_docs = db.collection('cleaning_photos').get()
        total_images = len(list(total_docs))
        total_pages = (total_images + IMAGES_PER_PAGE - 1) // IMAGES_PER_PAGE

        # Get paginated images
        query = db.collection('cleaning_photos').order_by('timestamp', direction=firestore.Query.DESCENDING)
        docs = query.limit(IMAGES_PER_PAGE).offset((page - 1) * IMAGES_PER_PAGE).stream()
        
        for doc in docs:
            image_data = doc.to_dict()
            images.append({
                'id': doc.id,
                'image': image_data['image'],
                'filename': image_data.get('filename', ''),
                'location': image_data.get('location', ''),
                'timestamp': image_data.get('timestamp', ''),
                'date': image_data.get('date', '')
            })
    except Exception as e:
        logger.error(f"Error fetching images: {e}")
        return render_template('index.html', images=[], error=str(e))
    
    return render_template('index.html', 
                         images=images, 
                         current_page=page,
                         total_pages=total_pages)

@app.route('/upload', methods=['POST'])
def upload():
    if app.config.get('DEMO_MODE', False):
        return jsonify({"message": "Demo mode: Image would be uploaded in production mode", "status": "demo"}), 200
    
    if 'photo' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    photo = request.files['photo']
    location = request.form.get('location', 'Unknown Location')
    
    if photo.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Get current timestamp
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        date = now.strftime("%B %d, %Y")

        # Optimize image
        image = Image.open(photo)
        optimized_image = optimize_image(image)
        
        # Convert to base64
        buffered = BytesIO()
        optimized_image.save(buffered, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # Store in Firestore
        doc_ref = db.collection('cleaning_photos').add({
            "image": img_str,
            "filename": photo.filename,
            "location": location,
            "timestamp": timestamp,
            "date": date
        })

        return jsonify({"message": "Image uploaded successfully!", "timestamp": timestamp}), 200
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/delete/<image_id>', methods=['DELETE'])
def delete_image(image_id):
    if app.config.get('DEMO_MODE', False):
        return jsonify({"message": "Demo mode: Image would be deleted in production mode"}), 200
    
    try:
        db.collection('cleaning_photos').document(image_id).delete()
        return '', 204  # No content response for successful deletion
    except Exception as e:
        logger.error(f"Error deleting image: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
