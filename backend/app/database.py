from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client.etymology


def get_words_collection():
    return db.words
