import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def drop_all():
    db_uri = settings.SQLALCHEMY_DATABASE_URI
    connect_args = {}
    if "localhost" not in db_uri and "127.0.0.1" not in db_uri:
        connect_args["ssl"] = True
    
    print("Connecting to Neon Database to clean up old schemas...")
    engine = create_async_engine(db_uri, connect_args=connect_args)
    
    tables_to_drop = [
        "alembic_version",
        "users",
        "employees",
        "projects",
        "tasks",
        "announcements",
        "policies"
    ]
    
    async with engine.begin() as conn:
        for table in tables_to_drop:
            print(f"Dropping table if exists: {table}...")
            await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
            
    print("Database wiped successfully! You are ready for a clean migration.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(drop_all())
