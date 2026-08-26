from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient
from redis import Redis

from app.core.config import settings

mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
mongo_db = mongo_client[settings.MONGO_DB_NAME]

qdrant_client = QdrantClient(url=settings.QDRANT_URL)

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
