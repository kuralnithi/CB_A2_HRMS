import logging
import subprocess
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

# Import the seed_data function from the root seed.py
import sys
import os
# Ensure the backend directory is in the path to import seed.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from seed import seed_data

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def init_db() -> None:
    logger.info("Initializing database...")
    
    # 1. Run Alembic migrations via subprocess to ensure synchronous execution
    try:
        logger.info("Running Alembic migrations...")
        result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True, check=True)
        logger.info(f"Alembic output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Alembic migration failed: {e.stderr}")
        raise e

    # 2. Check if users exist to determine if seeding is necessary
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text("SELECT COUNT(id) FROM users;"))
            count = result.scalar()
            
            if count == 0:
                logger.info("Database is empty. Running seed script...")
                await seed_data()
                logger.info("Database seeded successfully.")
            else:
                logger.info(f"Database already contains {count} users. Skipping seed.")
        except Exception as e:
            logger.error(f"Error during database check or seeding: {e}")
            raise e
