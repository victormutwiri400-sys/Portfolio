"""
Portfolio Backend - Flask Application
Handles profile, CV entries, certificates, and gallery photos
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
import re
import base64
import uuid
from datetime import datetime
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'mysql-victordesigner.alwaysdata.net'),
    'user': os.getenv('DB_USER', 'victordesigner'),
    'password': os.getenv('DB_PASSWORD', '#####'),
    'database': os.getenv('DB_NAME', 'victordesigner_portifolio')
}


# Database Connection Helper
def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


# Helper Functions
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Save uploaded file and return filename"""
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return filename
    return None


def save_base64_image(data):
    """Decode base64-encoded image data (optionally a data URI) and save it locally.
    Returns the stored filename, or None if the data is not a valid image.
    """
    if not data or not isinstance(data, str):
        return None

    data = data.strip()
    ext = None

    # Handle data URI format: data:image/png;base64,.... (common from mobile apps)
    if data.startswith('data:image'):
        mime_match = re.match(r'^data:image/([a-zA-Z0-9.+-]+);base64,', data)
        if not mime_match:
            return None
        ext = mime_match.group(1).lower()
        if ext == 'jpeg':
            ext = 'jpg'
        data = data.split(',', 1)[1]

    # Remove whitespace/newlines some clients insert in base64 payloads
    data = re.sub(r'\s+', '', data)

    try:
        image_bytes = base64.b64decode(data, validate=True)
    except Exception:
        return None

    if not image_bytes:
        return None

    # Detect the actual image format from magic bytes
    detected_ext = None
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        detected_ext = 'png'
    elif image_bytes[:3] == b'\xff\xd8\xff':
        detected_ext = 'jpg'
    elif image_bytes[:6] in (b'GIF87a', b'GIF89a'):
        detected_ext = 'gif'
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        detected_ext = 'webp'

    if detected_ext:
        ext = detected_ext
    if not ext or ext not in ALLOWED_EXTENSIONS:
        return None  # not a recognizable / supported image

    filename = secure_filename(f"{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}.{ext}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(file_path, 'wb') as f:
        f.write(image_bytes)
    return filename


def handle_image_upload(field_names):
    """Extract and save an image from the current request.
    Priority: multipart file -> base64 in form fields -> base64 in JSON body.
    Returns a tuple (saved_filename, error_message). error_message is None on success.
    """
    print(f"[upload] received files={list(request.files.keys())} fields={list(request.form.keys())}")

    # All accepted field names (both as file parts and as base64 text fields)
    all_keys = ('image', 'image_base64', 'image_url', 'imageUrl', 'photo', 'file', 'certificate')
    file_keys = tuple(field_names) + all_keys

    # 1) Multipart file upload from the device (preferred - same as profile API)
    for name in file_keys:
        file = request.files.get(name)
        if file and file.filename:
            filename = save_uploaded_file(file)
            if not filename:
                return None, 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'
            return filename, None

    # 2) Base64-encoded image data in form fields
    for key in all_keys:
        value = request.form.get(key, '').strip()
        if value:
            if value.startswith(('http://', 'https://')):
                return None, 'Image URLs are not accepted. Upload the photo from your device.'
            filename = save_base64_image(value)
            if not filename:
                return None, f'Invalid image data provided in the "{key}" field. Use a file upload or valid base64 image.'
            return filename, None

    # 3) Base64-encoded image data in a JSON body
    if request.is_json:
        data = request.get_json(silent=True) or {}
        for key in all_keys:
            value = (data.get(key) or '').strip()
            if value:
                if value.startswith(('http://', 'https://')):
                    return None, 'Image URLs are not accepted. Upload the photo from your device.'
                filename = save_base64_image(value)
                if not filename:
                    return None, f'Invalid image data provided in the "{key}" field. Use a file upload or valid base64 image.'
                return filename, None

    return None, None


def response(status, message, data=None, status_code=200):
    """Create standardized JSON response"""
    resp = {
        'status': status,
        'message': message
    }
    if data is not None:
        resp['data'] = data
    return jsonify(resp), status_code


# ============================================================================
# PROFILE ROUTES
# ============================================================================

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get profile information"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM profile LIMIT 1")
        profile = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if profile:
            # Convert image path to URL
            if profile.get('profile_image'):
                profile['profile_image'] = f"/uploads/{profile['profile_image']}"
            return response('success', 'Profile retrieved', profile)
        else:
            return response('error', 'Profile not found', None, 404)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/profile', methods=['POST', 'PUT'])
