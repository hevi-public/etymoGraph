from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client.etymology


def get_words_collection() -> AsyncIOMotorCollection:
    """Return the 'words' collection from the etymology database."""
    return db.words
