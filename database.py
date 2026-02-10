import sqlite3
import aiosqlite
from datetime import datetime, timedelta, date
import random
import asyncio
from typing import Dict, List, Tuple, Optional

# Путь к файлу базы данных
DB_NAME = 'macaco_bot.db'

# Создание всех таблиц
async def create_tables():
    async with aiosqlite.connect(DB_NAME) as db:
        # Пользователи
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Макаки
        await db.execute('''
            CREATE TABLE IF NOT EXISTS macacos (
                macaco_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT DEFAULT 'Макака',
                health INTEGER DEFAULT 100,
                hunger INTEGER DEFAULT 0,
                happiness INTEGER DEFAULT 50,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                weight INTEGER DEFAULT 10,
                last_fed TIMESTAMP,
                last_daily TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Бои
        await db.execute('''
            CREATE TABLE IF NOT EXISTS fights (
                fight_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fighter1_id INTEGER NOT NULL,
                fighter2_id INTEGER NOT NULL,
                winner_id INTEGER,
                bet_weight INTEGER DEFAULT 1,
                fight_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (fighter1_id) REFERENCES macacos (macaco_id),
                FOREIGN KEY (fighter2_id) REFERENCES macacos (macaco_id),
                FOREIGN KEY (winner_id) REFERENCES macacos (macaco_id)
            )
        ''')
        
        # Еда (новое)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS food_types (
                food_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                weight_gain INTEGER NOT NULL,
                happiness_gain INTEGER NOT NULL,
                hunger_decrease INTEGER NOT NULL,
                cooldown_hours INTEGER NOT NULL
            )
        ''')
        
        # Заполняем типы еды
        await db.execute('''
            INSERT OR IGNORE INTO food_types (food_id, name, weight_gain, happiness_gain, hunger_decrease, cooldown_hours)
            VALUES 
            (1, '🍌 Банан', 1, 10, 30, 5),
            (2, '🥩 Мясо', 3, 5, 50, 8),
            (3, '🍰 Торт', 5, 20, 70, 12),
            (4, '🥗 Салат', 2, 15, 40, 6)
        ''')
        
        await db.commit()
        print("✅ Все таблицы созданы!")

# Регистрация пользователя
async def get_or_create_user(user_data: Dict) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        user = await db.execute_fetchall(
            'SELECT * FROM users WHERE user_id = ?',
            (user_data['id'],)
        )
        
        if not user:
            await db.execute('''
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_data['id'], user_data.get('username'), 
                  user_data.get('first_name'), user_data.get('last_name')))
            await db.commit()
        
        return True

# Создание/получение макаки
async def get_or_create_macaco(user_id: int) -> Dict:
    async with aiosqlite.connect(DB_NAME) as db:
        macaco = await db.execute_fetchall(
            'SELECT * FROM macacos WHERE user_id = ?',
            (user_id,)
        )
        
        if not macaco:
            await db.execute('''
                INSERT INTO macacos (user_id, last_fed, weight, last_daily)
                VALUES (?, ?, ?, ?)
            ''', (user_id, datetime.now().isoformat(), 10, 
                  datetime.now().isoformat()))
            await db.commit()
            
            macaco = await db.execute_fetchall(
                'SELECT * FROM macacos WHERE user_id = ?',
                (user_id,)
            )
        
        return {
            'id': macaco[0][0],
            'user_id': macaco[0][1],
            'name': macaco[0][2],
            'health': macaco[0][3],
            'hunger': macaco[0][4],
            'happiness': macaco[0][5],
            'level': macaco[0][6],
            'exp': macaco[0][7],
            'weight': macaco[0][8],
            'last_fed': macaco[0][9],
            'last_daily': macaco[0][10]
        }

# Проверка КД для еды
async def can_feed_food(macaco_id: int, food_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем КД для выбранной еды
        cursor = await db.execute(
            'SELECT cooldown_hours FROM food_types WHERE food_id = ?',
            (food_id,)
        )
        food_data = await cursor.fetchone()
        
        if not food_data:
            return False, "Такой еды не существует"
        
        cooldown_hours = food_data[0]
        
        # Получаем время последнего кормления этой едой
        cursor = await db.execute('''
            SELECT last_fed FROM macacos WHERE macaco_id = ?
        ''', (macaco_id,))
        
        result = await cursor.fetchone()
        
        if not result or not result[0]:
            return True, None
        
        last_fed = datetime.fromisoformat(result[0])
        now = datetime.now()
        cooldown = timedelta(hours=cooldown_hours)
        time_left = (last_fed + cooldown) - now
        
        if time_left.total_seconds() > 0:
            hours = int(time_left.seconds // 3600)
            minutes = int((time_left.seconds % 3600) // 60)
            return False, f"{hours}ч {minutes}м"
        
        return True, None

# Получение информации о еде
async def get_food_info(food_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT * FROM food_types WHERE food_id = ?',
            (food_id,)
        )
        food = await cursor.fetchone()
        
        if food:
            return {
                'id': food[0],
                'name': food[1],
                'weight_gain': food[2],
                'happiness_gain': food[3],
                'hunger_decrease': food[4],
                'cooldown_hours': food[5]
            }
        return None

# Кормление макаки выбранной едой
async def feed_macaco_with_food(macaco_id: int, food_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем данные еды
        food_info = await get_food_info(food_id)
        
        if not food_info:
            return False
        
        # Обновляем макаку
        await db.execute('''
            UPDATE macacos 
            SET last_fed = ?, 
                hunger = hunger - ?, 
                happiness = happiness + ?,
                weight = weight + ?
            WHERE macaco_id = ?
        ''', (datetime.now().isoformat(), 
              food_info['hunger_decrease'],
              food_info['happiness_gain'],
              food_info['weight_gain'],
              macaco_id))
        
        await db.commit()
        return True

# Проверка ежедневной награды
async def can_get_daily(macaco_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT last_daily FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        result = await cursor.fetchone()
        
        if not result or not result[0]:
            return True, None
        
        last_daily = datetime.fromisoformat(result[0])
        now = datetime.now()
        
        # Проверяем, прошли ли сутки
        if now.date() > last_daily.date():
            return True, None
        else:
            # Рассчитываем время до следующей награды
            next_daily = (last_daily + timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )
            time_left = next_daily - now
            
            if time_left.total_seconds() > 0:
                hours = int(time_left.seconds // 3600)
                minutes = int((time_left.seconds % 3600) // 60)
                return False, f"{hours}ч {minutes}м"
            
            return True, None

# Выдача ежедневной награды
async def give_daily_reward(macaco_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute('''
                UPDATE macacos 
                SET weight = weight + 1,
                    last_daily = ?,
                    happiness = happiness + 5
                WHERE macaco_id = ?
            ''', (datetime.now().isoformat(), macaco_id))
            
            await db.commit()
            return True
        except:
            return False

# Поиск соперника
async def find_opponent(macaco_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT macaco_id, name, level, weight 
            FROM macacos 
            WHERE macaco_id != ? 
            ORDER BY RANDOM() LIMIT 1
        ''', (macaco_id,))
        
        opponent = await cursor.fetchone()
        
        if opponent:
            return {
                'id': opponent[0],
                'name': opponent[1],
                'level': opponent[2],
                'weight': opponent[3]
            }
        return None

