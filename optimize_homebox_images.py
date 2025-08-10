#!/usr/bin/env python3
"""
Homebox Image Optimization Script

This script optimizes all images in a Homebox installation by:
1. Converting images to WebP format for better compression
2. Updating the database to reflect correct MIME types
3. Preserving UUID-based filenames to maintain database integrity
4. Creating backups before making changes

Author: Daniel Rosehill
Date: August 2025
"""

import os
import sys
import shutil
import psycopg2
import hashlib
from pathlib import Path
from PIL import Image
import argparse
from datetime import datetime
import logging

# Import private configuration if available
try:
    from config_private import DB_CONFIG, HOMEBOX_DATA_PATH
except ImportError:
    # Default configuration - update these for your setup
    HOMEBOX_DATA_PATH = "/var/lib/docker/volumes/homebox-postgres-data/_data"
    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'homebox',
        'user': 'homebox',
        'password': 'your_password_here'
    }

# Supported image formats for conversion
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}
TARGET_FORMAT = 'webp'
TARGET_MIME = 'image/webp'

# WebP quality settings
WEBP_QUALITY = 85  # Good balance between quality and compression
WEBP_METHOD = 6    # Compression method (0-6, higher = better compression)

def setup_logging():
    """Set up logging configuration"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(f'homebox_optimization_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def create_backup(source_path, backup_dir):
    """Create a backup of the original file"""
    backup_path = backup_dir / Path(source_path).name
    shutil.copy2(source_path, backup_path)
    return backup_path

def get_file_hash(file_path):
    """Calculate SHA256 hash of a file for integrity checking"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def convert_to_webp(input_path, output_path, quality=WEBP_QUALITY):
    """Convert an image to WebP format"""
    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB if necessary (WebP supports both, but RGB is more efficient)
            if img.mode in ('RGBA', 'LA'):
                # Create a white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                else:
                    background.paste(img)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Save as WebP
            img.save(
                output_path,
                'WebP',
                quality=quality,
                method=WEBP_METHOD,
                optimize=True
            )
            return True
    except Exception as e:
        logging.error(f"Failed to convert {input_path}: {e}")
        return False

