from fastapi import APIRouter


api_v1 = APIRouter(prefix="/v1")


api_v1.include_router(users_routers)


