import asyncio
import logging
import os
import random
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, FSInputFile, 
    InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent, InlineQueryResultPhoto
)
from aiogram.enums import ParseMode

import database as db
import keyboards as kb
import config as cfg

# Загрузка переменных
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден в .env")
    exit(1)

# Настройка
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ========== КОМАНДЫ ==========

@dp.message(CommandStart())
async def start_command(message: Message):
    user = message.from_user
    
    # Регистрация
    user_data = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    await db.get_or_create_user(user_data)
    await db.get_or_create_macaco(user.id)
    
    welcome_text = (
        "🎮 *Добро пожаловать в Боевые Макаки PRO!* 🐒\n\n"
        "*Новые возможности:*\n"
        "• 🍽️ *4 вида еды* с разными эффектами\n"
        "• 🎁 *Ежедневная награда* (+1 кг каждый день)\n"
        "• 🎯 *Инлайн-режим* - пишите @macaco_бот команда\n"
        "• 🎬 *Анимации* для каждого действия\n\n"
        "👇 *Выбери действие:*"
    )
    
    await message.answer(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.main_menu_kb()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "📖 *Помощь по игре*\n\n"
        "*Основные команды:*\n"
        "• /start - начать игру\n"
        "• /help - эта справка\n"
        "• /top - топ игроков\n"
        "• /my - моя макака\n\n"
        "*Инлайн-режим:*\n"
        "1. Начните писать @ваш_бот\n"
        "2. Выберите команду:\n"
        "   - `info` - информация о макаке\n"
        "   - `feed` - покормить\n"
        "   - `fight` - найти бой\n"
        "   - `top` - топ игроков\n\n"
        "*Виды еды:*\n"
        "🍌 Банан: +1 кг, КД 5ч\n"
        "🥩 Мясо: +3 кг, КД 8ч\n"
        "🍰 Торт: +5 кг, КД 12ч\n"
        "🥗 Салат: +2 кг, КД 6ч"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("my"))
async def my_macaco_command(message: Message):
    await show_my_macaco(message.from_user.id, message)

# ========== КНОПКИ ==========

# Моя макака
@dp.callback_query(F.data == "my_macaco")
async def my_macaco_callback(callback: CallbackQuery):
    await show_my_macaco(callback.from_user.id, callback)

async def show_my_macaco(user_id: int, source):
    try:
        macaco = await db.get_or_create_macaco(user_id)
        
        # Проверяем ежедневную награду
        can_daily, daily_time = await db.can_get_daily(macaco['id'])
        daily_status = "✅ Доступна" if can_daily else f"⏳ Через: {daily_time}"
        
        info_text = (
            f"🐒 *{macaco['name']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏋️ *Вес:* {macaco['weight']} кг\n"
            f"⭐ *Уровень:* {macaco['level']}\n"
            f"📊 *Опыт:* {macaco['exp']}/100\n"
            f"❤️ *Здоровье:* {macaco['health']}/100\n"
            f"🍖 *Сытость:* {100 - macaco['hunger']}/100\n"
            f"😊 *Настроение:* {macaco['happiness']}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 *Ежедневная награда:* {daily_status}"
        )
        
        if isinstance(source, CallbackQuery):
            await source.message.edit_text(
                info_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.main_menu_kb()
            )
            await source.answer()
        else:
            await source.answer(
                info_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.main_menu_kb()
            )
            
    except Exception as e:
        logging.error(f"Ошибка в show_my_macaco: {e}")
        error_text = "❌ Ошибка при получении данных"
        if isinstance(source, CallbackQuery):
            await source.message.edit_text(error_text)
            await source.answer()
        else:
            await source.answer(error_text)

# Выбор еды
@dp.callback_query(F.data == "select_food")
async def select_food_callback(callback: CallbackQuery):
    food_text = (
        "🍽️ *Выберите еду для макаки:*\n\n"
        "🍌 *Банан:* +1 кг, КД 5ч\n"
        "🥩 *Мясо:* +3 кг, КД 8ч\n"
        "🍰 *Торт:* +5 кг, КД 12ч\n"
        "🥗 *Салат:* +2 кг, КД 6ч"
    )
    
    await callback.message.edit_text(
        food_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.food_selection_kb()
    )
    await callback.answer()

# Информация о выбранной еде
@dp.callback_query(F.data.startswith("food_"))
async def food_info_callback(callback: CallbackQuery):
    food_id = int(callback.data.split("_")[1])
    food_info = await db.get_food_info(food_id)
    
    if not food_info:
        await callback.answer("❌ Еда не найдена")
        return
    
    food_text = (
        f"{food_info['name']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏋️ *Прибавка веса:* +{food_info['weight_gain']} кг\n"
        f"😊 *Радость:* +{food_info['happiness_gain']}\n"
        f"🍖 *Сытость:* +{food_info['hunger_decrease']}\n"
        f"⏳ *Кулдаун:* {food_info['cooldown_hours']} часов\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Покормить макаку этой едой?"
    )
    
    await callback.message.edit_text(
        food_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb.food_info_kb(food_id)
    )
    await callback.answer()

