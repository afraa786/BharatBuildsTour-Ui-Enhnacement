from fastapi import APIRouter

from app.api.routes.demo import router as demo_router
from app.api.routes.health import router as health_router
from app.modules.payments.router import router as payments_router
from app.modules.runs.router import router as runs_router
from app.modules.whatsapp.router import router as whatsapp_router

router = APIRouter()
router.include_router(health_router)
router.include_router(whatsapp_router)
router.include_router(payments_router)
router.include_router(runs_router)
router.include_router(demo_router)
