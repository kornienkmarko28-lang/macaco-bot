import os
from typing import Dict, List

# Конфигурация гифок
GIF_CONFIG: Dict[str, Dict] = {
    'feeding': {
        'banana': {
            'path': 'images/feeding_banana.gif',
            'caption': '🍌 *Макака с удовольствием ест банан!*\n+1 кг к весу!',
            'alt_text': '🍌 Макака ест банан! +1 кг'
        },
        'meat': {
            'path': 'images/feeding_meat.gif',
            'caption': '🥩 *Макака уплетает мясо!*\n+3 кг к весу!',
            'alt_text': '🥩 Макака ест мясо! +3 кг'
        },
        'cake': {
            'path': 'images/feeding_cake.gif',
            'caption': '🍰 *Макака наслаждается тортом!*\n+5 кг к весу!',
            'alt_text': '🍰 Макака ест торт! +5 кг'
        },
        'salad': {
            'path': 'images/feeding_salad.gif',
            'caption': '🥗 *Макака хрустит салатом!*\n+2 кг к весу!',
            'alt_text': '🥗 Макака ест салат! +2 кг'
        }
    },
    'fight': {
        'win': {
            'path': 'images/fight_win.gif',
            'caption': '🎉 *ПОБЕДА!* Ваша макака победила!',
            'alt_text': '🎉 Победа в бою!'
        },
        'lose': {
            'path': 'images/fight_lose.gif',
            'caption': '😔 *Поражение...* Ваша макака проиграла.',
            'alt_text': '😔 Поражение в бою'
        },
        'start': {
            'path': 'images/fight_start.gif',
            'caption': '🥊 *Бой начинается!*',
            'alt_text': '🥊 Начало боя!'
        }
    },
    'daily': {
        'reward': {
            'path': 'images/daily_reward.gif',
            'caption': '🎁 *Ежедневная награда!*\n+1 кг к весу!',
            'alt_text': '🎁 Ежедневная награда! +1 кг'
        }
    },
    'walk': {
        'walking': {
            'path': 'images/walking.gif',
            'caption': '🚶 *Вы гуляете с макакой!*\nНастроение улучшено!',
            'alt_text': '🚶 Прогулка с макакой!'
        }
    }
}

# Конфигурация еды
FOOD_CONFIG: Dict[int, Dict] = {
    1: {'name': '🍌 Банан', 'weight': 1, 'happiness': 10, 'hunger': 30, 'cooldown': 5},
    2: {'name': '🥩 Мясо', 'weight': 3, 'happiness': 5, 'hunger': 50, 'cooldown': 8},
    3: {'name': '🍰 Торт', 'weight': 5, 'happiness': 20, 'hunger': 70, 'cooldown': 12},
    4: {'name': '🥗 Салат', 'weight': 2, 'happiness': 15, 'hunger': 40, 'cooldown': 6}
}

# Проверка существования гифок
def check_gif_exists(gif_type: str, gif_name: str) -> bool:
    config = GIF_CONFIG.get(gif_type, {}).get(gif_name, {})
    if not config or 'path' not in config:
        return False
    return os.path.exists(config['path'])

# Получение информации о гифке
def get_gif_info(gif_type: str, gif_name: str) -> Dict:
    config = GIF_CONFIG.get(gif_type, {}).get(gif_name, {})
    return config if config else {}