# Кормление выбранной едой
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
        
        # Проверяем КД
        can_feed, time_left = await db.can_feed_food(macaco['id'], food_id)
        
        if not can_feed:
            await callback.message.edit_text(
                f"⏳ *Нельзя кормить этой едой!*\n\n"
                f"До следующего кормления {food_info['name']}:\n"
                f"*{time_left}*\n\n"
                f"Выберите другую еду.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.food_selection_kb()
            )
            await callback.answer()
            return
        
        # Кормим
        success = await db.feed_macaco_with_food(macaco['id'], food_id)
        
        if not success:
            await callback.answer("❌ Ошибка при кормлении")
            return
        
        # Обновляем данные
        macaco = await db.get_or_create_macaco(user_id)
        
        # Отправляем гифку
        gif_types = {
            1: 'banana', 2: 'meat', 
            3: 'cake', 4: 'salad'
        }
        
        gif_type = gif_types.get(food_id, 'banana')
        gif_info = cfg.get_gif_info('feeding', gif_type)
        
        if gif_info and cfg.check_gif_exists('feeding', gif_type):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=f"{gif_info['caption']}\n"
                       f"Текущий вес: *{macaco['weight']} кг*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback.message.answer(
                f"{food_info['name']}\n"
                f"{gif_info.get('alt_text', 'Макака поела!')}\n"
                f"Текущий вес: *{macaco['weight']} кг*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"✅ *Макака накормлена!*\n\n"
            f"🍽️ {food_info['name']}\n"
            f"🏋️ Вес: *{macaco['weight']} кг*\n"
            f"😊 Настроение улучшено\n"
            f"🍖 Сытость улучшена",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logging.error(f"Ошибка в feed_with_food_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при кормлении",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# Ежедневная награда
@dp.callback_query(F.data == "daily_reward")
async def daily_reward_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        macaco = await db.get_or_create_macaco(user_id)
        
        # Проверяем доступность
        can_daily, time_left = await db.can_get_daily(macaco['id'])
        
        if not can_daily:
            await callback.message.edit_text(
                f"⏳ *Ежедневная награда еще не доступна!*\n\n"
                f"Следующая награда через:\n"
                f"*{time_left}*\n\n"
                f"Заходите завтра!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        # Выдаем награду
        success = await db.give_daily_reward(macaco['id'])
        
        if not success:
            await callback.answer("❌ Ошибка при выдаче награды")
            return
        
        # Обновляем данные
        macaco = await db.get_or_create_macaco(user_id)
        
        # Отправляем гифку
        gif_info = cfg.get_gif_info('daily', 'reward')
        
        if gif_info and cfg.check_gif_exists('daily', 'reward'):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=f"{gif_info['caption']}\n"
                       f"Текущий вес: *{macaco['weight']} кг*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback.message.answer(
                "🎁 *Ежедневная награда получена!*\n"
                f"+1 кг к весу!\n"
                f"Текущий вес: *{macaco['weight']} кг*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"✅ *Ежедневная награда получена!*\n\n"
            f"🎁 +1 кг к весу\n"
            f"😊 +5 к настроению\n"
            f"🏋️ Текущий вес: *{macaco['weight']} кг*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logging.error(f"Ошибка в daily_reward_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при получении награды",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# Поиск боя (остальной код аналогичный, но с гифками)
@dp.callback_query(F.data == "find_fight")
async def find_fight_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        user_macaco = await db.get_or_create_macaco(user_id)
        opponent = await db.find_opponent(user_macaco['id'])
        
        if not opponent:
            await callback.message.edit_text(
                "😕 *Соперников не найдено!*\n"
                "Пригласите друзей!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        fight_text = (
            f"⚔️ *Найден соперник!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🐒 *Вы:* {user_macaco['name']}\n"
            f"🏋️ Вес: {user_macaco['weight']} кг\n\n"
            f"🥊 *Соперник:* {opponent['name']}\n"
            f"🏋️ Вес: {opponent['weight']} кг\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 *Выберите ставку:*"
        )
        
        await callback.message.edit_text(
            fight_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.bet_selection_kb(opponent['id'])
        )
    
    except Exception as e:
        logging.error(f"Ошибка в find_fight_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при поиске боя",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# Обработка ставки (с гифкой начала боя)
@dp.callback_query(F.data.startswith("start_fight_"))
async def start_fight_callback(callback: CallbackQuery):
    data_parts = callback.data.split("_")
    
    if len(data_parts) != 4:
        await callback.answer("❌ Ошибка в данных")
        return
    
    try:
        opponent_id = int(data_parts[2])
        bet_amount = int(data_parts[3])
        user_id = callback.from_user.id
        
        user_macaco = await db.get_or_create_macaco(user_id)
        
        # Проверка ставки
        can_bet, message = await db.can_make_bet(user_macaco['id'], bet_amount)
        if not can_bet:
            await callback.message.edit_text(
                f"❌ {message}",
                reply_markup=kb.main_menu_kb()
            )
            await callback.answer()
            return
        
        # Гифка начала боя
        gif_info = cfg.get_gif_info('fight', 'start')
        if gif_info and cfg.check_gif_exists('fight', 'start'):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=gif_info['caption'],
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Бой
        fighters = [user_macaco['id'], opponent_id]
        winner_id = random.choice(fighters)
        loser_id = opponent_id if winner_id == user_macaco['id'] else user_macaco['id']
        
        # Обновление весов
        await db.update_weight_after_fight(winner_id, loser_id, bet_amount)
        await db.record_fight(user_macaco['id'], opponent_id, winner_id, bet_amount)
        
        # Опыт
        exp_gain = 25 if winner_id == user_macaco['id'] else 10
        async with aiosqlite.connect(db.DB_NAME) as conn:
            await conn.execute(
                'UPDATE macacos SET experience = experience + ? WHERE macaco_id = ?',
                (exp_gain, winner_id)
            )
            await conn.commit()
        
        # Результат
        user_macaco = await db.get_or_create_macaco(user_id)
        
        if winner_id == user_macaco['id']:
            result_icon = "🎉"
            result_gif = 'win'
            result_text = f"Вы победили и забираете *{bet_amount} кг*!"
        else:
            result_icon = "😔"
            result_gif = 'lose'
            result_text = f"Вы проиграли *{bet_amount} кг*."
        
        # Гифка результата
        gif_info = cfg.get_gif_info('fight', result_gif)
        if gif_info and cfg.check_gif_exists('fight', result_gif):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=gif_info['caption'],
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Сообщение о результате
        result_message = (
            f"{result_icon} *БОЙ ЗАВЕРШЁН!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{result_text}\n\n"
            f"🏋️ Ваш вес: *{user_macaco['weight']} кг*\n"
            f"📊 Опыт: +{exp_gain}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        await callback.message.edit_text(
            result_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.after_fight_kb()
        )
        
    except Exception as e:
        logging.error(f"Ошибка в start_fight_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка во время боя",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# Выгуливание
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
        
        # Гифка прогулки
        gif_info = cfg.get_gif_info('walk', 'walking')
        if gif_info and cfg.check_gif_exists('walk', 'walking'):
            animation = FSInputFile(gif_info['path'])
            await callback.message.answer_animation(
                animation,
                caption=gif_info['caption'],
                parse_mode=ParseMode.MARKDOWN
            )
        
        await callback.message.edit_text(
            f"🚶 *Прогулка успешна!*\n\n"
            f"😊 Настроение: +15\n"
            f"Текущее настроение: {macaco['happiness']}/100",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.main_menu_kb()
        )
        
    except Exception as e:
        logging.error(f"Ошибка в walk_macaco_callback: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при выгуливании",
            reply_markup=kb.main_menu_kb()
        )
    
    await callback.answer()

# Топ игроков
@dp.callback_query(F.data == "top_weight")
async def top_weight_callback(callback: CallbackQuery):
    await show_top_players(callback)

async def show_top_players(callback):
    try:
        top_macacos = await db.get_top_macacos(5)
        
        if not top_macacos:
            text = "📊 *Топ пуст!*\nБудьте первым!"
            markup = kb.main_menu_kb()
        else:
            text_lines = ["🏆 *ТОП-5 МАКАК* 🏆\n"]
            text_lines.append("━━━━━━━━━━━━━━━━━━━━")
            
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            
            for idx, (name, weight, level, username) in enumerate(top_macacos):
                if idx < 5:
                    medal = medals[idx]
                    user_display = f"@{username}" if username else "Без юзернейма"
                    text_lines.append(
                        f"{medal} *{name}*\n"
                        f"   🏋️ {weight} кг | ⭐ Ур. {level}\n"
                        f"   👤 {user_display}\n"
                    )
            
            text_lines.append("━━━━━━━━━━━━━━━━━━━━")
            text = "\n".join(text_lines)
            markup = kb.back_to_menu_kb()
        
        await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Ошибка в show_top_players: {e}")
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb.main_menu_kb())
        await callback.answer()

# ========== ИНЛАЙН-РЕЖИМ ==========

@dp.inline_query()
async def inline_mode(inline_query: InlineQuery):
    query = inline_query.query.lower().strip()
    user_id = inline_query.from_user.id
    
    results = []
    
    try:
        # Команда "info" или пустой запрос
        if query in ["", "info", "мой", "макака"]:
            macaco = await db.get_or_create_macaco(user_id)
            
            result = InlineQueryResultArticle(
                id="1",
                title=f"🐒 {macaco['name']}",
                description=f"Вес: {macaco['weight']} кг | Уровень: {macaco['level']}",
                input_message_content=InputTextMessageContent(
                    message_text=f"🐒 *{macaco['name']}*\n"
                                f"Вес: {macaco['weight']} кг\n"
                                f"Уровень: {macaco['level']}\n"
                                f"Опыт: {macaco['exp']}/100",
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=kb.inline_actions_kb(macaco['id']),
                thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
            )
            results.append(result)
        
        # Команда "feed"
        elif query in ["feed", "кормить", "еда"]:
            result = InlineQueryResultArticle(
                id="2",
                title="🍌 Покормить макаку",
                description="Выберите еду для макаки",
                input_message_content=InputTextMessageContent(
                    message_text="🍽️ *Выберите еду для макаки:*\n\n"
                                "Нажмите на кнопку ниже, чтобы выбрать еду.",
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=kb.food_selection_kb(),
                thumbnail_url="https://img.icons8.com/color/96/000000/banana.png"
            )
            results.append(result)
        
        # Команда "fight"
        elif query in ["fight", "бой", "драка"]:
            result = InlineQueryResultArticle(
                id="3",
                title="⚔️ Найти бой",
                description="Найти соперника для боя",
                input_message_content=InputTextMessageContent(
                    message_text="⚔️ *Поиск соперника...*\n\n"
                                "Нажмите на кнопку ниже, чтобы начать поиск.",
                    parse_mode=ParseMode.MARKDOWN
                ),
                reply_markup=kb.inline_actions_kb(0),
                thumbnail_url="https://img.icons8.com/color/96/000000/boxing.png"
            )
            results.append(result)
        
        # Команда "top"
        elif query in ["top", "топ", "рейтинг"]:
            top_macacos = await db.get_top_macacos(3)
            
            if top_macacos:
                top_text = "🏆 *ТОП-3 МАКАК:*\n"
                for idx, (name, weight, level, username) in enumerate(top_macacos[:3], 1):
                    medal = ["🥇", "🥈", "🥉"][idx-1]
                    top_text += f"{medal} {name} - {weight} кг\n"
            else:
                top_text = "🏆 Топ пуст!"
            
            result = InlineQueryResultArticle(
                id="4",
                title="🏆 Топ игроков",
                description="Лучшие макаки по весу",
                input_message_content=InputTextMessageContent(
                    message_text=top_text,
                    parse_mode=ParseMode.MARKDOWN
                ),
                thumbnail_url="https://img.icons8.com/color/96/000000/prize.png"
            )
            results.append(result)
        
        # Поиск макак
        else:
            found_macacos = await db.search_macacos(query, 5)
            
            for idx, macaco in enumerate(found_macacos):
                result = InlineQueryResultArticle(
                    id=f"search_{idx}",
                    title=f"🐒 {macaco['name']}",
                    description=f"Вес: {macaco['weight']} кг | Уровень: {macaco['level']}",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🐒 *{macaco['name']}*\n"
                                    f"Вес: {macaco['weight']} кг\n"
                                    f"Уровень: {macaco['level']}",
                        parse_mode=ParseMode.MARKDOWN
                    ),
                    reply_markup=kb.inline_actions_kb(macaco['id']),
                    thumbnail_url="https://img.icons8.com/color/96/000000/monkey.png"
                )
                results.append(result)
        
        # Если ничего не найдено
        if not results:
            result = InlineQueryResultArticle(
                id="0",
                title="🤔 Не найдено",
                description="Попробуйте другие команды: info, feed, fight, top",
                input_message_content=InputTextMessageContent(
                    message_text="Используйте команды:\n• info - информация\n• feed - кормить\n• fight - бой\n• top - топ"
                )
            )
            results.append(result)
        
        await inline_query.answer(results, cache_time=60, is_personal=True)
        
    except Exception as e:
        logging.error(f"Ошибка в inline_mode: {e}")
        # Пустой ответ в случае ошибки
        await inline_query.answer([], cache_time=60)

# ========== ЗАПУСК ==========

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот запущен: @{bot_info.username}")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        print(f"\n{'='*60}")
        print("ПРОВЕРЬТЕ:")
        print("1. Токен в .env файле")
        print("2. Библиотеки: pip install -r requirements.txt")
        print("3. Интернет соединение")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())