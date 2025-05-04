import json
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
from telegram import Update, InputFile
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters, Defaults
from config import config
from config.paths import *
from filelock import FileLock
from collections import deque
import threading
import time
import pytz
from functools import lru_cache
import shutil
import os
import matplotlib.pyplot as plt
import io

# Configure logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

# Set more restrictive log levels for noisy libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('filelock').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Message cache to track conversation flow
message_cache = {}
response_buffer = deque(maxlen=100)  # Buffer for batch processing
save_lock = FileLock(f"{RESPONSE_DATA_FILE}.lock")
excel_lock = FileLock(f"{RESPONSE_TRACKING_FILE}.lock")

# Cache timezone object to avoid repeated creation
@lru_cache(maxsize=1)
def get_timezone():
    """Get timezone object with caching"""
    if config.AUTO_DAYLIGHT_SAVINGS:
        try:
            return pytz.timezone(config.TIMEZONE)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone {config.TIMEZONE}, falling back to UTC")
            return pytz.UTC
    return datetime.timezone(datetime.timedelta(hours=config.FIXED_UTC_OFFSET or 0))

def get_current_time():
    """Get current time in configured timezone efficiently"""
    tz = get_timezone()
    if config.AUTO_DAYLIGHT_SAVINGS:
        return datetime.now(tz)
    return datetime.now(tz)

def format_timestamp(dt):
    """Format timestamp consistently with timezone"""
    if not dt.tzinfo:
        dt = pytz.UTC.localize(dt)
    tz = get_timezone()
    local_dt = dt.astimezone(tz)
    return local_dt.isoformat(timespec='seconds')

def save_response_buffer():
    """Periodically save buffered responses to disk"""
    while True:
        time.sleep(15)  # Save every 15 seconds instead of 60
        if response_buffer:
            try:
                with save_lock:
                    current_data = load_response_data()
                    while response_buffer:
                        current_data.append(response_buffer.popleft())
                    save_response_data(current_data)
                logger.info(f"Batch saved {len(current_data)} responses to JSON")
            except Exception as e:
                logger.error(f"Error in batch save: {e}")

# Start background save thread
save_thread = threading.Thread(target=save_response_buffer, daemon=True)
save_thread.start()

