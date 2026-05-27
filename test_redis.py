import asyncio
import redis.asyncio as redis

async def main():
    redis_url = "redis://default:fE8uXUexDalb6CEod2Y1zjtrniiZHere@redis-10967.c11.us-east-1-3.ec2.cloud.redislabs.com:10967"
    print(f"Connecting to Redis at: {redis_url}")
    client = redis.from_url(redis_url, socket_timeout=5.0, socket_connect_timeout=5.0)
    try:
        res = await client.ping()
        print(f"Ping successful! Result: {res}")
    except Exception as e:
        print(f"Ping failed: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
