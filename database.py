import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, date
from colorama import init as colorama_init, Fore
from config import Config

colorama_init(autoreset=True)


class Database:
    def __init__(self):
        db_path = getattr(Config, "DB_PATH", None)
        if not db_path:
            db_path = Path(__file__).parent / "bot.db"
        self.db_path = str(db_path)
        print(Fore.CYAN + f"[DB] Использую файл базы данных: {self.db_path}")
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _safe_execute(self, func, retries: int = 3, delay: float = 0.2):
        for attempt in range(retries):
            try:
                return func()
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < retries - 1:
                    print(Fore.YELLOW + f"[DB] База занята, повтор {attempt + 1}/{retries}")
                    time.sleep(delay * (attempt + 1))
                    continue
                raise

    def init_db(self):
        print(Fore.CYAN + "[DB] Инициализация таблиц")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    age INTEGER,
                    search_gender TEXT,
                    search_age_min INTEGER,
                    search_age_max INTEGER,
                    categories TEXT,
                    is_premium INTEGER DEFAULT 0,
                    premium_until TEXT,
                    games_played INTEGER DEFAULT 0,
                    truth_answered INTEGER DEFAULT 0,
                    dares_completed INTEGER DEFAULT 0,
                    rating REAL DEFAULT 1000.0,
                    random_search_count INTEGER DEFAULT 0,
                    random_search_last TEXT
                )
                """
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"
            )
            cursor.execute("PRAGMA table_info(users)")
            cols = {row["name"] for row in cursor.fetchall()}
            needed = {
                "gender": "gender TEXT",
                "age": "age INTEGER",
                "search_gender": "search_gender TEXT",
                "search_age_min": "search_age_min INTEGER",
                "search_age_max": "search_age_max INTEGER",
                "categories": "categories TEXT",
                "is_premium": "is_premium INTEGER DEFAULT 0",
                "premium_until": "premium_until TEXT",
                "games_played": "games_played INTEGER DEFAULT 0",
                "truth_answered": "truth_answered INTEGER DEFAULT 0",
                "dares_completed": "dares_completed INTEGER DEFAULT 0",
                "rating": "rating REAL DEFAULT 1000.0",
                "random_search_count": "random_search_count INTEGER DEFAULT 0",
                "random_search_last": "random_search_last TEXT",
            }
            for name, ddl in needed.items():
                if name not in cols:
                    print(Fore.YELLOW + f"[DB] Добавляю недостающий столбец: {name}")
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {ddl}")

    def user_exists(self, telegram_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            return cursor.fetchone() is not None

    def create_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> dict | None:
        print(Fore.GREEN + f"[DB] Регистрация пользователя {telegram_id}")
        def op():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO users (
                        telegram_id, username, first_name, last_name,
                        gender, age, search_gender, search_age_min, search_age_max,
                        categories, is_premium, premium_until,
                        games_played, truth_answered, dares_completed, rating,
                        random_search_count, random_search_last
                    ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, 0, 0, 0, 1000.0, 0, NULL)
                    """,
                    (telegram_id, username, first_name, last_name),
                )
                cursor.execute(
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        return self._safe_execute(op)

    def get_user(self, telegram_id: int) -> dict | None:
        def op():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        return self._safe_execute(op)

    def update_user(self, telegram_id: int, **kwargs):
        if not kwargs:
            return
        def op():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
                values = list(kwargs.values())
                values.append(telegram_id)
                print(
                    Fore.YELLOW
                    + f"[DB] Обновление пользователя {telegram_id}: "
                    + ", ".join(f"{k}={v}" for k, v in kwargs.items())
                )
                cursor.execute(
                    f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
                    values,
                )

        self._safe_execute(op)

    def increment_counters(
        self,
        telegram_id: int,
        games_delta: int = 0,
        truth_delta: int = 0,
        dares_delta: int = 0,
    ):
        user = self.get_user(telegram_id)
        if not user:
            return
        games = int(user.get("games_played", 0)) + games_delta
        truth = int(user.get("truth_answered", 0)) + truth_delta
        dares = int(user.get("dares_completed", 0)) + dares_delta
        from config import Config

        rating = float(user.get("rating", 1000.0)) + (
            (truth_delta + dares_delta) * Config.POINTS_PER_ACTION
        )
        self.update_user(
            telegram_id,
            games_played=games,
            truth_answered=truth,
            dares_completed=dares,
            rating=rating,
        )

    def can_use_random_search(self, telegram_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_premium, random_search_count, random_search_last FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            is_premium = int(row["is_premium"] or 0)
            if is_premium:
                return True
            count = int(row["random_search_count"] or 0)
            last_str = row["random_search_last"]
            today = date.today()
            if last_str:
                try:
                    last_date = datetime.strptime(last_str, "%Y-%m-%d").date()
                except Exception:
                    last_date = None
            else:
                last_date = None
            period_days = max(Config.FREE_SEARCH_PERIOD_DAYS, 1)
            if not last_date or (today - last_date).days >= period_days:
                cursor.execute(
                    """
                    UPDATE users
                    SET random_search_count = 1,
                        random_search_last = ?
                    WHERE telegram_id = ?
                    """,
                    (today.strftime("%Y-%m-%d"), telegram_id),
                )
                print(
                    Fore.CYAN
                    + f"[DB] Сброс лимита поиска для {telegram_id}, новая попытка 1/{Config.FREE_SEARCHES_PER_DAY}"
                )
                return True
            if count >= Config.FREE_SEARCHES_PER_DAY:
                print(Fore.CYAN + f"[DB] Лимит поиска исчерпан для {telegram_id}")
                return False
            new_count = count + 1
            cursor.execute(
                """
                UPDATE users
                SET random_search_count = ?
                WHERE telegram_id = ?
                """,
                (new_count, telegram_id),
            )
            print(
                Fore.CYAN
                + f"[DB] Поиск {telegram_id}: попытка {new_count}/{Config.FREE_SEARCHES_PER_DAY}"
            )
            return True


db = Database()
