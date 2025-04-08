import os
import firebase_admin
import base64
import json
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from PIL import Image
from io import BytesIO
from datetime import datetime
import logging
from werkzeug.utils import secure_filename
import uuid
from google.cloud import storage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    try:
        if app.config['DEMO_MODE']:
            # Get list of uploaded images from local storage
            images = []
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if filename.endswith(tuple(ALLOWED_EXTENSIONS)):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    stat = os.stat(file_path)
                    images.append({
                        'id': filename.split('.')[0],
                        'filename': filename,
                        'upload_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # Sort images by upload date (newest first)
            images.sort(key=lambda x: x['upload_date'], reverse=True)
            return render_template('index.html', images=images)
        else:
            # Get images from Firebase
            images_ref = db.collection('images')
            images = []
            for doc in images_ref.stream():
                image_data = doc.to_dict()
                images.append({
                    'id': doc.id,
                    'filename': image_data.get('filename', ''),
                    'upload_date': image_data.get('upload_date', '')
                })
            return render_template('index.html', images=images)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        flash('Error loading images')
        return render_template('index.html', images=[])

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'image' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            unique_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            extension = filename.rsplit('.', 1)[1].lower()
            new_filename = f"{unique_id}.{extension}"
            
            if app.config['DEMO_MODE']:
                # Save file locally
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            else:
                # Save file to Firebase Storage
                bucket = storage.bucket()
                blob = bucket.blob(f"images/{new_filename}")
                blob.upload_from_string(
                    file.read(),
                    content_type=file.content_type
                )
                
                # Save metadata to Firestore
                db.collection('images').add({
                    'filename': new_filename,
                    'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            flash('Image uploaded successfully')
            return redirect(url_for('index'))
        
        flash('Invalid file type')
        return redirect(request.url)
    except Exception as e:
        logger.error(f"Error in upload route: {e}")
        flash('Error uploading image')
        return redirect(request.url)

@app.route('/delete/<image_id>', methods=['POST'])
def delete_image(image_id):
    try:
        if app.config['DEMO_MODE']:
            # Delete from local storage
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if filename.startswith(image_id):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.remove(file_path)
                    flash('Image deleted successfully')
                    return redirect(url_for('index'))
        else:
            # Delete from Firebase
            db.collection('images').document(image_id).delete()
            flash('Image deleted successfully')
            return redirect(url_for('index'))
        
        flash('Image not found')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in delete route: {e}")
        flash('Error deleting image')
        return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        if app.config['DEMO_MODE']:
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        else:
            bucket = storage.bucket()
            blob = bucket.blob(f"images/{filename}")
            return redirect(blob.public_url)
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        return "File not found", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
