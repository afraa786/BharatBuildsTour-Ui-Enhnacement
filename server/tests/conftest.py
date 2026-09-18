import os

# The app validates its configuration at import time. Health tests do not connect
# to PostgreSQL, so use isolated local credentials for the test process.
os.environ.setdefault("POSTGRES_USER", "stockaware_test")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only-local-password")
os.environ.setdefault("POSTGRES_DB", "stockaware_test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret")
