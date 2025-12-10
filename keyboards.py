from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎮 Найти игру"), KeyboardButton("👥 С друзьями")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("⭐ Премиум")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("📞 Поддержка")]
    ], resize_keyboard=True)

def game_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🎲 Случайный игрок", callback_data="game_random"),
            InlineKeyboardButton("👥 С другом", callback_data="game_friend")
        ],
        [
            InlineKeyboardButton("🔍 Поиск по полу", callback_data="game_gender_search"),
            InlineKeyboardButton("🎯 Выбрать категории", callback_data="game_categories")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def categories_keyboard(selected_categories=None):
    if selected_categories is None:
        selected_categories = []
    
    categories = [
        ('acquaintance', '👋 Знакомство'),
        ('flirt', '😘 Флирт'),
        ('sexy', '🔥 Сексуальное'),
        ('extreme', '💀 Экстрим'),
        ('funny', '😂 Смешное')
    ]
    
    keyboard = []
    row = []
    for i, (cat_id, cat_name) in enumerate(categories):
        emoji = "✅" if cat_id in selected_categories else "⬜"
        row.append(InlineKeyboardButton(f"{emoji} {cat_name}", callback_data=f"cat_{cat_id}"))
        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([
        InlineKeyboardButton("✅ Готово", callback_data="categories_done"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def gender_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
            InlineKeyboardButton("👩 Женский", callback_data="gender_female"),
            InlineKeyboardButton("🌈 Другой", callback_data="gender_other")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def game_action_keyboard(game_id, can_skip=False):
    keyboard = [
        [InlineKeyboardButton("🗣️ Правда", callback_data=f"truth_{game_id}"),
         InlineKeyboardButton("🎭 Действие", callback_data=f"dare_{game_id}")],
    ]
    
    if can_skip:
        keyboard.append([InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🏁 Завершить игру", callback_data=f"end_{game_id}")])
    
    return InlineKeyboardMarkup(keyboard)

def verification_keyboard(game_id, action_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Выполнил", callback_data=f"verify_yes_{game_id}_{action_id}"),
            InlineKeyboardButton("❌ Не выполнил", callback_data=f"verify_no_{game_id}_{action_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def premium_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💰 1 месяц - 99₽", callback_data="premium_1"),
            InlineKeyboardButton("💎 3 месяца - 249₽", callback_data="premium_3")
        ],
        [
            InlineKeyboardButton("👑 12 месяцев - 799₽", callback_data="premium_12"),
            InlineKeyboardButton("🎁 Пробный 3 дня", callback_data="premium_trial")
        ],
        [InlineKeyboardButton("📋 Моя подписка", callback_data="premium_status"),
         InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def friend_invite_keyboard(invite_code):
    keyboard = [
        [InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{invite_code}"),
         InlineKeyboardButton("❌ Отклонить", callback_data="friend_decline")]
    ]
    return InlineKeyboardMarkup(keyboard)

def rating_keyboard(game_id, action_id):
    keyboard = [
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"rate_1_{game_id}_{action_id}"),
            InlineKeyboardButton("⭐⭐ 2", callback_data=f"rate_2_{game_id}_{action_id}"),
            InlineKeyboardButton("⭐⭐⭐ 3", callback_data=f"rate_3_{game_id}_{action_id}"),
            InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data=f"rate_4_{game_id}_{action_id}"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data=f"rate_5_{game_id}_{action_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)