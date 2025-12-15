from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import Config

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


def search_wait_keyboard():
    keyboard = [
        [InlineKeyboardButton("❌ Отменить поиск", callback_data="cancel_search")],
    ]
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
    keyboard = []
    labels = {
        "1": "1 месяц",
        "3": "3 месяца",
        "12": "12 месяцев",
    }
    prices = Config.PREMIUM_STAR_PRICES
    first_row = []
    if "1" in prices:
        first_row.append(
            InlineKeyboardButton(
                f"✨ {labels['1']} — {prices['1']}⭐", callback_data="premium_1"
            )
        )
    if "3" in prices:
        first_row.append(
            InlineKeyboardButton(
                f"💫 {labels['3']} — {prices['3']}⭐", callback_data="premium_3"
            )
        )
    if first_row:
        keyboard.append(first_row)

    if "12" in prices:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"👑 {labels['12']} — {prices['12']}⭐", callback_data="premium_12"
                ),
                InlineKeyboardButton("🎁 Пробный 3 дня", callback_data="premium_trial"),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton("📋 Моя подписка", callback_data="premium_status"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)

def friend_invite_keyboard(invite_code):
    keyboard = [
        [InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{invite_code}"),
         InlineKeyboardButton("❌ Отклонить", callback_data="friend_decline")]
    ]
    return InlineKeyboardMarkup(keyboard)


def friend_owner_keyboard(invite_code: str, game_id: int):
    keyboard = [
        [
            InlineKeyboardButton("🎯 Категории", callback_data=f"friend_cats_{game_id}"),
            InlineKeyboardButton("🔢 Раунды", callback_data=f"friend_rounds_{game_id}"),
        ],
        [
            InlineKeyboardButton("👥 Игроки", callback_data=f"friend_players_{game_id}"),
        ],
        [InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_friend_{game_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def friend_rounds_keyboard(game_id: int, current: int):
    options = [5, 10, 20, 40]
    rows = []
    row = []
    for idx, value in enumerate(options):
        label = f"{'✅ ' if value == current else ''}{value}"
        row.append(
            InlineKeyboardButton(label, callback_data=f"friend_round_set_{game_id}_{value}")
        )
        if len(row) == 2 or idx == len(options) - 1:
            rows.append(row)
            row = []
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"friend_back_{game_id}")])
    return InlineKeyboardMarkup(rows)


def friend_players_keyboard(game_id: int, current: int):
    options = [2, 4, 6, 8, 10]
    rows = []
    row = []
    for idx, value in enumerate(options):
        label = f"{'✅ ' if value == current else ''}{value}"
        row.append(
            InlineKeyboardButton(label, callback_data=f"friend_players_set_{game_id}_{value}")
        )
        if len(row) == 2 or idx == len(options) - 1:
            rows.append(row)
            row = []
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"friend_back_{game_id}")])
    return InlineKeyboardMarkup(rows)


def friend_mode_keyboard():
    keyboard = [
        [InlineKeyboardButton("🆕 Создать комнату", callback_data="game_friend")],
        [InlineKeyboardButton("🔑 Ввести код", callback_data="friend_enter_code")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def search_preferences_keyboard(current_gender: str = "Любой", age_label: str | None = None):
    if not age_label:
        age_label = "🎂 Возраст"

    options = [
        ("pref_gender_Мужской", "👨 Ищу парня", "Мужской"),
        ("pref_gender_Женский", "👩 Ищу девушку", "Женский"),
        ("pref_gender_Любой", "♾ Любой", "Любой"),
    ]

    keyboard_rows = [
        [
            InlineKeyboardButton(
                ("✅ " if current_gender == opt_value else "") + opt_label,
                callback_data=callback,
            )
            for callback, opt_label, opt_value in options[:2]
        ],
        [
            InlineKeyboardButton(
                ("✅ " if current_gender == options[2][2] else "") + options[2][1],
                callback_data=options[2][0],
            )
        ],
        [InlineKeyboardButton(age_label, callback_data="pref_age_edit")],
        [InlineKeyboardButton("🚀 Начать поиск", callback_data="start_gender_search")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard_rows)

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