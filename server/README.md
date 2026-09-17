# StockAware server

FastAPI service with PostgreSQL connection management, Alembic migrations, and health endpoints. Business APIs are intentionally staged for the next implementation phase. Start with the [build guide](../docs/build-plan.md).

The app package is organized by business domain under `app/modules/`. Put HTTP request and response models in each module's `schemas.py`, business rules in `service.py`, and database access in `repository.py`. Keep route handlers thin.

## Phase 1 database

The commercial PostgreSQL schema is managed only through Alembic. From the repository root:

```bash
make migrate
make seed
```

`make seed` inserts deterministic, clearly demo-only catalog, inventory, alias,
substitute, and pricing-policy fixtures. It uses PostgreSQL conflict handling,
is safe to rerun, and preserves existing stock and owner edits. The seeded
thresholds, prices, GST rates, and approval settings are not production policy.

The normal unit suite does not require PostgreSQL. With the Compose database
running, the Phase 1 integration suite creates a uniquely named temporary
database, exercises the real migration downgrade/upgrade cycle, and removes
that database afterward:

```bash
make test
make test-pg
```

Never point the integration suite at a database name it did not create.
