import asyncpg
from datetime import datetime, timedelta
import os
import asyncio
from typing import Dict, List, Tuple, Optional

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не задан! Добавьте его в переменные окружения Bothost.")

_pool = None
_pool_init_lock = asyncio.Lock()
_food_cache = None

async def get_pool():
    global _pool
    if _pool is None:
        async with _pool_init_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=5,
                    max_size=20,
                    command_timeout=60
                )
                print("✅ Пул соединений инициализирован")
    return _pool

async def load_food_cache():
    global _food_cache
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM food_types')
        _food_cache = {row['food_id']: dict(row) for row in rows}
    print(f"✅ Кэш еды загружен ({len(_food_cache)} записей)")

async def get_food_info_cached(food_id: int) -> Optional[Dict]:
    global _food_cache
    if _food_cache is None:
        await load_food_cache()
    return _food_cache.get(food_id)

async def create_tables():
    pool = await get_pool()
    async with pool.acquire() as conn:
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
                (1, '🍌 Банан', 1, 0, 30, 5, 10),
                (2, '🥩 Мясо', 3, 0, 50, 8, 15),
                (3, '🍰 Торт', 5, 0, 70, 12, 5),
                (4, '🥗 Салат', 2, 0, 40, 6, 12)
            ''')
        print("✅ Таблицы созданы/проверены")
    await load_food_cache()

async def get_or_create_user(user_data: Dict) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_data['id'])
        if not user:
            await conn.execute('''
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
            ''', user_data['id'], user_data.get('username'), user_data.get('first_name'), user_data.get('last_name'))
        return True

async def get_or_create_macaco(user_id: int) -> Dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
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
                VALUES ($1, NULL, $2, $3, $4, $5, 10)
            ''', user_id, now, now, now, now)
            row = await conn.fetchrow('''
                SELECT * FROM macacos 
                WHERE user_id = $1 
                ORDER BY macaco_id DESC 
                LIMIT 1
            ''', user_id)
        return dict(row)

async def get_macaco_with_decay(user_id: int) -> Dict:
    macaco = await get_or_create_macaco(user_id)
    await apply_happiness_decay(macaco['macaco_id'])
    await apply_hunger_decay(macaco['macaco_id'])
    await apply_health_decay(macaco['macaco_id'])
    return await get_or_create_macaco(user_id)

async def apply_hunger_decay(macaco_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT hunger, last_hunger_decay FROM macacos WHERE macaco_id = $1
        ''', macaco_id)
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

async def apply_health_decay(macaco_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT health, hunger, last_health_decay FROM macacos WHERE macaco_id = $1
        ''', macaco_id)
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

async def decrease_health(macaco_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        health = await conn.fetchval('SELECT health FROM macacos WHERE macaco_id = $1', macaco_id)
        if health is None:
            return 0
        new_health = max(0, health - amount)
        await conn.execute('UPDATE macacos SET health = $1 WHERE macaco_id = $2', new_health, macaco_id)
        return new_health

async def increase_health(macaco_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        health = await conn.fetchval('SELECT health FROM macacos WHERE macaco_id = $1', macaco_id)
        if health is None:
            return 0
        new_health = min(100, health + amount)
        await conn.execute('UPDATE macacos SET health = $1 WHERE macaco_id = $2', new_health, macaco_id)
        return new_health

async def can_feed_food(macaco_id: int, food_id: int) -> Tuple[bool, Optional[str]]:
    food = await get_food_info_cached(food_id)
    if not food:
        return False, "Нет такой еды"
    cooldown_hours = food['cooldown_hours']
    pool = await get_pool()
    async with pool.acquire() as conn:
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

async def feed_macaco_with_food(macaco_id: int, food_id: int) -> bool:
    food = await get_food_info_cached(food_id)
    if not food:
        return False
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE macacos 
            SET last_fed = $1,
                hunger = GREATEST(0, hunger - $2),
                weight = weight + $3,
                health = LEAST(100, health + $4)
            WHERE macaco_id = $5
        ''', datetime.now(),
              food['hunger_decrease'],
              food['weight_gain'],
              food['health_gain'],
              macaco_id)
        return True

async def can_get_daily(macaco_id: int) -> Tuple[bool, Optional[str]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
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

async def give_daily_reward(macaco_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE macacos
            SET weight = weight + 1,
                last_daily = $1,
                happiness = LEAST(100, happiness + 5),
                health = LEAST(100, health + 5)
            WHERE macaco_id = $2
        ''', datetime.now(), macaco_id)
        return True

async def apply_happiness_decay(macaco_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT happiness, last_happiness_decay FROM macacos WHERE macaco_id = $1
        ''', macaco_id)
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

async def decrease_happiness(macaco_id: int, amount: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        happiness = await conn.fetchval('SELECT happiness FROM macacos WHERE macaco_id = $1', macaco_id)
        if happiness is None:
            return 0
        new_happiness = max(0, happiness - amount)
        await conn.execute('UPDATE macacos SET happiness = $1 WHERE macaco_id = $2', new_happiness, macaco_id)
        return new_happiness

async def set_happiness(macaco_id: int, value: int) -> int:
    value = max(0, min(100, value))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('UPDATE macacos SET happiness = $1 WHERE macaco_id = $2', value, macaco_id)
        return value

async def walk_macaco(macaco_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('UPDATE macacos SET happiness = 100 WHERE macaco_id = $1', macaco_id)
        return 100

async def can_make_bet(macaco_id: int, bet_amount: int) -> Tuple[bool, str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        weight = await conn.fetchval('SELECT weight FROM macacos WHERE macaco_id = $1', macaco_id)
        if weight is None:
            return False, "Макака не найдена"
        if weight < bet_amount:
            return False, f"Недостаточно веса. У вас: {weight} кг"
        return True, "OK"

async def update_weight_after_fight(winner_id: int, loser_id: int, bet_weight: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('UPDATE macacos SET weight = weight + $1 WHERE macaco_id = $2', bet_weight, winner_id)
        await conn.execute('''
            UPDATE macacos 
            SET weight = GREATEST(1, weight - $1)
            WHERE macaco_id = $2
        ''', bet_weight, loser_id)

async def record_fight(fighter1_id: int, fighter2_id: int, winner_id: int, bet_weight: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO fights (fighter1_id, fighter2_id, winner_id, bet_weight)
            VALUES ($1, $2, $3, $4)
        ''', fighter1_id, fighter2_id, winner_id, bet_weight)

async def add_experience(macaco_id: int, amount: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
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

async def get_top_macacos(limit: int = 5) -> List[Tuple]:
    pool = await get_pool()
    async with pool.acquire() as conn:
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

async def search_macacos(query: str, limit: int = 10) -> List[Dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT m.macaco_id, m.name, m.weight, m.level, u.username
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.name ILIKE $1 OR u.username ILIKE $1
            ORDER BY m.weight DESC
            LIMIT $2
        ''', f'%{query}%', limit)
        return [dict(r) for r in rows]

async def init_db():
    """Вызывается при старте бота для создания таблиц и кэша."""
    await get_pool()
    await create_tables()
