# Telegram Bot Configuration

import os
from datetime import timezone, timedelta

# Get bot token from environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # You'll need to set this environment variable

# Time zone configuration
# Examples: 'UTC', 'Europe/London', 'US/Pacific', 'Asia/Tokyo'
# For Ukraine, use 'Europe/Kiev'
TIMEZONE = 'Europe/Kiev'

# Automatic time change settings
AUTO_DAYLIGHT_SAVINGS = True  # Set to False to disable automatic daylight savings adjustment
FIXED_UTC_OFFSET = None  # Set a fixed UTC offset (in hours) if AUTO_DAYLIGHT_SAVINGS is False
                        # Example: 2 for UTC+2, -5 for UTC-5

def get_current_timezone():
    """Get the current timezone based on configuration"""
    if not AUTO_DAYLIGHT_SAVINGS and FIXED_UTC_OFFSET is not None:
        return timezone(timedelta(hours=FIXED_UTC_OFFSET))
    return timezone.utc  # Default to UTC if no specific configuration

# File paths
TARGET_USERS_FILE = 'target_users.json'
ADMIN_USERS_FILE = 'admin_users.json'
RESPONSE_TRACKING_FILE = 'response_tracking.xlsx'
RESPONSE_DATA_FILE = 'response_data.json'

# Add message cache file path
MESSAGE_CACHE_FILE = 'message_cache.json'

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# Backup Settings
BACKUP_INTERVAL = 20  # Make backup every 20 saves
BACKUP_RETENTION_DAYS = 30  # Keep backups for 30 days
MIN_BACKUPS_TO_KEEP = 50  # Minimum number of backups to keep regardless of age 