def create_or_update_profile():
    """Create or update profile"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        name = request.form.get('name', '').strip()
        title = request.form.get('title', '').strip()
        bio = request.form.get('bio', '').strip()
        
        if not name or not title:
            return response('error', 'Name and title are required', None, 400)
        
        # Handle file upload
        profile_image = None
        if 'profile_image' in request.files:
            profile_image = save_uploaded_file(request.files['profile_image'])
        
        cursor = connection.cursor(dictionary=True)
        
        # Check if profile exists
        cursor.execute("SELECT id FROM profile")
        existing = cursor.fetchone()
        
        if existing:
            # Update existing profile
            if profile_image:
                cursor.execute(
                    "UPDATE profile SET name=%s, title=%s, bio=%s, profile_image=%s WHERE id=%s",
                    (name, title, bio, profile_image, existing['id'])
                )
            else:
                cursor.execute(
                    "UPDATE profile SET name=%s, title=%s, bio=%s WHERE id=%s",
                    (name, title, bio, existing['id'])
                )
            connection.commit()
            cursor.close()
            connection.close()
            return response('success', 'Profile updated successfully')
        else:
            # Create new profile
            cursor.execute(
                "INSERT INTO profile (name, title, bio, profile_image) VALUES (%s, %s, %s, %s)",
                (name, title, bio, profile_image)
            )
            connection.commit()
            profile_id = cursor.lastrowid
            cursor.close()
            connection.close()
            return response('success', 'Profile created successfully', {'id': profile_id})
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


# ============================================================================
# CV ENTRIES ROUTES
# ============================================================================

@app.route('/api/cv-entries', methods=['GET'])
def get_cv_entries():
    """Get all CV entries with optional filtering by section_type"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        section_type = request.args.get('section_type')
        cursor = connection.cursor(dictionary=True)
        
        if section_type and section_type in ['education', 'experience', 'skill']:
            cursor.execute(
                "SELECT * FROM cv_entries WHERE section_type=%s ORDER BY id DESC",
                (section_type,)
            )
        else:
            cursor.execute("SELECT * FROM cv_entries ORDER BY id DESC")
        
        entries = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return response('success', 'CV entries retrieved', entries)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/cv-entries', methods=['POST'])
def create_cv_entry():
    """Create a new CV entry"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        data = request.get_json()
        
        section_type = data.get('section_type', '').strip()
        title = data.get('title', '').strip()
        organization = data.get('organization', '').strip()
        duration = data.get('duration', '').strip()
        description = data.get('description', '').strip()
        
        # Validation
        if not section_type or section_type not in ['education', 'experience', 'skill']:
            return response('error', 'Invalid section_type. Must be education, experience, or skill', None, 400)
        if not title:
            return response('error', 'Title is required', None, 400)
        
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO cv_entries (section_type, title, organization, duration, description) VALUES (%s, %s, %s, %s, %s)",
            (section_type, title, organization, duration, description)
        )
        connection.commit()
        entry_id = cursor.lastrowid
        cursor.close()
        connection.close()
        
        return response('success', 'CV entry created successfully', {'id': entry_id}, 201)
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


@app.route('/api/cv-entries/<int:entry_id>', methods=['GET'])
def get_cv_entry(entry_id):
    """Get a specific CV entry"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM cv_entries WHERE id=%s", (entry_id,))
        entry = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if entry:
            return response('success', 'CV entry retrieved', entry)
        else:
            return response('error', 'CV entry not found', None, 404)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/cv-entries/<int:entry_id>', methods=['PUT'])
