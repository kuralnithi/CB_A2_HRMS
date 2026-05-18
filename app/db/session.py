from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Configure connect_args based on host (SSL is required for Neon/cloud DBs)
connect_args = {}
db_uri = settings.SQLALCHEMY_DATABASE_URI
if "localhost" not in db_uri and "127.0.0.1" not in db_uri:
    connect_args["ssl"] = True

engine = create_async_engine(db_uri, echo=False, connect_args=connect_args)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