def get_database_connection():
    """Establish database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        return None

def update_database_mime_type(conn, file_path, new_mime_type):
    """Update the MIME type in the database for a given file path"""
    try:
        cursor = conn.cursor()
        
        # The path in the database includes the data/ prefix
        db_path = f"data/{file_path.relative_to(Path(HOMEBOX_DATA_PATH))}"
        
        # Update MIME type for the file
        cursor.execute(
            "UPDATE attachments SET mime_type = %s WHERE path = %s",
            (new_mime_type, str(db_path))
        )
        
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
        
        return rows_affected > 0
    except Exception as e:
        logging.error(f"Database update failed for {file_path}: {e}")
        conn.rollback()
        return False

def find_image_files(data_path):
    """Find all image files in the Homebox data directory"""
    image_files = []
    data_path = Path(data_path)
    
    for file_path in data_path.rglob('*'):
        if file_path.is_file():
            # Check if it's an image by extension
            if file_path.suffix.lower() in SUPPORTED_FORMATS:
                image_files.append(file_path)
            # Also check files without extensions that might be images
            elif not file_path.suffix:
                try:
                    with Image.open(file_path) as img:
                        # If we can open it as an image, it's an image
                        image_files.append(file_path)
                except:
                    # Not an image, skip
                    pass
    
    return image_files

def analyze_images(image_files):
    """Analyze current image collection"""
    total_size = 0
    format_counts = {}
    
    for img_path in image_files:
        try:
            total_size += img_path.stat().st_size
            
            # Determine format
            if img_path.suffix:
                fmt = img_path.suffix.lower()
            else:
                # Try to determine format from file content
                try:
                    with Image.open(img_path) as img:
                        fmt = f".{img.format.lower()}"
                except:
                    fmt = ".unknown"
            
            format_counts[fmt] = format_counts.get(fmt, 0) + 1
            
        except Exception as e:
            logging.warning(f"Could not analyze {img_path}: {e}")
    
    return total_size, format_counts

def main():
    parser = argparse.ArgumentParser(description='Optimize Homebox images by converting to WebP')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--backup-dir', type=str, help='Directory to store backups (default: ./backups)')
    parser.add_argument('--quality', type=int, default=WEBP_QUALITY, help=f'WebP quality (1-100, default: {WEBP_QUALITY})')
    parser.add_argument('--skip-database', action='store_true', help='Skip database updates (file conversion only)')
    parser.add_argument('--data-path', type=str, help='Override Homebox data path')
    
    args = parser.parse_args()
    
    logger = setup_logging()
    logger.info("Starting Homebox image optimization")
    
    # Override data path if provided
    data_path = args.data_path if args.data_path else HOMEBOX_DATA_PATH
    
    # Set up backup directory
    backup_dir = Path(args.backup_dir) if args.backup_dir else Path('./backups')
    backup_dir.mkdir(exist_ok=True)
    
    # Find all image files
    logger.info(f"Scanning for images in {data_path}")
    image_files = find_image_files(data_path)
    logger.info(f"Found {len(image_files)} image files")
    
    if not image_files:
        logger.info("No image files found to optimize")
        return
    
    # Analyze current collection
    total_size, format_counts = analyze_images(image_files)
    logger.info(f"Current collection: {total_size / (1024*1024):.2f} MB")
    logger.info("Format distribution:")
    for fmt, count in sorted(format_counts.items()):
        logger.info(f"  {fmt}: {count} files")
    
    if args.dry_run:
        logger.info("DRY RUN: Would convert all images to WebP format")
        return
    
    # Set up database connection
    conn = None
    if not args.skip_database:
        conn = get_database_connection()
        if not conn:
            logger.error("Could not connect to database. Use --skip-database to continue with file conversion only.")
            return
    
    # Process each image
    converted_count = 0
    failed_count = 0
    total_saved = 0
    
    for img_path in image_files:
        try:
            logger.info(f"Processing: {img_path.name}")
            
            # Skip if already WebP
            if img_path.suffix.lower() == '.webp':
                logger.info(f"  Already WebP, skipping")
                continue
            
            # Create backup
            backup_path = create_backup(img_path, backup_dir)
            original_size = img_path.stat().st_size
            
            # Convert to WebP (in-place, keeping the same filename but changing content)
            temp_webp = img_path.with_suffix('.webp.tmp')
            
            if convert_to_webp(img_path, temp_webp, args.quality):
                new_size = temp_webp.stat().st_size
                
                # Replace original with WebP version (keeping original filename)
                shutil.move(temp_webp, img_path)
                
                # Update database if requested
                if conn and not args.skip_database:
                    if update_database_mime_type(conn, img_path, TARGET_MIME):
                        logger.info(f"  Database updated for {img_path.name}")
                    else:
                        logger.warning(f"  Database update failed for {img_path.name}")
                
                converted_count += 1
                saved = original_size - new_size
                total_saved += saved
                
                logger.info(f"  Converted: {original_size/1024:.1f}KB → {new_size/1024:.1f}KB (saved {saved/1024:.1f}KB)")
                
            else:
                failed_count += 1
                # Restore from backup if conversion failed
                shutil.move(backup_path, img_path)
                logger.error(f"  Conversion failed, restored from backup")
                
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing {img_path}: {e}")
    
    # Close database connection
    if conn:
        conn.close()
    
    # Summary
    logger.info("Optimization complete!")
    logger.info(f"Converted: {converted_count} files")
    logger.info(f"Failed: {failed_count} files")
    logger.info(f"Total space saved: {total_saved / (1024*1024):.2f} MB")
    
    if converted_count > 0:
        logger.info(f"Backups stored in: {backup_dir}")

if __name__ == "__main__":
    main()