def load_message_cache():
    try:
        with open(MESSAGE_CACHE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_message_cache(cache):
    with open(MESSAGE_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4)

# Load target users from JSON
def load_target_users():
    """Load target users from JSON file"""
    try:
        with open(TARGET_USERS_FILE, 'r') as f:
            data = json.load(f)
            # Handle both old and new format
            if isinstance(data, dict) and 'target_users' in data:
                return set(data['target_users'])
            elif isinstance(data, list):
                return set(data)
            return set()
    except FileNotFoundError:
        return set()

# Save target users to JSON
def save_target_users(target_users):
    """Save target users to JSON file"""
    with open(TARGET_USERS_FILE, 'w') as f:
        json.dump({'target_users': list(target_users)}, f, indent=4)
    logger.debug(f"Updated target users list (count: {len(target_users)})")

@lru_cache(maxsize=1)
def load_response_data():
    """Load response data with caching"""
    try:
        with save_lock:
            with open(RESPONSE_DATA_FILE, 'r') as f:
                return json.load(f)
    except FileNotFoundError:
        return []

def create_backup():
    """Create a backup of the response data file"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Backup JSON data
        json_backup = os.path.join(BACKUP_DIR, f'response_data_{timestamp}.json')
        with save_lock:
            shutil.copy2(RESPONSE_DATA_FILE, json_backup)
            
        # Backup Excel if exists
        if os.path.exists(RESPONSE_TRACKING_FILE):
            with excel_lock:
                excel_backup = os.path.join(BACKUP_DIR, f'response_tracking_{timestamp}.xlsx')
                shutil.copy2(RESPONSE_TRACKING_FILE, excel_backup)
        
        # Manage backups based on age and minimum count
        for file_type in ['.json', '.xlsx']:
            files = [(f, os.path.getmtime(os.path.join(BACKUP_DIR, f))) 
                    for f in os.listdir(BACKUP_DIR) if f.endswith(file_type)]
            # Sort by modification time, newest first
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Always keep minimum number of backups
            files_to_check = files[config.MIN_BACKUPS_TO_KEEP:]
            files_to_keep = files[:config.MIN_BACKUPS_TO_KEEP]
            
            # For the rest, keep files within retention period
            cutoff_time = time.time() - (config.BACKUP_RETENTION_DAYS * 24 * 60 * 60)
            for file_name, mtime in files_to_check:
                if mtime >= cutoff_time:
                    files_to_keep.append((file_name, mtime))
                else:
                    try:
                        os.remove(os.path.join(BACKUP_DIR, file_name))
                        logger.debug(f"Removed old backup: {file_name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove old backup {file_name}: {e}")
            
            logger.debug(f"Keeping {len(files_to_keep)} {file_type} backups")
        
        logger.info(f"Created backup: {timestamp}")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return False

def save_response_data(data):
    """Save response data with backup"""
    with save_lock:
        # First save to a temporary file
        temp_file = f"{RESPONSE_DATA_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4, default=str)
        
        # Then rename it to the actual file (atomic operation)
        os.replace(temp_file, RESPONSE_DATA_FILE)
        
        # Clear the cache to force reload on next access
        load_response_data.cache_clear()
        
        # Create more frequent backups (every 20 saves instead of 100)
        if len(data) % config.BACKUP_INTERVAL == 0:
            create_backup()
            logger.info(f"Created periodic backup (total responses: {len(data)})")
        else:
            logger.debug(f"Saved responses to file (count: {len(data)})")

# Initialize data
response_data = load_response_data()
message_cache = load_message_cache()
logger.info(f"Bot started with {len(response_data)} existing responses and {len(message_cache)} cached messages")

def load_admin_users():
    """Load admin users from JSON file"""
    try:
        with open(ADMIN_USERS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('admin_users', []))
    except FileNotFoundError:
        return set()

def save_admin_users(admin_users):
    """Save admin users to JSON file"""
    with open(ADMIN_USERS_FILE, 'w') as f:
        json.dump({'admin_users': list(admin_users)}, f, indent=4)
    logger.info(f"Saved admin users: {admin_users}")

async def check_admin(update: Update) -> bool:
    """Check if user has admin permissions"""
    user_id = update.effective_user.id
    admin_users = load_admin_users()
    if user_id not in admin_users:
        await update.message.reply_text("❌ This command requires admin privileges.")
        return False
    return True

async def check_worker(update: Update) -> bool:
    """Check if user is a tracked worker"""
    user_id = update.effective_user.id
    admin_users = load_admin_users()
    target_users = load_target_users()
    
    # Admins automatically have worker permissions
    if user_id in admin_users:
        return True
        
    if user_id not in target_users:
        await update.message.reply_text("❌ This command is only available to tracked workers and admins.")
        return False
    return True

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to show user their own ID"""
    user = update.effective_user
    user_info = f"Your Telegram ID is: {user.id}\nUsername: @{user.username or 'None'}\nFull name: {user.full_name}"
    logger.info(f"User ID request: {user_info}")
    await update.message.reply_text(user_info)

async def add_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a user to the tracking list"""
    if not await check_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Please provide a user ID to add.")
        return

    try:
        user_id = int(context.args[0])
        target_users = load_target_users()
        admin_users = load_admin_users()
        
        if user_id in admin_users:
            await update.message.reply_text(f"⚠️ User {user_id} is an admin and already has all permissions.")
            return
            
        if user_id in target_users:
            await update.message.reply_text(f"User {user_id} is already in tracking list.")
            return
            
        target_users.add(user_id)
        save_target_users(target_users)
        logger.info(f"Added user {user_id} to tracking list")
        await update.message.reply_text(f"✅ User {user_id} added to tracking list.")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user ID (number).")

async def remove_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user from the tracking list"""
    if not await check_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Please provide a user ID to remove.")
        return

    try:
        user_id = int(context.args[0])
        target_users = load_target_users()
        
        if user_id not in target_users:
            await update.message.reply_text(f"❌ User {user_id} not found in tracking list.")
            return
            
        target_users.remove(user_id)
        save_target_users(target_users)
        logger.info(f"Removed user {user_id} from tracking list")
        await update.message.reply_text(f"✅ User {user_id} removed from tracking list.")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user ID (number).")

async def list_target_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users being tracked"""
    if not await check_admin(update):
        return

    target_users = load_target_users()
    
    if not target_users:
        logger.info("No users are being tracked")
        await update.message.reply_text("📝 No users are currently being tracked.")
        return
        
    # Format the user list with usernames if available
    user_list = []
    for user_id in sorted(target_users):
        try:
            # Try to get user info from chat member
            chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            username = f"@{chat_member.user.username}" if chat_member.user.username else chat_member.user.full_name
            user_list.append(f"• {user_id} ({username})")
        except Exception:
            # If can't get user info, just show ID
            user_list.append(f"• {user_id}")
    
    users_text = "\n".join(user_list)
    message = f"📋 Currently tracking these users:\n{users_text}"
    
    logger.info(f"Currently tracking users: {target_users}")
    await update.message.reply_text(message)

def debug_message_structure(message):
    """Helper function to debug message structure"""
    debug_info = {
        'message_id': message.message_id,
        'date': str(message.date),
        'chat': {
            'id': message.chat.id,
            'type': message.chat.type
        },
        'from_user': {
            'id': message.from_user.id,
            'username': message.from_user.username
        },
        'text': message.text,
        'has_reply': message.reply_to_message is not None,
        'reply_details': None
    }
    
    # Add detailed reply information if available
    if message.reply_to_message:
        reply = message.reply_to_message
        debug_info['reply_details'] = {
            'message_id': reply.message_id,
            'from_user': {
                'id': reply.from_user.id if reply.from_user else None,
                'username': reply.from_user.username if reply.from_user else None
            },
            'text': reply.text,
            'date': str(reply.date)
        }
    
    return debug_info

def inspect_message(message):
    """Deep inspect a message object to understand its structure"""
    inspection = {
        'Basic Info': {
            'message_id': message.message_id,
            'date': str(message.date),
            'text': message.text,
            'from_user': str(message.from_user),
            'chat': str(message.chat)
        },
        'Reply Info': {
            'is_reply': message.reply_to_message is not None,
            'reply_to_message': str(message.reply_to_message) if message.reply_to_message else None
        }
    }
    
    # Add entities if present
    if message.entities:
        inspection['Entities'] = [
            {
                'type': str(entity.type),
                'offset': entity.offset,
                'length': entity.length,
                'url': getattr(entity, 'url', None),
                'user': str(getattr(entity, 'user', None))
            }
            for entity in message.entities
        ]
    
    # Add detailed reply information if it's a reply
    if message.reply_to_message:
        reply = message.reply_to_message
        inspection['Reply Details'] = {
            'original_message_id': reply.message_id,
            'original_text': reply.text,
            'original_date': str(reply.date),
            'original_sender': str(reply.from_user) if reply.from_user else None
        }
    
    return inspection

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    
    # Basic validation
    if not message or not message.from_user:
        logger.warning("Invalid message received")
        return

    try:
        # Check if user is in target list
        target_users = load_target_users()
        if user_id not in target_users:
            return

        if not message.reply_to_message:
            return

        # Get reply information with efficient timezone handling
        original_message = message.reply_to_message
        tz = get_timezone()
        response_time = get_current_time()
        question_time = original_message.date.astimezone(tz)
        
        response_info = {
            'user_id': user_id,
            'user_name': message.from_user.username or 'Unknown',
            'response_time': format_timestamp(response_time),
            'response_text': message.text,
            'chat_id': message.chat_id,
            'question_time': format_timestamp(question_time),
            'question_text': original_message.text,
            'original_message_id': original_message.message_id,
            'original_sender_id': original_message.from_user.id if original_message.from_user else None,
            'original_sender_username': original_message.from_user.username if original_message.from_user else None,
            'response_delay_seconds': (response_time - question_time).total_seconds()
        }
        
        # Add to buffer
        response_buffer.append(response_info)
        
        # Log concise tracking info
        logger.debug(f"Response tracked: User {user_id} -> Msg {original_message.message_id}")
            
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        # Send error only to admins
        admin_users = load_admin_users()
        if user_id in admin_users:
            await update.message.reply_text("❌ Error processing message. Please check logs.")

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export response data to Excel with enhanced formatting"""
    if not await check_admin(update):
        return

    # First ensure any pending responses are saved
    try:
        with save_lock:
            current_data = load_response_data()
            while response_buffer:
                current_data.append(response_buffer.popleft())
            save_response_data(current_data)
    except Exception as e:
        logger.error(f"Pre-export save failed: {str(e)}")
        await update.message.reply_text("❌ Error saving pending responses before export.")
        return

    if not current_data:
        logger.info("Export requested - no data available")
        await update.message.reply_text("No response data available.")
        return

    try:
        # Create DataFrame with better column names and organization
        df = pd.DataFrame(current_data)
        
        # Rename columns for better readability
        column_mapping = {
            'user_id': 'Responder ID',
            'user_name': 'Responder Username',
            'response_time': 'Response Time',
            'response_text': 'Response Message',
            'chat_id': 'Chat ID',
            'question_time': 'Original Message Time',
            'question_text': 'Original Message',
            'original_message_id': 'Original Message ID',
            'original_sender_id': 'Original Sender ID',
            'original_sender_username': 'Original Sender Username',
            'response_delay_seconds': 'Response Delay (seconds)'
        }
        df = df.rename(columns=column_mapping)
        
        # Add calculated columns
        df['Response Delay (minutes)'] = df['Response Delay (seconds)'] / 60
        df['Response Delay (hours)'] = df['Response Delay (seconds)'] / 3600
        
        # Convert timestamp columns to datetime
        for col in ['Response Time', 'Original Message Time']:
            df[col] = pd.to_datetime(df[col])
        
        # Format timestamp columns
        df['Response Time'] = df['Response Time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['Original Message Time'] = df['Original Message Time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Round delay columns
        df['Response Delay (seconds)'] = df['Response Delay (seconds)'].round(2)
        df['Response Delay (minutes)'] = df['Response Delay (minutes)'].round(2)
        df['Response Delay (hours)'] = df['Response Delay (hours)'].round(2)
        
        # Reorder columns for better readability
        column_order = [
            'Response Time',
            'Responder Username',
            'Responder ID',
            'Response Message',
            'Original Message Time',
            'Original Sender Username',
            'Original Sender ID',
            'Original Message',
            'Response Delay (seconds)',
            'Response Delay (minutes)',
            'Response Delay (hours)',
            'Chat ID',
            'Original Message ID'
        ]
        df = df[column_order]
        
        # Create Excel writer with xlsxwriter engine for better formatting
        with excel_lock:
            with pd.ExcelWriter(RESPONSE_TRACKING_FILE, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Response Data', index=False)
                
                # Get workbook and worksheet objects for formatting
                workbook = writer.book
                worksheet = writer.sheets['Response Data']
                
                # Define formats
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#D9E1F2',
                    'border': 1,
                    'text_wrap': True,
                    'valign': 'vcenter',
                    'align': 'center'
                })
                
                cell_format = workbook.add_format({
                    'text_wrap': True,
                    'valign': 'vcenter',
                    'align': 'left',
                    'border': 1
                })
                
                # Set column widths and apply formats
                for idx, col in enumerate(df.columns):
                    series = df[col]
                    max_len = max(
                        series.astype(str).apply(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(idx, idx, min(max_len, 50), cell_format)
                
                # Apply header format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Freeze the header row
                worksheet.freeze_panes(1, 0)
                
                # Add autofilter
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        
        logger.info(f"Exported {len(current_data)} responses to Excel")
        await update.message.reply_text(
            f"✅ Export complete:\n"
            f"• Responses: {len(current_data)}\n"
            f"• File: {RESPONSE_TRACKING_FILE}"
        )
        
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        await update.message.reply_text("❌ Export failed. Check logs for details.")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comprehensive debug command with useful information for workers"""
    if not await check_worker(update):
        return

    message = update.message
    user_id = message.from_user.id
    tz = get_timezone()
    current_time = get_current_time()

    # Basic user info
    debug_text = [
        "🔍 Debug Information:",
        f"\n👤 Your Information:",
        f"• ID: {user_id}",
        f"• Username: @{message.from_user.username or 'None'}",
        f"• Full name: {message.from_user.full_name}",
        f"• Current time: {format_timestamp(current_time)}",
        f"• Time zone: {tz.zone if hasattr(tz, 'zone') else f'UTC{tz.utcoffset(None)}'}",
    ]

    # Role information
    admin_users = load_admin_users()
    target_users = load_target_users()
    roles = []
    if user_id in admin_users:
        roles.append("Admin")
    if user_id in target_users:
        roles.append("Worker")
    debug_text.extend([
        f"\n🎭 Your Roles: {', '.join(roles)}",
        f"• Permissions: {', '.join(get_user_permissions(user_id))}"
    ])

    # Message context
    if message.reply_to_message:
        reply = message.reply_to_message
        reply_time = reply.date.astimezone(tz)
        debug_text.extend([
            f"\n💬 Reply Context:",
            f"• Original message ID: {reply.message_id}",
            f"• Original sender: @{reply.from_user.username if reply.from_user else 'Unknown'}",
            f"• Original time: {format_timestamp(reply_time)}",
            f"• Time since original: {format_time_delta(current_time - reply_time)}"
        ])

    # Statistics if available
    try:
        with open(RESPONSE_DATA_FILE, 'r') as f:
            response_data = json.load(f)
            user_responses = [r for r in response_data if r['user_id'] == user_id]
            if user_responses:
                avg_response_time = sum(float(r['response_delay_seconds']) for r in user_responses) / len(user_responses)
                debug_text.extend([
                    f"\n📊 Your Statistics:",
                    f"• Total responses: {len(user_responses)}",
                    f"• Average response time: {format_time_delta(avg_response_time)}"
                ])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    await update.message.reply_text("\n".join(debug_text))

def get_user_permissions(user_id: int) -> list:
    """Get list of permissions for a user"""
    permissions = ["View own stats"]
    if user_id in load_admin_users():
        permissions.extend([
            "Manage users",
            "Export data",
            "View all stats",
            "Manage admins"
        ])
    if user_id in load_target_users() or user_id in load_admin_users():
        permissions.extend([
            "Debug access",
            "Response tracking"
        ])
    return permissions

def format_time_delta(seconds: float) -> str:
    """Format time delta in a human-readable way"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics"""
    user_id = update.effective_user.id
    is_admin = user_id in load_admin_users()
    
    try:
        with open(RESPONSE_DATA_FILE, 'r') as f:
            response_data = json.load(f)
            
        if not is_admin and user_id not in load_target_users():
            await update.message.reply_text("❌ You don't have permission to view statistics.")
            return
            
        # Filter data based on permissions
        if is_admin:
            data_to_analyze = response_data
            title = "📊 Overall Statistics:"
        else:
            data_to_analyze = [r for r in response_data if r['user_id'] == user_id]
            title = "📊 Your Statistics:"
            
        if not data_to_analyze:
            await update.message.reply_text("No response data available.")
            return
            
        # Calculate statistics
        total_responses = len(data_to_analyze)
        avg_response_time = sum(float(r['response_delay_seconds']) for r in data_to_analyze) / total_responses
        
        # Group by date
        today = datetime.now().date()
        today_responses = [r for r in data_to_analyze 
                         if datetime.fromisoformat(r['response_time'].replace('Z', '+00:00')).date() == today]
        
        stats_text = [
            title,
            f"• Total responses: {total_responses}",
            f"• Average response time: {format_time_delta(avg_response_time)}",
            f"• Responses today: {len(today_responses)}"
        ]
        
        if is_admin:
            unique_workers = len(set(r['user_id'] for r in data_to_analyze))
            stats_text.extend([
                f"• Active workers: {unique_workers}",
                f"• Total tracked messages: {len(response_data)}"
            ])
            
        await update.message.reply_text("\n".join(stats_text))
            
    except Exception as e:
        logger.error(f"Error generating stats: {str(e)}")
        await update.message.reply_text("❌ Error generating statistics. Please try again later.")

async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate response time visualization"""
    user_id = update.effective_user.id
    is_admin = user_id in load_admin_users()
    
    if not await check_worker(update):
        return
    
    try:
        with open(RESPONSE_DATA_FILE, 'r') as f:
            response_data = json.load(f)
            
        if is_admin:
            data_to_analyze = response_data
            # Create visualization for all workers
            plt.figure(figsize=(12, 6))
            plt.clf()  # Clear the current figure
            
            # Calculate average response times per worker
            worker_stats = {}
            for worker_id in set(r['user_id'] for r in data_to_analyze):
                worker_responses = [r for r in data_to_analyze if r['user_id'] == worker_id]
                avg_time = sum(float(r['response_delay_seconds']) for r in worker_responses) / len(worker_responses)
                worker_name = worker_responses[0]['user_name']
                worker_stats[worker_name] = avg_time / 60  # Convert to minutes
            
            # Create bar chart
            workers = list(worker_stats.keys())
            times = list(worker_stats.values())
            
            plt.bar(workers, times, color='skyblue')
            plt.title('Average Response Time by Worker')
            plt.xlabel('Worker Username')
            plt.ylabel('Average Response Time (minutes)')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            
            # Send chart
            await update.message.reply_photo(
                photo=InputFile(buf, filename='response_times.png'),
                caption="📊 Average response times for all workers"
            )
            
            # Clean up
            plt.close()
            buf.close()
        else:
            # For individual workers, show their own stats
            data_to_analyze = [r for r in response_data if r['user_id'] == user_id]
            
            if not data_to_analyze:
                await update.message.reply_text("No response data available.")
                return
                
            plt.figure(figsize=(8, 4))
            plt.clf()
            
            # Calculate daily average response times for the last 7 days
            daily_stats = {}
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=6)
            
            current_date = start_date
            while current_date <= end_date:
                day_responses = [r for r in data_to_analyze 
                               if datetime.fromisoformat(r['response_time'].replace('Z', '+00:00')).date() == current_date]
                if day_responses:
                    avg_time = sum(float(r['response_delay_seconds']) for r in day_responses) / len(day_responses)
                    daily_stats[current_date.strftime('%Y-%m-%d')] = avg_time / 60  # Convert to minutes
                else:
                    daily_stats[current_date.strftime('%Y-%m-%d')] = 0
                current_date += timedelta(days=1)
            
            # Create bar chart
            dates = list(daily_stats.keys())
            times = list(daily_stats.values())
            
            plt.bar(dates, times, color='lightgreen')
            plt.title('Your Average Response Time (Last 7 Days)')
            plt.xlabel('Date')
            plt.ylabel('Average Response Time (minutes)')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            
            # Send chart
            await update.message.reply_photo(
                photo=InputFile(buf, filename='response_times.png'),
                caption="📊 Your response times over the last 7 days"
            )
            
            # Clean up
            plt.close()
            buf.close()
            
    except Exception as e:
        logger.error(f"Error generating chart: {str(e)}")
        await update.message.reply_text("❌ Error generating chart. Please try again later.")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a user to admin list"""
    if not await check_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Please provide a user ID to add as admin.")
        return

    try:
        user_id = int(context.args[0])
        admin_users = load_admin_users()
        target_users = load_target_users()
        
        if user_id in admin_users:
            await update.message.reply_text(f"User {user_id} is already an admin.")
            return
            
        # If user was a worker, remove them from workers list
        if user_id in target_users:
            target_users.remove(user_id)
            save_target_users(target_users)
            logger.info(f"Removed user {user_id} from workers (promoted to admin)")
            
        admin_users.add(user_id)
        save_admin_users(admin_users)
        logger.info(f"Added user {user_id} to admin list")
        await update.message.reply_text(f"✅ User {user_id} added as admin.")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user ID (number).")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user from admin list"""
    if not await check_admin(update):
        return

    if not context.args:
        await update.message.reply_text("Please provide a user ID to remove from admins.")
        return

    try:
        user_id = int(context.args[0])
        admin_users = load_admin_users()
        
        if user_id not in admin_users:
            await update.message.reply_text(f"❌ User {user_id} is not an admin.")
            return
            
        admin_users.remove(user_id)
        save_admin_users(admin_users)
        logger.info(f"Removed user {user_id} from admin list")
        await update.message.reply_text(f"✅ User {user_id} removed from admins.")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user ID (number).")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admin users"""
    if not await check_admin(update):
        return
        
    admin_users = load_admin_users()
    
    if not admin_users:
        await update.message.reply_text("📝 No admin users configured.")
        return
        
    admin_list = []
    for user_id in sorted(admin_users):
        try:
            chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            username = f"@{chat_member.user.username}" if chat_member.user.username else chat_member.user.full_name
            admin_list.append(f"• {user_id} ({username})")
        except Exception:
            admin_list.append(f"• {user_id}")
    
    message = "👑 Admin users:\n" + "\n".join(admin_list)
    await update.message.reply_text(message)

async def cleanup_old_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to clean up old response data"""
    if not await check_admin(update):
        return
        
    try:
        days = int(context.args[0]) if context.args else 30
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        with save_lock:
            data = load_response_data()
            original_count = len(data)
            
            # Filter out old responses
            data = [r for r in data if datetime.fromisoformat(r['response_time'].replace('Z', '+00:00')) > cutoff_date]
            
            # Create backup before cleanup
            if create_backup():
                save_response_data(data)
                removed_count = original_count - len(data)
                await update.message.reply_text(
                    f"✅ Cleanup complete:\n"
                    f"• Removed {removed_count} old responses\n"
                    f"• Kept {len(data)} responses\n"
                    f"• Backup created"
                )
            else:
                await update.message.reply_text("❌ Cleanup aborted: backup creation failed")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        await update.message.reply_text("❌ Error during cleanup. Check logs for details.")

async def list_backups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to list available backups"""
    if not await check_admin(update):
        return
        
    try:
        backup_info = []
        for file_type in ['.json', '.xlsx']:
            files = [(f, os.path.getmtime(os.path.join(BACKUP_DIR, f))) 
                    for f in os.listdir(BACKUP_DIR) if f.endswith(file_type)]
            files.sort(key=lambda x: x[1], reverse=True)
            
            if files:
                backup_info.append(f"\n{file_type.upper()} Backups:")
                for filename, mtime in files[:5]:  # Show 5 most recent
                    date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    backup_info.append(f"• {filename} ({date})")
                backup_info.append(f"Total {file_type} backups: {len(files)}")
        
        if backup_info:
            await update.message.reply_text("\n".join(backup_info))
        else:
            await update.message.reply_text("No backups found.")
            
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        await update.message.reply_text("❌ Error listing backups. Check logs for details.")

def main():
    """Start the bot."""
    # Ensure required files exist with proper structure
    default_files = {
        RESPONSE_DATA_FILE: [],
        MESSAGE_CACHE_FILE: {},
        TARGET_USERS_FILE: {'target_users': []},
        ADMIN_USERS_FILE: {'admin_users': []}
    }
    
    for file_path, default_content in default_files.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_content, f, indent=4)
                logger.debug(f"Created missing file: {file_path}")

    defaults = Defaults(
        parse_mode='HTML',
        allow_sending_without_reply=True
    )
    
    try:
        application = (
            Application.builder()
            .token(config.BOT_TOKEN)
            .defaults(defaults)
            .get_updates_http_version('1.1')
            .http_version('1.1')
            .build()
        )

        # Admin commands
        application.add_handler(CommandHandler("add_admin", add_admin))
        application.add_handler(CommandHandler("remove_admin", remove_admin))
        application.add_handler(CommandHandler("list_admins", list_admins))
        application.add_handler(CommandHandler("add_user", add_target_user))
        application.add_handler(CommandHandler("remove_user", remove_target_user))
        application.add_handler(CommandHandler("list_users", list_target_users))
        application.add_handler(CommandHandler("export", export_data))
        application.add_handler(CommandHandler("cleanup", cleanup_old_data))
        application.add_handler(CommandHandler("list_backups", list_backups))

        # Worker commands
        application.add_handler(CommandHandler("debug", debug))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("chart", chart))

        # Public commands
        application.add_handler(CommandHandler("myid", get_my_id))
        
        # Message handler
        message_handler = MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
        application.add_handler(message_handler)

        # Error handler
        application.add_error_handler(error_handler)

        # Start the bot
        logger.info("Bot started - ready to track responses")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.critical(f"Bot startup failed: {str(e)}")
        raise

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred while processing your request. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

if __name__ == '__main__':
    main() 