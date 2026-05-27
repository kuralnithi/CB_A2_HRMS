import json
import logging
import redis.asyncio as redis
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client. It will automatically connect/reconnect as needed.
try:
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None

async def get_cache(key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve and deserialize a value from Redis.
    Includes a graceful fallback: if Redis is unreachable, simply return None.
    """
    if not settings.ENABLE_CACHE or not redis_client:
        return None

    try:
        cached_data = await redis_client.get(key)
        if cached_data:
            logger.info(f"CACHE HIT: {key}")
            return json.loads(cached_data)
        else:
            logger.info(f"CACHE MISS: {key}")
            return None
    except Exception as e:
        # Graceful fallback: NEVER let a Redis error crash the application.
        logger.error(f"REDIS GET ERROR for key {key}: {str(e)}")
        return None


async def set_cache(key: str, value: Dict[str, Any], ttl: int) -> bool:
    """
    Serialize and store a value in Redis with a TTL.
    Includes a graceful fallback: if Redis is unreachable, ignore the error.
    """
    if not settings.ENABLE_CACHE or not redis_client:
        return False

    try:
        serialized_data = json.dumps(value)
        await redis_client.set(key, serialized_data, ex=ttl)
        return True
    except Exception as e:
        # Graceful fallback
        logger.error(f"REDIS SET ERROR for key {key}: {str(e)}")
        return False
