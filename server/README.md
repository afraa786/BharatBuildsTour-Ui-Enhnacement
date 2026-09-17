# StockAware server

FastAPI service with PostgreSQL connection management, Alembic migrations, and health endpoints. Business APIs are intentionally staged for the next implementation phase. Start with the [build guide](../docs/build-plan.md).

The app package is organized by business domain under `app/modules/`. Put HTTP request and response models in each module's `schemas.py`, business rules in `service.py`, and database access in `repository.py`. Keep route handlers thin.
