# Response Tracking Telegram Bot

A Telegram bot designed to track and analyze response times in conversations. The bot monitors replies between users and maintains detailed statistics.

## 📁 Project Structure
```
bot_folder/
├── config/           # Configuration files
│   ├── config.py    # Main configuration
│   ├── paths.py     # Path definitions
│   ├── admin_users.example.json  # Template for admin users
│   └── target_users.example.json # Template for target users
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

2. Set up environment variables:
```bash
# On Windows (PowerShell)
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"

# On Windows (Command Prompt)
set TELEGRAM_BOT_TOKEN=your_bot_token_here

# On Linux/macOS
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

3. Configure user access:
- Copy `config/admin_users.example.json` to `config/admin_users.json`
- Copy `config/target_users.example.json` to `config/target_users.json`
- Edit both files to include your actual user IDs

4. Configure the bot:
- Default timezone is set to 'Europe/Kiev'

5. Run the bot:
```bash
python bot.py
```

## ⚙️ Configuration

Key settings in `config/config.py`:
- `TELEGRAM_BOT_TOKEN`: Set as environment variable for security
- `TIMEZONE`: Your timezone (e.g., 'Europe/Kiev')
- `AUTO_DAYLIGHT_SAVINGS`: Enable/disable automatic DST adjustment
- `BACKUP_INTERVAL`: Create backup every X saves (default: 20)
- `BACKUP_RETENTION_DAYS`: Keep backups for X days (default: 30)
- `MIN_BACKUPS_TO_KEEP`: Minimum backups to keep (default: 50)

### Security Measures
- Bot token is stored as an environment variable
- Sensitive configuration files are excluded from version control
- User data files are kept local and not tracked in git
- Example configuration files are provided as templates

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
- `/stats` - Show response statistics

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

For support or questions, contact @yuumithecat. 

# Документація бота для відстеження відповідей в Telegram

## 1. Загальний опис
Бот призначений для відстеження та аналізу часу відповідей користувачів у Telegram. Він моніторить відповіді між користувачами, зберігає статистику та надає різноманітні інструменти для аналізу даних.

## 2. Структура проекту
/bot_folder/
├── config/           # Конфігураційні файли
│   ├── config.py    # Основні налаштування
│   ├── paths.py     # Шляхи до файлів
│   ├── admin_users.json  # Список адміністраторів
│   └── target_users.json # Список працівників
├── data/            # Дані
│   ├── backups/     # Резервні копії
│   ├── response_data.json  # Основні дані відповідей
│   ├── message_cache.json  # Кеш повідомлень
│   └── response_tracking.xlsx  # Excel звіт

## 3. Основна логіка роботи

### 3.1 Відстеження повідомлень
- Бот моніторить всі відповіді в чаті
- Фіксує лише відповіді від зареєстрованих працівників (target_users)
- Зберігає:
  * Час оригінального повідомлення
  * Час відповіді
  * Текст повідомлень
  * Інформацію про користувачів
  * Час затримки відповіді

### 3.2 Система ролей
- Адміністратори (повний доступ):
  * Управління користувачами
  * Перегляд всієї статистики
  * Експорт даних
  * Керування резервними копіями
- Працівники (обмежений доступ):
  * Перегляд власної статистики
  * Перегляд власних графіків
  * Базова інформація

### 3.3 Збереження даних
- Буферизація:
  * Нові відповіді спочатку зберігаються в буфер
  * Кожні 15 секунд дані зберігаються на диск
  * Використовується атомарне збереження через тимчасові файли
- Резервне копіювання:
  * Автоматичне створення копій кожні 20 збережень
  * Зберігання мінімум 50 останніх копій
  * Зберігання всіх копій за останні 30 днів
  * Копіювання як JSON, так і Excel файлів

### 3.4 Аналіз даних
- Статистика (/stats):
  * Загальна кількість відповідей
  * Середній час відповіді
  * Відповіді за сьогодні
  * Для адмінів: статистика по всіх працівниках
- Візуалізація (/chart):
  * Для працівників: графік власних відповідей за 7 днів
  * Для адмінів: порівняльний графік всіх працівників

### 3.5 Система команд
- Адміністративні:
  * /add_admin - Додати адміністратора
  * /remove_admin - Видалити адміністратора
  * /list_admins - Список адміністраторів
  * /add_user - Додати працівника
  * /remove_user - Видалити працівника
  * /list_users - Список працівників
  * /export - Експорт в Excel
  * /cleanup - Очищення старих даних
  * /list_backups - Список резервних копій
- Для працівників:
  * /debug - Відладочна інформація
  * /stats - Статистика
  * /chart - Графіки
- Загальні:
  * /myid - Отримати свій Telegram ID

### 3.6 Обробка помилок
- Логування всіх помилок
- Безпечне відновлення після збоїв
- Повідомлення адміністраторів про критичні помилки
- Автоматичне створення резервних копій перед ризикованими операціями

### 3.7 Безпека
- Блокування файлів для безпечного одночасного доступу
- Атомарні операції з файлами
- Перевірка прав доступу для кожної команди
- Безпечне зберігання конфігураційних даних

### 3.8 Формати даних
- JSON для основних даних:
  * Структурований формат
  * Легке читання та модифікація
  * Можливість ручного редагування
- Excel для звітів:
  * Форматований вивід
  * Зручне сортування та фільтрація
  * Готові для презентації дані

### 3.9 Часові зони
- Підтримка різних часових зон
- Автоматичне врахування переходу на літній/зимовий час
- Можливість встановлення фіксованого зміщення UTC

## 4. Технічні деталі

### 4.1 Використані бібліотеки
- python-telegram-bot: Робота з Telegram API
- pandas: Обробка та аналіз даних
- matplotlib: Створення графіків
- pytz: Робота з часовими зонами
- filelock: Блокування файлів

### 4.2 Оптимізація
- Кешування часових зон
- Буферизація відповідей
- Ефективне збереження даних
- Оптимізоване логування

### 4.3 Масштабованість
- Можливість додавання нових команд
- Розширюваність системи ролей
- Гнучке налаштування параметрів
- Модульна структура коду 