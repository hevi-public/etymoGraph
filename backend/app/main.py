from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_mongo_client
from app.routers import concept_map, etymology, layout, search, words


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.mongo_client = create_mongo_client()
    try:
        yield
    finally:
        app.state.mongo_client.close()


app = FastAPI(title="Etymology Explorer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(words.router, prefix="/api")
app.include_router(etymology.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(concept_map.router, prefix="/api")
app.include_router(layout.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
