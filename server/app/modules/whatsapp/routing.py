"""Trusted receiving-number routing.

Tenant and experience are derived only from Meta's receiving-number metadata.
Sender-controlled message fields are deliberately not accepted by this module.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import Business
from app.modules.whatsapp.models import WhatsAppNumberBinding


class WhatsAppExperience(StrEnum):
    OWNER_MANAGER = "owner_manager"
    CUSTOMER_COMMERCE = "customer_commerce"


class RoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatsAppRoutingContext:
    provider: str
    phone_number_id: str
    business_id: UUID
    experience: WhatsAppExperience


def resolve_routing_context(
    db: Session,
    phone_number_id: str | None,
    *,
    provider: str = "meta_whatsapp",
) -> WhatsAppRoutingContext:
    if not phone_number_id:
        raise RoutingError("receiving phone number is required")
    binding = db.scalar(
        select(WhatsAppNumberBinding).where(
            WhatsAppNumberBinding.provider == provider,
            WhatsAppNumberBinding.phone_number_id == phone_number_id,
            WhatsAppNumberBinding.enabled.is_(True),
        )
    )
    if binding is None:
        raise RoutingError("receiving number is not enabled")
    if db.get(Business, binding.business_id) is None:
        raise RoutingError("bound business does not exist")
    try:
        experience = WhatsAppExperience(binding.experience)
    except ValueError as exc:
        raise RoutingError("unsupported WhatsApp experience") from exc
    return WhatsAppRoutingContext(provider, phone_number_id, binding.business_id, experience)
