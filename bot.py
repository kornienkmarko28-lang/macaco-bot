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
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramEntityTooLarge

import database as db
import keyboards as kb
import config as cfg

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print("❌ ОШИБКА: Токен не найден!")
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
BOT_USERNAME = None  # Сюда сохраним юзернейм бота после запуска

class Rename(StatesGroup):
    waiting_for_name = State()

class Challenge(StatesGroup):
    waiting_for_opponent = State()
    waiting_for_bet = State()

active_challenges = {}
challenge_counter = 0

# ---------- Отправка гифок ----------
async def send_gif(chat_id, gif_type: str, gif_name: str, caption: str = "", parse_mode=None):
    try:
        gif_info = cfg.get_gif_info(gif_type, gif_name)
        if gif_info and cfg.check_gif_exists(gif_type, gif_name):
            animation = FSInputFile(gif_info['path'])
            await bot.send_animation(chat_id, animation, caption=caption or gif_info.get('caption', ''), parse_mode=parse_mode)
            return True
    except Exception as e:
        logger.warning(f"Гифка {gif_type}/{gif_name}: {e}")
    return False

# ---------- Показать макаку ----------
async def show_my_macaco(user_id: int, source):
    try:
        if isinstance(source, CallbackQuery):
            await source.answer()
        macaco = await db.get_or_create_macaco(user_id)
        await db.apply_happiness_decay(macaco['id'])
        await db.apply_hunger_decay(macaco['id'])
        await db.apply_health_decay(macaco['id'])
        macaco = await db.get_or_create_macaco(user_id)
        can_daily, daily_time = await db.can_get_daily(macaco['id'])
        daily_status = "✅ Доступна" if can_daily else f"⏳ Через: {daily_time}"
        hunger_status = "😋 Сыт" if macaco['hunger'] < 30 else "😐 Голоден" if macaco['hunger'] < 70 else "🆘 Очень голоден"
        info_text = (
            f"🐒 <b>{macaco['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏋️ <b>Вес:</b> {macaco['weight']} кг\n"
            f"⭐ <b>Уровень:</b> {macaco['level']}\n"
            f"📊 <b>Опыт:</b> {macaco['exp']}/100\n"
            f"❤️ <b>Здоровье:</b> {macaco['health']}/100\n"
            f"🍖 <b>Сытость:</b> {100 - macaco['hunger']}/100 ({hunger_status})\n"
            f"😊 <b>Настроение:</b> {macaco['happiness']}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 <b>Ежедневная награда:</b> {daily_status}\n"
            f"✏️ /rename — сменить имя"
        )
        markup = kb.main_menu_kb()
        if isinstance(source, CallbackQuery):
            try:
                await source.message.edit_text(info_text, parse_mode=ParseMode.HTML, reply_markup=markup)
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise e
        else:
            await source.answer(info_text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка в show_my_macaco: {e}")
        error_text = "❌ Ошибка при получении данных макаки"
        if isinstance(source, CallbackQuery):
            await source.message.edit_text(error_text)
        else:
            await source.answer(error_text)

# ---------- Топ игроков ----------
async def show_top_players(callback: CallbackQuery):
    try:
        top = await db.get_top_macacos(5)
        if not top:
            text = "📊 <b>Топ пуст!</b>\nБудьте первым!"
            markup = kb.main_menu_kb()
        else:
            lines = ["🏆 <b>ТОП-5 МАКАК</b> 🏆\n", "━━━━━━━━━━━━━━━━━━━━"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, (name, weight, level, username) in enumerate(top[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(f"{medal} <b>{name}</b>\n   🏋️ {weight} кг | ⭐ Ур. {level}\n   👤 {user_display}\n")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb()
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка топа: {e}")
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb())
        await callback.answer()

# ---------- КОМАНДЫ ----------
@dp.message(CommandStart())
async def start_command(message: Message):
    user = message.from_user
    user_data = {'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
    await db.get_or_create_user(user_data)
    macaco = await db.get_or_create_macaco(user.id)
    await db.apply_happiness_decay(macaco['id'])
    await db.apply_hunger_decay(macaco['id'])
    await db.apply_health_decay(macaco['id'])
    welcome_text = (
        "🎮 <b>Добро пожаловать в Боевые Макаки PRO!</b> 🐒\n\n"
        "<b>Что нового:</b>\n"
        "• 4 вида еды с разными эффектами\n"
        "• Ежедневная награда (+1 кг, +❤️, +😊)\n"
        f"• Инлайн-режим — @{BOT_USERNAME} команда\n"
        "• ✏️ /rename — дай имя макаке!\n"
        "• ⚔️ Вызов на бой с подтверждением\n"
        "• 😊 Настроение: падает со временем и при проигрыше\n"
        "• 🚶 Прогулка — восстанавливает настроение и здоровье\n"
        "• 🍖 Сытость: падает каждые 2 часа, влияет на бой и здоровье\n"
        "• ❤️ Здоровье: падает при голоде и в боях\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=kb.main_menu_kb())

@dp.message(Command("help"))
async def help_command(message: Message):
    """Команда /help - использует глобальный BOT_USERNAME"""
    global BOT_USERNAME
    # Если по какой-то причине BOT_USERNAME не задан, используем заглушку
    bot_username = BOT_USERNAME or "bot"
    
    # Основной текст помощи (уже проверен, не превышает лимит)
    help_text = (
        "📖 <b>ПОМОЩЬ ПО ИГРЕ — БОЕВЫЕ МАКАКИ PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🐒 1. ОСНОВНЫЕ КОМАНДЫ</b>\n"
        "• /start — начать игру (создать макаку)\n"
        "• /my — информация о твоей макаке\n"
        "• /rename — сменить имя макаке\n"
        "• /top — топ-5 самых тяжёлых макак\n"
        "• /help — эта справка\n\n"
        "<b>🍌 2. ЕДА И КОРМЛЕНИЕ</b>\n"
        "┌─────────────────────────────────────┐\n"
        "│ 🍌 Банан   │ +1 кг │ +10 😊 │ -30 🍖 │ +10 ❤️ │ КД 5ч │\n"
        "│ 🥩 Мясо    │ +3 кг │  +5 😊 │ -50 🍖 │ +15 ❤️ │ КД 8ч │\n"
        "│ 🍰 Торт    │ +5 кг │ +20 😊 │ -70 🍖 │  +5 ❤️ │ КД12ч │\n"
        "│ 🥗 Салат   │ +2 кг │ +15 😊 │ -40 🍖 │ +12 ❤️ │ КД 6ч │\n"
        "└─────────────────────────────────────┘\n"
        "• При сытости = 0 макака теряет здоровье.\n"
        "• При настроении = 0 макака отказывается есть.\n\n"
        "<b>🎁 3. ЕЖЕДНЕВНАЯ НАГРАДА</b>\n"
        "• +1 кг веса, +5 😊, +5 ❤️. Доступна раз в сутки.\n\n"
        "<b>🚶 4. ПРОГУЛКА</b>\n"
        "• Настроение = 100, +15 ❤️.\n\n"
        "<b>⚔️ 5. БОЕВАЯ СИСТЕМА</b>\n"
        "• <b>Вызов:</b> «Вызвать на бой» → соперник → ставка.\n"
        "• <b>Принятие:</b> 60 сек на ответ.\n"
        "• <b>Условия:</b> ❤️ > 0, 🍖 < 70, вес ≥ ставки.\n"
        "• <b>Результат:</b>\n"
        "  - Победитель: +25 опыта, забирает вес ставки.\n"
        "  - Проигравший: +10 опыта, теряет вес, -20 😊, -10 ❤️.\n\n"
        "<b>📊 6. ХАРАКТЕРИСТИКИ</b>\n"
        "┌─────────────────────────────────────┐\n"
        "│ 🏋️ Вес      │ еда/победа ↑, поражение ↓  │\n"
        "│ ⭐ Уровень  │ 100 опыта = +1 уровень    │\n"
        "│ 📊 Опыт    │ +25 победа, +10 поражение │\n"
        "│ ❤️ Здоровье│ голод (-5/ч), поражение (-10)│\n"
        "│            │ еда/прогулка/ежедневка +  │\n"
        "│ 🍖 Сытость │ падает: каждые 2ч (-5)   │\n"
        "│ 😊 Настрое-│ время (-10/ч), поражение (-20)│\n"
        "│    ние     │ еда/прогулка/ежедневка + │\n"
        "└─────────────────────────────────────┘\n\n"
        "<b>💬 7. ИНЛАЙН-РЕЖИМ</b>\n"
        f"• @{bot_username} info — инфо о макаке\n"
        f"• @{bot_username} feed — меню кормления\n"
        f"• @{bot_username} fight — список соперников\n"
        f"• @{bot_username} top — топ игроков\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🐒 <b>Желаем весёлых боёв и вкусных бананов!</b>"
    )
    
    try:
        await message.answer(help_text, parse_mode=ParseMode.HTML, reply_markup=kb.back_to_menu_kb())
    except TelegramEntityTooLarge:
        # Если вдруг сообщение слишком длинное — отправляем краткую версию
        short_help = (
            "📖 <b>ПОМОЩЬ (кратко)</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "/start, /my, /rename, /top, /help\n"
            "🍌 Еда: +вес, +❤️, +😊, -🍖, КД 5-12ч\n"
            "🎁 Ежедневно: +1 кг, +5❤️, +5😊\n"
            "🚶 Прогулка: 😊=100, +15❤️\n"
            "⚔️ Бой: вызов → ставка → 60сек\n"
            "   Победа: +25 опыта, +вес\n"
            "   Поражение: +10 опыта, -вес, -20😊, -10❤️\n"
            "📊 Здоровье ↓ при 🍖=0 и поражении\n"
            f"💬 Инлайн: @{bot_username} info/feed/fight/top\n"
            "━━━━━━━━━━━━━━━━"
        )
        await message.answer(short_help, parse_mode=ParseMode.HTML, reply_markup=kb.back_to_menu_kb())
    except Exception as e:
        logger.error(f"Ошибка в help_command: {e}", exc_info=True)
        await message.answer("❌ Не удалось загрузить справку. Попробуйте позже.", reply_markup=kb.back_to_menu_kb())

@dp.message(Command("my"))
async def my_macaco_command(message: Message):
    await show_my_macaco(message.from_user.id, message)

@dp.message(Command("top"))
async def top_command(message: Message):
    try:
        top = await db.get_top_macacos(5)
        if not top:
            text = "📊 <b>Топ пуст!</b>\nБудьте первым!"
            markup = kb.main_menu_kb()
        else:
            lines = ["🏆 <b>ТОП-5 МАКАК</b> 🏆\n", "━━━━━━━━━━━━━━━━━━━━"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, (name, weight, level, username) in enumerate(top[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(f"{medal} <b>{name}</b>\n   🏋️ {weight} кг | ⭐ Ур. {level}\n   👤 {user_display}\n")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb()
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка top: {e}")
        await message.answer("❌ Ошибка")

@dp.message(Command("rename"))
async def rename_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    macaco = await db.get_or_create_macaco(user_id)
    await message.answer(
        f"🐒 Текущее имя: <b>{macaco['name']}</b>\n\n"
        f"✏️ Напишите новое имя (до 20 символов, буквы/цифры/пробел/дефис/подчёркивание):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Rename.waiting_for_name)

@dp.message(Rename.waiting_for_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    user_id = message.from_user.id
    if len(new_name) > 20:
        await message.answer("❌ Слишком длинное! Максимум 20 символов.")
        return
    if len(new_name) < 2:
        await message.answer("❌ Слишком короткое! Минимум 2 символа.")
        return
    if not all(c.isalnum() or c in ' _-' for c in new_name):
        await message.answer("❌ Недопустимые символы.")
        return
    async with aiosqlite.connect(db.DB_NAME) as conn:
        await conn.execute('UPDATE macacos SET name = ? WHERE user_id = ?', (new_name, user_id))
        await conn.commit()
    await message.answer(f"✅ Имя изменено на <b>{new_name}</b>!", parse_mode=ParseMode.HTML, reply_markup=kb.main_menu_kb())
    await state.clear()

# ---------- КНОПКИ ----------
@dp.callback_query(F.data == "my_macaco")
async def my_macaco_callback(callback: CallbackQuery):
    await show_my_macaco(callback.from_user.id, callback)

@dp.callback_query(F.data == "select_food")
async def select_food_callback(callback: CallbackQuery):
    text = (
        "🍽️ <b>Выберите еду:</b>\n\n"
        "🍌 Банан: +1 кг, КД 5ч, +10 😊, -30 🍖, +10 ❤️\n"
        "🥩 Мясо: +3 кг, КД 8ч, +5 😊, -50 🍖, +15 ❤️\n"
        "🍰 Торт: +5 кг, КД 12ч, +20 😊, -70 🍖, +5 ❤️\n"
        "🥗 Салат: +2 кг, КД 6ч, +15 😊, -40 🍖, +12 ❤️"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb.food_selection_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("food_"))
async def food_info_callback(callback: CallbackQuery):
    food_id = int(callback.data.split("_")[1])
    food = await db.get_food_info(food_id)
    if not food:
        await callback.answer("❌ Еда не найдена")
        return
    text = (
        f"{food['name']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏋️ +{food['weight_gain']} кг\n"
        f"😊 +{food['happiness_gain']}\n"
        f"🍖 -{food['hunger_decrease']}\n"
        f"❤️ +{food['health_gain']}\n"
        f"⏳ КД {food['cooldown_hours']} ч\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Покормить этой едой?"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb.food_info_kb(food_id))
    await callback.answer()

@dp.callback_query(F.data.startswith("feed_"))
async def feed_with_food_callback(callback: CallbackQuery):
    food_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    try:
        macaco = await db.get_or_create_macaco(user_id)
        await db.apply_happiness_decay(macaco['id'])
        await db.apply_hunger_decay(macaco['id'])
        await db.apply_health_decay(macaco['id'])
        macaco = await db.get_or_create_macaco(user_id)
        if macaco['happiness'] <= 0:
            await callback.message.edit_text(
                "🥺 <b>Я расстроена…</b>\nСначала подними мне настроение прогулкой!",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        food = await db.get_food_info(food_id)
        if not food:
            await callback.answer("❌ Еда не найдена")
            return
        can_feed, time_left = await db.can_feed_food(macaco['id'], food_id)
        if not can_feed:
            await callback.message.edit_text(
                f"⏳ <b>Нельзя кормить {food['name']}!</b>\nДо следующего раза: {time_left}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.food_selection_kb()
            )
            await callback.answer()
            return
        await db.feed_macaco_with_food(macaco['id'], food_id)
        macaco = await db.get_or_create_macaco(user_id)
        await callback.message.answer(
            f"🍽️ <b>Макака поела {food['name']}!</b>\n"
            f"🏋️ Вес: +{food['weight_gain']} кг (теперь {macaco['weight']} кг)\n"
            f"❤️ Здоровье: +{food['health_gain']} (теперь {macaco['health']}/100)\n"
            f"🍖 Сытость: -{food['hunger_decrease']} (теперь {100 - macaco['hunger']}/100)\n"
            f"😊 Настроение: +{food['happiness_gain']} (теперь {macaco['happiness']}/100)",
            parse_mode=ParseMode.HTML
        )
        await callback.message.edit_text(
            f"✅ <b>Макака накормлена!</b>\n\n"
            f"🍽️ {food['name']}\n"
            f"🏋️ Вес: <b>{macaco['weight']} кг</b>\n"
            f"❤️ Здоровье: {macaco['health']}/100\n"
            f"🍖 Сытость: {100 - macaco['hunger']}/100\n"
            f"😊 Настроение: {macaco['happiness']}/100",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка кормления: {e}")
        await callback.message.edit_text("❌ Ошибка при кормлении", reply_markup=kb.main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "daily_reward")
async def daily_reward_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        macaco = await db.get_or_create_macaco(user_id)
        await db.apply_happiness_decay(macaco['id'])
        await db.apply_hunger_decay(macaco['id'])
        await db.apply_health_decay(macaco['id'])
        macaco = await db.get_or_create_macaco(user_id)
        can, time_left = await db.can_get_daily(macaco['id'])
        if not can:
            await callback.message.edit_text(
                f"⏳ Награда ещё не доступна. Следующая через: {time_left}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        await db.give_daily_reward(macaco['id'])
        macaco = await db.get_or_create_macaco(user_id)
        await send_gif(callback.message.chat.id, 'daily', 'reward',
                       caption=f"Текущий вес: <b>{macaco['weight']} кг</b>", parse_mode=ParseMode.HTML)
        await callback.message.edit_text(
            f"✅ <b>Ежедневная награда получена!</b>\n\n"
            f"🎁 +1 кг веса\n"
            f"❤️ +5 здоровья\n"
            f"😊 +5 настроения\n"
            f"🏋️ Текущий вес: <b>{macaco['weight']} кг</b>\n"
            f"❤️ Здоровье: {macaco['health']}/100\n"
            f"😊 Настроение: {macaco['happiness']}/100",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка ежедневки: {e}")
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "walk_macaco")
async def walk_macaco_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        macaco = await db.get_or_create_macaco(user_id)
        await db.apply_happiness_decay(macaco['id'])
        await db.apply_hunger_decay(macaco['id'])
        await db.apply_health_decay(macaco['id'])
        await db.walk_macaco(macaco['id'])
        macaco = await db.get_or_create_macaco(user_id)
        await send_gif(callback.message.chat.id, 'walk', 'walking', parse_mode=ParseMode.HTML)
        await callback.message.edit_text(
            f"🚶 <b>Прогулка успешна!</b>\n\n"
            f"😊 Настроение полностью восстановлено (100)\n"
            f"❤️ Здоровье +15 (теперь {macaco['health']}/100)",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка прогулки: {e}")
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "top_weight")
async def top_weight_callback(callback: CallbackQuery):
    await show_top_players(callback)

# ---------- ВЫЗОВ НА БОЙ ----------
@dp.callback_query(F.data == "challenge_fight")
async def challenge_list_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    user_macaco = await db.get_or_create_macaco(user_id)
    await db.apply_happiness_decay(user_macaco['id'])
    await db.apply_hunger_decay(user_macaco['id'])
    await db.apply_health_decay(user_macaco['id'])
    user_macaco = await db.get_or_create_macaco(user_id)
    if user_macaco['health'] <= 0:
        await callback.message.edit_text("💔 Слишком слаб для боя! Восстанови здоровье.", reply_markup=kb.main_menu_kb())
        return
    if user_macaco['hunger'] >= 70:
        await callback.message.edit_text("🍖 Слишком голоден для боя! Покорми макаку.", reply_markup=kb.main_menu_kb())
        return
    async with aiosqlite.connect(db.DB_NAME) as conn:
        opponents = await (await conn.execute(
            'SELECT macaco_id, name, weight, level, user_id FROM macacos WHERE user_id != ?', (user_id,)
        )).fetchall()
    if not opponents:
        await callback.message.edit_text("😕 Нет соперников!", reply_markup=kb.main_menu_kb())
        return
    await state.update_data(opponents_list=opponents)
    btns = []
    for opp in opponents[:10]:
        opp_id, name, weight, level, _ = opp
        btns.append([InlineKeyboardButton(text=f"{name} | 🏋️ {weight} кг | ⭐ {level}", callback_data=f"select_opp_{opp_id}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    await callback.message.edit_text("🥊 <b>Выберите соперника:</b>", parse_mode=ParseMode.HTML,
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("select_opp_"))
async def select_opponent_callback(callback: CallbackQuery, state: FSMContext):
    opp_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    await callback.answer()
    async with aiosqlite.connect(db.DB_NAME) as conn:
        opp = await (await conn.execute('SELECT name, weight, level FROM macacos WHERE macaco_id = ?', (opp_id,))).fetchone()
    if not opp:
        await callback.message.edit_text("❌ Соперник недоступен", reply_markup=kb.main_menu_kb())
        return
    await state.update_data(challenge_opponent_id=opp_id, opponent_name=opp[0])
    await callback.message.edit_text(
        f"⚔️ <b>Вызов на бой</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🥊 <b>Соперник:</b> {opp[0]}\n🏋️ Вес: {opp[1]} кг\n⭐ Уровень: {opp[2]}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <b>Выберите ставку:</b>",
        parse_mode=ParseMode.HTML, reply_markup=kb.bet_selection_challenge_kb()
    )

@dp.callback_query(F.data.startswith("challenge_bet_"))
async def challenge_bet_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка данных")
        return
    bet = int(parts[2])
    user_id = callback.from_user.id
    data = await state.get_data()
    opp_id = data.get('challenge_opponent_id')
    if not opp_id:
        await callback.message.edit_text("❌ Не выбран соперник", reply_markup=kb.main_menu_kb())
        await state.clear()
        await callback.answer()
        return
    user_macaco = await db.get_or_create_macaco(user_id)
    await db.apply_happiness_decay(user_macaco['id'])
    await db.apply_hunger_decay(user_macaco['id'])
    await db.apply_health_decay(user_macaco['id'])
    user_macaco = await db.get_or_create_macaco(user_id)
    can, msg = await db.can_make_bet(user_macaco['id'], bet)
    if not can:
        await callback.message.edit_text(f"❌ {msg}", reply_markup=kb.main_menu_kb())
        await callback.answer()
        return
    async with aiosqlite.connect(db.DB_NAME) as conn:
        opp_data = await (await conn.execute(
            'SELECT name, weight, user_id FROM macacos WHERE macaco_id = ?', (opp_id,)
        )).fetchone()
    if not opp_data:
        await callback.message.edit_text("❌ Соперник недоступен", reply_markup=kb.main_menu_kb())
        await callback.answer()
        return
    opp_name, opp_weight, opp_user_id = opp_data
    if opp_weight < bet:
        await callback.message.edit_text(f"❌ У соперника недостаточно веса!", parse_mode=ParseMode.HTML,
                                         reply_markup=kb.main_menu_kb())
        await callback.answer()
        return
    try:
        await bot.send_chat_action(opp_user_id, action="typing")
    except:
        await callback.message.edit_text(f"😕 Соперник ({opp_name}) ещё не запускал бота.", reply_markup=kb.main_menu_kb())
        await callback.answer()
        return
    global challenge_counter
    challenge_counter += 1
    cid = f"{user_id}-{opp_id}-{challenge_counter}"
    challenge_text = (
        f"⚔️ <b>Вас вызывают на бой!</b>\n\n"
        f"🐒 <b>Противник:</b> {user_macaco['name']}\n"
        f"🏋️ Вес: {user_macaco['weight']} кг\n"
        f"⭐ Уровень: {user_macaco['level']}\n"
        f"💰 <b>Ставка:</b> {bet} кг\n\n"
        f"<i>У вас есть 60 секунд.</i>"
    )
    try:
        challenge_msg = await bot.send_message(opp_user_id, challenge_text, parse_mode=ParseMode.HTML,
                                               reply_markup=kb.challenge_response_kb(cid, bet))
    except Exception as e:
        logger.error(f"Не удалось отправить вызов: {e}")
        await callback.message.edit_text("❌ Не удалось отправить вызов", reply_markup=kb.main_menu_kb())
        await callback.answer()
        return
    async def timeout():
        await asyncio.sleep(60)
        if cid in active_challenges:
            del active_challenges[cid]
            try:
                await challenge_msg.edit_text(f"⏳ Время вышло. Вызов от {user_macaco['name']} отклонён.")
                await callback.message.edit_text("⏳ Соперник не ответил.", reply_markup=kb.main_menu_kb())
            except: pass
    task = asyncio.create_task(timeout())
    active_challenges[cid] = {
        'challenger_id': user_id,
        'challenger_macaco_id': user_macaco['id'],
        'challenger_name': user_macaco['name'],
        'opponent_id': opp_user_id,
        'opponent_macaco_id': opp_id,
        'opponent_name': opp_name,
        'bet': bet,
        'message': challenge_msg,
        'task': task,
        'challenge_msg_id': callback.message.message_id,
        'challenge_chat_id': callback.message.chat.id
    }
    await callback.message.edit_text(
        f"✅ <b>Вызов отправлен!</b>\n\n🥊 Соперник: {opp_name}\n💰 Ставка: {bet} кг\n\nОжидайте ответа... (60 сек)",
        parse_mode=ParseMode.HTML, reply_markup=kb.main_menu_kb()
    )
    await callback.answer()
    await state.clear()

@dp.callback_query(F.data.startswith("accept_fight_"))
async def accept_fight_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка данных")
        return
    cid = parts[2]
    if cid not in active_challenges:
        await callback.message.edit_text("❌ Вызов недействителен", reply_markup=None)
        await callback.answer()
        return
    chall = active_challenges[cid]
    opp_user_id = callback.from_user.id
    if opp_user_id != chall['opponent_id']:
        await callback.answer("❌ Это не ваш вызов!")
        return
    chall['task'].cancel()
    c_macaco = await db.get_or_create_macaco(chall['challenger_id'])
    o_macaco = await db.get_or_create_macaco(opp_user_id)
    await db.apply_happiness_decay(c_macaco['id'])
    await db.apply_hunger_decay(c_macaco['id'])
    await db.apply_health_decay(c_macaco['id'])
    await db.apply_happiness_decay(o_macaco['id'])
    await db.apply_hunger_decay(o_macaco['id'])
    await db.apply_health_decay(o_macaco['id'])
    c_macaco = await db.get_or_create_macaco(chall['challenger_id'])
    o_macaco = await db.get_or_create_macaco(opp_user_id)
    bet = chall['bet']
    if c_macaco['health'] <= 0 or o_macaco['health'] <= 0:
        await callback.message.edit_text("💔 Один из участников не может драться (здоровье = 0).", reply_markup=kb.main_menu_kb())
        del active_challenges[cid]
        await callback.answer()
        return
    if c_macaco['hunger'] >= 70 or o_macaco['hunger'] >= 70:
        await callback.message.edit_text("🍖 Один из участников слишком голоден.", reply_markup=kb.main_menu_kb())
        del active_challenges[cid]
        await callback.answer()
        return
    if c_macaco['weight'] < bet or o_macaco['weight'] < bet:
        await callback.message.edit_text("❌ Недостаточно веса у одного из участников.", reply_markup=kb.main_menu_kb())
        del active_challenges[cid]
        await callback.answer()
        return
    await send_gif(callback.message.chat.id, 'fight', 'start', parse_mode=ParseMode.HTML)
    winner_id = random.choice([c_macaco['id'], o_macaco['id']])
    loser_id = o_macaco['id'] if winner_id == c_macaco['id'] else c_macaco['id']
    await db.decrease_happiness(loser_id, 20)
    await db.decrease_health(loser_id, 10)
    await db.update_weight_after_fight(winner_id, loser_id, bet)
    await db.record_fight(c_macaco['id'], o_macaco['id'], winner_id, bet)
    exp_gain = 25 if winner_id == c_macaco['id'] else 10
    await db.add_experience(winner_id, exp_gain)
    c_macaco = await db.get_or_create_macaco(chall['challenger_id'])
    o_macaco = await db.get_or_create_macaco(opp_user_id)
    if winner_id == c_macaco['id']:
        result_text = f"🎉 <b>ПОБЕДА!</b> {c_macaco['name']} победил {o_macaco['name']} и забрал {bet} кг!"
        loser_h = o_macaco['happiness']
        loser_hp = o_macaco['health']
    else:
        result_text = f"😔 <b>ПОРАЖЕНИЕ</b> {c_macaco['name']} проиграл {o_macaco['name']} и потерял {bet} кг.\n😊 -20, ❤️ -10"
        loser_h = c_macaco['happiness']
        loser_hp = c_macaco['health']
    result_msg = (
        f"{'🎉' if winner_id == c_macaco['id'] else '😔'} <b>БОЙ ЗАВЕРШЁН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n{result_text}\n\n"
        f"🏋️ {c_macaco['name']}: {c_macaco['weight']} кг\n"
        f"🏋️ {o_macaco['name']}: {o_macaco['weight']} кг\n"
        f"📊 Победитель +{exp_gain} опыта\n"
        f"😊 Настроение проигравшего: {loser_h}/100\n"
        f"❤️ Здоровье проигравшего: {loser_hp}/100\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.edit_text(result_msg, parse_mode=ParseMode.HTML, reply_markup=None)
    try:
        await bot.send_message(chall['challenger_id'], result_msg, parse_mode=ParseMode.HTML)
    except:
        pass
    del active_challenges[cid]
    await callback.answer()

@dp.callback_query(F.data.startswith("decline_fight_"))
async def decline_fight_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка")
        return
    cid = parts[2]
    if cid not in active_challenges:
        await callback.message.edit_text("❌ Вызов недействителен", reply_markup=None)
        await callback.answer()
        return
    chall = active_challenges[cid]
    chall['task'].cancel()
    try:
        await bot.send_message(chall['challenger_id'], f"😕 {chall['opponent_name']} отклонил ваш вызов.")
    except:
        pass
    await callback.message.edit_text(f"❌ Вы отклонили вызов от {chall['challenger_name']}.", reply_markup=None)
    del active_challenges[cid]
    await callback.answer()

@dp.callback_query(F.data == "cancel_fight")
async def cancel_fight_callback(callback: CallbackQuery):
    await callback.message.edit_text("❌ Бой отменён", reply_markup=kb.main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text("👇 <b>Главное меню:</b>", parse_mode=ParseMode.HTML, reply_markup=kb.main_menu_kb())
    await callback.answer()

# ---------- КНОПКА ПОМОЩИ (ИСПРАВЛЕНО) ----------
@dp.callback_query(F.data == "help_info")
async def help_info_callback(callback: CallbackQuery):
    await callback.answer()  # Сразу отвечаем, чтобы кнопка не зависла
    await help_command(callback.message)

# ---------- ИНЛАЙН-РЕЖИМ ----------
@dp.inline_query()
async def inline_mode(inline_query: InlineQuery):
    q = inline_query.query.lower().strip()
    uid = inline_query.from_user.id
    results = []
    try:
        if q in ["", "info", "мой", "макака"]:
            m = await db.get_or_create_macaco(uid)
            await db.apply_happiness_decay(m['id'])
            await db.apply_hunger_decay(m['id'])
            await db.apply_health_decay(m['id'])
            m = await db.get_or_create_macaco(uid)
            results.append(InlineQueryResultArticle(
                id="1", title=f"🐒 {m['name']}",
                description=f"Вес: {m['weight']} кг | Ур. {m['level']} | ❤️ {m['health']} | 🍖 {100 - m['hunger']} | 😊 {m['happiness']}",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"🐒 <b>{m['name']}</b>\nВес: {m['weight']} кг\nУровень: {m['level']}\nОпыт: {m['exp']}/100\n"
                        f"❤️ Здоровье: {m['health']}/100\n🍖 Сытость: {100 - m['hunger']}/100\n😊 Настроение: {m['happiness']}/100"
                    ), parse_mode=ParseMode.HTML
                ),
                reply_markup=kb.inline_actions_kb(m['id']),
                thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
            ))
        elif q in ["feed", "кормить", "еда"]:
            results.append(InlineQueryResultArticle(
                id="2", title="🍌 Покормить макаку", description="Выберите еду",
                input_message_content=InputTextMessageContent(message_text="🍽️ <b>Выберите еду:</b>", parse_mode=ParseMode.HTML),
                reply_markup=kb.food_selection_kb(),
                thumbnail_url="https://img.icons8.com/color/96/000000/banana.png"
            ))
        elif q in ["fight", "бой", "вызов"]:
            results.append(InlineQueryResultArticle(
                id="3", title="⚔️ Вызвать на бой", description="Список соперников",
                input_message_content=InputTextMessageContent(message_text="⚔️ <b>Вызов на бой</b>", parse_mode=ParseMode.HTML),
                reply_markup=kb.inline_actions_kb(0),
                thumbnail_url="https://img.icons8.com/color/96/000000/boxing.png"
            ))
        elif q in ["top", "топ", "рейтинг"]:
            top = await db.get_top_macacos(3)
            if top:
                txt = "🏆 <b>ТОП-3 МАКАК:</b>\n"
                medals = ["🥇", "🥈", "🥉"]
                for i, (name, w, lvl, _) in enumerate(top):
                    txt += f"{medals[i]} {name} — {w} кг (ур. {lvl})\n"
            else:
                txt = "🏆 Топ пуст!"
            results.append(InlineQueryResultArticle(
                id="4", title="🏆 Топ игроков", description="Лучшие по весу",
                input_message_content=InputTextMessageContent(message_text=txt, parse_mode=ParseMode.HTML),
                thumbnail_url="https://img.icons8.com/color/96/000000/prize.png"
            ))
        else:
            found = await db.search_macacos(q, 5)
            for i, m in enumerate(found):
                results.append(InlineQueryResultArticle(
                    id=f"search_{i}", title=f"🐒 {m['name']}",
                    description=f"Вес: {m['weight']} кг | Ур. {m['level']}",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🐒 <b>{m['name']}</b>\nВес: {m['weight']} кг\nУровень: {m['level']}",
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=kb.inline_actions_kb(m['id']),
                    thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
                ))
        if not results:
            results.append(InlineQueryResultArticle(
                id="0", title="🤔 Не найдено", description="Попробуйте: info, feed, fight, top",
                input_message_content=InputTextMessageContent(message_text="Команды: info, feed, fight, top")
            ))
        await inline_query.answer(results, cache_time=60, is_personal=True)
    except Exception as e:
        logger.error(f"Инлайн ошибка: {e}")
        await inline_query.answer([], cache_time=60)

# ---------- ЗАПУСК ----------
async def main():
    global BOT_USERNAME
    logger.info("🤖 Бот 'Боевые Макаки PRO' запускается...")
    try:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
        logger.info(f"✅ Бот авторизован: @{BOT_USERNAME}")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print("\nПРОВЕРЬТЕ:\n1. Токен в BOT_TOKEN\n2. Зависимости\n3. Интернет\n")

if __name__ == "__main__":
    asyncio.run(main())
