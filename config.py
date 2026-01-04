import os
from dotenv import load_dotenv

load_dotenv()

def get_env(key: str, default=None, required=True):
    """Получить переменную окружения с валидацией"""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value

# Telegram Bot
BOT_TOKEN = get_env('BOT_TOKEN')
ADMIN_USER_ID = int(get_env('ADMIN_USER_ID'))

# PostgreSQL
DB_HOST = get_env('DB_HOST', 'database', required=False)
DB_PORT = int(get_env('DB_PORT', 5432))
DB_NAME = get_env('DB_NAME', 'trading_journal', required=False)
DB_USER = get_env('DB_USER', 'mainuser', required=False)
DB_PASSWORD = get_env('DB_PASSWORD')

# Database URL для asyncpg
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Настройки анализа (время в МСК)
ANALYSIS_HOUR = int(get_env('ANALYSIS_HOUR', 20))
WEEKLY_REPORT_DAY = int(get_env('WEEKLY_REPORT_DAY', 6))
WEEKLY_REPORT_HOUR = int(get_env('WEEKLY_REPORT_HOUR', 18))

# Теги для категоризации
STRATEGY_TAGS = ['стратегия', 'strategy', 'план', 'plan']
IMPULSE_TAGS = ['фомо', 'fomo', 'импульс', 'impulse', 'отыгрыш', 'revenge', 'тильт', 'tilt']