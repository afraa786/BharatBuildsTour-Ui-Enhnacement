from fastapi import APIRouter

from app.api.auth_routes import router as auth_router
from app.api.owner_routes import router as owner_router
from app.api.routes.health import router as health_router
from app.modules.catalog.routes import router as catalog_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.invoices.routes import router as invoices_router
from app.modules.payments.router import router as razorpay_router
from app.modules.payments.routes import router as payments_router
from app.modules.pricing.routes import router as pricing_router
from app.modules.runs.router import router as runs_router
from app.modules.whatsapp.router import router as whatsapp_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(owner_router)
router.include_router(catalog_router)
router.include_router(inventory_router)
router.include_router(pricing_router)
router.include_router(payments_router)
router.include_router(invoices_router)
router.include_router(razorpay_router)
router.include_router(whatsapp_router)
router.include_router(runs_router)
