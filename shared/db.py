from motor.motor_asyncio import AsyncIOMotorClient
from .settings import MONGO_URL, DB_NAME

_client = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
    return _client

def get_db():
    return get_client()[DB_NAME]
