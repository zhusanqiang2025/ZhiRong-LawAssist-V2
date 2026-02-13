import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
print(f"Testing connection to Redis at: {redis_url}")

try:
    r = redis.from_url(redis_url)
    r.ping()
    print("Successfully connected to Redis.")
except Exception as e:
    print(f"Failed to connect to Redis: {e}")
