import asyncio
import logging
import os
import random
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
import html

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
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
GROUP_INVITE_LINK = os.getenv('GROUP_INVITE_LINK')  # ссылка на основную группу

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден!")
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

BOT_USERNAME = None

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

# ---------- Отправка главного меню ----------
async def send_main_menu(chat_id: int, user_id: int):
    macaco = await db.get_macaco_with_decay(user_id)
    safe_name = html.escape(macaco['name'])

    welcome_text = (
        f"<b>Меню макаки {safe_name}</b> 🐒\n\n"
        f"Вес: {macaco['weight']} кг\n"
        f"Уровень: {macaco['level']}\n"
        f"Здоровье: {macaco['health']}/100\n"
        f"Сытость: {100 - macaco['hunger']}/100\n"
        f"Настроение: {macaco['happiness']}/100\n\n"
        "👇 Выбери действие:"
    )
    markup = kb.main_menu_kb(user_id)
    await bot.send_message(chat_id, welcome_text, parse_mode=ParseMode.HTML, reply_markup=markup)

# ---------- Показать макаку ----------
async def show_my_macaco(user_id: int, source):
    try:
        if isinstance(source, CallbackQuery):
            if source.message is None:
                await source.answer("Сообщение устарело. Нажмите /start заново.", show_alert=True)
                return
            await source.answer()
        macaco = await db.get_macaco_with_decay(user_id)

        can_daily, daily_time = await db.can_get_daily(macaco['macaco_id'])
        daily_status = "✅ Доступна" if can_daily else f"⏳ Через: {daily_time}"
        hunger_status = "😋 Сыт" if macaco['hunger'] < 30 else "😐 Голоден" if macaco['hunger'] < 70 else "🆘 Очень голоден"
        info_text = (
            f"🐒 {macaco['name']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Вес: {macaco['weight']} кг\n"
            f"Уровень: {macaco['level']}\n"
            f"Опыт: {macaco['experience']}/100\n"
            f"Здоровье: {macaco['health']}/100\n"
            f"Сытость: {100 - macaco['hunger']}/100 ({hunger_status})\n"
            f"Настроение: {macaco['happiness']}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Ежедневная награда: {daily_status}\n"
            f"✏️ /rename — сменить имя"
        )
        markup = kb.back_to_menu_kb(user_id)
        if isinstance(source, CallbackQuery):
            try:
                await source.message.edit_text(info_text, parse_mode=None, reply_markup=markup)
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise e
        else:
            await source.answer(info_text, parse_mode=None, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка в show_my_macaco: {e}")
        error_text = "❌ Ошибка при получении данных макаки"
        if isinstance(source, CallbackQuery):
            if source.message:
                await source.message.edit_text(error_text)
        else:
            await source.answer(error_text)

# ---------- Топ игроков ----------
async def show_top_players(callback: CallbackQuery, user_id: int):
    try:
        if callback.message is None:
            await callback.answer("Сообщение устарело.", show_alert=True)
            return
        top = await db.get_top_macacos(5)
        if not top:
            text = "📊 Топ пуст! Будьте первым!"
            markup = kb.main_menu_kb(user_id)
        else:
            lines = ["🏆 ТОП-5 МАКАК 🏆\n", "────────────────────"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, (name, weight, level, username) in enumerate(top[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(f"{medal} {name}\n   🏋️ {weight} кг | ⭐ Ур. {level}\n   👤 {user_display}\n")
            lines.append("────────────────────")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb(user_id)
        await callback.message.edit_text(text, parse_mode=None, reply_markup=markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка топа: {e}")
        if callback.message:
            await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb(user_id))
        await callback.answer()

# ---------- КОМАНДЫ ----------
@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    user = message.from_user
    user_data = {'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
    await db.get_or_create_user(user_data)
    macaco = await db.get_or_create_macaco(user.id)
    # Применяем распад, чтобы показать актуальные данные
    await db.apply_happiness_decay(macaco['macaco_id'])
    await db.apply_hunger_decay(macaco['macaco_id'])
    await db.apply_health_decay(macaco['macaco_id'])
    macaco = await db.get_or_create_macaco(user.id)

    # Если имя стандартное – предлагаем сменить
    if macaco['name'] == 'Макака':
        await message.answer(
            "👋 Добро пожаловать в Боевые Макаки PRO!\n\n"
            "У вашей макаки пока нет имени. Давайте её назовём!\n"
            "✏️ Напишите имя (до 20 символов, можно использовать буквы, цифры, пробел, дефис и подчёркивание):",
            parse_mode=None
        )
        await state.set_state(Rename.waiting_for_name)
    else:
        await send_main_menu(message.chat.id, user.id)

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "📖 *ПОМОЩЬ: БОЕВЫЕ МАКАКИ PRO*\n"
        "═══════════════════════════════\n\n"
        "🔹 **ОСНОВНЫЕ КОМАНДЫ**\n"
        "/start – начать игру / создать макаку\n"
        "/my    – информация о твоей макаке\n"
        "/rename– сменить имя макаке\n"
        "/top   – топ‑5 самых тяжёлых макак\n"
        "/help  – эта справка\n\n"
        "🔹 **ЕДА**\n"
        "🍌 Банан     +1 кг   +30🍖  +10❤️  КД 5ч\n"
        "🥩 Мясо      +3 кг   +50🍖  +15❤️  КД 8ч\n"
        "🍰 Торт      +5 кг   +70🍖  +5❤️   КД12ч\n"
        "🥗 Салат     +2 кг   +40🍖  +12❤️  КД 6ч\n"
        "   ❗ При сытости = 0 макака теряет здоровье.\n"
        "   ❗ При настроении = 0 отказывается есть.\n\n"
        "🔹 **ЕЖЕДНЕВНАЯ НАГРАДА** 🎁\n"
        "   +1 кг, +5❤️, +5😊. Доступна раз в сутки.\n\n"
        "🔹 **ПРОГУЛКА** 🚶\n"
        "   • Настроение восстанавливается до 100.\n"
        "   • Здоровье не изменяется.\n\n"
        "🔹 **БОЕВАЯ СИСТЕМА** ⚔️\n"
        "   • Вызов: «Вызвать на бой» → соперник → ставка (1,3,5,10 кг).\n"
        "   • Принятие: у соперника 120 сек на ответ.\n"
        "   • Условия: ❤️ > 0, 🍖 > 60, вес ≥ ставки у обоих.\n"
        "   • Результат:\n"
        "     ✅ Победитель: +25 опыта, забирает вес ставки.\n"
        "     ❌ Проигравший: +10 опыта, теряет вес, -20😊, -10❤️.\n\n"
        "🔹 **ХАРАКТЕРИСТИКИ МАКАКИ**\n"
        "   🏋️ Вес       — растёт от еды и побед, падает от поражений.\n"
        "   ⭐ Уровень   — 100 опыта = +1 уровень.\n"
        "   📊 Опыт     — победа +25, поражение +10.\n"
        "   ❤️ Здоровье — падает: голод (-5/ч), поражение (-10);\n"
        "                 растёт: еда, ежедневная награда.\n"
        "   🍖 Сытость  — падает: каждые 2 ч (-5); растёт: еда.\n"
        "   😊 Настроение — падает: время (-10/ч), поражение (-20);\n"
        "                   растёт: прогулка (до 100), ежедневка.\n\n"
        "═══════════════════════════════\n"
        "🐒 Желаем весёлых боёв и вкусных бананов!"
    )
    try:
        await message.answer(help_text, parse_mode=None, reply_markup=kb.back_to_menu_kb(message.from_user.id))
    except Exception as e:
        logger.error(f"Ошибка в help_command: {e}", exc_info=True)
        short = (
            "📖 ПОМОЩЬ (кратко)\n"
            "────────────────\n"
            "/start, /my, /rename, /top, /help\n"
            "🍌 Еда: +вес, +❤️, +🍖, КД 5-12ч\n"
            "🎁 Ежедневно: +1 кг, +5❤️, +5😊\n"
            "🚶 Прогулка: 😊=100\n"
            "⚔️ Бой: вызов → ставка → 120сек\n"
            "   ✅ +25 опыта, +вес\n"
            "   ❌ +10 опыта, -вес, -20😊, -10❤️"
        )
        await message.answer(short, parse_mode=None, reply_markup=kb.back_to_menu_kb(message.from_user.id))

@dp.message(Command("my"))
async def my_macaco_command(message: Message):
    await show_my_macaco(message.from_user.id, message)

@dp.message(Command("top"))
async def top_command(message: Message):
    user_id = message.from_user.id
    try:
        top = await db.get_top_macacos(5)
        if not top:
            text = "📊 Топ пуст! Будьте первым!"
            markup = kb.main_menu_kb(user_id)
        else:
            lines = ["🏆 ТОП-5 МАКАК 🏆\n", "────────────────────"]
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, (name, weight, level, username) in enumerate(top[:5]):
                medal = medals[idx]
                user_display = f"@{username}" if username else "Без юзернейма"
                lines.append(f"{medal} {name}\n   🏋️ {weight} кг | ⭐ Ур. {level}\n   👤 {user_display}\n")
            lines.append("────────────────────")
            text = "\n".join(lines)
            markup = kb.back_to_menu_kb(user_id)
        await message.answer(text, parse_mode=None, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка top: {e}")
        await message.answer("❌ Ошибка")

@dp.message(Command("rename"))
async def rename_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    macaco = await db.get_or_create_macaco(user_id)
    await message.answer(
        f"🐒 Текущее имя: {macaco['name']}\n\n"
        f"✏️ Напишите новое имя (до 20 символов, буквы/цифры/пробел/дефис/подчёркивание):",
        parse_mode=None
    )
    await state.set_state(Rename.waiting_for_name)

@dp.message(Rename.waiting_for_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    user_id = message.from_user.id
    if len(new_name) > 20:
        await message.answer("❌ Слишком длинное! Максимум 20 символов.\nПопробуйте ещё раз:")
        return
    if len(new_name) < 2:
        await message.answer("❌ Слишком короткое! Минимум 2 символа.\nПопробуйте ещё раз:")
        return
    if not all(c.isalnum() or c in ' _-' for c in new_name):
        await message.answer("❌ Недопустимые символы.\nПопробуйте ещё раз:")
        return

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute('UPDATE macacos SET name = $1 WHERE user_id = $2', new_name, user_id)

    # Если есть ссылка на группу, отправляем приглашение (только при первом именовании – всегда сейчас)
    if GROUP_INVITE_LINK:
        await message.answer(
            f"Отлично, теперь у твоей макаки есть имя {new_name}! 🐒\n"
            f"Присоединяйся к нашей группе, чтобы сражаться с друзьями:",
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Перейти в группу", url=GROUP_INVITE_LINK)]
            ])
        )

    # Показываем главное меню
    await send_main_menu(message.chat.id, user_id)
    await state.clear()

# ---------- Универсальный обработчик защищённых callback ----------
@dp.callback_query(F.data.contains(":"))
async def protected_callback_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    action = parts[0]
    try:
        owner_id = int(parts[1])
    except ValueError:
        await callback.answer("Ошибка идентификатора", show_alert=True)
        return

    current_user_id = callback.from_user.id

    if current_user_id != owner_id:
        await callback.answer()
        await send_main_menu(callback.message.chat.id, current_user_id)
        return

    # ---------- Обработка основных действий ----------
    if action == "my_macaco":
        await show_my_macaco(current_user_id, callback)

    elif action == "select_food":
        macaco = await db.get_or_create_macaco(current_user_id)
        safe_name = html.escape(macaco['name'])
        text = (
            f"<b>Меню макаки {safe_name}</b> 🐒\n\n"
            "🍽️ Выберите еду:\n\n"
            "🍌 Банан: +1 кг, КД 5ч, +30 🍖, +10 ❤️\n"
            "🥩 Мясо: +3 кг, КД 8ч, +50 🍖, +15 ❤️\n"
            "🍰 Торт: +5 кг, КД 12ч, +70 🍖, +5 ❤️\n"
            "🥗 Салат: +2 кг, КД 6ч, +40 🍖, +12 ❤️"
        )
        markup = kb.food_selection_kb(current_user_id)
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        await callback.answer()

    elif action.startswith("food_"):
        macaco = await db.get_or_create_macaco(current_user_id)
        safe_name = html.escape(macaco['name'])
        food_id = int(action.split("_")[1])
        food = await db.get_food_info_cached(food_id)
        if not food:
            await callback.answer("❌ Еда не найдена")
            return
        text = (
            f"<b>Меню макаки {safe_name}</b> 🐒\n\n"
            f"{food['name']}\n"
            f"────────────────────\n"
            f"🏋️ +{food['weight_gain']} кг\n"
            f"🍖 +{food['hunger_decrease']}\n"
            f"❤️ +{food['health_gain']}\n"
            f"⏳ КД {food['cooldown_hours']} ч\n"
            f"────────────────────\n"
            f"Покормить этой едой?"
        )
        markup = kb.food_info_kb(food_id, current_user_id)
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        await callback.answer()

    elif action.startswith("feed_"):
        food_id = int(action.split("_")[1])
        user_id = current_user_id
        try:
            macaco = await db.get_macaco_with_decay(user_id)

            if macaco['happiness'] <= 0:
                await callback.message.edit_text(
                    "🥺 Я расстроена…\nСначала подними мне настроение прогулкой!",
                    parse_mode=None,
                    reply_markup=kb.main_menu_kb(user_id)
                )
                await callback.answer()
                return

            food = await db.get_food_info_cached(food_id)
            if not food:
                await callback.answer("❌ Еда не найдена")
                return

            can_feed, time_left = await db.can_feed_food(macaco['macaco_id'], food_id)
            if not can_feed:
                await callback.message.edit_text(
                    f"⏳ Нельзя кормить {food['name']}!\nДо следующего раза: {time_left}",
                    parse_mode=None,
                    reply_markup=kb.food_selection_kb(user_id)
                )
                await callback.answer()
                return

            await db.feed_macaco_with_food(macaco['macaco_id'], food_id)
            macaco = await db.get_or_create_macaco(user_id)

            await callback.message.answer(
                f"🍽️ Макака поела {food['name']}!\n"
                f"🏋️ Вес: +{food['weight_gain']} кг (теперь {macaco['weight']} кг)\n"
                f"❤️ Здоровье: +{food['health_gain']} (теперь {macaco['health']}/100)\n"
                f"🍖 Сытость: +{food['hunger_decrease']} (теперь {100 - macaco['hunger']}/100)\n"
                f"😊 Настроение: {macaco['happiness']}/100",
                parse_mode=None
            )
            await callback.message.edit_text(
                f"✅ Макака накормлена!\n\n"
                f"🍽️ {food['name']}\n"
                f"🏋️ Вес: {macaco['weight']} кг\n"
                f"❤️ Здоровье: {macaco['health']}/100\n"
                f"🍖 Сытость: {100 - macaco['hunger']}/100\n"
                f"😊 Настроение: {macaco['happiness']}/100",
                parse_mode=None,
                reply_markup=kb.main_menu_kb(user_id)
            )
        except Exception as e:
            logger.error(f"Ошибка кормления: {e}")
            await callback.message.edit_text("❌ Ошибка при кормлении", reply_markup=kb.main_menu_kb(user_id))
        await callback.answer()

    elif action == "daily_reward":
        user_id = current_user_id
        try:
            macaco = await db.get_macaco_with_decay(user_id)

            can, time_left = await db.can_get_daily(macaco['macaco_id'])
            if not can:
                await callback.message.edit_text(
                    f"⏳ Награда ещё не доступна. Следующая через: {time_left}",
                    parse_mode=None,
                    reply_markup=kb.main_menu_kb(user_id)
                )
                await callback.answer()
                return

            await db.give_daily_reward(macaco['macaco_id'])
            macaco = await db.get_or_create_macaco(user_id)

            # Если сообщение в группе, отправляем гифку в ЛС
            chat = callback.message.chat
            if chat.type != 'private':
                try:
                    await send_gif(
                        user_id,
                        'daily',
                        'reward',
                        caption=f"Текущий вес: {macaco['weight']} кг",
                        parse_mode=None
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить гифку в ЛС: {e}")
            else:
                # Если уже в личке, отправляем гифку прямо сюда
                await send_gif(
                    chat.id,
                    'daily',
                    'reward',
                    caption=f"Текущий вес: {macaco['weight']} кг",
                    parse_mode=None
                )

            await callback.message.edit_text(
                f"✅ Ежедневная награда получена!\n\n"
                f"🎁 +1 кг веса\n"
                f"❤️ +5 здоровья\n"
                f"😊 +5 настроения\n"
                f"🏋️ Текущий вес: {macaco['weight']} кг\n"
                f"❤️ Здоровье: {macaco['health']}/100\n"
                f"😊 Настроение: {macaco['happiness']}/100",
                parse_mode=None,
                reply_markup=kb.main_menu_kb(user_id)
            )
        except Exception as e:
            logger.error(f"Ошибка ежедневки: {e}")
            await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb(user_id))
        await callback.answer()

    elif action == "walk_macaco":
        user_id = current_user_id
        try:
            macaco = await db.get_macaco_with_decay(user_id)
            await db.walk_macaco(macaco['macaco_id'])
            macaco = await db.get_or_create_macaco(user_id)

            await callback.message.edit_text(
                f"🚶 Прогулка успешна!\n\n"
                f"😊 Настроение полностью восстановлено (100)\n"
                f"❤️ Здоровье осталось без изменений: {macaco['health']}/100",
                parse_mode=None,
                reply_markup=kb.main_menu_kb(user_id)
            )
        except Exception as e:
            logger.error(f"Ошибка прогулки: {e}")
            await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb(user_id))
        await callback.answer()

    elif action == "top_weight":
        await show_top_players(callback, current_user_id)

    elif action == "help_info":
        await callback.answer()
        await help_command(callback.message)

    elif action == "main_menu":
        await send_main_menu(callback.message.chat.id, current_user_id)
        await callback.answer()

    elif action == "cancel_fight":
        await callback.message.edit_text("❌ Бой отменён", reply_markup=kb.main_menu_kb(current_user_id))
        await callback.answer()

    # ---------- ВЫЗОВ НА БОЙ ----------
    elif action == "challenge_fight":
        user_id = current_user_id
        user_macaco = await db.get_macaco_with_decay(user_id)

        if user_macaco['health'] <= 0:
            await callback.message.edit_text("💔 Слишком слаб для боя! Восстанови здоровье.", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        if 100 - user_macaco['hunger'] <= 60:
            await callback.message.edit_text("🍖 Слишком голоден для боя! Покорми макаку.", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            opponents = await conn.fetch('''
                SELECT macaco_id, name, weight, level, user_id FROM macacos WHERE user_id != $1
            ''', user_id)

        if not opponents:
            await callback.message.edit_text("😕 Нет соперников!", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        safe_name = html.escape(user_macaco['name'])
        header = f"<b>Меню макаки {safe_name}</b> 🐒\n\n"
        await state.update_data(opponents_list=opponents, challenger_id=user_id)

        btns = []
        for opp in opponents[:10]:
            opp_id, name, weight, level, _ = opp
            btns.append([InlineKeyboardButton(text=f"{name} | 🏋️ {weight} кг | ⭐ {level}", callback_data=f"select_opp:{user_id}:{opp_id}")])
        btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"main_menu:{user_id}")])
        markup = InlineKeyboardMarkup(inline_keyboard=btns)
        await callback.message.edit_text(header + "🥊 Выберите соперника:", parse_mode=ParseMode.HTML, reply_markup=markup)
        await callback.answer()

    elif action == "select_opp":
        if len(parts) != 3:
            await callback.answer("Ошибка данных", show_alert=True)
            return
        try:
            opponent_id = int(parts[2])
        except ValueError:
            await callback.answer("Ошибка данных соперника", show_alert=True)
            return

        user_id = current_user_id
        macaco = await db.get_or_create_macaco(user_id)
        safe_name = html.escape(macaco['name'])
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            opp = await conn.fetchrow('SELECT name, weight, level FROM macacos WHERE macaco_id = $1', opponent_id)
        if not opp:
            await callback.message.edit_text("❌ Соперник недоступен", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        await state.update_data(challenge_opponent_id=opponent_id, opponent_name=opp['name'])

        text = (
            f"<b>Меню макаки {safe_name}</b> 🐒\n\n"
            f"⚔️ Вызов на бой\n────────────────────\n"
            f"🥊 Соперник: {opp['name']}\n🏋️ Вес: {opp['weight']} кг\n⭐ Уровень: {opp['level']}\n────────────────────\n"
            f"👇 Выберите ставку:"
        )
        markup = kb.bet_selection_challenge_kb(user_id, opponent_id)
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        await callback.answer()

    elif action.startswith("challenge_bet_"):
        if len(parts) != 3:
            await callback.answer("Ошибка данных", show_alert=True)
            return
        bet_amount = int(action.split("_")[2])
        opponent_id = int(parts[2])
        user_id = current_user_id

        user_macaco = await db.get_macaco_with_decay(user_id)

        can, msg = await db.can_make_bet(user_macaco['macaco_id'], bet_amount)
        if not can:
            await callback.message.edit_text(f"❌ {msg}", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            opp_data = await conn.fetchrow('SELECT name, weight, user_id FROM macacos WHERE macaco_id = $1', opponent_id)
        if not opp_data:
            await callback.message.edit_text("❌ Соперник недоступен", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return
        opp_name, opp_weight, opp_user_id = opp_data['name'], opp_data['weight'], opp_data['user_id']

        if opp_weight < bet_amount:
            await callback.message.edit_text(f"❌ У соперника недостаточно веса!", parse_mode=None,
                                             reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        try:
            await bot.send_chat_action(opp_user_id, action="typing")
        except:
            await callback.message.edit_text(f"😕 Соперник ({opp_name}) ещё не запускал бота.", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        global challenge_counter
        challenge_counter += 1
        cid = f"{user_id}-{opponent_id}-{challenge_counter}"
        challenge_text = (
            f"⚔️ Вас вызывают на бой!\n\n"
            f"🐒 Противник: {user_macaco['name']}\n"
            f"🏋️ Вес: {user_macaco['weight']} кг\n"
            f"⭐ Уровень: {user_macaco['level']}\n"
            f"💰 Ставка: {bet_amount} кг\n\n"
            f"У вас есть 120 секунд."
        )
        try:
            challenge_msg = await bot.send_message(opp_user_id, challenge_text, parse_mode=None,
                                                   reply_markup=kb.challenge_response_kb(cid, bet_amount))
        except Exception as e:
            logger.error(f"Не удалось отправить вызов: {e}")
            await callback.message.edit_text("❌ Не удалось отправить вызов", reply_markup=kb.main_menu_kb(user_id))
            await callback.answer()
            return

        async def timeout():
            await asyncio.sleep(120)
            if cid in active_challenges:
                del active_challenges[cid]
                try:
                    await challenge_msg.edit_text(f"⏳ Время вышло. Вызов от {user_macaco['name']} отклонён.")
                    await callback.message.edit_text("⏳ Соперник не ответил.", reply_markup=kb.main_menu_kb(user_id))
                except:
                    pass

        task = asyncio.create_task(timeout())
        active_challenges[cid] = {
            'challenger_id': user_id,
            'challenger_macaco_id': user_macaco['macaco_id'],
            'challenger_name': user_macaco['name'],
            'opponent_id': opp_user_id,
            'opponent_macaco_id': opponent_id,
            'opponent_name': opp_name,
            'bet': bet_amount,
            'message': challenge_msg,
            'task': task,
            'challenge_msg_id': callback.message.message_id,
            'challenge_chat_id': callback.message.chat.id
        }

        await callback.message.edit_text(
            f"✅ Вызов отправлен!\n\n🥊 Соперник: {opp_name}\n💰 Ставка: {bet_amount} кг\n\nОжидайте ответа... (120 сек)",
            parse_mode=None, reply_markup=kb.main_menu_kb(user_id)
        )
        await callback.answer()
        await state.clear()

    else:
        await callback.answer("Неизвестное действие", show_alert=True)

# ---------- Обработчики для ответа на вызов (без owner_id – личные сообщения) ----------
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

    c_macaco = await db.get_macaco_with_decay(chall['challenger_id'])
    o_macaco = await db.get_macaco_with_decay(opp_user_id)
    bet = chall['bet']

    if c_macaco['health'] <= 0 or o_macaco['health'] <= 0:
        await callback.message.edit_text("💔 Один из участников не может драться (здоровье = 0).", reply_markup=None)
        del active_challenges[cid]
        await callback.answer()
        return

    c_sat = 100 - c_macaco['hunger']
    o_sat = 100 - o_macaco['hunger']
    if c_sat <= 60 or o_sat <= 60:
        await callback.message.edit_text("🍖 Один из участников слишком голоден.", reply_markup=None)
        del active_challenges[cid]
        await callback.answer()
        return

    if c_macaco['weight'] < bet or o_macaco['weight'] < bet:
        await callback.message.edit_text("❌ Недостаточно веса у одного из участников.", reply_markup=None)
        del active_challenges[cid]
        await callback.answer()
        return

    await send_gif(callback.message.chat.id, 'fight', 'start', parse_mode=None)

    winner_id = random.choice([c_macaco['macaco_id'], o_macaco['macaco_id']])
    loser_id = o_macaco['macaco_id'] if winner_id == c_macaco['macaco_id'] else c_macaco['macaco_id']

    await db.decrease_happiness(loser_id, 20)
    await db.decrease_health(loser_id, 10)
    await db.update_weight_after_fight(winner_id, loser_id, bet)
    await db.record_fight(c_macaco['macaco_id'], o_macaco['macaco_id'], winner_id, bet)

    exp_gain = 25 if winner_id == c_macaco['macaco_id'] else 10
    await db.add_experience(winner_id, exp_gain)

    c_macaco = await db.get_or_create_macaco(chall['challenger_id'])
    o_macaco = await db.get_or_create_macaco(opp_user_id)

    if winner_id == c_macaco['macaco_id']:
        result_text = f"🎉 ПОБЕДА! {c_macaco['name']} победил {o_macaco['name']} и забрал {bet} кг!"
        loser_h = o_macaco['happiness']
        loser_hp = o_macaco['health']
    else:
        result_text = f"😔 ПОРАЖЕНИЕ {c_macaco['name']} проиграл {o_macaco['name']} и потерял {bet} кг.\n😊 -20, ❤️ -10"
        loser_h = c_macaco['happiness']
        loser_hp = c_macaco['health']

    result_msg = (
        f"{'🎉' if winner_id == c_macaco['macaco_id'] else '😔'} БОЙ ЗАВЕРШЁН!\n"
        f"────────────────────\n{result_text}\n\n"
        f"🏋️ {c_macaco['name']}: {c_macaco['weight']} кг\n"
        f"🏋️ {o_macaco['name']}: {o_macaco['weight']} кг\n"
        f"📊 Победитель +{exp_gain} опыта\n"
        f"😊 Настроение проигравшего: {loser_h}/100\n"
        f"❤️ Здоровье проигравшего: {loser_hp}/100\n"
        f"────────────────────"
    )

    await callback.message.edit_text(result_msg, parse_mode=None, reply_markup=None)
    try:
        await bot.send_message(chall['challenger_id'], result_msg, parse_mode=None)
    except Exception as e:
        logger.warning(f"Не удалось отправить результат инициатору боя: {e}")

    if chall['challenge_chat_id'] != chall['challenger_id'] and chall['challenge_chat_id'] != opp_user_id:
        try:
            await bot.send_message(chall['challenge_chat_id'], result_msg, parse_mode=None)
        except Exception as e:
            logger.warning(f"Не удалось отправить результат в общий чат: {e}")

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

async def main():
    global BOT_USERNAME
    logger.info("🤖 Бот 'Боевые Макаки PRO' запускается...")
    await db.init_db()
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
