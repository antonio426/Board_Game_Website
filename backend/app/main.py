from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import actions, auth, chat, crawl, games, health, recommendations, translate
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(crawl.router, prefix="/api/v1")
app.include_router(games.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(translate.router, prefix="/api/v1")

import os as _os

_DATA_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data")
_IMAGES_DIR = _os.path.join(_DATA_DIR, "images")
_THUMBNAILS_DIR = _os.path.join(_DATA_DIR, "thumbnails")

if _os.path.isdir(_IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=_IMAGES_DIR), name="images")
if _os.path.isdir(_THUMBNAILS_DIR):
    app.mount("/thumbnails", StaticFiles(directory=_THUMBNAILS_DIR), name="thumbnails")
