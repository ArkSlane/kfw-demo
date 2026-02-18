"""
MongoDB client management with proper lifecycle (startup / shutdown).
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from .settings import MONGO_URL, DB_NAME

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGO_URL,
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )
        logger.info("MongoDB client created (pool: 5–50)")
    return _client


def get_db():
    return get_client()[DB_NAME]


async def close_client() -> None:
    """Close the MongoDB client. Call during shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")
