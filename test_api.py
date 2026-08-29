"""
Test script to verify API endpoints
Run this after starting the Flask server to test all endpoints
"""

import requests
import json
import base64
from datetime import datetime

BASE_URL = "http://localhost:5000/api"

def print_response(method, endpoint, status_code, data):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{method} {endpoint}")
    print(f"Status: {status_code}")
    print(f"Response: {json.dumps(data, indent=2)}")
    print(f"{'='*60}")

def test_health():
    """Test health check"""
    print("\n\n🏥 Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print_response("GET", "/api/health", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

def test_profile():
    """Test profile endpoints"""
    print("\n\n👤 Testing Profile Endpoints...")
    
    # Create/Update profile
    try:
        files = {
            'name': (None, 'Victor Kipchirchir'),
            'title': (None, 'Full-Stack Developer'),
            'bio': (None, 'Passionate about building amazing web applications')
        }
        response = requests.post(f"{BASE_URL}/profile", files=files)
        print_response("POST", "/api/profile", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get profile
    try:
        response = requests.get(f"{BASE_URL}/profile")
        print_response("GET", "/api/profile", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

def test_cv_entries():
    """Test CV entry endpoints"""
    print("\n\n📄 Testing CV Entry Endpoints...")
    
    # Create education entry
    try:
        data = {
            "section_type": "education",
            "title": "Bachelor of Science in Computer Science",
            "organization": "University of Nairobi",
            "duration": "2018 - 2022",
            "description": "Major in Computer Science with focus on Software Engineering"
        }
        response = requests.post(f"{BASE_URL}/cv-entries", json=data)
        print_response("POST", "/api/cv-entries (education)", response.status_code, response.json())
        education_id = response.json().get('data', {}).get('id')
    except Exception as e:
        print(f"❌ Error: {e}")
        education_id = None
    
    # Create experience entry
    try:
        data = {
            "section_type": "experience",
            "title": "Junior Developer",
            "organization": "Tech Startup Inc",
            "duration": "2022 - Present",
            "description": "Developing web applications using Python, JavaScript, and React"
        }
        response = requests.post(f"{BASE_URL}/cv-entries", json=data)
        print_response("POST", "/api/cv-entries (experience)", response.status_code, response.json())
        experience_id = response.json().get('data', {}).get('id')
    except Exception as e:
        print(f"❌ Error: {e}")
        experience_id = None
    
    # Create skill entry
    try:
        data = {
            "section_type": "skill",
            "title": "Python",
            "description": "Advanced proficiency in Python programming"
        }
        response = requests.post(f"{BASE_URL}/cv-entries", json=data)
        print_response("POST", "/api/cv-entries (skill)", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get all entries
    try:
        response = requests.get(f"{BASE_URL}/cv-entries")
        print_response("GET", "/api/cv-entries", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get filtered entries
    try:
        response = requests.get(f"{BASE_URL}/cv-entries?section_type=education")
        print_response("GET", "/api/cv-entries?section_type=education", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get single entry
    if education_id:
        try:
            response = requests.get(f"{BASE_URL}/cv-entries/{education_id}")
            print_response("GET", f"/api/cv-entries/{education_id}", response.status_code, response.json())
        except Exception as e:
            print(f"❌ Error: {e}")

def test_certificates():
    """Test certificate endpoints"""
    print("\n\n🏅 Testing Certificate Endpoints...")

    # Tiny valid 1x1 PNG to simulate a certificate photo from the device
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )

    # Create certificate - photo uploaded from the device as a file (same as profile)
    try:
        files = {
            'title': (None, 'AWS Certified Solutions Architect'),
            'issuer': (None, 'Amazon Web Services'),
            'image': ('certificate.png', tiny_png, 'image/png')
        }
        response = requests.post(f"{BASE_URL}/certificates", files=files)
        print_response("POST", "/api/certificates (device file upload)", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

    # Create certificate - base64 photo data in a JSON body (fallback path)
    try:
        data = {
            "title": "Cisco CCNA",
            "issuer": "Cisco",
            "image_base64": "data:image/png;base64," + base64.b64encode(tiny_png).decode()
        }
        response = requests.post(f"{BASE_URL}/certificates", json=data)
        print_response("POST", "/api/certificates (base64 photo)", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

    # A URL is never accepted - should return 400
    try:
        files = {
            'title': (None, 'Invalid URL Certificate'),
            'issuer': (None, 'Test'),
            'image_url': (None, 'https://example.com/cert.png')
        }
        response = requests.post(f"{BASE_URL}/certificates", files=files)
        print_response("POST", "/api/certificates (URL - should fail)", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

    # Get all certificates
    try:
        response = requests.get(f"{BASE_URL}/certificates")
        print_response("GET", "/api/certificates", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

def test_gallery():
    """Test gallery endpoints"""
    print("\n\n🖼️  Testing Gallery Endpoints...")
    
    # Create gallery entry (without file - will fail but shows request format)
    try:
        files = {
            'caption': (None, 'Graduation Day 2022')
        }
        # Note: This will fail because no image file is provided
        response = requests.post(f"{BASE_URL}/gallery", files=files)
        print_response("POST", "/api/gallery", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Get all photos
    try:
        response = requests.get(f"{BASE_URL}/gallery")
        print_response("GET", "/api/gallery", response.status_code, response.json())
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Portfolio API Test Suite")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_health()
    test_profile()
    test_cv_entries()
    test_certificates()
    test_gallery()
    
    print("\n" + "="*60)
    print("✓ Test Suite Completed")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
