import asyncio
import aiosqlite

DB_NAME = 'macaco_bot.db'

async def update_database():
    print("🔄 Обновление базы данных...")
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем и добавляем недостающие колонки
        cursor = await db.execute("PRAGMA table_info(macacos)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Колонка last_daily
        if 'last_daily' not in column_names:
            print("➕ Добавляем колонку 'last_daily'...")
            await db.execute('ALTER TABLE macacos ADD COLUMN last_daily TIMESTAMP')
            await db.commit()
            print("✅ Колонка 'last_daily' добавлена!")
        
        # Создаем таблицу food_types если её нет
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
        
        # Очищаем и заново заполняем таблицу еды
        await db.execute('DELETE FROM food_types')
        
        await db.execute('''
            INSERT INTO food_types (food_id, name, weight_gain, happiness_gain, hunger_decrease, cooldown_hours)
            VALUES 
            (1, '🍌 Банан', 1, 10, 30, 5),
            (2, '🥩 Мясо', 3, 5, 50, 8),
            (3, '🍰 Торт', 5, 20, 70, 12),
            (4, '🥗 Салат', 2, 15, 40, 6)
        ''')
        
        await db.commit()
        print("✅ Таблица 'food_types' обновлена!")
        
        # Устанавливаем значения по умолчанию для существующих записей
        cursor = await db.execute("SELECT COUNT(*) FROM macacos WHERE last_daily IS NULL")
        count = (await cursor.fetchone())[0]
        
        if count > 0:
            print(f"🔄 Обновляем {count} записей...")
            await db.execute("UPDATE macacos SET last_daily = datetime('now') WHERE last_daily IS NULL")
            await db.commit()
            print("✅ Записи обновлены!")
    
    print("🎉 База данных полностью обновлена!")

if __name__ == "__main__":
    asyncio.run(update_database())