# Portfolio Backend - Flask Application

A professional Flask backend for your portfolio application with MySQL database integration.

## Features

✓ **Profile Management** - Store and update your profile with name, title, bio, and profile picture
✓ **CV/Resume Sections** - Add education, experience, and skills
✓ **Certificate Upload** - Upload and manage certificates with images
✓ **Gallery** - Store graduation photos and other gallery images
✓ **File Upload** - Secure file upload with validation
✓ **CORS Support** - Ready for frontend integration
✓ **RESTful API** - Complete REST API for all operations

## Installation

### 1. Prerequisites

- Python 3.8+
- MySQL Server installed and running
- pip (Python package manager)

### 2. Install Dependencies

```bash
pip install flask mysql-connector-python python-dotenv flask-cors werkzeug
```

### 3. Configure Database

Edit `.env` file with your MySQL credentials:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=portfolio
```

### 4. Initialize Database

Run the database initialization script to create all tables:

```bash
python init_db.py
```

You should see output like:

```
✓ Database and tables created successfully!
✓ Database: portfolio
✓ Tables: profile, cv_entries, certificates, gallery_photos
```

### 5. Run the Application

```bash
python port.py
```

Server will start at: `http://localhost:5000`

## API Endpoints

### Profile Management

**Get Profile**

```
GET /api/profile
```

**Create/Update Profile**

```
POST /api/profile
PUT /api/profile
Content-Type: multipart/form-data

Fields:
- name (required)
- title (required)
- bio (optional)
- profile_image (optional, file)
```

### CV Entries

**Get All CV Entries**

```
GET /api/cv-entries
GET /api/cv-entries?section_type=education  # filter by type
```

**Get Single Entry**

```
GET /api/cv-entries/<id>
```

**Create CV Entry**

```
POST /api/cv-entries
Content-Type: application/json

Body:
{
  "section_type": "education|experience|skill",
  "title": "Entry Title",
  "organization": "Organization Name",
  "duration": "2020 - 2022",
  "description": "Detailed description"
}
```

**Update CV Entry**

```
PUT /api/cv-entries/<id>
Content-Type: application/json
```

**Delete CV Entry**

```
DELETE /api/cv-entries/<id>
```

### Certificates

**Get All Certificates**

```
GET /api/certificates
```

**Get Single Certificate**

```
GET /api/certificates/<id>
```

**Create Certificate**

```
POST /api/certificates
Content-Type: multipart/form-data

Fields:
- title (required)
- issuer (optional)
- image (required, file)
```

The photo is uploaded from the device as a file, exactly like the profile
image (`profile_image`). Accepted field names: `image`, `image_url`,
`photo`, `file`, or `certificate`. Base64-encoded image data is also
accepted as a fallback in the `image`/`image_base64` form or JSON field.
Image URLs are never stored - only files saved to `./uploads/`.

**Delete Certificate**

```
DELETE /api/certificates/<id>
```

### Gallery

**Get All Gallery Photos**

```
GET /api/gallery
```

**Get Single Photo**

```
GET /api/gallery/<id>
```

**Add Photo to Gallery**

```
POST /api/gallery
Content-Type: multipart/form-data

Fields:
- caption (optional)
- image (required, file)
```

**Update Photo Caption**

```
PUT /api/gallery/<id>
Content-Type: application/json

Body:
{
  "caption": "New caption"
}
```

**Delete Photo**

```
DELETE /api/gallery/<id>
```

## File Upload

- **Maximum file size**: 50MB
- **Allowed formats**: PNG, JPG, JPEG, GIF, WebP
- **Upload folder**: `./uploads/`
- **Access uploaded files**: `http://localhost:5000/uploads/filename`

## Response Format

All API responses follow a standard format:

**Success Response (200)**

```json
{
  "status": "success",
  "message": "Operation completed successfully",
  "data": {}
}
```

**Error Response**

```json
{
  "status": "error",
  "message": "Error description"
}
```

## Testing with cURL

### Create Profile

```bash
curl -X POST http://localhost:5000/api/profile \
  -F "name=Victor Kipchirchir" \
  -F "title=Software Developer" \
  -F "bio=Full-stack developer with passion for building applications" \
  -F "profile_image=@/path/to/image.jpg"
```

### Get Profile

```bash
curl http://localhost:5000/api/profile
```

### Add CV Entry

```bash
curl -X POST http://localhost:5000/api/cv-entries \
  -H "Content-Type: application/json" \
  -d '{
    "section_type": "education",
    "title": "Bachelor of Science in Computer Science",
    "organization": "University Name",
    "duration": "2018 - 2022",
    "description": "Major in Computer Science"
  }'
```

### Upload Certificate

```bash
curl -X POST http://localhost:5000/api/certificates \
  -F "title=AWS Certified Solutions Architect" \
  -F "issuer=Amazon Web Services" \
  -F "image=@/path/to/certificate.jpg"
```

### Add Gallery Photo

```bash
curl -X POST http://localhost:5000/api/gallery \
  -F "caption=Graduation Day 2022" \
  -F "image=@/path/to/photo.jpg"
```

## Directory Structure

```
Portfolio/
├── port.py                 # Main Flask application
├── init_db.py              # Database initialization script
├── .env                    # Environment variables (configure with your DB credentials)
├── .gitignore              # Git ignore file
├── uploads/                # Uploaded files directory (created automatically)
└── README.md               # This file
```

## Security Notes

1. **CORS**: Currently enables CORS for all origins. Restrict in production:

   ```python
   CORS(app, resources={r"/api/*": {"origins": "your-domain.com"}})
   ```

2. **File Upload**: Files are validated by extension. Add MIME type validation for production.

3. **Database**: Store database credentials in environment variables, never in code.

4. **Error Messages**: Production environment should use generic error messages.

## Troubleshooting

**"Database connection failed"**

- Check MySQL is running
- Verify `.env` credentials are correct
- Ensure database name matches

**"Failed to create profile image"**

- Check `uploads/` folder exists and is writable
- Verify file format is PNG, JPG, JPEG, GIF, or WebP

**"Certificate image is required" / "Photo image is required"**

- In Insomnia, make sure the request body type is **Multipart Form**:
  1. Select `POST` and set URL to `http://localhost:5000/api/certificates`
  2. Tab: **Body** → **Multipart Form**
  3. Add `title` (Text), `issuer` (Text)
  4. Add `image` → set **Type = File** → choose the certificate photo from your device
  5. Send
- If the body type is `JSON` or `Form URL Encoded`, the file is NOT sent as a file.
- The field name must be `image` (or `photo` / `file` / `certificate`).
- Base64-encoded image data is also accepted in `image` / `image_base64` (form or JSON).
- Image URLs are never stored - only device file uploads are accepted.
- Check the server console: the backend logs every received field, e.g.
  `[upload] received files=[...] fields=[...]`.

**CORS Errors**

- Ensure `flask-cors` is installed
- Check frontend is making requests to correct URL

**File Too Large**

- Maximum upload is 50MB
- Change `MAX_CONTENT_LENGTH` in `port.py` to allow larger files

## Next Steps

1. Configure frontend to call these API endpoints
2. Add authentication/authorization
3. Implement input sanitization
4. Add request rate limiting
5. Set up logging
6. Deploy to production server

## Support

For issues or questions, check the Flask and MySQL documentation or review the API endpoint examples above.
