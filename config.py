import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    # Telegram
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        print("ОШИБКА: BOT_TOKEN не указан в .env файле!")
        sys.exit(1)

    ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []

    # Database
    DB_PATH = Path(__file__).parent / 'data' / 'bot.db'
    DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DB_PATH}')

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Пути
    BASE_DIR = Path(__file__).parent
    LOGS_DIR = BASE_DIR / 'logs'
    DATA_DIR = BASE_DIR / 'data'

    # Создаем директории если их нет
    LOGS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    # Настройки игры
    MAX_PLAYERS_PER_GAME = 10
    GAME_TIMEOUT = 300  # 5 минут
    # Ограничения бесплатного поиска:
    # FREE_SEARCHES_PER_DAY — сколько бесплатных попыток даётся внутри одного периода.
    # FREE_SEARCH_PERIOD_DAYS — длина периода (в днях), после которого лимит обнуляется.
    FREE_SEARCHES_PER_DAY = int(os.getenv("FREE_SEARCHES_PER_DAY", 3))
    FREE_SEARCH_PERIOD_DAYS = int(os.getenv("FREE_SEARCH_PERIOD_DAYS", 1))

    # Категории
    CATEGORIES = {
        'acquaintance': '👋 Знакомство',
        'flirt': '😘 Флирт',
        'sexy': '🔥 Сексуальное (18+)',
        'extreme': '💀 Экстрим (18+)',
        'funny': '😂 Смешное'
    }

    # Премиум настройки
    SUBSCRIPTION_PRICES = {
        '1': 99,    # 1 месяц (историческая цена в рублях)
        '3': 249,   # 3 месяца
        '12': 799   # 12 месяцев
    }

    # Оплата премиума через Telegram Stars
    STAR_PROVIDER_TOKEN = os.getenv('STAR_PROVIDER_TOKEN') or ''
    PREMIUM_STAR_PRICES = {
        '1': 300,    # 1 месяц — 300⭐
        '3': 800,    # 3 месяца — 800⭐
        '12': 2500,  # 12 месяцев — 2500⭐
    }

    # Очки
    POINTS_PER_ACTION = int(os.getenv('POINTS_PER_ACTION', 5))

    # Контакты разработчика
    DEVELOPER_CONTACT = os.getenv('DEVELOPER_CONTACT', '@xauspro')
