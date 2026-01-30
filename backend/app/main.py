from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import words, etymology, search

app = FastAPI(title="Etymology Explorer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(words.router, prefix="/api")
app.include_router(etymology.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