# Проверка ставки
async def can_make_bet(macaco_id: int, bet_amount: int) -> Tuple[bool, str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT weight FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        result = await cursor.fetchone()
        
        if not result:
            return False, "Макака не найдена"
        
        current_weight = result[0]
        
        if current_weight < bet_amount:
            return False, f"Недостаточно веса. У вас: {current_weight} кг"
        
        return True, "OK"

# Обновление весов после боя
async def update_weight_after_fight(winner_id: int, loser_id: int, bet_weight: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Победителю
        await db.execute(
            'UPDATE macacos SET weight = weight + ? WHERE macaco_id = ?',
            (bet_weight, winner_id)
        )
        
        # Проигравшему
        await db.execute('''
            UPDATE macacos 
            SET weight = CASE 
                WHEN (weight - ?) < 1 THEN 1 
                ELSE (weight - ?) 
            END 
            WHERE macaco_id = ?
        ''', (bet_weight, bet_weight, loser_id))
        
        await db.commit()

# Запись боя
async def record_fight(fighter1_id: int, fighter2_id: int, winner_id: int, bet_weight: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO fights (fighter1_id, fighter2_id, winner_id, bet_weight)
            VALUES (?, ?, ?, ?)
        ''', (fighter1_id, fighter2_id, winner_id, bet_weight))
        await db.commit()

# Топ игроков
async def get_top_macacos(limit: int = 5) -> List[Tuple]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT m.name, m.weight, m.level, u.username 
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            ORDER BY m.weight DESC, m.level DESC 
            LIMIT ?
        ''', (limit,))
        return await cursor.fetchall()

# Поиск макак для инлайн-режима
async def search_macacos(query: str, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT m.macaco_id, m.name, m.weight, m.level, u.username
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.name LIKE ? OR u.username LIKE ?
            ORDER BY m.weight DESC
            LIMIT ?
        ''', (f'%{query}%', f'%{query}%', limit))
        
        results = await cursor.fetchall()
        return [
            {
                'id': r[0],
                'name': r[1],
                'weight': r[2],
                'level': r[3],
                'username': r[4]
            }
            for r in results
        ]

# Инициализация БД
asyncio.run(create_tables())