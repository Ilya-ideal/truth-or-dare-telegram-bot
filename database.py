import sqlite3
import redis
import json
from pathlib import Path
from config import Config
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self.redis_client = redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)
        self.init_db()
        
    def init_db(self):
        """Инициализация базы данных SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создание таблиц
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    age INTEGER,
                    language TEXT DEFAULT 'ru',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_premium BOOLEAN DEFAULT 0,
                    premium_until TIMESTAMP,
                    games_played INTEGER DEFAULT 0,
                    truth_answered INTEGER DEFAULT 0,
                    dares_completed INTEGER DEFAULT 0,
                    rating REAL DEFAULT 1000.0,
                    preferred_gender TEXT,
                    min_age INTEGER DEFAULT 18,
                    max_age INTEGER DEFAULT 60,
                    categories TEXT DEFAULT '["acquaintance", "flirt"]',
                    current_game_id INTEGER,
                    waiting_for_game BOOLEAN DEFAULT 0,
                    last_search TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT,
                    status TEXT DEFAULT 'waiting',
                    categories TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    current_player_id INTEGER,
                    creator_id INTEGER,
                    current_round INTEGER DEFAULT 0,
                    max_rounds INTEGER DEFAULT 10,
                    turn_order TEXT,
                    used_questions TEXT DEFAULT '[]',
                    used_dares TEXT DEFAULT '[]'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER,
                    user_id INTEGER,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    score INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (game_id) REFERENCES games (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    difficulty INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'ru',
                    is_active BOOLEAN DEFAULT 1,
                    rating REAL DEFAULT 0.0,
                    times_used INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    difficulty INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'ru',
                    requires_proof BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    rating REAL DEFAULT 0.0,
                    times_used INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT DEFAULT 'RUB',
                    provider_payment_id TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Создание индексов
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_waiting ON users(waiting_for_game)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_games_status ON games(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id)')
            
            # Заполнение начальными данными
            self._seed_initial_data(cursor)
            
            conn.commit()
            logger.info("База данных успешно инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
        finally:
            conn.close()
    
    def _seed_initial_data(self, cursor):
        """Заполнение начальными вопросами и действиями"""
        from questions_actions import QUESTIONS, DARES
        
        # Проверяем, есть ли уже вопросы
        cursor.execute("SELECT COUNT(*) FROM questions")
        if cursor.fetchone()[0] == 0:
            logger.info("Добавление начальных вопросов...")
            for category, questions_list in QUESTIONS.items():
                for question in questions_list:
                    cursor.execute(
                        "INSERT INTO questions (text, category) VALUES (?, ?)",
                        (question, category)
                    )
        
        # Проверяем, есть ли уже действия
        cursor.execute("SELECT COUNT(*) FROM dares")
        if cursor.fetchone()[0] == 0:
            logger.info("Добавление начальных действий...")
            for category, dares_list in DARES.items():
                for dare in dares_list:
                    requires_proof = 1 if any(word in dare.lower() for word in ['сним', 'фото', 'видео', 'докажи']) else 0
                    cursor.execute(
                        "INSERT INTO dares (text, category, requires_proof) VALUES (?, ?, ?)",
                        (dare, category, requires_proof)
                    )
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с базой"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа по имени столбца
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def cache_get(self, key):
        """Получение данных из кеша Redis"""
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Ошибка чтения из кеша: {e}")
        return None
    
    def cache_set(self, key, value, expire=3600):
        """Сохранение данных в кеш Redis"""
        try:
            self.redis_client.setex(key, expire, json.dumps(value))
        except Exception as e:
            logger.error(f"Ошибка записи в кеш: {e}")
    
    def cache_delete(self, key):
        """Удаление данных из кеша Redis"""
        try:
            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Ошибка удаления из кеша: {e}")
    
    def user_exists(self, telegram_id):
        """Проверка существования пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            return cursor.fetchone() is not None
    
    def get_user(self, telegram_id):
        """Получение пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None
    
    def create_user(self, telegram_id, username, first_name, last_name):
        """Создание нового пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO users 
                   (telegram_id, username, first_name, last_name) 
                   VALUES (?, ?, ?, ?)""",
                (telegram_id, username, first_name, last_name)
            )
            return cursor.lastrowid
    
    def update_user(self, telegram_id, **kwargs):
        """Обновление данных пользователя"""
        if not kwargs:
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
            values = list(kwargs.values())
            values.append(telegram_id)
            
            cursor.execute(
                f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
                values
            )

# Глобальный экземпляр базы данных
db = Database()