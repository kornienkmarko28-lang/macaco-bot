from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

# Главное меню
def main_menu_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🐒 Моя макака", callback_data="my_macaco")],
        [
            InlineKeyboardButton(text="🍌 Покормить", callback_data="select_food"),
            InlineKeyboardButton(text="🎁 Ежедневная награда", callback_data="daily_reward")
        ],
        [
            InlineKeyboardButton(text="⚔️ Найти бой", callback_data="find_fight"),
            InlineKeyboardButton(text="🚶 Выгулять", callback_data="walk_macaco")
        ],
        [InlineKeyboardButton(text="🏆 Топ по весу", callback_data="top_weight")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help_info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Выбор еды
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

# Информация о еде
def food_info_kb(food_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✅ Покормить этой едой", callback_data=f"feed_{food_id}")],
        [InlineKeyboardButton(text="⬅️ Выбрать другую еду", callback_data="select_food")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Выбор ставки для боя
def bet_selection_kb(opponent_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="1 кг", callback_data=f"bet_1_{opponent_id}"),
            InlineKeyboardButton(text="3 кг", callback_data=f"bet_3_{opponent_id}")
        ],
        [
            InlineKeyboardButton(text="5 кг", callback_data=f"bet_5_{opponent_id}"),
            InlineKeyboardButton(text="10 кг", callback_data=f"bet_10_{opponent_id}")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fight")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Подтверждение боя
def fight_confirmation_kb(opponent_id: int, bet_amount: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Начать бой", callback_data=f"start_fight_{opponent_id}_{bet_amount}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fight")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# После боя
def after_fight_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data="find_fight")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Кнопка назад
def back_to_menu_kb() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Инлайн-кнопки для режима inline
def inline_actions_kb(macaco_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🐒 Инфо", callback_data=f"inline_info_{macaco_id}"),
            InlineKeyboardButton(text="🍌 Кормить", callback_data=f"inline_feed_{macaco_id}")
        ],
        [
            InlineKeyboardButton(text="⚔️ Вызвать на бой", callback_data=f"inline_fight_{macaco_id}"),
            InlineKeyboardButton(text="🏆 Топ", callback_data="inline_top")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)