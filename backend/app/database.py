from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.config import settings


def create_mongo_client() -> AsyncIOMotorClient:
    """Construct the Motor client.

    Called only from the FastAPI lifespan, never at import time: Motor binds to the
    event loop captured at construction, so an import-time client binds the wrong
    loop under pytest-asyncio (or any process that restarts the loop). SPC-00020
    Steps 1-3 / SPC-00021 Phase 0.
    """
    return AsyncIOMotorClient(settings.mongo_uri)


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """Return the etymology database from the lifespan-managed client on app.state."""
    return request.app.state.mongo_client.etymology


def get_words_collection(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AsyncIOMotorCollection:
    """Return the 'words' collection from the etymology database."""
    return db.words
