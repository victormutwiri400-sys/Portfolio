"""Portfolio Backend - Flask app with Cloudinary image storage and MySQL/MariaDB."""
import os
import secrets
import uuid
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from mysql.connector import Error, IntegrityError
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": "*"}})

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(cloud_name=CLOUDINARY_CLOUD_NAME, api_key=CLOUDINARY_API_KEY, api_secret=CLOUDINARY_API_SECRET, secure=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql-victordesigner.alwaysdata.net"),
    "user": os.getenv("DB_USER", "victordesigner"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "victordesigner_portifolio"),
}

# Secret admin token required for every mutating request (POST/PUT/DELETE).
# Set a long, random value in your .env — never commit the real token.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Revoked share links are hard-deleted from the database once they have been
# disabled AND expired for this many days. This keeps the table from growing
# forever without needing a scheduled job (runs whenever the list is fetched).
SHARE_LINK_RETENTION_DAYS = int(os.getenv("SHARE_LINK_RETENTION_DAYS", "30"))
PROJECT_CATEGORIES = {
    "Full-Stack Development",
    "Web Applications",
    "Graphic and Vector Design",
    "Other Projects",
}


def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"Database connection error: {e}")
        return None


def response(status, message, data=None, status_code=200):
    result = {"status": status, "message": message}
    if data is not None:
        result["data"] = data
    return jsonify(result), status_code


def allowed_file(filename):
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)


def cloudinary_ready():
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def upload_to_cloudinary(file, folder="portfolio"):
    if not cloudinary_ready() or not file or not file.filename or not allowed_file(file.filename):
        return None
    try:
        original_name = secure_filename(file.filename)
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"
        result = cloudinary.uploader.upload(file, public_id=f"{folder}/{unique_name}", resource_type="image", overwrite=False, use_filename=False)
        return {"url": result.get("secure_url"), "public_id": result.get("public_id")}
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


def upload_base64_to_cloudinary(data, folder="portfolio"):
    if not cloudinary_ready() or not data or not isinstance(data, str) or not data.strip():
        return None
    try:
        result = cloudinary.uploader.upload(data.strip(), folder=folder, resource_type="image")
        return {"url": result.get("secure_url"), "public_id": result.get("public_id")}
    except Exception as e:
        print(f"Cloudinary base64 upload error: {e}")
        return None


def handle_image_upload(field_names, folder="portfolio"):
    if not cloudinary_ready():
        return None, "Cloudinary is not configured. Please add CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET."
    keys = ("image", "image_base64", "image_url", "imageUrl", "photo", "file", "certificate", "profile_image", "gallery_photo")
    for name in tuple(field_names) + keys:
        file = request.files.get(name)
        if file and file.filename:
            if not allowed_file(file.filename):
                return None, "Invalid file type. Allowed: png, jpg, jpeg, gif, webp"
            uploaded = upload_to_cloudinary(file, folder=folder)
            return (uploaded, None) if uploaded else (None, "Unable to upload image to Cloudinary.")
    for key in keys:
        value = request.form.get(key, "").strip()
        if value.startswith(("http://", "https://")):
            return None, "Image URLs are not accepted here. Please upload an image file."
        if value:
            uploaded = upload_base64_to_cloudinary(value, folder=folder)
            return (uploaded, None) if uploaded else (None, f'Invalid image data in "{key}".')
    if request.is_json:
        data = request.get_json(silent=True) or {}
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                if value.strip().startswith(("http://", "https://")):
                    return None, "Image URLs are not accepted here. Please upload an image file."
                uploaded = upload_base64_to_cloudinary(value.strip(), folder=folder)
                return (uploaded, None) if uploaded else (None, f'Invalid image data in "{key}".')
    return None, None


