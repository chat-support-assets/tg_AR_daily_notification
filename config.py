import os
from dotenv import load_dotenv


# Загрузка переменных окружения
load_dotenv()

# Токены ботов
BOT_INR_TOKEN = os.getenv('BOT_INR_TOKEN')
BOT_OTHER_TOKEN = os.getenv('BOT_OTHER_TOKEN')

# ID таблицы Google Sheets
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Путь к JSON-ключу сервисного аккаунта
SERVICE_ACCOUNT_FILE = 'service_account.json'

# Названия листов
SHEET_TOTAL_SCORE = 'Total score'
SHEET_AR_TEXT = 'AR_text'

# Название топика в Telegram
TOPIC_NAME = 'AR'

# Файл для кэша агентов
AGENTS_CACHE_FILE = 'agents.json'

# Папка для логов
LOGS_DIR = 'logs'
LOG_FILE = 'bot.log'
LOG_RETENTION_DAYS = 3

# Диапазоны скоростей
SPEED_RANGES = {
    '94+': (94, 100),
    '90-94': (90, 94),
    '85-90': (85, 90),
    '80-84.9': (80, 84.9),
    'Ниже 80': (0, 80)
}

# Порог для отправки сообщения о 120+ минутах
THRESHOLD_120_PLUS = 2.5