def update_cv_entry(entry_id):
    """Update a CV entry"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        data = request.get_json()
        
        section_type = data.get('section_type', '').strip()
        title = data.get('title', '').strip()
        organization = data.get('organization', '').strip()
        duration = data.get('duration', '').strip()
        description = data.get('description', '').strip()
        
        if section_type and section_type not in ['education', 'experience', 'skill']:
            return response('error', 'Invalid section_type', None, 400)
        if not title:
            return response('error', 'Title is required', None, 400)
        
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE cv_entries SET section_type=%s, title=%s, organization=%s, duration=%s, description=%s WHERE id=%s",
            (section_type, title, organization, duration, description, entry_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return response('error', 'CV entry not found', None, 404)
        
        cursor.close()
        connection.close()
        return response('success', 'CV entry updated successfully')
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


@app.route('/api/cv-entries/<int:entry_id>', methods=['DELETE'])
def delete_cv_entry(entry_id):
    """Delete a CV entry"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM cv_entries WHERE id=%s", (entry_id,))
        connection.commit()
        
        if cursor.rowcount == 0:
            return response('error', 'CV entry not found', None, 404)
        
        cursor.close()
        connection.close()
        return response('success', 'CV entry deleted successfully')
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


# ============================================================================
# CERTIFICATES ROUTES
# ============================================================================

@app.route('/api/certificates', methods=['GET'])
def get_certificates():
    """Get all certificates"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM certificates ORDER BY id DESC")
        certificates = cursor.fetchall()
        cursor.close()
        connection.close()
        
        # Convert image paths to URLs
        for cert in certificates:
            if cert.get('image_url'):
                cert['image_url'] = f"/uploads/{cert['image_url']}"
        
        return response('success', 'Certificates retrieved', certificates)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/certificates', methods=['POST'])
def create_certificate():
    """Create a new certificate"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        title = request.form.get('title', '').strip()
        issuer = request.form.get('issuer', '').strip()
        
        if not title:
            return response('error', 'Title is required', None, 400)
        
        # Handle image upload - multipart file from the device, with base64 fallback
        image_url, upload_error = handle_image_upload(('image', 'photo', 'file', 'certificate'))
        if upload_error:
            return response('error', upload_error, None, 400)
        
        if not image_url:
            return response(
                'error',
                'Certificate image is required. Attach the photo as a multipart file '
                'under the "image" field, or send base64 data in "image"/"image_base64". '
                'External image URLs are never accepted.',
                None, 400
            )
        
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO certificates (title, issuer, image_url) VALUES (%s, %s, %s)",
            (title, issuer, image_url)
        )
        connection.commit()
        certificate_id = cursor.lastrowid
        cursor.close()
        connection.close()
        
        return response('success', 'Certificate created successfully', {'id': certificate_id}, 201)
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


