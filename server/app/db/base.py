from importlib import import_module

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Explicit registry: Alembic imports this module, so every owned model is loaded here.
MODEL_MODULES = (
    "app.modules.runs.models",
    "app.modules.whatsapp.models",
    "app.modules.identity.models",
    "app.modules.catalog.models",
    "app.modules.inventory.models",
    "app.modules.pricing.models",
    "app.modules.payments.models",
    "app.modules.invoices.models",
)

for module in MODEL_MODULES:
    import_module(module)
