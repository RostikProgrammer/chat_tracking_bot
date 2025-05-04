# Response Tracking Telegram Bot

A Telegram bot designed to track and analyze response times in conversations. The bot monitors replies between users and maintains detailed statistics.

## 📁 Project Structure
```
bot_folder/
├── config/           # Configuration files
│   ├── config.py    # Main configuration
│   ├── paths.py     # Path definitions
│   ├── admin_users.json
│   └── target_users.json
├── data/            # Data storage
│   ├── backups/     # Automatic backups
│   ├── response_data.json
│   ├── message_cache.json
│   └── response_tracking.xlsx
└── bot.py           # Main bot script
```


## 🚀 Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the bot:
- Edit `config/config.py` to set your bot token and preferences
- Default timezone is set to 'Europe/Kiev'

3. Run the bot:
```bash
python bot.py
```

## ⚙️ Configuration

Key settings in `config/config.py`:
- `BOT_TOKEN`: Your Telegram bot token
- `TIMEZONE`: Your timezone (e.g., 'Europe/Kiev')
- `AUTO_DAYLIGHT_SAVINGS`: Enable/disable automatic DST adjustment
- `BACKUP_INTERVAL`: Create backup every X saves (default: 20)
- `BACKUP_RETENTION_DAYS`: Keep backups for X days (default: 30)
- `MIN_BACKUPS_TO_KEEP`: Minimum backups to keep (default: 50)

## 💾 Backup System

The bot includes a robust backup system:
- Automatic backups every 20 saves
- Keeps minimum 50 recent backups
- Retains all backups from last 30 days
- Backs up both JSON data and Excel reports
- Creates backups before risky operations

### Backup Commands
- `/list_backups` - Show available backups
- `/export` - Generate Excel report

## 🛠 Commands

### Admin Commands
- `/add_admin <user_id>` - Add admin user
- `/remove_admin <user_id>` - Remove admin user
- `/list_admins` - List all admins
- `/add_user <user_id>` - Add tracked user
- `/remove_user <user_id>` - Remove tracked user
- `/list_users` - List tracked users
- `/export` - Export data to Excel
- `/cleanup [days]` - Remove old data
- `/list_backups` - Show backup status

### Worker Commands
- `/debug` - Show debug information
- `/stats` - Show text-based response statistics
- `/chart` - Generate visual response time charts

### Public Commands
- `/myid` - Get your Telegram ID

## 📊 Data Management

The bot tracks:
- Response times between messages
- User interaction statistics
- Message context and content
- User activity patterns

Data is stored in:
- `response_data.json`: Raw response data
- `response_tracking.xlsx`: Formatted Excel report
- Regular backups in `data/backups/`

## 🔒 Security Features

- File locking for safe concurrent access
- Atomic file operations
- Role-based access control
- Secure backup management
- Private logging and notifications

## 📋 Logging

The bot maintains detailed logs:
- Response tracking
- User actions
- System operations
- Backup status
- Error reporting

## ⚠️ Error Handling

The bot includes:
- Comprehensive error catching
- Admin notifications for issues
- Safe data recovery options
- Automatic backup before risky operations

## 🔄 Maintenance

Regular maintenance tasks:
1. Check `/list_backups` for backup status
2. Use `/export` to create Excel reports
3. Monitor disk space in `data/backups/`
4. Review logs for any issues
5. Use `/cleanup` to manage old data

## 📝 Notes

- Keep your bot token secure
- Regularly check backup integrity
- Monitor disk space usage
- Update user permissions as needed
- Review logs periodically

For support or questions, contact the bot administrator. 
