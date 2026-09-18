"""Experience dispatch boundary. Customer commerce remains outside this phase."""

from importlib import import_module
from typing import TYPE_CHECKING, Protocol

from sqlalchemy.orm import Session

from app.modules.runs import service as runs_service
from app.modules.runs.intent_router import ActorType, route_message
from app.modules.whatsapp.routing import WhatsAppExperience, WhatsAppRoutingContext

if TYPE_CHECKING:
    from app.modules.runs.service import OutboundMessage


class CustomerCommerceHandler(Protocol):
    def __call__(
        self,
        db: Session,
        context: WhatsAppRoutingContext,
        message: dict,
    ) -> list["OutboundMessage"]: ...


class CommerceHandlerUnavailable(RuntimeError):
    pass


def _default_customer_commerce(
    db: Session,
    context: WhatsAppRoutingContext,
    message: dict,
) -> list["OutboundMessage"]:
    """Adapt trusted routing context to the existing commerce entry point."""
    try:
        commerce_service = import_module("app.modules.commerce.service")
    except ImportError as exc:
        raise CommerceHandlerUnavailable("customer_commerce handler is not installed") from exc

    return commerce_service.process_customer_commerce_message(
        db,
        business_id=context.business_id,
        phone_number_id=context.phone_number_id,
        wa_id=message["wa_id"],
        text_body=message["text"],
    )


customer_commerce_handler: CustomerCommerceHandler = _default_customer_commerce


def register_customer_commerce_handler(handler: CustomerCommerceHandler) -> None:
    """Install the commerce entry point during application composition.

    The routing context, not the message, is authoritative for business and
    experience.
    """
    global customer_commerce_handler
    customer_commerce_handler = handler


def ensure_experience_handler_available(context: WhatsAppRoutingContext) -> None:
    if context.experience is WhatsAppExperience.CUSTOMER_COMMERCE:
        if customer_commerce_handler is _default_customer_commerce:
            try:
                import_module("app.modules.commerce.service")
            except ImportError as exc:
                raise CommerceHandlerUnavailable(
                    "customer_commerce handler is not installed"
                ) from exc


def dispatch_inbound_message(
    db: Session,
    context: WhatsAppRoutingContext,
    message: dict,
    *,
    admin_wa_ids: set[str],
    vendor_wa_ids: set[str],
) -> list["OutboundMessage"]:
    if context.experience is WhatsAppExperience.CUSTOMER_COMMERCE:
        return customer_commerce_handler(db, context, message)

    decision = route_message(
        message["text"],
        actor_hint=(
            ActorType.ADMIN
            if message["wa_id"] in admin_wa_ids
            else ActorType.VENDOR
            if message["wa_id"] in vendor_wa_ids
            else None
        ),
        wa_id=message["wa_id"],
        admin_wa_ids=admin_wa_ids,
        vendor_wa_ids=vendor_wa_ids,
    )
    if decision.actor is ActorType.ADMIN:
        return runs_service.process_admin_message(
            db,
            message["wa_id"],
            message["text"],
            phone_number_id=context.phone_number_id,
        )
    if decision.actor is ActorType.VENDOR:
        return runs_service.process_vendor_message(db, message["wa_id"], message["text"])
    return runs_service.process_buyer_message(
        db,
        message["wa_id"],
        message["text"],
        phone_number_id=context.phone_number_id,
    )
