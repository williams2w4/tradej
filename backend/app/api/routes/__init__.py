from fastapi import APIRouter

from app.api.routes import calendar, imports, settings, stats, trades

api_router = APIRouter()
api_router.include_router(imports.router)
api_router.include_router(trades.router)
api_router.include_router(stats.router)
api_router.include_router(calendar.router)
api_router.include_router(settings.router)
