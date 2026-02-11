from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== ГЛАВНОЕ МЕНЮ ==========
def main_menu_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🐒 Моя макака", callback_data="my_macaco")],
        [
            InlineKeyboardButton(text="🍌 Покормить", callback_data="select_food"),
            InlineKeyboardButton(text="🎁 Ежедневная награда", callback_data="daily_reward")
        ],
        [
            InlineKeyboardButton(text="⚔️ Вызвать на бой", callback_data="challenge_fight"),
            InlineKeyboardButton(text="🚶 Выгулять", callback_data="walk_macaco")
        ],
        [InlineKeyboardButton(text="🏆 Топ по весу", callback_data="top_weight")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help_info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== МЕНЮ ВЫБОРА ЕДЫ ==========
def food_selection_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🍌 Банан (+1 кг)", callback_data="food_1"),
            InlineKeyboardButton(text="🥩 Мясо (+3 кг)", callback_data="food_2")
        ],
        [
            InlineKeyboardButton(text="🍰 Торт (+5 кг)", callback_data="food_3"),
            InlineKeyboardButton(text="🥗 Салат (+2 кг)", callback_data="food_4")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def food_info_kb(food_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✅ Покормить этой едой", callback_data=f"feed_{food_id}")],
        [InlineKeyboardButton(text="⬅️ Выбрать другую еду", callback_data="select_food")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== МЕНЮ ВЫБОРА СТАВКИ ДЛЯ ВЫЗОВА ==========
def bet_selection_challenge_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="1 кг", callback_data="challenge_bet_1"),
            InlineKeyboardButton(text="3 кг", callback_data="challenge_bet_3")
        ],
        [
            InlineKeyboardButton(text="5 кг", callback_data="challenge_bet_5"),
            InlineKeyboardButton(text="10 кг", callback_data="challenge_bet_10")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fight")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== КНОПКИ ДЛЯ ОТВЕТА НА ВЫЗОВ ==========
def challenge_response_kb(challenge_id: str, bet: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🥊 Принять бой", callback_data=f"accept_fight_{challenge_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_fight_{challenge_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== ПОСЛЕ БОЯ ==========
def after_fight_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data="challenge_fight")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== КНОПКА НАЗАД ==========
def back_to_menu_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== ИНЛАЙН-КНОПКИ ==========
def inline_actions_kb(macaco_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🐒 Инфо", callback_data=f"inline_info_{macaco_id}"),
            InlineKeyboardButton(text="🍌 Кормить", callback_data=f"inline_feed_{macaco_id}")
        ],
        [
            InlineKeyboardButton(text="⚔️ Вызвать на бой", callback_data="challenge_fight"),
            InlineKeyboardButton(text="🏆 Топ", callback_data="inline_top")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
