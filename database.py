import aiosqlite
from datetime import datetime, timedelta
import random
import asyncio
from typing import Dict, List, Tuple, Optional

DB_NAME = 'macaco_bot.db'

async def create_tables():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
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
                last_happiness_decay TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_hunger_decay TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_health_decay TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
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
        await db.execute('DROP TABLE IF EXISTS food_types')
        await db.execute('''
            CREATE TABLE food_types (
                food_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                weight_gain INTEGER NOT NULL,
                happiness_gain INTEGER NOT NULL,
                hunger_decrease INTEGER NOT NULL,
                cooldown_hours INTEGER NOT NULL,
                health_gain INTEGER DEFAULT 10
            )
        ''')
        await db.execute('''
            INSERT INTO food_types (food_id, name, weight_gain, happiness_gain, hunger_decrease, cooldown_hours, health_gain)
            VALUES 
            (1, '🍌 Банан', 1, 10, 30, 5, 10),
            (2, '🥩 Мясо', 3, 5, 50, 8, 15),
            (3, '🍰 Торт', 5, 20, 70, 12, 5),
            (4, '🥗 Салат', 2, 15, 40, 6, 12)
        ''')
        await db.commit()
        print("✅ Таблицы созданы/обновлены")
        await add_missing_columns()

async def add_missing_columns():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("PRAGMA table_info(macacos)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'last_hunger_decay' not in column_names:
            await db.execute('ALTER TABLE macacos ADD COLUMN last_hunger_decay TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        if 'last_health_decay' not in column_names:
            await db.execute('ALTER TABLE macacos ADD COLUMN last_health_decay TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        await db.commit()

async def get_or_create_user(user_data: Dict) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        user = await db.execute_fetchall('SELECT * FROM users WHERE user_id = ?', (user_data['id'],))
        if not user:
            await db.execute('''
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_data['id'], user_data.get('username'), user_data.get('first_name'), user_data.get('last_name')))
            await db.commit()
        return True

async def get_or_create_macaco(user_id: int) -> Dict:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT * FROM macacos 
            WHERE user_id = ? 
            ORDER BY macaco_id DESC 
            LIMIT 1
        ''', (user_id,))
        row = await cursor.fetchone()
        if not row:
            now = datetime.now().isoformat()
            await db.execute('''
                INSERT INTO macacos (user_id, last_fed, last_daily, last_happiness_decay, last_hunger_decay, last_health_decay, weight)
                VALUES (?, ?, ?, ?, ?, ?, 10)
            ''', (user_id, now, now, now, now, now))
            await db.commit()
            cursor = await db.execute('''
                SELECT * FROM macacos 
                WHERE user_id = ? 
                ORDER BY macaco_id DESC 
                LIMIT 1
            ''', (user_id,))
            row = await cursor.fetchone()
        col_names = [description[0] for description in cursor.description]
        return {
            'id': row[col_names.index('macaco_id')],
            'user_id': row[col_names.index('user_id')],
            'name': row[col_names.index('name')],
            'health': row[col_names.index('health')],
            'hunger': row[col_names.index('hunger')],
            'happiness': row[col_names.index('happiness')],
            'level': row[col_names.index('level')],
            'exp': row[col_names.index('experience')],
            'weight': row[col_names.index('weight')],
            'last_fed': row[col_names.index('last_fed')],
            'last_daily': row[col_names.index('last_daily')],
            'last_happiness_decay': row[col_names.index('last_happiness_decay')],
            'last_hunger_decay': row[col_names.index('last_hunger_decay')],
            'last_health_decay': row[col_names.index('last_health_decay')],
        }

async def apply_hunger_decay(macaco_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT hunger, last_hunger_decay FROM macacos WHERE macaco_id = ?', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        hunger, last_decay_str = row
        last_decay = datetime.fromisoformat(last_decay_str) if last_decay_str else datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            hunger_increase = (hours_passed // 2) * 5
            hunger = min(100, hunger + hunger_increase)
            new_last_decay = last_decay + timedelta(hours=hours_passed // 2 * 2)
            await db.execute('UPDATE macacos SET hunger = ?, last_hunger_decay = ? WHERE macaco_id = ?',
                             (hunger, new_last_decay.isoformat(), macaco_id))
            await db.commit()
        return hunger

async def apply_health_decay(macaco_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT health, hunger, last_health_decay FROM macacos WHERE macaco_id = ?', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        health, hunger, last_decay_str = row
        if hunger < 100:
            return health
        last_decay = datetime.fromisoformat(last_decay_str) if last_decay_str else datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            health = max(0, health - hours_passed * 5)
            new_last_decay = last_decay + timedelta(hours=hours_passed)
            await db.execute('UPDATE macacos SET health = ?, last_health_decay = ? WHERE macaco_id = ?',
                             (health, new_last_decay.isoformat(), macaco_id))
            await db.commit()
        return health

async def decrease_health(macaco_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT health FROM macacos WHERE macaco_id = ?', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        new_health = max(0, row[0] - amount)
        await db.execute('UPDATE macacos SET health = ? WHERE macaco_id = ?', (new_health, macaco_id))
        await db.commit()
        return new_health

async def increase_health(macaco_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT health FROM macacos WHERE macaco_id = ?', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        new_health = min(100, row[0] + amount)
        await db.execute('UPDATE macacos SET health = ? WHERE macaco_id = ?', (new_health, macaco_id))
        await db.commit()
        return new_health

async def get_food_info(food_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT * FROM food_types WHERE food_id = ?', (food_id,))
        row = await cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'weight_gain': row[2],
                'happiness_gain': row[3],
                'hunger_decrease': row[4],
                'cooldown_hours': row[5],
                'health_gain': row[6]
            }
        return None

async def can_feed_food(macaco_id: int, food_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        food = await (await db.execute('SELECT cooldown_hours FROM food_types WHERE food_id = ?', (food_id,))).fetchone()
        if not food:
            return False, "Нет такой еды"
        cooldown_hours = food[0]
        row = await (await db.execute('SELECT last_fed FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row or not row[0]:
            return True, None
        last_fed = datetime.fromisoformat(row[0])
        now = datetime.now()
        if (now - last_fed).total_seconds() > cooldown_hours * 3600:
            return True, None
        diff = last_fed + timedelta(hours=cooldown_hours) - now
        hours = int(diff.seconds // 3600)
        minutes = int((diff.seconds % 3600) // 60)
        return False, f"{hours}ч {minutes}м"

async def feed_macaco_with_food(macaco_id: int, food_id: int) -> bool:
    food = await get_food_info(food_id)
    if not food:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE macacos 
            SET last_fed = ?,
                hunger = MAX(0, hunger - ?),
                happiness = MIN(100, happiness + ?),
                weight = weight + ?,
                health = MIN(100, health + ?)
            WHERE macaco_id = ?
        ''', (datetime.now().isoformat(),
              food['hunger_decrease'],
              food['happiness_gain'],
              food['weight_gain'],
              food['health_gain'],
              macaco_id))
        await db.commit()
        return True

async def can_get_daily(macaco_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute('SELECT last_daily FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row or not row[0]:
            return True, None
        last = datetime.fromisoformat(row[0]).date()
        today = datetime.now().date()
        if today > last:
            return True, None
        next_day = datetime.combine(last + timedelta(days=1), datetime.min.time())
        diff = next_day - datetime.now()
        hours = int(diff.seconds // 3600)
        minutes = int((diff.seconds % 3600) // 60)
        return False, f"{hours}ч {minutes}м"

async def give_daily_reward(macaco_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE macacos
            SET weight = weight + 1,
                last_daily = ?,
                happiness = MIN(100, happiness + 5),
                health = MIN(100, health + 5)
            WHERE macaco_id = ?
        ''', (datetime.now().isoformat(), macaco_id))
        await db.commit()
        return True

async def apply_happiness_decay(macaco_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute('SELECT happiness, last_happiness_decay FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row:
            return 0
        happiness, last_decay_str = row
        last_decay = datetime.fromisoformat(last_decay_str) if last_decay_str else datetime.now()
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)
        if hours_passed > 0:
            happiness = max(0, happiness - hours_passed * 10)
            new_last_decay = last_decay + timedelta(hours=hours_passed)
            await db.execute('UPDATE macacos SET happiness = ?, last_happiness_decay = ? WHERE macaco_id = ?',
                             (happiness, new_last_decay.isoformat(), macaco_id))
            await db.commit()
        return happiness

async def decrease_happiness(macaco_id: int, amount: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute('SELECT happiness FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row:
            return 0
        new_happiness = max(0, row[0] - amount)
        await db.execute('UPDATE macacos SET happiness = ? WHERE macaco_id = ?', (new_happiness, macaco_id))
        await db.commit()
        return new_happiness

async def set_happiness(macaco_id: int, value: int) -> int:
    value = max(0, min(100, value))
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE macacos SET happiness = ? WHERE macaco_id = ?', (value, macaco_id))
        await db.commit()
        return value

async def walk_macaco(macaco_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE macacos SET happiness = 100, health = MIN(100, health + 15) WHERE macaco_id = ?', (macaco_id,))
        await db.commit()
        return 100

async def can_make_bet(macaco_id: int, bet_amount: int) -> Tuple[bool, str]:
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute('SELECT weight FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row:
            return False, "Макака не найдена"
        if row[0] < bet_amount:
            return False, f"Недостаточно веса. У вас: {row[0]} кг"
        return True, "OK"

async def update_weight_after_fight(winner_id: int, loser_id: int, bet_weight: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE macacos SET weight = weight + ? WHERE macaco_id = ?', (bet_weight, winner_id))
        await db.execute('''
            UPDATE macacos 
            SET weight = CASE 
                WHEN (weight - ?) < 1 THEN 1 
                ELSE (weight - ?) 
            END 
            WHERE macaco_id = ?
        ''', (bet_weight, bet_weight, loser_id))
        await db.commit()

async def record_fight(fighter1_id: int, fighter2_id: int, winner_id: int, bet_weight: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO fights (fighter1_id, fighter2_id, winner_id, bet_weight) VALUES (?, ?, ?, ?)',
                         (fighter1_id, fighter2_id, winner_id, bet_weight))
        await db.commit()

async def add_experience(macaco_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        row = await (await db.execute('SELECT experience, level FROM macacos WHERE macaco_id = ?', (macaco_id,))).fetchone()
        if not row:
            return
        exp, level = row
        exp += amount
        while exp >= 100:
            exp -= 100
            level += 1
        await db.execute('UPDATE macacos SET experience = ?, level = ? WHERE macaco_id = ?', (exp, level, macaco_id))
        await db.commit()

async def get_top_macacos(limit: int = 5) -> List[Tuple]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT m.name, m.weight, m.level, u.username 
            FROM macacos m
            LEFT JOIN users u ON m.user_id = u.user_id
            INNER JOIN (
                SELECT user_id, MAX(macaco_id) as last_id
                FROM macacos
                GROUP BY user_id
            ) latest ON m.user_id = latest.user_id AND m.macaco_id = latest.last_id
            ORDER BY m.weight DESC, m.level DESC 
            LIMIT ?
        ''', (limit,))
        return await cursor.fetchall()

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
        rows = await cursor.fetchall()
        return [
            {
                'id': r[0],
                'name': r[1],
                'weight': r[2],
                'level': r[3],
                'username': r[4]
            }
            for r in rows
        ]

asyncio.run(create_tables())