@app.route('/api/certificates/<int:cert_id>', methods=['GET'])
def get_certificate(cert_id):
    """Get a specific certificate"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM certificates WHERE id=%s", (cert_id,))
        certificate = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if certificate:
            if certificate.get('image_url'):
                certificate['image_url'] = f"/uploads/{certificate['image_url']}"
            return response('success', 'Certificate retrieved', certificate)
        else:
            return response('error', 'Certificate not found', None, 404)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/certificates/<int:cert_id>', methods=['DELETE'])
def delete_certificate(cert_id):
    """Delete a certificate"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get certificate to delete image file
        cursor.execute("SELECT image_url FROM certificates WHERE id=%s", (cert_id,))
        certificate = cursor.fetchone()
        
        if not certificate:
            return response('error', 'Certificate not found', None, 404)
        
        # Delete from database
        cursor.execute("DELETE FROM certificates WHERE id=%s", (cert_id,))
        connection.commit()
        cursor.close()
        connection.close()
        
        # Delete image file
        if certificate.get('image_url'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], certificate['image_url'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        return response('success', 'Certificate deleted successfully')
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


# ============================================================================
# GALLERY ROUTES
# ============================================================================

@app.route('/api/gallery', methods=['GET'])
def get_gallery_photos():
    """Get all gallery photos"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gallery_photos ORDER BY id DESC")
        photos = cursor.fetchall()
        cursor.close()
        connection.close()
        
        # Convert image paths to URLs
        for photo in photos:
            if photo.get('image_url'):
                photo['image_url'] = f"/uploads/{photo['image_url']}"
        
        return response('success', 'Gallery photos retrieved', photos)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/gallery', methods=['POST'])
def create_gallery_photo():
    """Add a new photo to gallery"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        caption = request.form.get('caption', '').strip()
        
        # Handle image upload - multipart file from the device, with base64 fallback
        image_url, upload_error = handle_image_upload(('image', 'photo', 'file', 'gallery_photo'))
        if upload_error:
            return response('error', upload_error, None, 400)
        
        if not image_url:
            return response(
                'error',
                'Photo image is required. Attach the photo as a multipart file '
                'under the "image" field, or send base64 data in "image"/"image_base64". '
                'External image URLs are never accepted.',
                None, 400
            )
        
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO gallery_photos (caption, image_url) VALUES (%s, %s)",
            (caption, image_url)
        )
        connection.commit()
        photo_id = cursor.lastrowid
        cursor.close()
        connection.close()
        
        return response('success', 'Photo added to gallery successfully', {'id': photo_id}, 201)
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


@app.route('/api/gallery/<int:photo_id>', methods=['GET'])
def get_gallery_photo(photo_id):
    """Get a specific gallery photo"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM gallery_photos WHERE id=%s", (photo_id,))
        photo = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if photo:
            if photo.get('image_url'):
                photo['image_url'] = f"/uploads/{photo['image_url']}"
            return response('success', 'Photo retrieved', photo)
        else:
            return response('error', 'Photo not found', None, 404)
    except Error as e:
        return response('error', f'Database error: {str(e)}', None, 500)


@app.route('/api/gallery/<int:photo_id>', methods=['PUT'])
def update_gallery_photo(photo_id):
    """Update gallery photo caption"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        data = request.get_json()
        caption = data.get('caption', '').strip()
        
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE gallery_photos SET caption=%s WHERE id=%s",
            (caption, photo_id)
        )
        connection.commit()
        
        if cursor.rowcount == 0:
            return response('error', 'Photo not found', None, 404)
        
        cursor.close()
        connection.close()
        return response('success', 'Photo updated successfully')
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


@app.route('/api/gallery/<int:photo_id>', methods=['DELETE'])
def delete_gallery_photo(photo_id):
    """Delete a gallery photo"""
    connection = get_db_connection()
    if not connection:
        return response('error', 'Database connection failed', None, 500)
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get photo to delete image file
        cursor.execute("SELECT image_url FROM gallery_photos WHERE id=%s", (photo_id,))
        photo = cursor.fetchone()
        
        if not photo:
            return response('error', 'Photo not found', None, 404)
        
        # Delete from database
        cursor.execute("DELETE FROM gallery_photos WHERE id=%s", (photo_id,))
        connection.commit()
        cursor.close()
        connection.close()
        
        # Delete image file
        if photo.get('image_url'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo['image_url'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        return response('success', 'Photo deleted successfully')
    
    except Error as e:
        connection.rollback()
        return response('error', f'Database error: {str(e)}', None, 500)
    finally:
        if connection.is_connected():
            connection.close()


# ============================================================================
# UTILITY ROUTES
# ============================================================================

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    return app.send_from_directory(app.config['UPLOAD_FOLDER'], secure_filename(filename))


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    connection = get_db_connection()
    if connection:
        connection.close()
        return response('success', 'Server and database are healthy')
    else:
        return response('error', 'Database connection failed', None, 500)


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return response('error', 'Endpoint not found', None, 404)


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return response('error', 'Internal server error', None, 500)


if __name__ == '__main__':
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
