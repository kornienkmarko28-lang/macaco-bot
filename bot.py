import asyncio
import logging
import os
import random
import aiosqlite
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent
)
from aiogram.enums import ParseMode

import database as db
import keyboards as kb
import config as cfg

# ========== ЗАГРУЗКА ТОКЕНА ==========
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден в переменных окружения!")
    print("💡 Убедитесь, что в Bothost добавлена переменная BOT_TOKEN")
    exit(1)

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== FSM ДЛЯ ПЕРЕИМЕНОВАНИЯ ==========
class Rename(StatesGroup):
    waiting_for_name = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def show_my_macaco(user_id: int, source):
    """Показать информацию о макаке пользователя"""
    try:
        macaco = await db.get_or_create_macaco(user_id)
        
        can_daily, daily_time = await db.can_get_daily(macaco['id'])
        daily_status = "✅ Доступна" if can_daily else f"⏳ Через: {daily_time}"
        
        info_text = (
            f"🐒 <b>{macaco['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏋️ <b>Вес:</b> {macaco['weight']} кг\n"
            f"⭐ <b>Уровень:</b> {macaco['level']}\n"
            f"📊 <b>Опыт:</b> {macaco['exp']}/100\n"
            f"❤️ <b>Здоровье:</b> {macaco['health']}/100\n"
            f"🍖 <b>Сытость:</b> {100 - macaco['hunger']}/100\n"
            f"😊 <b>Настроение:</b> {macaco['happiness']}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 <b>Ежедневная награда:</b> {daily_status}\n"
            f"✏️ /rename — сменить имя"
        )
        
        markup = kb.main_menu_kb()
        
        if isinstance(source, CallbackQuery):
            await source.message.edit_text(
                info_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup
            )
            await source.answer()
        else:
            await source.answer(
                info_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Ошибка в show_my_macaco: {e}")
        error_text = "❌ Ошибка при получении данных макаки"
        if isinstance(source, CallbackQuery):
            await source.message.edit_text(error_text)
            await source.answer()
        else:
            await source.answer(error_text)

async def show_top_players(callback: CallbackQuery):
    """Показать топ игроков"""
    try:
        top_macacos = await db.get_top_macacos(5)
        
        if not top_macacos:
            text = "📊 <b>Топ пуст!</b>\nБудьте первым!"
            markup = kb.main_menu_kb()
        else:
            lines = ["🏆 <b>ТОП-5 МАКАК</b> 🏆\n", "━━━━━━━━━━━━━━━━━━━━"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            
            for idx, (name, weight, level, username) in enumerate(top_macacos[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(
                    f"{medal} <b>{name}</b>\n"
                    f"   🏋️ {weight} кг | ⭐ Ур. {level}\n"
                    f"   👤 {user_display}\n"
                )
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb()
        
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_top_players: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке топа",
            reply_markup=kb.main_menu_kb()
        )
        await callback.answer()

# ========== КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_command(message: Message):
    user = message.from_user
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    await db.get_or_create_user(user_data)
    await db.get_or_create_macaco(user.id)
    
    bot_username = (await bot.get_me()).username
    
    welcome_text = (
        "🎮 <b>Добро пожаловать в Боевые Макаки PRO!</b> 🐒\n\n"
        "<b>Новые возможности:</b>\n"
        "• 4 вида еды с разными эффектами\n"
        "• Ежедневная награда (+1 кг каждый день)\n"
        f"• Инлайн-режим — пишите @{bot_username} команда\n"
        "• Анимация для каждого действия\n"
        "• ✏️ /rename — дай имя своей макаке!\n"
        "\n"
        "👇 <b>Выбери действие:</b>"
    )
    
    await message.answer(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.main_menu_kb()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    bot_username = (await bot.get_me()).username
    help_text = (
        "📖 <b>Помощь по игре</b>\n\n"
        "<b>Основные команды:</b>\n"
        "• /start — начать игру\n"
        "• /help — эта справка\n"
        "• /top — топ игроков\n"
        "• /my — моя макака\n"
        "• /rename — сменить имя макаке\n\n"
        "<b>Инлайн-режим:</b>\n"
        f"Начните писать @{bot_username} в любом чате и выберите команду:\n"
        "• info — информация о макаке\n"
        "• feed — покормить\n"
        "• fight — найти бой\n"
        "• top — топ игроков\n\n"
        "<b>Виды еды:</b>\n"
        "• 🍌 Банан: +1 кг, КД 5ч\n"
        "• 🥩 Мясо: +3 кг, КД 8ч\n"
        "• 🍰 Торт: +5 кг, КД 12ч\n"
        "• 🥗 Салат: +2 кг, КД 6ч"
    )
    
    await message.answer(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.back_to_menu_kb()
    )

@dp.message(Command("my"))
async def my_macaco_command(message: Message):
    await show_my_macaco(message.from_user.id, message)

@dp.message(Command("top"))
async def top_command(message: Message):
    try:
        top_macacos = await db.get_top_macacos(5)
        
        if not top_macacos:
            text = "📊 <b>Топ пуст!</b>\nБудьте первым!"
            markup = kb.main_menu_kb()
        else:
            lines = ["🏆 <b>ТОП-5 МАКАК</b> 🏆\n", "━━━━━━━━━━━━━━━━━━━━"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            
            for idx, (name, weight, level, username) in enumerate(top_macacos[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(
                    f"{medal} <b>{name}</b>\n"
                    f"   🏋️ {weight} кг | ⭐ Ур. {level}\n"
                    f"   👤 {user_display}\n"
                )
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb()
        
        await message.answer(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка в top_command: {e}")
        await message.answer("❌ Ошибка при загрузке топа")

@dp.message(Command("rename"))
async def rename_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    macaco = await db.get_or_create_macaco(user_id)
    
    await message.answer(
        f"🐒 Текущее имя вашей макаки: <b>{macaco['name']}</b>\n\n"
        f"✏️ Напишите новое имя (до 20 символов, можно использовать буквы, цифры, пробел, дефис и подчёркивание):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Rename.waiting_for_name)

@dp.message(Rename.waiting_for_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    user_id = message.from_user.id
    
    # Проверки
    if len(new_name) > 20:
        await message.answer("❌ Имя слишком длинное! Максимум 20 символов.\nПопробуйте ещё раз:")
        return
    if len(new_name) < 2:
        await message.answer("❌ Имя слишком короткое! Минимум 2 символа.\nПопробуйте ещё раз:")
        return
    if not all(c.isalnum() or c in ' _-' for c in new_name):
        await message.answer("❌ Можно использовать только буквы, цифры, пробел, дефис и подчёркивание.\nПопробуйте ещё раз:")
        return
    
    # Сохраняем новое имя в базу
    async with aiosqlite.connect(db.DB_NAME) as conn:
        await conn.execute(
            'UPDATE macacos SET name = ? WHERE user_id = ?',
            (new_name, user_id)
        )
        await conn.commit()
    
    await message.answer(
        f"✅ Имя успешно изменено на <b>{new_name}</b>!",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.main_menu_kb()
    )
    await state.clear()

# ========== ОБРАБОТЧИКИ КНОПОК ==========
@dp.callback_query(F.data == "my_macaco")
async def my_macaco_callback(callback: CallbackQuery):
    await show_my_macaco(callback.from_user.id, callback)

@dp.callback_query(F.data == "select_food")
async def select_food_callback(callback: CallbackQuery):
    text = (
        "🍽️ <b>Выберите еду для макаки:</b>\n\n"
        "🍌 Банан: +1 кг, КД 5ч\n"
        "🥩 Мясо: +3 кг, КД 8ч\n"
        "🍰 Торт: +5 кг, КД 12ч\n"
        "🥗 Салат: +2 кг, КД 6ч"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.food_selection_kb()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("food_"))
async def food_info_callback(callback: CallbackQuery):
    food_id = int(callback.data.split("_")[1])
    food_info = await db.get_food_info(food_id)
    
    if not food_info:
        await callback.answer("❌ Еда не найдена")
        return
    
    text = (
        f"{food_info['name']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏋️ <b>Прибавка веса:</b> +{food_info['weight_gain']} кг\n"
        f"😊 <b>Радость:</b> +{food_info['happiness_gain']}\n"
        f"🍖 <b>Сытость:</b> +{food_info['hunger_decrease']}\n"
        f"⏳ <b>Кулдаун:</b> {food_info['cooldown_hours']} ч\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Покормить макаку этой едой?"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.food_info_kb(food_id)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("feed_"))
async def feed_with_food_callback(callback: CallbackQuery):
    food_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    try:
        macaco = await db.get_or_create_macaco(user_id)
        food_info = await db.get_food_info(food_id)
        
        if not food_info:
            await callback.answer("❌ Еда не найдена")
            return
        
        can_feed, time_left = await db.can_feed_food(macaco['id'], food_id)
        
        if not can_feed:
            await callback.message.edit_text(
                f"⏳ <b>Нельзя кормить этой едой!</b>\n\n"
                f"До следующего кормления {food_info['name']}: {time_left}\n"
                f"Выберите другую еду.",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.food_selection_kb()
            )
            await callback.answer()
            return
        
        success = await db.feed_macaco_with_food(macaco['id'], food_id)
        if not success:
            await callback.answer("❌ Ошибка при кормлении")
            return
        
        macaco = await db.get_or_create_macaco(user_id)
        
        # Отправка гифки
        gif_types = {1: 'banana', 2: 'meat', 3: 'cake', 4: 'salad'}
        gif_type = gif_types.get(food_id, 'banana')
        gif_info = cfg.get_gif_info('feeding', gif_type)
        
        if gif_info and cfg.check_gif_exists('feeding', gif_type):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=f"{gif_info['caption']}\n"
                        f"Текущий вес: <b>{macaco['weight']} кг</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.answer(
                f"{food_info['name']} — макака поела!\n"
                f"Текущий вес: <b>{macaco['weight']} кг</b>",
                parse_mode=ParseMode.HTML
            )
        
        await callback.message.edit_text(
            f"✅ <b>Макака накормлена!</b>\n\n"
            f"🍽️ {food_info['name']}\n"
            f"🏋️ Вес: <b>{macaco['weight']} кг</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в feed_with_food_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при кормлении",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "daily_reward")
async def daily_reward_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        macaco = await db.get_or_create_macaco(user_id)
        can_daily, time_left = await db.can_get_daily(macaco['id'])
        
        if not can_daily:
            await callback.message.edit_text(
                f"⏳ <b>Ежедневная награда ещё не доступна!</b>\n\n"
                f"Следующая награда через: <b>{time_left}</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        success = await db.give_daily_reward(macaco['id'])
        if not success:
            await callback.answer("❌ Ошибка при получении награды")
            return
        
        macaco = await db.get_or_create_macaco(user_id)
        
        gif_info = cfg.get_gif_info('daily', 'reward')
        if gif_info and cfg.check_gif_exists('daily', 'reward'):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=f"{gif_info['caption']}\n"
                        f"Текущий вес: <b>{macaco['weight']} кг</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.answer(
                "🎁 <b>Ежедневная награда получена!</b>\n"
                f"+1 кг к весу!\n"
                f"Текущий вес: <b>{macaco['weight']} кг</b>",
                parse_mode=ParseMode.HTML
            )
        
        await callback.message.edit_text(
            f"✅ <b>Ежедневная награда получена!</b>\n\n"
            f"🎁 +1 кг к весу\n"
            f"😊 +5 к настроению\n"
            f"🏋️ Текущий вес: <b>{macaco['weight']} кг</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в daily_reward_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при получении награды",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "find_fight")
async def find_fight_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        user_macaco = await db.get_or_create_macaco(user_id)
        opponent = await db.find_opponent(user_macaco['id'])
        
        if not opponent:
            await callback.message.edit_text(
                "😕 <b>Соперников не найдено!</b>\n"
                "Пригласите друзей в игру или создайте тестового бойца через терминал.\n\n"
                "💡 <i>Один в поле не воин – нужна хотя бы ещё одна макака!</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        text = (
            f"⚔️ <b>Найден соперник!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🐒 <b>Ваша макака:</b> {user_macaco['name']}\n"
            f"🏋️ Вес: {user_macaco['weight']} кг\n"
            f"⭐ Уровень: {user_macaco['level']}\n\n"
            f"🥊 <b>Соперник:</b> {opponent['name']}\n"
            f"🏋️ Вес: {opponent['weight']} кг\n"
            f"⭐ Уровень: {opponent['level']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <b>Выберите ставку:</b>"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.bet_selection_kb(opponent['id'])
        )
        
    except Exception as e:
        logger.error(f"Ошибка в find_fight_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при поиске боя",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# ---------- ВАЖНО: ОБРАБОТЧИК ВЫБОРА СТАВКИ ----------
@dp.callback_query(F.data.startswith("bet_"))
async def bet_selection_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка в данных ставки")
        return

    try:
        bet_amount = int(parts[1])
        opponent_id = int(parts[2])
        user_id = callback.from_user.id

        user_macaco = await db.get_or_create_macaco(user_id)

        # Проверяем, может ли макака сделать ставку
        can_bet, msg = await db.can_make_bet(user_macaco['id'], bet_amount)
        if not can_bet:
            await callback.message.edit_text(
                f"❌ {msg}",
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return

        # Получаем данные соперника для отображения имени
        async with aiosqlite.connect(db.DB_NAME) as conn:
            cursor = await conn.execute(
                'SELECT name, weight FROM macacos WHERE macaco_id = ?',
                (opponent_id,)
            )
            opponent_data = await cursor.fetchone()

        if not opponent_data:
            await callback.message.edit_text(
                "❌ Соперник больше не доступен",
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return

        opponent_name = opponent_data[0]
        opponent_weight = opponent_data[1]

        if opponent_weight < bet_amount:
            await callback.message.edit_text(
                f"❌ У соперника недостаточно веса!\n"
                f"Вес {opponent_name}: {opponent_weight} кг\n"
                f"Ваша ставка: {bet_amount} кг",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return

        # Показываем экран подтверждения
        confirm_text = (
            f"🥊 <b>Подтверждение боя</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🐒 <b>Ваш боец:</b> {user_macaco['name']}\n"
            f"🏋️ Вес: {user_macaco['weight']} кг\n"
            f"💰 Ставка: {bet_amount} кг\n\n"
            f"🥊 <b>Соперник:</b> {opponent_name}\n"
            f"🏋️ Вес: {opponent_weight} кг\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Победитель забирает {bet_amount} кг у проигравшего!</i>"
        )

        await callback.message.edit_text(
            confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.fight_confirmation_kb(opponent_id, bet_amount)
        )

    except Exception as e:
        logger.error(f"Ошибка в bet_selection_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при выборе ставки",
            reply_markup=kb.main_menu_kb()
        )

    await callback.answer()

@dp.callback_query(F.data.startswith("start_fight_"))
async def start_fight_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 4:
        await callback.answer("❌ Ошибка данных")
        return
    
    try:
        opponent_id = int(parts[2])
        bet_amount = int(parts[3])
        user_id = callback.from_user.id
        
        user_macaco = await db.get_or_create_macaco(user_id)
        
        can_bet, msg = await db.can_make_bet(user_macaco['id'], bet_amount)
        if not can_bet:
            await callback.message.edit_text(
                f"❌ {msg}",
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        # Получаем данные соперника
        async with aiosqlite.connect(db.DB_NAME) as conn:
            cursor = await conn.execute(
                'SELECT macaco_id, name, weight FROM macacos WHERE macaco_id = ?',
                (opponent_id,)
            )
            opponent_data = await cursor.fetchone()
        
        if not opponent_data:
            await callback.message.edit_text(
                "❌ Соперник больше не доступен",
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        # Гифка начала боя
        gif_info = cfg.get_gif_info('fight', 'start')
        if gif_info and cfg.check_gif_exists('fight', 'start'):
            anim = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                anim,
                caption=gif_info['caption'],
                parse_mode=ParseMode.HTML
            )
        
        # Симуляция боя
        winner_id = random.choice([user_macaco['id'], opponent_id])
        loser_id = opponent_id if winner_id == user_macaco['id'] else user_macaco['id']
        
        await db.update_weight_after_fight(winner_id, loser_id, bet_amount)
        await db.record_fight(user_macaco['id'], opponent_id, winner_id, bet_amount)
        
        exp_gain = 25 if winner_id == user_macaco['id'] else 10
        async with aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute(
                'UPDATE macacos SET experience = experience + ? WHERE macaco_id = ?',
                (exp_gain, winner_id)
            )
            await conn.commit()
        
        user_macaco = await db.get_or_create_macaco(user_id)
        
        if winner_id == user_macaco['id']:
            result_gif = 'win'
            result_text = f"🎉 <b>ПОБЕДА!</b> Ваша макака забирает {bet_amount} кг у {opponent_data[1]}!"
        else:
            result_gif = 'lose'
            result_text = f"😔 <b>ПОРАЖЕНИЕ</b> Ваша макака теряет {bet_amount} кг в пользу {opponent_data[1]}."
        
        # Гифка результата
        gif_info = cfg.get_gif_info('fight', result_gif)
        if gif_info and cfg.check_gif_exists('fight', result_gif):
            anim = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                anim,
                caption=gif_info['caption'],
                parse_mode=ParseMode.HTML
            )
        
        result_msg = (
            f"{'🎉' if winner_id == user_macaco['id'] else '😔'} <b>БОЙ ЗАВЕРШЁН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{result_text}\n\n"
            f"🏋️ Ваш вес: <b>{user_macaco['weight']} кг</b>\n"
            f"📊 Опыт: +{exp_gain}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        await callback.message.edit_text(
            result_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.after_fight_kb()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в start_fight_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка во время боя",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "walk_macaco")
async def walk_macaco_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        async with aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute(
                'UPDATE macacos SET happiness = happiness + 15 WHERE user_id = ?',
                (user_id,)
            )
            await conn.commit()
        
        macaco = await db.get_or_create_macaco(user_id)
        
        gif_info = cfg.get_gif_info('walk', 'walking')
        if gif_info and cfg.check_gif_exists('walk', 'walking'):
            anim = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                anim,
                caption=gif_info['caption'],
                parse_mode=ParseMode.HTML
            )
        
        await callback.message.edit_text(
            f"🚶 <b>Прогулка успешна!</b>\n\n"
            f"😊 Настроение: +15\n"
            f"Текущее настроение: {macaco['happiness']}/100",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в walk_macaco_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при выгуливании",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "top_weight")
async def top_weight_callback(callback: CallbackQuery):
    await show_top_players(callback)

@dp.callback_query(F.data == "cancel_fight")
async def cancel_fight_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "❌ Бой отменён",
        reply_markup=kb.main_menu_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "👇 <b>Главное меню:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.main_menu_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "help_info")
async def help_info_callback(callback: CallbackQuery):
    await help_command(callback.message)

# ========== ИНЛАЙН-РЕЖИМ ==========
@dp.inline_query()
async def inline_mode(inline_query: InlineQuery):
    query = inline_query.query.lower().strip()
    user_id = inline_query.from_user.id
    
    results = []
    
    try:
        if query in ["", "info", "мой", "макака"]:
            macaco = await db.get_or_create_macaco(user_id)
            result = InlineQueryResultArticle(
                id="1",
                title=f"🐒 {macaco['name']}",
                description=f"Вес: {macaco['weight']} кг | Ур. {macaco['level']}",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"🐒 <b>{macaco['name']}</b>\n"
                        f"Вес: {macaco['weight']} кг\n"
                        f"Уровень: {macaco['level']}\n"
                        f"Опыт: {macaco['exp']}/100"
                    ),
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=kb.inline_actions_kb(macaco['id']),
                thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
            )
            results.append(result)
        
        elif query in ["feed", "кормить", "еда"]:
            result = InlineQueryResultArticle(
                id="2",
                title="🍌 Покормить макаку",
                description="Выберите еду",
                input_message_content=InputTextMessageContent(
                    message_text="🍽️ <b>Выберите еду:</b>",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=kb.food_selection_kb(),
                thumbnail_url="https://img.icons8.com/color/96/000000/banana.png"
            )
            results.append(result)
        
        elif query in ["fight", "бой", "драка"]:
            result = InlineQueryResultArticle(
                id="3",
                title="⚔️ Найти бой",
                description="Поиск соперника",
                input_message_content=InputTextMessageContent(
                    message_text="⚔️ <b>Поиск соперника...</b>",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=kb.inline_actions_kb(0),
                thumbnail_url="https://img.icons8.com/color/96/000000/boxing.png"
            )
            results.append(result)
        
        elif query in ["top", "топ", "рейтинг"]:
            top = await db.get_top_macacos(3)
            if top:
                text = "🏆 <b>ТОП-3 МАКАК:</b>\n"
                medals = ["🥇", "🥈", "🥉"]
                for idx, (name, weight, level, username) in enumerate(top):
                    text += f"{medals[idx]} {name} — {weight} кг\n"
            else:
                text = "🏆 Топ пуст!"
            
            result = InlineQueryResultArticle(
                id="4",
                title="🏆 Топ игроков",
                description="Лучшие по весу",
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode=ParseMode.HTML
                ),
                thumbnail_url="https://img.icons8.com/color/96/000000/prize.png"
            )
            results.append(result)
        
        else:
            found = await db.search_macacos(query, 5)
            for idx, m in enumerate(found):
                result = InlineQueryResultArticle(
                    id=f"search_{idx}",
                    title=f"🐒 {m['name']}",
                    description=f"Вес: {m['weight']} кг | Ур. {m['level']}",
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"🐒 <b>{m['name']}</b>\n"
                            f"Вес: {m['weight']} кг\n"
                            f"Уровень: {m['level']}"
                        ),
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=kb.inline_actions_kb(m['id']),
                    thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
                )
                results.append(result)
        
        if not results:
            result = InlineQueryResultArticle(
                id="0",
                title="🤔 Не найдено",
                description="Попробуйте: info, feed, fight, top",
                input_message_content=InputTextMessageContent(
                    message_text="Команды: info, feed, fight, top"
                )
            )
            results.append(result)
        
        await inline_query.answer(results, cache_time=60, is_personal=True)
    
    except Exception as e:
        logger.error(f"Ошибка в inline_mode: {e}")
        await inline_query.answer([], cache_time=60)

# ========== ЗАПУСК ==========
async def main():
    logger.info("🤖 Бот 'Боевые Макаки PRO' запускается...")
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот авторизован: @{bot_info.username}")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print("\n" + "="*60)
        print("ПРОВЕРЬТЕ:")
        print("1. Токен в переменной BOT_TOKEN на Bothost")
        print("2. Установлены ли все зависимости (requirements.txt)")
        print("3. Интернет-соединение")
        print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
