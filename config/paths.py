import os

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')

# Ensure directories exist
for directory in [DATA_DIR, CONFIG_DIR, BACKUP_DIR]:
    os.makedirs(directory, exist_ok=True)

# Data files
RESPONSE_DATA_FILE = os.path.join(DATA_DIR, 'response_data.json')
MESSAGE_CACHE_FILE = os.path.join(DATA_DIR, 'message_cache.json')
RESPONSE_TRACKING_FILE = os.path.join(DATA_DIR, 'response_tracking.xlsx')

# Config files
TARGET_USERS_FILE = os.path.join(CONFIG_DIR, 'target_users.json')
ADMIN_USERS_FILE = os.path.join(CONFIG_DIR, 'admin_users.json') 