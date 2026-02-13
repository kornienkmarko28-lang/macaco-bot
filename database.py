import asyncpg
from datetime import datetime, timedelta
import os
import random
import asyncio
from typing import Dict, List, Tuple, Optional

# ========== ПОДКЛЮЧЕНИЕ К БАЗЕ ==========
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не задан! Добавьте его в переменные окружения Bothost.")

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

# ========== СОЗДАНИЕ ТАБЛИЦ ==========
async def create_tables():
    conn = await get_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS macacos (
                macaco_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                name TEXT DEFAULT 'Макака',
                health INTEGER DEFAULT 100,
                hunger INTEGER DEFAULT 0,
                happiness INTEGER DEFAULT 50,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                weight INTEGER DEFAULT 10,
                last_fed TIMESTAMP,
                last_daily TIMESTAMP,
                last_happiness_decay TIMESTAMP,
                last_hunger_decay TIMESTAMP,
                last_health_decay TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS fights (
                fight_id SERIAL PRIMARY KEY,
                fighter1_id INTEGER NOT NULL REFERENCES macacos(macaco_id),
                fighter2_id INTEGER NOT NULL REFERENCES macacos(macaco_id),
                winner_id INTEGER REFERENCES macacos(macaco_id),
                bet_weight INTEGER DEFAULT 1,
                fight_time TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS food_types (
                food_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                weight_gain INTEGER NOT NULL,
                happiness_gain INTEGER NOT NULL,
                hunger_decrease INTEGER NOT NULL,
                cooldown_hours INTEGER NOT NULL,
                health_gain INTEGER DEFAULT 10
            )
        ''')
        count = await conn.fetchval('SELECT COUNT(*) FROM food_types')
        if count == 0:
            await conn.execute('''
                INSERT INTO food_types (food_id, name, weight_gain, happiness_gain, hunger_decrease, cooldown_hours, health_gain)
                VALUES 
                (1, '🍌 Банан', 1, 10, 30, 5, 10),
                (2, '🥩 Мясо', 3, 5, 50, 8, 15),
                (3, '🍰 Торт', 5, 20, 70, 12, 5),
                (4, '🥗 Салат', 2, 15, 40, 6, 12)
            ''')
        print("✅ Таблицы созданы/проверены")
    finally:
        await conn.close()

# ========== ПОЛЬЗОВАТЕЛИ ==========
async def get_or_create_user(user_data: Dict) -> bool:
    conn = await get_connection()
    try:
        user = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_data['id'])
        if not user:
            await conn.execute('''
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
            ''', user_data['id'], user_data.get('username'), user_data.get('first_name'), user_data.get('last_name'))
        return True
    finally:
        await conn.close()

# ========== МАКАКИ ==========
async def get_or_create_macaco(user_id: int) -> Dict:
    conn = await get_connection()
    try:
        row = await conn.fetchrow('''
            SELECT * FROM macacos 
            WHERE user_id = $1 
            ORDER BY macaco_id DESC 
            LIMIT 1
        ''', user_id)
        
        if not row:
            now = datetime.now()
            await conn.execute('''
                INSERT INTO macacos (user_id, last_fed, last_daily, last_happiness_decay, last_hunger_decay, last_health_decay, weight)
                VALUES ($1, $2, $3, $4, $5, $6, 10)
            ''', user_id, now, now, now, now, now)
            row = await conn.fetchrow('''
                SELECT * FROM macacos 
                WHERE user_id = $1 
                ORDER BY macaco_id DESC 
                LIMIT 1
            ''', user_id)
        
        return dict(row)
    finally:
        await conn.close()

# ========== ГОЛОД ==========
async def apply_hunger_decay(macaco_id: int) -> int:
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT hunger, last_hunger_decay FROM macacos WHERE macaco_id = $1', macaco_id)
        if not row:
            return 0
        hunger = row['hunger']
        last_decay = row['last_hunger_decay']
        if last_decay is None:
            last_decay = datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            hunger_increase = (hours_passed // 2) * 5
            hunger = min(100, hunger + hunger_increase)
            new_last_decay = last_decay + timedelta(hours=hours_passed // 2 * 2)
            await conn.execute('''
                UPDATE macacos 
                SET hunger = $1, last_hunger_decay = $2 
                WHERE macaco_id = $3
            ''', hunger, new_last_decay, macaco_id)
        return hunger
    finally:
        await conn.close()

# ========== ЗДОРОВЬЕ ==========
async def apply_health_decay(macaco_id: int) -> int:
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT health, hunger, last_health_decay FROM macacos WHERE macaco_id = $1', macaco_id)
        if not row:
            return 0
        health = row['health']
        hunger = row['hunger']
        last_decay = row['last_health_decay']
        if hunger < 100:
            return health
        if last_decay is None:
            last_decay = datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            health = max(0, health - hours_passed * 5)
            new_last_decay = last_decay + timedelta(hours=hours_passed)
            await conn.execute('''
                UPDATE macacos 
                SET health = $1, last_health_decay = $2 
                WHERE macaco_id = $3
            ''', health, new_last_decay, macaco_id)
        return health
    finally:
        await conn.close()

async def decrease_health(macaco_id: int, amount: int) -> int:
    conn = await get_connection()
    try:
        health = await conn.fetchval('SELECT health FROM macacos WHERE macaco_id = $1', macaco_id)
        if health is None:
            return 0
        new_health = max(0, health - amount)
        await conn.execute('UPDATE macacos SET health = $1 WHERE macaco_id = $2', new_health, macaco_id)
        return new_health
    finally:
        await conn.close()

async def increase_health(macaco_id: int, amount: int) -> int:
    conn = await get_connection()
    try:
        health = await conn.fetchval('SELECT health FROM macacos WHERE macaco_id = $1', macaco_id)
        if health is None:
            return 0
        new_health = min(100, health + amount)
        await conn.execute('UPDATE macacos SET health = $1 WHERE macaco_id = $2', new_health, macaco_id)
        return new_health
    finally:
        await conn.close()

# ========== КОРМЛЕНИЕ ==========
async def can_feed_food(macaco_id: int, food_id: int) -> Tuple[bool, Optional[str]]:
    conn = await get_connection()
    try:
        food = await conn.fetchrow('SELECT cooldown_hours FROM food_types WHERE food_id = $1', food_id)
        if not food:
            return False, "Нет такой еды"
        cooldown_hours = food['cooldown_hours']
        last_fed = await conn.fetchval('SELECT last_fed FROM macacos WHERE macaco_id = $1', macaco_id)
        if last_fed is None:
            return True, None
        now = datetime.now()
        if (now - last_fed).total_seconds() > cooldown_hours * 3600:
            return True, None
        diff = last_fed + timedelta(hours=cooldown_hours) - now
        hours = int(diff.seconds // 3600)
        minutes = int((diff.seconds % 3600) // 60)
        return False, f"{hours}ч {minutes}м"
    finally:
        await conn.close()

async def get_food_info(food_id: int) -> Optional[Dict]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT * FROM food_types WHERE food_id = $1', food_id)
        return dict(row) if row else None
    finally:
        await conn.close()

async def feed_macaco_with_food(macaco_id: int, food_id: int) -> bool:
    food = await get_food_info(food_id)
    if not food:
        return False
    conn = await get_connection()
    try:
        await conn.execute('''
            UPDATE macacos 
            SET last_fed = $1,
                hunger = GREATEST(0, hunger - $2),
                happiness = LEAST(100, happiness + $3),
                weight = weight + $4,
                health = LEAST(100, health + $5)
            WHERE macaco_id = $6
        ''', datetime.now(),
              food['hunger_decrease'],
              food['happiness_gain'],
              food['weight_gain'],
              food['health_gain'],
              macaco_id)
        return True
    finally:
        await conn.close()

# ========== ЕЖЕДНЕВНАЯ НАГРАДА ==========
async def can_get_daily(macaco_id: int) -> Tuple[bool, Optional[str]]:
    conn = await get_connection()
    try:
        last_daily = await conn.fetchval('SELECT last_daily FROM macacos WHERE macaco_id = $1', macaco_id)
        if last_daily is None:
            return True, None
        last = last_daily.date()
        today = datetime.now().date()
        if today > last:
            return True, None
        next_day = datetime.combine(last + timedelta(days=1), datetime.min.time())
        diff = next_day - datetime.now()
        hours = int(diff.seconds // 3600)
        minutes = int((diff.seconds % 3600) // 60)
        return False, f"{hours}ч {minutes}м"
    finally:
        await conn.close()

async def give_daily_reward(macaco_id: int) -> bool:
    conn = await get_connection()
    try:
        await conn.execute('''
            UPDATE macacos
            SET weight = weight + 1,
                last_daily = $1,
                happiness = LEAST(100, happiness + 5),
                health = LEAST(100, health + 5)
            WHERE macaco_id = $2
        ''', datetime.now(), macaco_id)
        return True
    finally:
        await conn.close()

# ========== НАСТРОЕНИЕ ==========
async def apply_happiness_decay(macaco_id: int) -> int:
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT happiness, last_happiness_decay FROM macacos WHERE macaco_id = $1', macaco_id)
        if not row:
            return 0
        happiness = row['happiness']
        last_decay = row['last_happiness_decay']
        if last_decay is None:
            last_decay = datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            happiness = max(0, happiness - hours_passed * 10)
            new_last_decay = last_decay + timedelta(hours=hours_passed)
            await conn.execute('''
                UPDATE macacos 
                SET happiness = $1, last_happiness_decay = $2 
                WHERE macaco_id = $3
            ''', happiness, new_last_decay, macaco_id)
        return happiness
    finally:
        await conn.close()

async def decrease_happiness(macaco_id: int, amount: int) -> int:
    conn = await get_connection()
    try:
        happiness = await conn.fetchval('SELECT happiness FROM macacos WHERE macaco_id = $1', macaco_id)
        if happiness is None:
            return 0
        new_happiness = max(0, happiness - amount)
        await conn.execute('UPDATE macacos SET happiness = $1 WHERE macaco_id = $2', new_happiness, macaco_id)
        return new_happiness
    finally:
        await conn.close()

async def set_happiness(macaco_id: int, value: int) -> int:
    value = max(0, min(100, value))
    conn = await get_connection()
    try:
        await conn.execute('UPDATE macacos SET happiness = $1 WHERE macaco_id = $2', value, macaco_id)
        return value
    finally:
        await conn.close()

# ========== ПРОГУЛКА ==========
async def walk_macaco(macaco_id: int) -> int:
    conn = await get_connection()
    try:
        await conn.execute('UPDATE macacos SET happiness = 100 WHERE macaco_id = $1', macaco_id)
        return 100
    finally:
        await conn.close()

# ========== БОИ ==========
async def can_make_bet(macaco_id: int, bet_amount: int) -> Tuple[bool, str]:
    conn = await get_connection()
    try:
        weight = await conn.fetchval('SELECT weight FROM macacos WHERE macaco_id = $1', macaco_id)
        if weight is None:
            return False, "Макака не найдена"
        if weight < bet_amount:
            return False, f"Недостаточно веса. У вас: {weight} кг"
        return True, "OK"
    finally:
        await conn.close()

async def update_weight_after_fight(winner_id: int, loser_id: int, bet_weight: int):
    conn = await get_connection()
    try:
        await conn.execute('UPDATE macacos SET weight = weight + $1 WHERE macaco_id = $2', bet_weight, winner_id)
        await conn.execute('''
            UPDATE macacos 
            SET weight = GREATEST(1, weight - $1)
            WHERE macaco_id = $2
        ''', bet_weight, loser_id)
    finally:
        await conn.close()

async def record_fight(fighter1_id: int, fighter2_id: int, winner_id: int, bet_weight: int):
    conn = await get_connection()
    try:
        await conn.execute('''
            INSERT INTO fights (fighter1_id, fighter2_id, winner_id, bet_weight)
            VALUES ($1, $2, $3, $4)
        ''', fighter1_id, fighter2_id, winner_id, bet_weight)
    finally:
        await conn.close()

# ========== ОПЫТ ==========
async def add_experience(macaco_id: int, amount: int):
    conn = await get_connection()
    try:
        row = await conn.fetchrow('SELECT experience, level FROM macacos WHERE macaco_id = $1', macaco_id)
        if not row:
            return
        exp = row['experience']
        level = row['level']
        exp += amount
        while exp >= 100:
            exp -= 100
            level += 1
        await conn.execute('UPDATE macacos SET experience = $1, level = $2 WHERE macaco_id = $3', exp, level, macaco_id)
    finally:
        await conn.close()

# ========== ТОП ==========
async def get_top_macacos(limit: int = 5) -> List[Tuple]:
    conn = await get_connection()
    try:
        rows = await conn.fetch('''
            SELECT m.name, m.weight, m.level, u.username 
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            INNER JOIN (
                SELECT user_id, MAX(macaco_id) as last_id
                FROM macacos
                GROUP BY user_id
            ) latest ON m.user_id = latest.user_id AND m.macaco_id = latest.last_id
            ORDER BY m.weight DESC, m.level DESC 
            LIMIT $1
        ''', limit)
        return [(r['name'], r['weight'], r['level'], r['username']) for r in rows]
    finally:
        await conn.close()

# ========== ПОИСК ==========
async def search_macacos(query: str, limit: int = 10) -> List[Dict]:
    conn = await get_connection()
    try:
        rows = await conn.fetch('''
            SELECT m.macaco_id, m.name, m.weight, m.level, u.username
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.name ILIKE $1 OR u.username ILIKE $1
            ORDER BY m.weight DESC
            LIMIT $2
        ''', f'%{query}%', limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ========== ИНИЦИАЛИЗАЦИЯ ==========
asyncio.run(create_tables())
