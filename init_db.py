"""
Database initialization script
Run this once to create all necessary tables
"""

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
}

DB_NAME = os.getenv('DB_NAME', 'portfolio')

def create_database_and_tables():
    """Create database and tables if they don't exist"""
    connection = None
    try:
        # Connect to MySQL
        print("Connecting to MySQL...")
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        print(f"Creating database '{DB_NAME}' if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        
        # Select the database
        cursor.execute(f"USE {DB_NAME}")
        
        # Create profile table
        print("Creating 'profile' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                bio TEXT,
                profile_image VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Create cv_entries table
        print("Creating 'cv_entries' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cv_entries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                section_type ENUM('education', 'experience', 'skill') NOT NULL,
                title VARCHAR(255) NOT NULL,
                organization VARCHAR(255),
                duration VARCHAR(100),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Create certificates table
        print("Creating 'certificates' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                issuer VARCHAR(255),
                image_url VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Create gallery_photos table
        print("Creating 'gallery_photos' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gallery_photos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                caption VARCHAR(255),
                image_url VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        connection.commit()
        cursor.close()
        
        print("\n✓ Database and tables created successfully!")
        print(f"✓ Database: {DB_NAME}")
        print("✓ Tables: profile, cv_entries, certificates, gallery_photos")
        
    except Error as e:
        print(f"✗ Error: {e}")
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("✓ Database connection closed")


if __name__ == '__main__':
    create_database_and_tables()
