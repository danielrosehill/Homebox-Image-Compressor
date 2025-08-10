# Homebox Image Compressor

A Python tool to optimize images in [Homebox](https://github.com/sysadminsmedia/homebox) inventory management systems by converting them to WebP format while preserving database mappings and UUID-based filenames.

## Features

- **Batch convert thousands of images** to WebP format for optimal compression
- **Preserve database integrity** by updating MIME types correctly
- **Maintain UUID filenames** so database mappings remain intact
- **Create automatic backups** of original files before conversion
- **Detailed logging** of the optimization process
- **Dry-run mode** to preview changes before execution

## Why Use This Tool?

Homebox stores inventory item images that can accumulate to thousands of files over time. These images are often:
- Stored as PNG files (larger file sizes)
- Have incorrect MIME types in the database (`application/octet-stream`)
- Take up significant storage space

This tool addresses all these issues while maintaining full compatibility with your existing Homebox installation.

## Installation

### Prerequisites
- Python 3.8+
- Access to Homebox Docker volumes
- PostgreSQL database access

### Setup
```bash
# Clone the repository
git clone https://github.com/danielrosehill/Homebox-Image-Compressor.git
cd Homebox-Image-Compressor

# Install dependencies
pip install -r requirements.txt

# Create your private configuration (see Configuration section)
cp config_private.py.example config_private.py
# Edit config_private.py with your settings
```

## Configuration

Create a `config_private.py` file (excluded from git) with your specific settings:

```python
# Homebox data path (Docker volume location)
HOMEBOX_DATA_PATH = "/var/lib/docker/volumes/homebox-postgres-data/_data"

# Database configuration
DB_CONFIG = {
    'host': 'localhost',  # or your database host
    'port': 5432,
    'database': 'homebox',
    'user': 'homebox',
    'password': 'your_password_here'
}
```

## Usage

### Basic Commands

```bash
# Dry run (recommended first step)
python optimize_homebox_images.py --dry-run

# Full optimization with database updates
sudo python optimize_homebox_images.py

# File conversion only (skip database updates)
sudo python optimize_homebox_images.py --skip-database

# Custom quality setting (1-100, default 85)
sudo python optimize_homebox_images.py --quality 90

# Custom backup directory
sudo python optimize_homebox_images.py --backup-dir /path/to/backups
```

### Command Line Options

- `--dry-run`: Preview what would be optimized without making changes
- `--backup-dir DIR`: Specify backup directory (default: ./backups)
- `--quality N`: WebP quality 1-100 (default: 85)
- `--skip-database`: Skip database updates (file conversion only)
- `--data-path PATH`: Override Homebox data path

## How It Works

### File Processing
1. Scans Homebox data directory for image files
2. Identifies images by extension and content analysis
3. Creates backups of original files
4. Converts images to WebP format with specified quality
5. Replaces original files while preserving UUID filenames

### Database Updates
1. Connects to PostgreSQL database
2. Updates `attachments` table `mime_type` field to `image/webp`
3. Preserves all `path` references (UUID-based filenames)
4. Maintains referential integrity

### Safety Features
- **Automatic backups**: Original files backed up before conversion
- **Rollback capability**: Failed conversions restore from backup
- **Dry run mode**: Preview all changes before execution
- **Comprehensive logging**: Detailed logs of all operations
- **Error handling**: Graceful handling of conversion failures

## Expected Results

Based on typical Homebox installations:
- **30-70% reduction** in total image storage
- **Faster image loading** in web interface
- **Proper MIME types** for all images in database
- **Maintained functionality** - all inventory items remain accessible

## Database Schema

The tool updates the `attachments` table in your Homebox database:

```sql
-- Before: Mixed MIME types
SELECT mime_type, COUNT(*) FROM attachments GROUP BY mime_type;
-- application/octet-stream | 5899
-- image/webp              | 451

-- After: Consistent WebP MIME types
-- image/webp              | 6350
```

## Safety Recommendations

1. **Create a backup** of your Homebox data before running
2. **Stop Homebox containers** during optimization to prevent conflicts
3. **Run dry-run first** to preview changes
4. **Monitor available disk space** (temporary files are created during conversion)
5. **Test with a small subset** if you have concerns

### Stopping Homebox for Optimization

```bash
# Stop Homebox containers
cd /path/to/your/homebox/deployment
docker-compose down

# Run optimization
sudo python optimize_homebox_images.py

# Restart Homebox
docker-compose up -d
```

## Troubleshooting

### Permission Issues
The script needs root access to read Docker volumes:
```bash
sudo python optimize_homebox_images.py
```

### Database Connection Errors
- Verify Homebox containers are running: `docker ps | grep homebox`
- Check database credentials in `config_private.py`
- Ensure database is accessible from your host
- Use `--skip-database` if database updates aren't needed

### Conversion Failures
- Check available disk space
- Verify image file integrity
- Review logs for specific error messages
- Use lower quality setting if memory issues occur

### Backup Recovery
If you need to restore original files:
```bash
# Restore from backups directory
cp backups/* /var/lib/docker/volumes/homebox-postgres-data/_data/path/to/documents/
```

## Performance Notes

- Processing time depends on image count and sizes
- Typical rate: 50-100 images per minute
- WebP conversion is CPU-intensive
- Database updates are fast (batch operations)
- Monitor system resources during large conversions

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool modifies your Homebox image files and database. While it includes safety features like backups and dry-run mode, always ensure you have proper backups of your data before running any optimization tools.

## Support

If you encounter issues:
1. Check the troubleshooting section
2. Review the generated log files
3. Open an issue on GitHub with details about your setup and error messages

---

**Note**: This tool is designed for Homebox installations using PostgreSQL databases. SQLite support may be added in future versions.
