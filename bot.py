#!/usr/bin/env python3
import logging
import re
from datetime import datetime, timedelta
from telegram import LabeledPrice, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from config import Config
from database import db
from game_logic import GameLogic
from keyboards import (
    main_menu,
    game_type_keyboard,
    categories_keyboard,
    premium_keyboard,
    game_action_keyboard,
    friend_invite_keyboard,
    friend_owner_keyboard,
    friend_mode_keyboard,
    search_preferences_keyboard,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
for noisy_logger in ["httpx", "httpcore", "telegram", "apscheduler"]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def log_action(message: str):
    logger.info("[GAME] %s", message)


class TruthOrDareBot:
    def __init__(self):
        log_action("Инициализация бота 'Правда или Действие'")
        self.game_logic = GameLogic(db)
        self.message_owners = {}
        self.pending_answers = {}

    def register_owned_message(self, message, owner_id: int):
        if not message:
            return
        key = (message.chat.id, message.message_id)
        self.message_owners[key] = owner_id
        log_action(f"Привязка сообщения {key} к пользователю {owner_id}")

    def _load_user(self, telegram_id: int, user) -> tuple[dict, list]:
        user_data = db.get_user(telegram_id)
        if not user_data:
            db.create_user(
                telegram_id,
                getattr(user, "username", None),
                getattr(user, "first_name", None),
                getattr(user, "last_name", None),
            )
            user_data = db.get_user(telegram_id)
        categories_raw = (user_data or {}).get("categories")
        categories = None
        if categories_raw:
            try:
                categories = eval(categories_raw)
            except Exception:
                categories = None
        return user_data, categories or ["acquaintance", "flirt"]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        telegram_id = user.id
        if chat.type != "private":
            await update.message.reply_text(
                "Чтобы играть, открой со мной личный чат и нажми /start."
            )
            return
        if not db.user_exists(telegram_id):
            db.create_user(
                telegram_id,
                user.username,
                user.first_name,
                user.last_name,
            )
            logger.info(f"Новый пользователь: {telegram_id} - {user.username}")
            msg = await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n"
                f"Добро пожаловать в игру «Правда или Действие»!\n\n"
                f"Доступные режимы:\n"
                f"• 🎲 Случайный соперник\n"
                f"• 👥 Игра с друзьями (комнаты до 10 человек)\n"
                f"• 🔍 Поиск по полу (премиум)\n\n"
                f"Выбери действие через меню ниже.",
                reply_markup=main_menu(),
            )
        else:
            msg = await update.message.reply_text(
                f"С возвращением, {user.first_name}! 🎮\n"
                f"Выбери действие:",
                reply_markup=main_menu(),
            )
        self.register_owned_message(msg, user.id)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        text = (update.message.text or "").strip()
        user = update.effective_user
        logger.info(f"Сообщение от {user.id} в чате {chat.id} ({chat.type}): {text}")
        log_action(f"Обработка сообщения от {user.id}: {text}")

        pending = context.user_data.get("pending_answer") or self.pending_answers.get(user.id)

        if pending:
            game_id = pending["game_id"]
            player_id = pending["player_id"]
            player_name = pending["player_name"]
            answer_text = update.message.text
            log_action(f"Ответ игрока {player_name} ({player_id}) в игре {game_id}: {answer_text}")

            game = self.game_logic.get_game_by_id(game_id)
            if not game:
                context.user_data["pending_answer"] = None
                self.pending_answers.pop(user.id, None)
                return

            # Формируем сообщение
            broadcast = (
                f"💬 {player_name} ответил(а):\n"
                f"{answer_text}"
            )

            # Рассылаем всем участникам комнаты
            for uid in game.players:
                # Автор ответа уже видит своё сообщение, отправим ему только подтверждение
                if uid == player_id:
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text="✅ Ответ получен.",
                        )
                    except Exception as e:
                        logger.error(
                            f"Не удалось отправить подтверждение игроку {uid}: {e}"
                        )
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=broadcast,
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить ответ игроку {uid}: {e}")

            # Очищаем ожидание ответа
            context.user_data["pending_answer"] = None
            self.pending_answers.pop(user.id, None)

            # Переход хода
            next_player = self.game_logic.next_turn_random(game_id)
            log_action(f"Передача хода в игре {game_id}. Следующий игрок: {next_player}")

            # Уведомления игрокам
            for uid in game.players:
                if uid == next_player:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="Теперь *твой ход*.\nВыбирай:\n🗣 Правда или 🎭 Действие",
                        parse_mode="Markdown",
                        reply_markup=game_action_keyboard(game_id, True),
                    )
                else:
                        await context.bot.send_message(
                            chat_id=uid,
                            text="Ход другого игрока.",
                        )
            return

        if context.user_data.get("awaiting_join_code"):
            code = (text or "").strip().upper()
            context.user_data.pop("awaiting_join_code", None)
            success, msg_text, game_state = self.game_logic.join_friend_game(code, user.id)
            if not success:
                await update.message.reply_text(f"❌ {msg_text}")
                return
            log_action(
                f"Игрок {user.id} присоединился к комнате {game_state.invite_code}. "
                f"Онлайн: {len(game_state.players)}/{game_state.max_players}"
            )
            await update.message.reply_text(
                self._join_success_text(game_state),
                reply_markup=main_menu(),
                parse_mode="HTML",
            )
            await self._broadcast_room_join(game_state, context, update.effective_user)
            return

        awaited_game_id = context.user_data.get("awaiting_friend_players")
        if awaited_game_id:
            state = self.game_logic.get_game_by_id(awaited_game_id)
            if not state or state.host_id != user.id:
                context.user_data.pop("awaiting_friend_players", None)
            else:
                try:
                    desired = int(text)
                except Exception:
                    await update.message.reply_text("Отправь число игроков от 2 до 10 или /cancel.")
                    return
                desired = max(2, min(desired, 10))
                state.max_players = desired
                context.user_data.pop("awaiting_friend_players", None)
                log_action(
                    f"Создатель {user.id} установил лимит игроков {desired} для комнаты {state.invite_code}"
                )
                await update.message.reply_text(
                    f"Лимит игроков установлен: {desired}. Рассылай код и жми \"Начать игру\" когда будете готовы.",
                    reply_markup=main_menu(),
                )
                return
        if text.lower() == "/cancel":
            context.user_data.pop("awaiting_age_input", None)
            context.user_data.pop("awaiting_search_age_input", None)
            await update.message.reply_text(
                "Действие отменено. Возвращаю меню.", reply_markup=main_menu()
            )
            return
        awaiting_age = context.user_data.get("awaiting_age_input")
        if awaiting_age or text.isdigit():
            if text.isdigit():
                age_value = int(text)
                if 10 <= age_value <= 100:
                    db.update_user(user.id, age=age_value)
                    context.user_data.pop("awaiting_age_input", None)
                    await update.message.reply_text(
                        f"Возраст обновлён: {age_value}", reply_markup=main_menu()
                    )
                    return
            if awaiting_age:
                await update.message.reply_text(
                    "Отправь возраст числом от 10 до 100 или /cancel для выхода.",
                )
                return
        if context.user_data.get("awaiting_search_age_input"):
            numbers = [int(n) for n in re.findall(r"\d+", text)]
            if numbers:
                if len(numbers) == 1:
                    min_age = max_age = numbers[0]
                else:
                    min_age, max_age = numbers[0], numbers[1]
                    if min_age > max_age:
                        min_age, max_age = max_age, min_age
                db.update_user(user.id, search_age_min=min_age, search_age_max=max_age)
                context.user_data.pop("awaiting_search_age_input", None)
                await update.message.reply_text(
                    f"Диапазон для поиска сохранён: {min_age}-{max_age}",
                    reply_markup=main_menu(),
                )
                return
            await update.message.reply_text(
                "Укажи возрастной диапазон в формате 18-30 или одно число, либо /cancel.",
            )
            return
        if chat.type != "private":
            await update.message.reply_text(
                "Играть с ботом можно только в личных сообщениях.\n"
                "Открой со мной диалог @truth_or_1dare_game_bot и нажми /start."
            )
            return
        if text == "🎮 Найти игру":
            msg = await update.message.reply_text(
                "Выбери тип игры:",
                reply_markup=game_type_keyboard(),
            )
            self.register_owned_message(msg, user.id)
            return
        if text == "👥 С друзьями":
            msg = await update.message.reply_text(
                "Выбери вариант:", reply_markup=friend_mode_keyboard()
            )
            self.register_owned_message(msg, user.id)
            return
        if text == "🔍 Поиск по полу":
            await self.start_gender_search_menu(update, context)
            return
        if text == "📊 Статистика":
            await self.show_stats(update, context)
            return
        if text == "⭐ Премиум":
            msg = await update.message.reply_text(
                "⭐ Премиум подписка открывает дополнительные возможности:\n"
                "• безлимитный поиск случайных игр\n"
                "• поиск по полу и возрасту\n"
                "• приоритет в матчмейкинге\n\n"
                "Выбери вариант:",
                reply_markup=premium_keyboard(),
            )
            self.register_owned_message(msg, user.id)
            return
        if text == "⚙️ Настройки":
            await self.show_settings(update, context)
            return
        if text == "📞 Поддержка":
            await update.message.reply_text(
                f"Если у тебя есть вопросы или предложения — напиши разработчику: {Config.DEVELOPER_CONTACT}",
            )
            return
        return

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        chat = query.message.chat
        data = query.data or ""
        user = query.from_user
        telegram_id = user.id
        if chat.type != "private":
            await query.answer(
                "Играть можно только в личных сообщениях.\n"
                "Открой со мной диалог и нажми /start.",
                show_alert=True,
            )
            return
        key = (query.message.chat.id, query.message.message_id)
        owner = self.message_owners.get(key)
        if not data.startswith("join_"):
            if owner is not None and owner != telegram_id:
                await query.answer(
                    "Эта панель принадлежит другому игроку.\n"
                    "Вызови своё меню через /start.",
                    show_alert=True,
                )
                return
        await query.answer()
        logger.info(f"Callback от {telegram_id}: {data}")
        if data == "game_random":
            await self.start_random_game(query, context)
            return
        if data == "game_friend":
            await self.create_friend_game_callback(query, context)
            return
        if data == "friend_enter_code":
            context.user_data["awaiting_join_code"] = True
            await query.edit_message_text("Введи код приглашения, который дал создатель комнаты.")
            return
        if data == "game_categories":
            await self.show_category_selection(query, context)
            return
        if data in {"game_search_gender", "game_gender_search"}:
            await self.gender_search_callback(query, context)
            return
        if data == "start_gender_search":
            await self.start_premium_search(query, context)
            return
        if data.startswith("pref_gender_"):
            await self.update_search_gender_preference(query, context, data)
            return
        if data.startswith("cat_"):
            await self.toggle_category(query, context, data)
            return
        if data == "categories_done":
            await self.save_categories(query, context)
            return
        if data in {"gender_male", "gender_female", "gender_other"}:
            await self.set_gender(query, context, data)
            return
        if data.startswith("join_"):
            await self.join_friend_game(query, context, data)
            return
        if data.startswith("start_friend_"):
            await self.start_friend_game(query, context, data)
            return
        if data.startswith("truth_"):
            await self.send_task(query, context, data, "truth")
            return
        if data.startswith("dare_"):
            await self.send_task(query, context, data, "dare")
            return
        if data == "set_age":
            await self.prompt_age_input(query, context)
            return
        if data.startswith("skip_"):
            await self.skip_turn(query, context, data)
            return
        if data.startswith("end_"):
            await self.end_game(query, context, data)
            return
        if data.startswith("premium_") or data == "premium_status":
            await self.handle_premium_callback(query, context, data)
            return
        if data == "friend_decline":
            await query.edit_message_text("Комната отклонена.")
            return
        if data == "cancel":
            await query.edit_message_text("❌ Действие отменено")
            return
        if data == "back_to_menu":
            msg = await query.message.reply_text(
                "Главное меню:",
                reply_markup=main_menu(),
            )
            self.register_owned_message(msg, telegram_id)
            try:
                await query.message.delete()
            except Exception:
                pass
            return
        await query.edit_message_text("Неизвестное действие.")

    async def start_random_game(self, query, context):
        chat = query.message.chat
        if chat.type != "private":
            await query.edit_message_text(
                "Для поиска случайной игры напиши мне в личные сообщения и нажми /start."
            )
            return
        user = query.from_user
        telegram_id = user.id
        user_data, categories = self._load_user(telegram_id, user)
        if not db.can_use_random_search(telegram_id):
            period_text = (
                "за сегодня"
                if Config.FREE_SEARCH_PERIOD_DAYS == 1
                else f"за {Config.FREE_SEARCH_PERIOD_DAYS} дн."
            )
            await query.edit_message_text(
                f"Лимит из {Config.FREE_SEARCHES_PER_DAY} бесплатных поисков {period_text} исчерпан.\n"
                "Ожидай следующего периода или оформи премиум для безлимитной игры."
            )
            return
        game_state = await self.game_logic.find_random_game(
            telegram_id,
            categories,
            search_gender=user_data.get("search_gender"),
            search_age_min=user_data.get("search_age_min"),
            search_age_max=user_data.get("search_age_max"),
            user_gender=user_data.get("gender"),
            user_age=user_data.get("age"),
            is_premium=bool(user_data.get("is_premium")),
        )
        if game_state is None:
            msg = await query.edit_message_text(
                "🔍 Ищем соперника...\n"
                "Как только найдётся второй игрок, игра начнётся автоматически.",
            )
            self.register_owned_message(msg, telegram_id)
            log_action(f"Игрок {telegram_id} встал в очередь случайной игры")
            return
        msg = await query.edit_message_text(
            "🎮 Найден соперник!\nИгра начинается.",
        )
        self.register_owned_message(msg, telegram_id)
        log_action(f"Сформирована случайная игра {game_state.id} для игроков {game_state.players}")
        await self.notify_game_start(game_state, context)

    async def notify_game_start(self, game_state, context: ContextTypes.DEFAULT_TYPE):
        if not game_state.current_player:
            self.game_logic.set_initial_turn(game_state.id)
        current = game_state.current_player
        log_action(
            f"Старт игры {game_state.id}. Ход игрока {current}. Участники: {game_state.players}"
        )
        for uid in game_state.players:
            try:
                text = "🎮 Игра началась!\n"
                if uid == current:
                    text += "Сейчас твой ход. Выбирай «Правда» или «Действие»."
                else:
                    text += "Сейчас ход другого игрока. Ожидай своей очереди."
                msg = await context.bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=game_action_keyboard(game_state.id, True),
                )
                self.register_owned_message(msg, uid)
            except Exception as e:
                logger.error(f"Не удалось отправить старт игроку {uid}: {e}")
        for uid in game_state.players:
            db.increment_counters(uid, games_delta=1)

    async def create_friend_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat.type != "private":
            await update.message.reply_text(
                "Создавать комнаты можно только в личных сообщениях с ботом.\n"
                "Открой со мной диалог и нажми /start."
            )
            return
        user = update.effective_user
        telegram_id = user.id
        user_data = db.get_user(telegram_id)
        if not user_data:
            db.create_user(
                telegram_id,
                user.username,
                user.first_name,
                user.last_name,
            )
            user_data = db.get_user(telegram_id)
        categories_raw = user_data.get("categories") if user_data else None
        categories = None
        if categories_raw:
            try:
                categories = eval(categories_raw)
            except Exception:
                categories = None
        game_state = self.game_logic.create_friend_game(telegram_id, categories, max_rounds=10)
        invite_code = game_state.invite_code
        msg = await update.message.reply_text(
            f"👥 Комната создана!\n\n"
            f"Код приглашения: <code>{invite_code}</code>\n\n"
            f"Максимум игроков сейчас: {game_state.max_players}. Отправь число от 2 до 10, чтобы изменить лимит.\n"
            f"Когда все соберутся — нажми \"Начать игру\".",
            parse_mode="HTML",
            reply_markup=friend_owner_keyboard(invite_code, game_state.id),
        )
        self.register_owned_message(msg, user.id)
        context.user_data["awaiting_friend_players"] = game_state.id

    async def create_friend_game_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        chat = query.message.chat
        if chat.type != "private":
            await query.answer(
                "Создавать комнаты можно только в личке с ботом.",
                show_alert=True,
            )
            return
        user = query.from_user
        telegram_id = user.id
        user_data = db.get_user(telegram_id)
        if not user_data:
            db.create_user(
                telegram_id,
                user.username,
                user.first_name,
                user.last_name,
            )
            user_data = db.get_user(telegram_id)
        categories_raw = user_data.get("categories") if user_data else None
        categories = None
        if categories_raw:
            try:
                categories = eval(categories_raw)
            except Exception:
                categories = None
        game_state = self.game_logic.create_friend_game(telegram_id, categories, max_rounds=10)
        invite_code = game_state.invite_code
        msg = await query.edit_message_text(
            f"👥 Комната создана!\n\n"
            f"Код приглашения: <code>{invite_code}</code>\n\n"
            f"Максимум игроков сейчас: {game_state.max_players}. Отправь число от 2 до 10, чтобы изменить лимит.\n"
            f"Когда все соберутся — нажми \"Начать игру\".",
            parse_mode="HTML",
            reply_markup=friend_owner_keyboard(invite_code, game_state.id),
        )
        self.register_owned_message(msg, user.id)
        context.user_data["awaiting_friend_players"] = game_state.id

    async def join_friend_game(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        chat = query.message.chat
        if chat.type != "private":
            await query.answer(
                "Присоединяться к комнатам можно только в личных сообщениях с ботом.",
                show_alert=True,
            )
            return
        invite_code = data.replace("join_", "", 1)
        user = query.from_user
        telegram_id = user.id
        success, msg_text, game_state = self.game_logic.join_friend_game(invite_code, telegram_id)
        if not success:
            await query.edit_message_text(f"❌ {msg_text}")
            return
        await query.edit_message_text(
            self._join_success_text(game_state), parse_mode="HTML"
        )
        await self._broadcast_room_join(game_state, context, query.from_user)

    async def start_friend_game(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        chat = query.message.chat
        if chat.type != "private":
            await query.answer(
                "Запускать игру можно только в личных сообщениях с ботом.",
                show_alert=True,
            )
            return
        game_id = int(data.replace("start_friend_", "", 1))
        state = self.game_logic.get_game_by_id(game_id)
        if not state:
            await query.edit_message_text("Комната не найдена или уже закрыта.")
            return
        if state.host_id != query.from_user.id:
            await query.answer("Только создатель комнаты может запустить игру.", show_alert=True)
            return
        if state.started:
            await query.answer("Игра уже началась.")
            return
        if len(state.players) < 2:
            await query.answer("Нужно минимум 2 игрока, чтобы начать.", show_alert=True)
            return
        state.started = True
        await self.notify_game_start(state, context)
        await query.edit_message_text("🚀 Игра запущена!")

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = db.get_user(user.id)
        if not user_data:
            await update.message.reply_text("Сначала зарегистрируйся через /start")
            return
        rating_value = user_data.get("rating", 1000)
        try:
            rating_text = str(round(float(rating_value), 1))
        except Exception:
            rating_text = str(rating_value)
        text = (
            "📊 <b>Твоя статистика</b>\n\n"
            f"🎮 Игр сыграно: {user_data.get('games_played', 0)}\n"
            f"🗣️ Ответов на правду: {user_data.get('truth_answered', 0)}\n"
            f"🎭 Выполненных действий: {user_data.get('dares_completed', 0)}\n"
            f"⭐ Рейтинг: {rating_text}\n\n"
            "👤 <b>Информация</b>\n"
            f"Пол: {user_data.get('gender', 'Не указан')}\n"
            f"Возраст: {user_data.get('age', 'Не указан')}\n"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        user_data = db.get_user(update.effective_user.id)
        gender = (user_data or {}).get("gender", "Не указан")
        age = (user_data or {}).get("age", "Не указан")
        categories_raw = (user_data or {}).get("categories")
        if categories_raw:
            try:
                cats = eval(categories_raw)
                cat_names = [Config.CATEGORIES.get(c, c) for c in cats]
                cats_text = ", ".join(cat_names)
            except Exception:
                cats_text = "Знакомство, Флирт"
        else:
            cats_text = "Знакомство, Флирт"
        text = (
            "⚙️ <b>Настройки профиля</b>\n\n"
            f"👤 Пол: {gender}\n"
            f"🎂 Возраст: {age}\n"
            f"🎯 Категории: {cats_text}\n\n"
            "Пол можно сменить ниже, категории — через «🎮 Найти игру → Выбрать категории».\n"
            "Нажми «🎂 Указать возраст» или отправь число сообщением, чтобы обновить возраст."
        )
        keyboard = [
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
            ],
            [
                InlineKeyboardButton(text="🌈 Другой", callback_data="gender_other"),
            ],
            [
                InlineKeyboardButton(text="🎂 Указать возраст", callback_data="set_age"),
            ],
        ]
        msg = await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        self.register_owned_message(msg, update.effective_user.id)

    async def show_category_selection(self, query, context: ContextTypes.DEFAULT_TYPE):
        user = query.from_user
        user_data = db.get_user(user.id)
        categories_raw = (user_data or {}).get("categories")
        selected = []
        if categories_raw:
            try:
                selected = eval(categories_raw)
            except Exception:
                selected = []
        context.user_data["categories"] = selected
        await query.edit_message_text(
            "Выбери категории для игры:",
            reply_markup=categories_keyboard(selected),
        )

    async def toggle_category(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        cat_id = data.replace("cat_", "", 1)
        selected = context.user_data.get("categories", [])
        if cat_id in selected:
            selected.remove(cat_id)
        else:
            selected.append(cat_id)
        context.user_data["categories"] = selected
        await query.edit_message_reply_markup(
            reply_markup=categories_keyboard(selected),
        )

    async def save_categories(self, query, context: ContextTypes.DEFAULT_TYPE):
        user = query.from_user
        selected = context.user_data.get("categories", [])
        if not selected:
            selected = ["acquaintance", "flirt"]
        db.update_user(user.id, categories=str(selected))
        await query.edit_message_text(
            "🎯 Категории сохранены.\n"
            "Теперь поиск игр будет учитывать твои предпочтения.",
        )

    async def set_gender(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        user = query.from_user
        mapping = {
            "gender_male": "Мужской",
            "gender_female": "Женский",
            "gender_other": "Другой",
        }
        gender = mapping.get(data, "Не указан")
        db.update_user(user.id, gender=gender)
        await query.edit_message_text(
            f"Пол обновлён: {gender}",
        )

    async def send_task(self, query, context: ContextTypes.DEFAULT_TYPE, data: str, kind: str):
        parts = data.split("_")
        if len(parts) < 2:
            await query.edit_message_text("Ошибка формата данных игры.")
            return
        game_id = int(parts[1])
        game_state = self.game_logic.get_game_by_id(game_id)
        if not game_state:
            await query.edit_message_text("Игра не найдена или уже завершена.")
            return
        current_player = game_state.current_player
        user_id = query.from_user.id
        if current_player is not None and user_id != current_player:
            await query.answer("Сейчас ход другого игрока", show_alert=True)
            return
        task_text = self.game_logic.get_task(game_id, kind)
        if kind == "truth":
            prefix = "🗣️ Правда"
            choice_text = "правду"
        else:
            prefix = "🎭 Действие"
            choice_text = "действие"
        player_name = query.from_user.first_name or query.from_user.username or str(user_id)

        pending = {
            "game_id": game_id,
            "player_id": user_id,
            "player_name": player_name,
        }
        context.user_data["pending_answer"] = pending
        self.pending_answers[user_id] = pending

        await query.edit_message_text(
            f"{prefix}. Ответь сообщением.",
        )
        try:
            personal = await context.bot.send_message(
                chat_id=user_id,
                text=f"{prefix}:\n\n{task_text}",
            )
            self.register_owned_message(personal, user_id)
        except Exception as e:
            logger.error(f"Не удалось отправить задание игроку {user_id}: {e}")
        broadcast_text = (
            f"🎲 {player_name} выбрал(а) {choice_text}.\n\n"
            f"{prefix}:\n\n{task_text}"
        )
        for uid in game_state.players:
            if uid == user_id:
                continue
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=broadcast_text,
                )
            except Exception as e:
                logger.error(f"Не удалось отправить вопрос игроку {uid}: {e}")
        if kind == "truth":
            db.increment_counters(user_id, truth_delta=1)
        else:
            db.increment_counters(user_id, dares_delta=1)

    async def skip_turn(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        parts = data.split("_")
        if len(parts) < 2:
            await query.edit_message_text("Ошибка формата данных игры.")
            return
        game_id = int(parts[1])
        game_state = self.game_logic.get_game_by_id(game_id)
        if not game_state:
            await query.edit_message_text("Игра не найдена или уже завершена.")
            return
        current_player = game_state.current_player
        user_id = query.from_user.id
        if current_player is not None and user_id != current_player:
            await query.answer("Сейчас ход другого игрока", show_alert=True)
            return
        await query.edit_message_text(
            "⏭️ Задание пропущено. Ход переходит другому игроку."
        )
        next_player = self.game_logic.next_turn_random(game_id)
        if next_player is None:
            self.game_logic.finish_game(game_id)
            for uid in game_state.players:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="🏁 Игра завершена. Лимит раундов исчерпан.",
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить игрока {uid} о завершении: {e}")
            return
        for uid in game_state.players:
            try:
                text = "Ход переходит другому игроку.\n"
                if uid == next_player:
                    text = "Теперь твой ход. Выбирай «Правда» или «Действие»."
                msg = await context.bot.send_message(
                    chat_id=uid,
                    text=text,
                    reply_markup=game_action_keyboard(game_id, True),
                )
                self.register_owned_message(msg, uid)
            except Exception as e:
                logger.error(f"Не удалось уведомить игрока {uid} о ходе: {e}")

    async def end_game(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        parts = data.split("_")
        if len(parts) < 2:
            await query.edit_message_text("Ошибка формата данных игры.")
            return
        game_id = int(parts[1])
        game_state = self.game_logic.get_game_by_id(game_id)
        if not game_state:
            await query.edit_message_text("Игра уже завершена.")
            return
        user_id = query.from_user.id
        if game_state.current_player is not None and user_id != game_state.current_player:
            await query.answer("Завершить игру может только игрок, у которого ход", show_alert=True)
            return
        self.game_logic.finish_game(game_id)
        await query.edit_message_text("🏁 Игра завершена. Спасибо за игру!")
        for uid in game_state.players:
            if uid == user_id:
                continue
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text="🏁 Игра была завершена одним из игроков.",
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить игрока {uid} о завершении: {e}")

    async def start_gender_search_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = db.get_user(update.effective_user.id)
        if not user_data:
            await update.message.reply_text("Сначала зарегистрируйся через /start")
            return
        if not int(user_data.get("is_premium") or 0):
            await update.message.reply_text(
                "🔍 Поиск по полу и возрасту доступен только премиум-пользователям.\n"
                "Оформи премиум за Telegram Stars, чтобы пользоваться этим режимом.",
                reply_markup=premium_keyboard(),
            )
            return
        context.user_data["awaiting_search_age_input"] = True
        await update.message.reply_text(
            self._search_preferences_text(user_data),
            reply_markup=search_preferences_keyboard(user_data.get("search_gender", "Любой")),
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "Отправь возрастной диапазон для поиска (например 18-30) или одно число.",
        )

    async def gender_search_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        user_data = db.get_user(query.from_user.id)
        if not user_data:
            await query.edit_message_text("Сначала зарегистрируйся через /start")
            return
        if not int(user_data.get("is_premium") or 0):
            await query.edit_message_text(
                "🔍 Поиск по полу и возрасту доступен только премиум-пользователям.\n"
                "Нажми на кнопку ниже, чтобы купить премиум за Telegram Stars.",
                reply_markup=premium_keyboard(),
            )
            return
        await query.edit_message_text(
            self._search_preferences_text(user_data),
            reply_markup=search_preferences_keyboard(user_data.get("search_gender", "Любой")),
            parse_mode="HTML",
        )

    async def start_premium_search(self, query, context: ContextTypes.DEFAULT_TYPE):
        chat = query.message.chat
        if chat.type != "private":
            await query.answer(
                "Поиск по параметрам доступен только в личном чате с ботом.",
                show_alert=True,
            )
            return
        user = query.from_user
        telegram_id = user.id
        user_data, categories = self._load_user(telegram_id, user)
        if not int(user_data.get("is_premium") or 0):
            await query.edit_message_text(
                "Эта функция доступна только премиум-пользователям.\n"
                "Купи премиум за Telegram Stars и возвращайся к поиску.",
                reply_markup=premium_keyboard(),
            )
            return
        game_state = await self.game_logic.find_random_game(
            telegram_id,
            categories,
            search_gender=user_data.get("search_gender"),
            search_age_min=user_data.get("search_age_min"),
            search_age_max=user_data.get("search_age_max"),
            user_gender=user_data.get("gender"),
            user_age=user_data.get("age"),
            is_premium=True,
        )
        if game_state is None:
            msg = await query.edit_message_text(
                "🔍 Ищем соперника с подходящими параметрами..."
            )
            self.register_owned_message(msg, telegram_id)
            return
        msg = await query.edit_message_text(
            "🎮 Найден соперник по параметрам! Игра начинается."
        )
        self.register_owned_message(msg, telegram_id)
        await self.notify_game_start(game_state, context)

    async def update_search_gender_preference(
        self, query, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        gender_value = data.replace("pref_gender_", "", 1)
        db.update_user(query.from_user.id, search_gender=gender_value)
        user_data = db.get_user(query.from_user.id) or {}
        await query.edit_message_text(
            self._search_preferences_text(user_data),
            reply_markup=search_preferences_keyboard(gender_value),
            parse_mode="HTML",
        )

    def _search_preferences_text(self, user_data: dict) -> str:
        gender_pref = user_data.get("search_gender") or "Любой"
        age_min = user_data.get("search_age_min")
        age_max = user_data.get("search_age_max")
        if age_min is None and age_max is None:
            age_text = "Любой"
        elif age_min is not None and age_max is not None:
            age_text = f"{age_min}-{age_max}"
        elif age_min is not None:
            age_text = f"от {age_min}"
        else:
            age_text = f"до {age_max}"
        return (
            "🔍 <b>Поиск по параметрам</b>\n\n"
            f"Пол для поиска: {gender_pref}\n"
            f"Возрастной диапазон: {age_text}\n\n"
            "Выбери пол собеседника кнопками ниже или отправь возрастной диапазон сообщением."
        )

    async def prompt_age_input(self, query, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["awaiting_age_input"] = True
        await query.edit_message_text(
            "Отправь свой возраст числом от 10 до 100, чтобы сохранить его в профиле."
        )

    def _join_success_text(self, game_state) -> str:
        return (
            "✅ Ты присоединился к комнате.\n"
            f"Сейчас игроков: <b>{len(game_state.players)}</b> из {game_state.max_players}.\n"
            "Ожидаем запуска игры создателем."
        )

    async def _broadcast_room_join(self, game_state, context, joiner):
        joiner_name = joiner.first_name or joiner.username or str(joiner.id)
        note = (
            f"👥 {joiner_name} вошёл в комнату.\n"
            f"Игроков сейчас: {len(game_state.players)}/{game_state.max_players}."
        )
        for uid in game_state.players:
            try:
                await context.bot.send_message(chat_id=uid, text=note)
            except Exception as e:
                logger.error(f"Не удалось уведомить игрока {uid} о входе в комнату: {e}")

    def _grant_premium(self, user_id: int, months: int | None = None, days: int | None = None) -> str:
        if months is None and days is None:
            months = 1
        extra_days = days if days is not None else 30 * (months or 1)
        until = datetime.utcnow() + timedelta(days=extra_days)
        db.update_user(user_id, is_premium=1, premium_until=until.isoformat())
        return until.strftime("%d.%m.%Y")

    async def _send_premium_invoice(self, query, context: ContextTypes.DEFAULT_TYPE, months: str):
        if months not in Config.PREMIUM_STAR_PRICES:
            await query.answer("Неверный срок подписки", show_alert=True)
            return
        price = int(Config.PREMIUM_STAR_PRICES[months])
        payload = f"premium:{months}:{query.from_user.id}"
        await context.bot.send_invoice(
            chat_id=query.message.chat.id,
            title="⭐ Премиум аккаунт",
            description=(
                "Доступ к поиску по полу и возрасту, приоритет в матчмейкинге"
                " и безлимитные попытки поиска."
            ),
            payload=payload,
            provider_token=Config.STAR_PROVIDER_TOKEN or "",
            currency="XTR",
            prices=[LabeledPrice(label=f"Премиум на {months} мес", amount=price)],
            max_tip_amount=0,
            start_parameter="premium",
        )

    async def handle_premium_callback(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        if data == "premium_status":
            user = db.get_user(query.from_user.id)
            if user and user.get("is_premium"):
                until = user.get("premium_until") or "неизвестно"
                await query.edit_message_text(
                    f"👑 У тебя уже есть премиум.\nДействует до: {until}",
                )
            else:
                await query.edit_message_text(
                    "У тебя пока нет премиума.\nВыбери подходящий вариант покупки.",
                    reply_markup=premium_keyboard(),
                )
            return
        plan = data.replace("premium_", "", 1)
        if plan == "trial":
            until = self._grant_premium(query.from_user.id, days=3)
            await query.edit_message_text(
                f"🎁 Пробный премиум активирован до {until}! Приятной игры!",
            )
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text="Главное меню",
                reply_markup=main_menu(),
            )
            return
        await self._send_premium_invoice(query, context, plan)

    async def precheckout_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.pre_checkout_query
        await query.answer(ok=True)

    async def successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        payment = update.message.successful_payment
        payload = payment.invoice_payload or ""
        if payload.startswith("premium:"):
            try:
                _, months, uid_str = payload.split(":", 2)
                months_int = int(months)
            except Exception:
                months_int = 1
            until = self._grant_premium(update.effective_user.id, months=months_int)
            await update.message.reply_text(
                f"Спасибо за покупку! Премиум активирован до {until}.",
                reply_markup=main_menu(),
            )
            return

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Исключение в обработчике:", exc_info=context.error)
        try:
            if update and isinstance(update, Update) and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Произошла внутренняя ошибка. Попробуй ещё раз позже.",
                )
        except Exception:
            pass


def main():
    log_action("Запуск приложения")
    app = Application.builder().token(Config.BOT_TOKEN).build()
    bot_logic = TruthOrDareBot()
    app.add_handler(CommandHandler("start", bot_logic.start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_logic.handle_message))
    app.add_handler(CallbackQueryHandler(bot_logic.handle_callback))
    app.add_handler(PreCheckoutQueryHandler(bot_logic.precheckout_check))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, bot_logic.successful_payment))
    app.add_error_handler(bot_logic.error_handler)
    logger.info("Бот запущен. Ожидание обновлений...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
