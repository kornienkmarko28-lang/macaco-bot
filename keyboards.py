from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🐒 Моя макака", callback_data=f"my_macaco:{user_id}")],
        [
            InlineKeyboardButton(text="🍌 Покормить", callback_data=f"select_food:{user_id}"),
            InlineKeyboardButton(text="🎁 Ежедневная награда", callback_data=f"daily_reward:{user_id}")
        ],
        [
            InlineKeyboardButton(text="⚔️ Вызвать на бой", callback_data=f"challenge_fight:{user_id}"),
            InlineKeyboardButton(text="🚶 Выгулять", callback_data=f"walk_macaco:{user_id}")
        ],
        [InlineKeyboardButton(text="🏆 Топ по весу", callback_data=f"top_weight:{user_id}")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data=f"help_info:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def food_selection_kb(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🍌 Банан (+1 кг)", callback_data=f"food_1:{user_id}"),
            InlineKeyboardButton(text="🥩 Мясо (+3 кг)", callback_data=f"food_2:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🍰 Торт (+5 кг)", callback_data=f"food_3:{user_id}"),
            InlineKeyboardButton(text="🥗 Салат (+2 кг)", callback_data=f"food_4:{user_id}")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"main_menu:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def food_info_kb(food_id: int, user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✅ Покормить этой едой", callback_data=f"feed_{food_id}:{user_id}")],
        [InlineKeyboardButton(text="⬅️ Выбрать другую еду", callback_data=f"select_food:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def bet_selection_challenge_kb(user_id: int, opponent_id: int) -> InlineKeyboardMarkup:
    # Здесь opponent_id не нужно проверять на владельца, но для единообразия добавим user_id владельца вызова
    keyboard = [
        [
            InlineKeyboardButton(text="1 кг", callback_data=f"challenge_bet_1:{user_id}:{opponent_id}"),
            InlineKeyboardButton(text="3 кг", callback_data=f"challenge_bet_3:{user_id}:{opponent_id}")
        ],
        [
            InlineKeyboardButton(text="5 кг", callback_data=f"challenge_bet_5:{user_id}:{opponent_id}"),
            InlineKeyboardButton(text="10 кг", callback_data=f"challenge_bet_10:{user_id}:{opponent_id}")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_fight:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def challenge_response_kb(challenge_id: str, bet: int) -> InlineKeyboardMarkup:
    # Кнопки для ответа на вызов – отправляются в личку, владелец один, проверка не нужна
    keyboard = [
        [
            InlineKeyboardButton(text="🥊 Принять бой", callback_data=f"accept_fight_{challenge_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_fight_{challenge_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def after_fight_kb(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⚔️ Новый бой", callback_data=f"challenge_fight:{user_id}")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=f"main_menu:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_to_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=f"main_menu:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def inline_actions_kb(macaco_id: int) -> InlineKeyboardMarkup:
    # Для инлайн-режима владелец – тот, кто нажал, поэтому user_id не добавляем, обрабатываем отдельно
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
