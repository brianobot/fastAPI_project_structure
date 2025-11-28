from fastapi import APIRouter

from app.routers.auth import router as auth_router

api = APIRouter(prefix="/v1")


api.include_router(auth_router)