from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import model modules here as they are added so Alembic can discover metadata.
from app.modules.runs import models as runs_models  # noqa: E402,F401
from app.modules.whatsapp import models as whatsapp_models  # noqa: E402,F401
