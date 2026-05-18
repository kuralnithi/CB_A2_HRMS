import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(user='postgres', password='Pasam123@kural', host='localhost', port=5432, database='postgres')
        await conn.execute('CREATE DATABASE hr_copilot')
        print("Database hr_copilot created successfully.")
        await conn.close()
    except asyncpg.exceptions.DuplicateDatabaseError:
        print("Database hr_copilot already exists.")

if __name__ == "__main__":
    asyncio.run(main())
