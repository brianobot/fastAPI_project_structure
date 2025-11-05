from fastapi import APIRouter


api_v1 = APIRouter(prefix="/v1")
api_v2 = APIRouter(prefix="/v2")

# include routes to a root route
# from app.routers import routers as user_routers
# api_v1.include_router(users_routers)


