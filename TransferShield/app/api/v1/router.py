from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.payment import router as payment_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(payment_router)