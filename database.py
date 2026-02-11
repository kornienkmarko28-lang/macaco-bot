import aiosqlite
from datetime import datetime, timedelta
import random
import asyncio
from typing import Dict, List, Tuple, Optional

DB_NAME = 'macaco_bot.db'

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ С ПРОВЕРКОЙ КОЛОНОК ==========
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
                last_happiness_decay TIMESTAMP,
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
        # Еда
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
        await db.execute('''
            INSERT OR IGNORE INTO food_types (food_id, name, weight_gain, happiness_gain, hunger_decrease, cooldown_hours)
            VALUES 
            (1, '🍌 Банан', 1, 10, 30, 5),
            (2, '🥩 Мясо', 3, 5, 50, 8),
            (3, '🍰 Торт', 5, 20, 70, 12),
            (4, '🥗 Салат', 2, 15, 40, 6)
        ''')
        await db.commit()
        print("✅ Таблицы созданы/проверены")
        
        # Проверяем наличие колонки last_happiness_decay (для старых БД)
        await add_last_happiness_decay_column()

async def add_last_happiness_decay_column():
    """Добавляет колонку last_happiness_decay, если её нет"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("PRAGMA table_info(macacos)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'last_happiness_decay' not in column_names:
            print("➕ Добавляем колонку last_happiness_decay...")
            await db.execute('''
                ALTER TABLE macacos ADD COLUMN last_happiness_decay TIMESTAMP
            ''')
            # Заполняем существующие записи текущим временем
            now = datetime.now().isoformat()
            await db.execute('''
                UPDATE macacos SET last_happiness_decay = ? WHERE last_happiness_decay IS NULL
            ''', (now,))
            await db.commit()
            print("✅ Колонка last_happiness_decay добавлена и заполнена.")

# ========== ПОЛЬЗОВАТЕЛИ ==========
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

# ========== МАКАКИ ==========
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
                INSERT INTO macacos (user_id, last_fed, last_daily, last_happiness_decay, weight)
                VALUES (?, ?, ?, ?, 10)
            ''', (user_id, now, now, now))
            await db.commit()
            cursor = await db.execute('''
                SELECT * FROM macacos 
                WHERE user_id = ? 
                ORDER BY macaco_id DESC 
                LIMIT 1
            ''', (user_id,))
            row = await cursor.fetchone()
        
        return {
            'id': row[0],
            'user_id': row[1],
            'name': row[2],
            'health': row[3],
            'hunger': row[4],
            'happiness': row[5],
            'level': row[6],
            'exp': row[7],
            'weight': row[8],
            'last_fed': row[9],
            'last_daily': row[10],
            'last_happiness_decay': row[11] if len(row) > 11 else None
        }

# ========== СНИЖЕНИЕ НАСТРОЕНИЯ ОТ ВРЕМЕНИ ==========
async def apply_happiness_decay(macaco_id: int) -> int:
    """
    Уменьшает настроение в зависимости от времени, прошедшего с last_happiness_decay.
    Каждый полный час = -10 настроения (минимум 0).
    Возвращает текущее настроение после применения.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем текущее настроение и время последнего обновления
        cursor = await db.execute('''
            SELECT happiness, last_happiness_decay FROM macacos WHERE macaco_id = ?
        ''', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        
        happiness, last_decay_str = row
        if not last_decay_str:
            last_decay = datetime.now()
        else:
            last_decay = datetime.fromisoformat(last_decay_str)
        
        now = datetime.now()
        delta = now - last_decay
        hours_passed = int(delta.total_seconds() // 3600)  # полные часы
        
        if hours_passed > 0:
            # Снижаем настроение на 10 за каждый час
            happiness = max(0, happiness - hours_passed * 10)
            # Обновляем last_happiness_decay, прибавляем часы (чтобы не терять остаток)
            new_last_decay = last_decay + timedelta(hours=hours_passed)
            
            await db.execute('''
                UPDATE macacos 
                SET happiness = ?, last_happiness_decay = ?
                WHERE macaco_id = ?
            ''', (happiness, new_last_decay.isoformat(), macaco_id))
            await db.commit()
        
        return happiness

# ========== УМЕНЬШИТЬ НАСТРОЕНИЕ (ПРИ ПРОИГРЫШЕ) ==========
async def decrease_happiness(macaco_id: int, amount: int) -> int:
    """Уменьшает настроение на amount (минимум 0). Возвращает новое настроение."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT happiness FROM macacos WHERE macaco_id = ?
        ''', (macaco_id,))
        row = await cursor.fetchone()
        if not row:
            return 0
        
        new_happiness = max(0, row[0] - amount)
        await db.execute('''
            UPDATE macacos SET happiness = ? WHERE macaco_id = ?
        ''', (new_happiness, macaco_id))
        await db.commit()
        return new_happiness

# ========== УСТАНОВИТЬ НАСТРОЕНИЕ (ПРОГУЛКА) ==========
async def set_happiness(macaco_id: int, value: int) -> int:
    """Устанавливает настроение (значение ограничивается 0-100)."""
    value = max(0, min(100, value))
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE macacos SET happiness = ? WHERE macaco_id = ?
        ''', (value, macaco_id))
        await db.commit()
        return value

# ========== КОРМЛЕНИЕ ==========
async def can_feed_food(macaco_id: int, food_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT cooldown_hours FROM food_types WHERE food_id = ?',
            (food_id,)
        )
        food = await cursor.fetchone()
        if not food:
            return False, "Нет такой еды"
        cooldown_hours = food[0]
        cursor = await db.execute(
            'SELECT last_fed FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        row = await cursor.fetchone()
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

async def get_food_info(food_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT * FROM food_types WHERE food_id = ?',
            (food_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'weight_gain': row[2],
                'happiness_gain': row[3],
                'hunger_decrease': row[4],
                'cooldown_hours': row[5]
            }
        return None

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
                weight = weight + ?
            WHERE macaco_id = ?
        ''', (datetime.now().isoformat(),
              food['hunger_decrease'],
              food['happiness_gain'],
              food['weight_gain'],
              macaco_id))
        await db.commit()
        return True

# ========== ЕЖЕДНЕВНАЯ НАГРАДА ==========
async def can_get_daily(macaco_id: int) -> Tuple[bool, Optional[str]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT last_daily FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        row = await cursor.fetchone()
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
                happiness = MIN(100, happiness + 5)
            WHERE macaco_id = ?
        ''', (datetime.now().isoformat(), macaco_id))
        await db.commit()
        return True

# ========== БОИ ==========
async def find_opponent(macaco_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('''
            SELECT macaco_id, name, level, weight 
            FROM macacos 
            WHERE macaco_id != ? 
            ORDER BY RANDOM() LIMIT 1
        ''', (macaco_id,))
        row = await cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'level': row[2],
                'weight': row[3]
            }
        return None

async def can_make_bet(macaco_id: int, bet_amount: int) -> Tuple[bool, str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT weight FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Макака не найдена"
        if row[0] < bet_amount:
            return False, f"Недостаточно веса. У вас: {row[0]} кг"
        return True, "OK"

async def update_weight_after_fight(winner_id: int, loser_id: int, bet_weight: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE macacos SET weight = weight + ? WHERE macaco_id = ?',
            (bet_weight, winner_id)
        )
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
        await db.execute('''
            INSERT INTO fights (fighter1_id, fighter2_id, winner_id, bet_weight)
            VALUES (?, ?, ?, ?)
        ''', (fighter1_id, fighter2_id, winner_id, bet_weight))
        await db.commit()

# ========== ОПЫТ И УРОВНИ ==========
async def add_experience(macaco_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            'SELECT experience, level FROM macacos WHERE macaco_id = ?',
            (macaco_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return
        exp, level = row
        exp += amount
        while exp >= 100:
            exp -= 100
            level += 1
        await db.execute(
            'UPDATE macacos SET experience = ?, level = ? WHERE macaco_id = ?',
            (exp, level, macaco_id)
        )
        await db.commit()

# ========== ТОП ==========
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

# ========== ПОИСК ==========
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

# ========== ИНИЦИАЛИЗАЦИЯ ==========
asyncio.run(create_tables())
