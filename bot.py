#!/usr/bin/env python3
"""
Основной файл бота - упрощенная версия без сложных зависимостей
"""

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from config import Config
from database import db
from keyboards import *
from game_logic import GameLogic
from questions_actions import QUESTIONS, DARES

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(Config.LOGS_DIR / 'bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TruthOrDareBot:
    def __init__(self):
        self.game_logic = GameLogic(db)
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        
        # Регистрация или получение пользователя
        if not db.user_exists(user.id):
            user_id = db.create_user(user.id, user.username, user.first_name, user.last_name)
            logger.info(f"Новый пользователь: {user.id} - {user.username}")
            
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n"
                f"Добро пожаловать в игру 'Правда или Действие'!\n\n"
                f"🎮 <b>Быстрый старт:</b>\n"
                f"1. Нажми '🎮 Найти игру'\n"
                f"2. Выбери тип игры\n"
                f"3. Начинай играть!\n\n"
                f"📱 Используй меню ниже для навигации",
                parse_mode='HTML',
                reply_markup=main_menu()
            )
        else:
            await update.message.reply_text(
                f"С возвращением, {user.first_name}! 🎮\n"
                f"Выбери действие:",
                reply_markup=main_menu()
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text
        
        if text == "🎮 Найти игру":
            await self.show_game_menu(update, context)
        elif text == "👥 С друзьями":
            await self.create_friend_game(update, context)
        elif text == "📊 Статистика":
            await self.show_stats(update, context)
        elif text == "⭐ Премиум":
            await self.show_premium(update, context)
        elif text == "⚙️ Настройки":
            await self.show_settings(update, context)
        elif text == "📞 Поддержка":
            await update.message.reply_text(
                "📞 <b>Поддержка</b>\n\n"
                "По всем вопросам:\n"
                "@your_support_username\n\n"
                "⚠️ <b>Важно:</b>\n"
                "• Игра предназначена для лиц 18+\n"
                "• Уважайте других игроков\n"
                "• Сообщайте о нарушениях",
                parse_mode='HTML'
            )
        elif text.startswith("/join"):
            # Присоединение по коду
            code = text.split()[1] if len(text.split()) > 1 else None
            if code:
                await self.join_game_by_code(update, context, code)
    
    async def show_game_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню выбора игры"""
        user_data = db.get_user(update.effective_user.id)
        free_searches = self.get_free_searches_left(user_data)
        
        text = (
            "🎮 <b>Выбери тип игры:</b>\n\n"
            "🎲 <b>Случайный игрок</b> - игра с рандомным соперником\n"
            "👥 <b>С другом</b> - создай комнату для друзей\n"
            "🔍 <b>Поиск по полу</b> - премиум функция\n"
            "🎯 <b>Категории</b> - выбери темы вопросов\n\n"
        )
        
        if free_searches > 0:
            text += f"ℹ️ У тебя осталось {free_searches} бесплатных поисков сегодня"
        else:
            text += "ℹ️ Бесплатные поиски закончились. Оформи премиум!"
        
        await update.message.reply_text(
            text,
            parse_mode='HTML',
            reply_markup=game_type_keyboard()
        )
    
    async def create_friend_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создание игры с друзьями"""
        user_data = db.get_user(update.effective_user.id)
        game_id = self.game_logic.create_game(user_data, 'friend')
        
        # Генерация кода приглашения
        invite_code = f"TD{game_id:06d}"
        
        # Сохраняем в контексте
        context.user_data['invite_code'] = invite_code
        
        await update.message.reply_text(
            f"👥 <b>Комната создана!</b>\n\n"
            f"Код приглашения: <code>{invite_code}</code>\n\n"
            f"Отправь этот код другу или нажми кнопку ниже, чтобы поделиться.\n"
            f"Игра начнется, когда присоединится хотя бы 1 человек.",
            parse_mode='HTML',
            reply_markup=friend_invite_keyboard(invite_code)
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ статистики"""
        user_data = db.get_user(update.effective_user.id)
        
        if not user_data:
            await update.message.reply_text("Сначала зарегистрируйтесь через /start")
            return
        
        stats_text = (
            f"📊 <b>Твоя статистика</b>\n\n"
            f"🎮 Игр сыграно: {user_data.get('games_played', 0)}\n"
            f"🗣️ Ответов на правду: {user_data.get('truth_answered', 0)}\n"
            f"🎭 Выполненных действий: {user_data.get('dares_completed', 0)}\n"
            f"⭐ Рейтинг: {user_data.get('rating', 1000):.1f}\n\n"
            f"👤 <b>Информация:</b>\n"
            f"Пол: {user_data.get('gender', 'Не указан')}\n"
            f"Возраст: {user_data.get('age', 'Не указан')}\n"
        )
        
        if user_data.get('is_premium'):
            premium_until = user_data.get('premium_until')
            if premium_until:
                if isinstance(premium_until, str):
                    premium_until = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
                days_left = (premium_until - datetime.utcnow()).days
                stats_text += f"💎 Премиум: ✅ (осталось {days_left} дней)\n"
            else:
                stats_text += "💎 Премиум: ✅\n"
        else:
            stats_text += "💎 Премиум: ❌\n"
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
    
    async def show_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о премиум"""
        text = (
            "⭐ <b>Премиум подписка</b>\n\n"
            "🔓 <b>Разблокируй все возможности:</b>\n"
            "• Поиск игроков по полу\n"
            "• Приоритет в поиске\n"
            "• Все категории вопросов\n"
            "• Увеличенный лимит игр\n"
            "• Без рекламы\n\n"
            "💎 <b>Тарифы:</b>\n"
            "1 месяц - 99₽\n"
            "3 месяца - 249₽ (экономия 16%)\n"
            "12 месяцев - 799₽ (экономия 33%)\n\n"
            "Нажми кнопку для покупки:"
        )
        
        await update.message.reply_text(
            text,
            parse_mode='HTML',
            reply_markup=premium_keyboard()
        )
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Настройки профиля"""
        user_data = db.get_user(update.effective_user.id)
        
        keyboard = [
            [
                InlineKeyboardButton("👤 Пол и возраст", callback_data="settings_gender"),
                InlineKeyboardButton("🎯 Категории", callback_data="settings_categories")
            ],
            [
                InlineKeyboardButton("🔔 Уведомления", callback_data="settings_notifications"),
                InlineKeyboardButton("🌐 Язык", callback_data="settings_language")
            ],
            [InlineKeyboardButton("↩️ Назад", callback_data="back_to_menu")]
        ]
        
        gender = user_data.get('gender', 'Не указан')
        age = user_data.get('age', 'Не указан')
        categories = user_data.get('categories', '["acquaintance", "flirt"]')
        
        try:
            categories_list = eval(categories) if isinstance(categories, str) else categories
            categories_text = ", ".join([Config.CATEGORIES.get(c, c) for c in categories_list])
        except:
            categories_text = "Знакомство, Флирт"
        
        text = (
            f"⚙️ <b>Настройки профиля</b>\n\n"
            f"👤 Пол: {gender}\n"
            f"🎂 Возраст: {age}\n"
            f"🎯 Категории: {categories_text}\n\n"
            f"Выбери настройку для изменения:"
        )
        
        await update.message.reply_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback-запросов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "game_random":
            await self.start_random_game(query, context)
        elif data == "game_friend":
            await self.create_friend_game_callback(query, context)
        elif data.startswith("cat_"):
            await self.handle_category_toggle(query, context, data)
        elif data == "categories_done":
            await self.save_categories(query, context)
        elif data.startswith("premium_"):
            await self.handle_premium_purchase(query, context, data)
        elif data == "cancel":
            await query.edit_message_text("❌ Действие отменено")
        elif data == "back_to_menu":
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=main_menu()
            )
    
    async def start_random_game(self, query, context):
        """Запуск случайной игры"""
        user_data = db.get_user(query.from_user.id)
        
        # Проверяем лимиты
        if not self.can_search_free(user_data):
            await query.edit_message_text(
                "❌ <b>Лимит исчерпан</b>\n\n"
                "Бесплатные поиски на сегодня закончились.\n\n"
                "💎 Оформи премиум для:\n"
                "• Неограниченных поисков\n"
                "• Поиска по полу\n"
                "• Приоритета в очереди",
                parse_mode='HTML',
                reply_markup=premium_keyboard()
            )
            return
        
        # Обновляем счетчик поисков
        self.update_search_count(user_data)
        
        # Ищем игру
        game_found = await self.game_logic.find_random_game(user_data)
        
        if game_found:
            await query.edit_message_text(
                "🎮 <b>Игра найдена!</b>\n\n"
                "Начинаем через 3 секунды...",
                parse_mode='HTML'
            )
            await asyncio.sleep(3)
            await self.start_game_session(query, context, game_found)
        else:
            await query.edit_message_text(
                "🔍 <b>Ищем соперника...</b>\n\n"
                "Ожидайте, обычно это занимает 1-2 минуты.\n"
                "Мы уведомим вас, когда найдем партнера.",
                parse_mode='HTML'
            )
    
    async def start_game_session(self, query, context, game_data):
        """Запуск игровой сессии"""
        # Получаем первого игрока
        current_player_id = game_data['current_player_id']
        user_data = db.get_user(query.from_user.id)
        
        if user_data['id'] == current_player_id:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"🎮 <b>Твой ход!</b>\nРаунд: 1/{game_data['max_rounds']}\n\nВыбери:",
                parse_mode='HTML',
                reply_markup=game_action_keyboard(game_data['id'])
            )
        else:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"🎮 <b>Ход другого игрока</b>\nРаунд: 1/{game_data['max_rounds']}\n\nОжидай своего хода...",
                parse_mode='HTML'
            )
    
    def get_free_searches_left(self, user_data):
        """Получение оставшихся бесплатных поисков"""
        if user_data.get('is_premium'):
            return 999  # У премиум пользователей неограниченно
        
        last_search = user_data.get('last_search')
        if not last_search:
            return Config.FREE_SEARCHES_PER_DAY
        
        if isinstance(last_search, str):
            last_search = datetime.fromisoformat(last_search.replace('Z', '+00:00'))
        
        # Сбрасываем счетчик если прошло больше суток
        if datetime.utcnow() - last_search > timedelta(days=1):
            return Config.FREE_SEARCHES_PER_DAY
        
        # Получаем количество использованных поисков сегодня
        search_count = user_data.get('search_count', 0)
        return max(0, Config.FREE_SEARCHES_PER_DAY - search_count)
    
    def can_search_free(self, user_data):
        """Проверка возможности бесплатного поиска"""
        return self.get_free_searches_left(user_data) > 0
    
    def update_search_count(self, user_data):
        """Обновление счетчика поисков"""
        current_time = datetime.utcnow().isoformat()
        
        # Проверяем, нужно ли сбросить счетчик
        last_search = user_data.get('last_search')
        if last_search and isinstance(last_search, str):
            last_search = datetime.fromisoformat(last_search.replace('Z', '+00:00'))
            if datetime.utcnow() - last_search > timedelta(days=1):
                # Сбрасываем счетчик
                db.update_user(user_data['telegram_id'], 
                             search_count=1,
                             last_search=current_time)
            else:
                # Увеличиваем счетчик
                new_count = user_data.get('search_count', 0) + 1
                db.update_user(user_data['telegram_id'],
                             search_count=new_count,
                             last_search=current_time)
        else:
            # Первый поиск
            db.update_user(user_data['telegram_id'],
                         search_count=1,
                         last_search=current_time)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=context.error)
        
        # Отправляем сообщение об ошибке администратору
        if Config.ADMIN_IDS:
            error_msg = f"❌ Ошибка в боте:\n{context.error}"
            for admin_id in Config.ADMIN_IDS:
                try:
                    await context.bot.send_message(admin_id, error_msg)
                except:
                    pass

def main():
    """Основная функция запуска"""
    # Проверяем наличие токена
    if not Config.BOT_TOKEN:
        logger.error("BOT_TOKEN не указан в .env файле!")
        return
    
    # Создаем приложение
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Создаем экземпляр бота
    bot = TruthOrDareBot()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("game", bot.show_game_menu))
    application.add_handler(CommandHandler("stats", bot.show_stats))
    application.add_handler(CommandHandler("premium", bot.show_premium))
    application.add_handler(CommandHandler("settings", bot.show_settings))
    application.add_handler(CommandHandler("help", bot.start))
    
    # Команды администратора
    application.add_handler(CommandHandler("admin", bot.start))
    
    # Обработка сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Обработка callback-запросов
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Обработчик ошибок
    application.add_error_handler(bot.error_handler)
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")