def with_db(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        connection = get_db_connection()
        if not connection:
            return response("error", "Database connection failed", None, 500)
        try:
            result = f(connection, *args, **kwargs)
            connection.commit()
            return result
        except Error as e:
            connection.rollback()
            return response("error", f"Database error: {str(e)}", None, 500)
        finally:
            if connection and connection.is_connected():
                connection.close()
    return wrapper


def admin_required(f):
    """Reject any mutating request that does not carry the admin token.

    Guards against direct POST/PUT/DELETE calls from the browser, curl, or
    Postman even when the UI hides the management buttons.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        provided = request.headers.get("X-Admin-Token", "")
        # TEMPORARY DIAGNOSTIC — boolean only, no secret values. REMOVE AFTER VERIFICATION.
        print(
            f"[diag admin_required] X-Admin-Token present: {bool(provided)}, "
            f"ADMIN_TOKEN configured: {bool(ADMIN_TOKEN)}, "
            f"comparison succeeded: {provided == ADMIN_TOKEN}"
        )
        if not ADMIN_TOKEN or provided != ADMIN_TOKEN:
            return response("error", "Unauthorized. A valid admin token is required.", None, 401)

        return f(*args, **kwargs)

    return wrapper


def valid_project_url(value, optional=False):
    if optional and not value:
        return True
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not any(character.isspace() for character in value)
    )


def parse_project(row):
    """Convert database row fields to the frontend project representation."""
    import json

    try:
        technologies = json.loads(row.get("technologies") or "[]")
    except (TypeError, ValueError):
        technologies = []
    row["technologies"] = technologies if isinstance(technologies, list) else []
    row["is_featured"] = bool(row.get("is_featured"))
    return row


@app.route("/api/projects", methods=["GET"])
@with_db
def get_projects(connection):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM portfolio_projects ORDER BY is_featured DESC, id DESC")
    return response("success", "Projects retrieved", [parse_project(row) for row in cursor.fetchall()])


@app.route("/api/projects", methods=["POST"])
@admin_required
@with_db
def create_project(connection):
    import json

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    project_url = request.form.get("project_url", "").strip()
    github_url = request.form.get("github_url", "").strip()
    if not title or len(title) > 255:
        return response("error", "Title is required and must be 255 characters or fewer", None, 400)
    if not description or len(description) > 5000:
        return response("error", "Description is required and must be 5000 characters or fewer", None, 400)
    if category not in PROJECT_CATEGORIES:
        return response("error", "Invalid project category", None, 400)
    if not valid_project_url(project_url) or not valid_project_url(github_url, optional=True):
        return response("error", "Project links must be valid HTTP or HTTPS URLs", None, 400)

    technologies_value = request.form.get("technologies", "[]")
    try:
        technologies = json.loads(technologies_value) if isinstance(technologies_value, str) else technologies_value
    except (TypeError, ValueError):
        return response("error", "Technologies must be a JSON array", None, 400)
    if not isinstance(technologies, list) or any(not isinstance(item, str) or len(item) > 100 for item in technologies):
        return response("error", "Technologies must be a list of strings (100 characters maximum each)", None, 400)

    image_url = None
    if any(file.filename for file in request.files.values()):
        image_data, upload_error = handle_image_upload(("image",), folder="portfolio/projects")
        if upload_error:
            return response("error", upload_error, None, 400)
        image_url = image_data["url"] if image_data else None
    is_featured = request.form.get("is_featured", "false").lower() in ("true", "1", "yes")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO portfolio_projects (title, description, category, technologies, project_url, github_url, image_url, is_featured) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (title, description, category, json.dumps(technologies), project_url, github_url or None, image_url, is_featured),
    )
    return response("success", "Project created successfully", {"id": cursor.lastrowid}, 201)


@app.route("/api/projects/<int:project_id>", methods=["PUT"])
@admin_required
@with_db
def update_project(connection, project_id):
    import json

    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM portfolio_projects WHERE id=%s", (project_id,))
    existing = cursor.fetchone()
    if not existing:
        return response("error", "Project not found", None, 404)

    def field(name, old):
        return request.form.get(name, old)

    title = field("title", existing["title"]).strip()
    description = field("description", existing["description"]).strip()
    category = field("category", existing["category"]).strip()
    project_url = field("project_url", existing["project_url"]).strip()
    github_url = field("github_url", existing.get("github_url") or "").strip()
    if not title or len(title) > 255:
        return response("error", "Title is required and must be 255 characters or fewer", None, 400)
    if not description or len(description) > 5000:
        return response("error", "Description is required and must be 5000 characters or fewer", None, 400)
    if category not in PROJECT_CATEGORIES:
        return response("error", "Invalid project category", None, 400)
    if not valid_project_url(project_url) or not valid_project_url(github_url, optional=True):
        return response("error", "Project links must be valid HTTP or HTTPS URLs", None, 400)

    technologies_raw = request.form.get("technologies")
    if technologies_raw is None:
        technologies = json.loads(existing.get("technologies") or "[]")
    else:
        try:
            technologies = json.loads(technologies_raw)
        except (TypeError, ValueError):
            return response("error", "Technologies must be a JSON array", None, 400)
    if not isinstance(technologies, list) or any(not isinstance(item, str) or len(item) > 100 for item in technologies):
        return response("error", "Technologies must be a list of strings (100 characters maximum each)", None, 400)

    image_url = existing.get("image_url")
    if any(file.filename for file in request.files.values()):
        image_data, upload_error = handle_image_upload(("image",), folder="portfolio/projects")
        if upload_error:
            return response("error", upload_error, None, 400)
        if image_data:
            image_url = image_data["url"]
    is_featured = request.form.get("is_featured", str(bool(existing.get("is_featured")))).lower() in ("true", "1", "yes")
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE portfolio_projects SET title=%s, description=%s, category=%s, technologies=%s, project_url=%s, github_url=%s, image_url=%s, is_featured=%s WHERE id=%s",
        (title, description, category, json.dumps(technologies), project_url, github_url or None, image_url, is_featured, project_id),
    )
    return response("success", "Project updated successfully")


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@admin_required
@with_db
def delete_project(connection, project_id):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM portfolio_projects WHERE id=%s", (project_id,))
    if cursor.rowcount == 0:
        return response("error", "Project not found", None, 404)
    return response("success", "Project deleted successfully")


@app.route("/api/profile", methods=["GET"])
@with_db
def get_profile(connection):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM profile LIMIT 1")
    profile = cursor.fetchone()
    if profile:
        return response("success", "Profile retrieved", profile)
    return response("error", "Profile not found", None, 404)


@app.route("/api/profile", methods=["POST", "PUT"])
@admin_required
@with_db
def create_or_update_profile(connection):
    name = request.form.get("name", "").strip()
    title = request.form.get("title", "").strip()
    bio = request.form.get("bio", "").strip()
    if not name or not title:
        return response("error", "Name and title are required", None, 400)
    image_data, upload_error = handle_image_upload(("profile_image", "image", "photo", "file"), folder="portfolio/profile")
    if upload_error:
        return response("error", upload_error, None, 400)
    profile_image = image_data["url"] if image_data else None
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id FROM profile LIMIT 1")
    existing = cursor.fetchone()
    if existing:
        if profile_image:
            cursor.execute("UPDATE profile SET name=%s, title=%s, bio=%s, profile_image=%s WHERE id=%s", (name, title, bio, profile_image, existing["id"]))
        else:
            cursor.execute("UPDATE profile SET name=%s, title=%s, bio=%s WHERE id=%s", (name, title, bio, existing["id"]))
        return response("success", "Profile updated successfully")
    cursor.execute("INSERT INTO profile (name, title, bio, profile_image) VALUES (%s, %s, %s, %s)", (name, title, bio, profile_image))
    return response("success", "Profile created successfully", {"id": cursor.lastrowid}, 201)


@app.route("/api/cv-entries", methods=["GET"])
@with_db
def get_cv_entries(connection):
    section_type = request.args.get("section_type")
    cursor = connection.cursor(dictionary=True)
    if section_type in ["education", "experience", "skill"]:
        cursor.execute("SELECT * FROM cv_entries WHERE section_type=%s ORDER BY id DESC", (section_type,))
    else:
        cursor.execute("SELECT * FROM cv_entries ORDER BY id DESC")
    return response("success", "CV entries retrieved", cursor.fetchall())


@app.route("/api/cv-entries", methods=["POST"])
@admin_required
@with_db
def create_cv_entry(connection):
    data = request.get_json(silent=True) or {}
    section_type = data.get("section_type", "").strip()
    title = data.get("title", "").strip()
    organization = data.get("organization", "").strip()
    duration = data.get("duration", "").strip()
    description = data.get("description", "").strip()
    if section_type not in ["education", "experience", "skill"]:
        return response("error", "Invalid section_type. Must be education, experience, or skill", None, 400)
    if not title:
        return response("error", "Title is required", None, 400)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO cv_entries (section_type, title, organization, duration, description) VALUES (%s, %s, %s, %s, %s)", (section_type, title, organization, duration, description))
    return response("success", "CV entry created successfully", {"id": cursor.lastrowid}, 201)


@app.route("/api/cv-entries/<int:entry_id>", methods=["GET"])
@with_db
def get_cv_entry(connection, entry_id):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cv_entries WHERE id=%s", (entry_id,))
    entry = cursor.fetchone()
    if entry:
        return response("success", "CV entry retrieved", entry)
    return response("error", "CV entry not found", None, 404)


@app.route("/api/cv-entries/<int:entry_id>", methods=["PUT"])
@admin_required
@with_db
def update_cv_entry(connection, entry_id):
    data = request.get_json(silent=True) or {}
    section_type = data.get("section_type", "").strip()
    title = data.get("title", "").strip()
    organization = data.get("organization", "").strip()
    duration = data.get("duration", "").strip()
    description = data.get("description", "").strip()
    if section_type and section_type not in ["education", "experience", "skill"]:
        return response("error", "Invalid section_type", None, 400)
    if not title:
        return response("error", "Title is required", None, 400)
    cursor = connection.cursor()
    cursor.execute("UPDATE cv_entries SET section_type=%s, title=%s, organization=%s, duration=%s, description=%s WHERE id=%s", (section_type, title, organization, duration, description, entry_id))
    if cursor.rowcount == 0:
        return response("error", "CV entry not found", None, 404)
    return response("success", "CV entry updated successfully")


@app.route("/api/cv-entries/<int:entry_id>", methods=["DELETE"])
@admin_required
@with_db
def delete_cv_entry(connection, entry_id):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM cv_entries WHERE id=%s", (entry_id,))
    if cursor.rowcount == 0:
        return response("error", "CV entry not found", None, 404)
    return response("success", "CV entry deleted successfully")


@app.route("/api/certificates", methods=["GET"])
@with_db
def get_certificates(connection):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM certificates ORDER BY id DESC")
    return response("success", "Certificates retrieved", cursor.fetchall())


@app.route("/api/certificates", methods=["POST"])
@admin_required
@with_db
def create_certificate(connection):
    title = request.form.get("title", "").strip()
    issuer = request.form.get("issuer", "").strip()
    if not title:
        return response("error", "Title is required", None, 400)
    image_data, upload_error = handle_image_upload(("image", "photo", "file", "certificate"), folder="portfolio/certificates")
    if upload_error:
        return response("error", upload_error, None, 400)
    if not image_data:
        return response("error", "Certificate image is required.", None, 400)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO certificates (title, issuer, image_url) VALUES (%s, %s, %s)", (title, issuer, image_data["url"]))
    return response("success", "Certificate created successfully", {"id": cursor.lastrowid}, 201)


@app.route("/api/certificates/<int:cert_id>", methods=["GET"])
@with_db
def get_certificate(connection, cert_id):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM certificates WHERE id=%s", (cert_id,))
    certificate = cursor.fetchone()
    if certificate:
        return response("success", "Certificate retrieved", certificate)
    return response("error", "Certificate not found", None, 404)


@app.route("/api/certificates/<int:cert_id>", methods=["DELETE"])
@admin_required
@with_db
def delete_certificate(connection, cert_id):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM certificates WHERE id=%s", (cert_id,))
    if cursor.rowcount == 0:
        return response("error", "Certificate not found", None, 404)
    return response("success", "Certificate deleted successfully")


@app.route("/api/gallery", methods=["GET"])
@with_db
def get_gallery_photos(connection):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM gallery_photos ORDER BY id DESC")
    return response("success", "Gallery photos retrieved", cursor.fetchall())


@app.route("/api/gallery", methods=["POST"])
@admin_required
@with_db
def create_gallery_photo(connection):
    caption = request.form.get("caption", "").strip()
    image_data, upload_error = handle_image_upload(("image", "photo", "file", "gallery_photo"), folder="portfolio/gallery")
    if upload_error:
        return response("error", upload_error, None, 400)
    if not image_data:
        return response("error", "Gallery image is required.", None, 400)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO gallery_photos (caption, image_url) VALUES (%s, %s)", (caption, image_data["url"]))
    return response("success", "Photo added to gallery successfully", {"id": cursor.lastrowid}, 201)


@app.route("/api/gallery/<int:photo_id>", methods=["GET"])
@with_db
def get_gallery_photo(connection, photo_id):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM gallery_photos WHERE id=%s", (photo_id,))
    photo = cursor.fetchone()
    if photo:
        return response("success", "Photo retrieved", photo)
    return response("error", "Photo not found", None, 404)


@app.route("/api/gallery/<int:photo_id>", methods=["PUT"])
@admin_required
@with_db
def update_gallery_photo(connection, photo_id):
    data = request.get_json(silent=True) or {}
    caption = data.get("caption", "").strip()
    cursor = connection.cursor()
    cursor.execute("UPDATE gallery_photos SET caption=%s WHERE id=%s", (caption, photo_id))
    if cursor.rowcount == 0:
        return response("error", "Photo not found", None, 404)
    return response("success", "Photo updated successfully")


@app.route("/api/gallery/<int:photo_id>", methods=["DELETE"])
@admin_required
@with_db
def delete_gallery_photo(connection, photo_id):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM gallery_photos WHERE id=%s", (photo_id,))
    if cursor.rowcount == 0:
        return response("error", "Photo not found", None, 404)
    return response("success", "Photo deleted successfully")


def share_link_status(row):
    """Calculate the current status of a share link row."""
    if not row.get("is_active"):
        return "disabled"
    expires_at = row.get("expires_at")
    if expires_at and expires_at <= datetime.utcnow():
        return "expired"
    return "active"


def _to_utc_iso(value):
    """Format a DB datetime (stored as UTC) as an ISO string with a Z marker."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    value = str(value).replace(" ", "T")
    return value if value.endswith("Z") else value + "Z"


def serialize_share_link(row):
    """Format a portfolio_share_links row for API responses."""
    return {
        "id": row.get("id"),
        "token": row.get("token"),
        "expires_at": _to_utc_iso(row.get("expires_at")),
        "created_at": _to_utc_iso(row.get("created_at")),
        "is_active": bool(row.get("is_active")),
        "status": share_link_status(row),
        "share_path": "/share/{}".format(row.get("token")),
    }


@app.route("/api/share-links", methods=["POST"])
@admin_required
@with_db
def create_share_link(connection):
    data = request.get_json(silent=True) or {}
    expires_at = (data.get("expires_at") or "").strip()
    if not expires_at:
        return response("error", "expires_at is required", None, 400)
    try:
        if expires_at.endswith("Z"):
            expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
        else:
            expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return response("error", "Invalid expires_at format. Use YYYY-MM-DDTHH:MM:SS", None, 400)
    if expiry <= datetime.utcnow():
        return response("error", "expires_at must be a future date", None, 400)
    cursor = connection.cursor()
    inserted = False
    token = ""
    for _ in range(5):
        token = secrets.token_urlsafe(32)
        try:
            cursor.execute("INSERT INTO portfolio_share_links (token, expires_at, is_active) VALUES (%s, %s, TRUE)", (token, expiry.strftime("%Y-%m-%d %H:%M:%S")))
            inserted = True
            break
        except IntegrityError:
            continue
    if not inserted:
        return response("error", "Could not generate a unique share token", None, 500)
    return response("success", "Share link created successfully", {
        "id": cursor.lastrowid,
        "token": token,
        "expires_at": expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "share_path": "/share/{}".format(token),
    }, 201)


@app.route("/api/share-links", methods=["GET"])
@admin_required
@with_db
def get_share_links(connection):
    cursor = connection.cursor()
    # Auto-cleanup: permanently remove revoked links whose expiry passed more
    # than SHARE_LINK_RETENTION_DAYS ago. expires_at is stored in UTC, so we
    # compare against UTC_TIMESTAMP() for consistency.
    cursor.execute(
        "DELETE FROM portfolio_share_links WHERE is_active = FALSE AND expires_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY)",
        (SHARE_LINK_RETENTION_DAYS,),
    )
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, token, expires_at, created_at, is_active FROM portfolio_share_links ORDER BY id DESC")
    return response("success", "Share links retrieved", [serialize_share_link(row) for row in cursor.fetchall()])


@app.route("/api/share-links/<token>", methods=["GET"])
@with_db
def validate_share_link(connection, token):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, token, expires_at, is_active FROM portfolio_share_links WHERE token=%s", (token,))
    row = cursor.fetchone()
    if not row:
        return response("error", "Share link not found", None, 404)
    if not row.get("is_active"):
        return response("error", "Share link has been disabled", None, 403)
    if row.get("expires_at") and row["expires_at"] <= datetime.utcnow():
        return response("error", "Share link has expired", None, 410)
    return response("success", "Share link is valid", {
        "id": row.get("id"),
        "token": row.get("token"),
        "expires_at": _to_utc_iso(row.get("expires_at")),
        "status": "active",
        "share_path": "/share/{}".format(row.get("token")),
    })


@app.route("/api/share-links/<int:share_id>", methods=["DELETE"])
@admin_required
@with_db
def revoke_share_link(connection, share_id):
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, is_active FROM portfolio_share_links WHERE id=%s", (share_id,))
    row = cursor.fetchone()
    if not row:
        return response("error", "Share link not found", None, 404)
    if row.get("is_active"):
        cursor.execute("UPDATE portfolio_share_links SET is_active = FALSE WHERE id=%s", (share_id,))
    return response("success", "Share link revoked successfully")


@app.route("/api/share-links/<int:share_id>/delete", methods=["DELETE"])
@admin_required
@with_db
def delete_share_link(connection, share_id):
    # Permanent removal — the row is gone from the database, so the URL will
    # never work again (not even for an already-expired or disabled link).
    cursor = connection.cursor()
    cursor.execute("DELETE FROM portfolio_share_links WHERE id=%s", (share_id,))
    if cursor.rowcount == 0:
        return response("error", "Share link not found", None, 404)
    return response("success", "Share link deleted successfully")


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    """Validate a submitted admin token before the frontend unlocks controls."""
    data = request.get_json(silent=True) or {}
    provided = (data.get("token") or "").strip()
    # TEMPORARY DIAGNOSTIC — boolean only, no secret values. REMOVE AFTER VERIFICATION.
    print(f"[diag admin_login] ADMIN_TOKEN configured: {bool(ADMIN_TOKEN)}")
    if ADMIN_TOKEN and provided == ADMIN_TOKEN:
        return response("success", "Authenticated")
    # TEMPORARY DIAGNOSTIC — boolean only, no secret values. REMOVE AFTER VERIFICATION.
    print(f"[diag admin_login] token comparison succeeded: {bool(ADMIN_TOKEN) and provided == ADMIN_TOKEN}")
    return response("error", "Invalid admin token", None, 401)


# TEMPORARY DIAGNOSTIC — REMOVE AFTER PRODUCTION VERIFICATION.
# Boolean-only status: never returns or logs secret values.
@app.route("/api/__diag_admin_env", methods=["GET"])
def __diag_admin_env():
    return response(
        "success",
        "Admin environment diagnostic",
        {"admin_token_configured": bool(ADMIN_TOKEN)},
    )


@app.route("/api/health", methods=["GET"])
def health_check():
    connection = get_db_connection()
    if connection:
        connection.close()
        return response("success", "Server and database are healthy")
    return response("error", "Database connection failed", None, 500)


@app.errorhandler(404)
def not_found(error):
    return response("error", "Endpoint not found", None, 404)


@app.errorhandler(500)
def internal_error(error):
    return response("error", "Internal server error", None, 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)