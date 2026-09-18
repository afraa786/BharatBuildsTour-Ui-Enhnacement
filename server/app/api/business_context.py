import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header

from app.api.commercial import CommercialError
from app.core.config import get_settings


def require_business_context(
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> UUID:
    """Authenticate a server-side caller and bind it to one configured business."""
    settings = get_settings()
    configured_token = settings.internal_service_token.get_secret_value()
    if not configured_token or not settings.internal_business_id:
        raise CommercialError(
            503,
            "AUTHORIZATION_NOT_CONFIGURED",
            "Commercial API authorization is not configured.",
        )
    if internal_token is None or not hmac.compare_digest(internal_token, configured_token):
        raise CommercialError(401, "UNAUTHORIZED", "A valid internal service identity is required.")
    try:
        return UUID(settings.internal_business_id)
    except ValueError as exc:
        raise CommercialError(
            503,
            "AUTHORIZATION_NOT_CONFIGURED",
            "Commercial API authorization is not configured.",
        ) from exc


AuthorizedBusinessId = Annotated[UUID, Depends(require_business_context)]


def enforce_business_claim(claim: UUID, authorized_business_id: UUID) -> None:
    if claim != authorized_business_id:
        raise CommercialError(404, "NOT_FOUND", "Business-scoped resource not found.")
