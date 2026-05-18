import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    db_url = "postgresql+asyncpg://neondb_owner:npg_2BeX5lpuECnU@ep-aged-union-a47ak6ww-pooler.us-east-1.aws.neon.tech/neondb?ssl=require"
    print(f"Connecting to: {db_url}")
    engine = create_async_engine(db_url, echo=True)
    try:
        async with engine.connect() as conn:
            print("Successfully connected to Neon PostgreSQL!")
    except Exception as e:
        print(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
