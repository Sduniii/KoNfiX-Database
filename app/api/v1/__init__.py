from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.download import router as download_router
from app.api.v1.manufacturers import router as manufacturers_router
from app.api.v1.upload import router as upload_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(upload_router)
api_v1_router.include_router(download_router)
api_v1_router.include_router(devices_router)
api_v1_router.include_router(manufacturers_router)

__all__ = ["api_v1_router"]
