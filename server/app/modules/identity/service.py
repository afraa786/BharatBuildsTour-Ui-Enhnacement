import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.identity.models import Buyer


def normalize_whatsapp_identity(wa_id: str) -> str:
    """Store Meta's digits-only wa_id; accept formatted E.164 input equivalently."""
    value = re.sub(r"[\s().-]", "", wa_id)
    if value.startswith("+"):
        value = value[1:]
    if not value.isascii() or not value.isdecimal() or not 8 <= len(value) <= 15:
        raise ValueError("Invalid WhatsApp identity")
    return value


def resolve_or_create_whatsapp_buyer(
    session: Session, business_id: UUID, whatsapp_e164: str, display_name: str | None = None
) -> Buyer:
    """
    Resolves an existing buyer or creates a new Lead (is_customer=False).
    Uses INSERT ... ON CONFLICT DO NOTHING for concurrency safety.
    """
    whatsapp_e164 = normalize_whatsapp_identity(whatsapp_e164)
    # Attempt to insert Lead
    stmt = (
        insert(Buyer)
        .values(
            business_id=business_id,
            whatsapp_e164=whatsapp_e164,
            display_name=display_name,
            is_customer=False,
            source="whatsapp",
        )
        .on_conflict_do_nothing(index_elements=["business_id", "whatsapp_e164"])
        .returning(Buyer)
    )

    buyer = session.scalars(stmt).first()
    if buyer:
        return buyer

    # If it didn't insert, it already exists, fetch it
    buyer = session.scalars(
        select(Buyer).where(Buyer.business_id == business_id, Buyer.whatsapp_e164 == whatsapp_e164)
    ).first()

    if not buyer:
        # A concurrent delete after the conflict is unlikely, but fail closed
        # rather than returning an unscoped or synthetic Buyer.
        raise RuntimeError("Failed to resolve or create buyer.")

    return buyer


def promote_buyer_to_customer(session: Session, business_id: UUID, buyer_id: UUID) -> Buyer:
    """
    Promotes a buyer from Lead to Customer.
    Idempotent: if already True, remains True.
    """
    buyer = session.scalars(
        select(Buyer)
        .where(Buyer.business_id == business_id, Buyer.id == buyer_id)
        .with_for_update()
    ).first()

    if not buyer:
        raise ValueError(f"Buyer {buyer_id} not found in business {business_id}.")

    if not buyer.is_customer:
        buyer.is_customer = True

    return buyer
