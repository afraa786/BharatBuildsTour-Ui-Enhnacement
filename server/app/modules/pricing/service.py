import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.api.commercial import CommercialError
from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.pricing import repository
from app.modules.pricing.models import Quote, QuoteItem
from app.modules.pricing.money import MAX_PAISE, price_line
from app.modules.pricing.schemas import QuoteCreateIn, QuoteLineOut, QuoteOut, QuoteStatus

ACTION = "pricing.quote"


def _fingerprint(request: QuoteCreateIn) -> str:
    payload = request.model_dump(mode="json")
    for line in payload["lines"]:
        line["quantity"] = f"{Decimal(line['quantity']):.3f}"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{ACTION}:{canonical}".encode()).hexdigest()


def _safe_quote(session: Session, quote: Quote) -> QuoteOut:
    items = repository.get_quote_items(session, quote.business_id, quote.id)
    return QuoteOut(
        business_id=quote.business_id,
        run_id=quote.run_id,
        quote_id=quote.id,
        quote_version=quote.quote_version,
        status=QuoteStatus(quote.status),
        currency=quote.currency,
        subtotal_paise=quote.subtotal_paise,
        tax_paise=quote.tax_paise,
        total_paise=quote.total_paise,
        expires_at=quote.expires_at,
        approval_required=quote.approval_required,
        approval_satisfied=quote.approval_satisfied,
        approval_reasons=quote.policy_snapshot.get("approval_reasons", []),
        lines=[
            QuoteLineOut(
                product_id=item.product_id,
                sku=item.sku_snapshot,
                name=item.name_snapshot,
                quantity=item.quantity,
                unit=item.sellable_unit_snapshot,
                unit_price_paise=item.unit_price_paise,
                discount_bps=item.discount_bps,
                discount_paise=item.discount_paise,
                taxable_paise=item.taxable_paise,
                gst_rate_bps=item.gst_rate_bps,
                tax_paise=item.tax_paise,
                line_total_paise=item.line_total_paise,
            )
            for item in items
        ],
    )


def create_quote(
    session: Session, business_id: UUID, request: QuoteCreateIn, idempotency_key: str
) -> QuoteOut:
    fingerprint = _fingerprint(request)
    idempotency, claimed = repository.claim_idempotency(
        session, business_id, ACTION, idempotency_key, fingerprint
    )
    if idempotency.request_sha256 != fingerprint:
        raise CommercialError(
            409, "IDEMPOTENCY_CONFLICT", "Idempotency key was used for another request."
        )
    if not claimed:
        if idempotency.state == "COMPLETED" and idempotency.response_reference:
            return QuoteOut.model_validate(idempotency.response_reference)
        raise CommercialError(
            409, "IDEMPOTENCY_IN_PROGRESS", "The original request is still processing."
        )

    now = datetime.now(UTC)
    business = repository.get_business(session, business_id)
    if business is None:
        raise CommercialError(404, "NOT_FOUND", "Business not found.")
    if business.quote_validity_minutes is None:
        raise CommercialError(
            409, "QUOTE_VALIDITY_UNCONFIGURED", "Quote validity is not configured."
        )
    buyer = repository.get_buyer(session, business_id, request.buyer_id)
    if buyer is None:
        raise CommercialError(404, "NOT_FOUND", "Buyer not found.")
    if not buyer.display_name and not buyer.whatsapp_e164:
        raise CommercialError(422, "VALIDATION_ERROR", "Buyer identity is incomplete.")
    rules = repository.get_active_rule(session, business_id, now)
    if len(rules) != 1:
        raise CommercialError(
            409, "PRICING_RULE_UNAVAILABLE", "Exactly one active pricing rule is required."
        )
    rule = rules[0]
    products = repository.get_active_products(
        session, business_id, {line.product_id for line in request.lines}
    )
    if len(products) != len({line.product_id for line in request.lines}):
        raise CommercialError(404, "NOT_FOUND", "Product not found.")

    snapshots: list[dict] = []
    approval_reasons: list[str] = []
    for index, line in enumerate(request.lines, 1):
        product = products[line.product_id]
        quantity = Decimal(line.quantity)
        if normalize_catalog_text(line.unit) != normalize_catalog_text(product.sellable_unit):
            raise CommercialError(
                422, "VALIDATION_ERROR", "Quote line unit does not match the product."
            )
        if product.indivisible and quantity != quantity.to_integral_value():
            raise CommercialError(422, "VALIDATION_ERROR", "Product quantity must be whole units.")
        try:
            priced = price_line(
                unit_price_paise=product.base_unit_price_paise,
                cost_unit_paise=product.cost_unit_paise,
                quantity=quantity,
                discount_bps=line.discount_bps,
                gst_rate_bps=product.gst_rate_bps,
                max_discount_bps=rule.max_discount_bps,
                min_margin_bps=rule.min_margin_bps,
            )
        except ValueError as exc:
            raise CommercialError(422, "VALIDATION_ERROR", str(exc)) from exc
        approval_reasons.extend(priced.approval_reasons)
        snapshots.append(
            {
                "line_no": index,
                "product_id": product.id,
                "sku_snapshot": product.sku,
                "name_snapshot": product.name,
                "sellable_unit_snapshot": product.sellable_unit,
                "stock_unit_snapshot": product.stock_unit,
                "pack_size": product.pack_size,
                "quantity": quantity,
                "cost_unit_paise": product.cost_unit_paise,
                "unit_price_paise": product.base_unit_price_paise,
                "gross_paise": priced.gross_paise,
                "discount_bps": line.discount_bps,
                "discount_paise": priced.discount_paise,
                "taxable_paise": priced.taxable_paise,
                "gst_rate_bps": product.gst_rate_bps,
                "tax_paise": priced.tax_paise,
                "line_total_paise": priced.line_total_paise,
            }
        )

    if business.approval_required_for_all is True:
        approval_reasons.append("OWNER_APPROVAL_POLICY")
    elif business.approval_required_for_all is None:
        approval_reasons.append("APPROVAL_POLICY_UNCONFIGURED")
    approval_reasons = list(dict.fromkeys(approval_reasons))
    approval_required = bool(approval_reasons)
    status = QuoteStatus.DRAFT if approval_required else QuoteStatus.GENERATED

    subtotal_paise = sum(item["taxable_paise"] for item in snapshots)
    tax_paise = sum(item["tax_paise"] for item in snapshots)
    total_paise = subtotal_paise + tax_paise
    if max(subtotal_paise, tax_paise, total_paise) > MAX_PAISE:
        raise CommercialError(422, "VALIDATION_ERROR", "Quote amount exceeds BIGINT paise range.")

    lineage = repository.lock_lineage(session, business_id, request.run_id)
    previous = repository.get_current_quote_locked(session, business_id, request.run_id)
    if previous is not None:
        if repository.has_unsettled_payment(session, business_id, previous.id):
            raise CommercialError(
                409,
                "PAYMENT_RECONCILIATION_REQUIRED",
                "The previous quote has a payment that must be reconciled first.",
            )
        if previous.status in {QuoteStatus.DRAFT, QuoteStatus.GENERATED, QuoteStatus.ACCEPTED}:
            previous.status = QuoteStatus.CANCELLED
        previous.is_current = False
        session.flush()

    version = lineage.latest_version + 1
    lineage.latest_version = version
    quote = Quote(
        id=uuid4(),
        business_id=business_id,
        run_id=request.run_id,
        quote_version=version,
        is_current=True,
        buyer_id=buyer.id,
        buyer_snapshot={
            "display_name": buyer.display_name,
            "whatsapp_e164": buyer.whatsapp_e164,
            "legal_name": buyer.legal_name,
            "billing_address": buyer.billing_address,
            "gstin": buyer.gstin,
            "buyer_name_missing": buyer.display_name is None,
        },
        pricing_rule_id=rule.id,
        pricing_rule_version=rule.version,
        policy_snapshot={
            "rule_id": str(rule.id),
            "rule_version": rule.version,
            "max_discount_bps": rule.max_discount_bps,
            "min_margin_bps": rule.min_margin_bps,
            "approval_required_for_all": business.approval_required_for_all,
            "approval_reasons": approval_reasons,
        },
        tax_context_snapshot={
            "seller_gstin": business.gstin,
            "buyer_gstin": buyer.gstin,
            "classification": None,
        },
        status=status,
        currency="INR",
        subtotal_paise=subtotal_paise,
        tax_paise=tax_paise,
        total_paise=total_paise,
        approval_required=approval_required,
        approval_satisfied=False,
        expires_at=now + timedelta(minutes=business.quote_validity_minutes),
        generated_at=now if status == QuoteStatus.GENERATED else None,
    )
    session.add(quote)
    session.flush()
    for snapshot in snapshots:
        session.add(QuoteItem(id=uuid4(), business_id=business_id, quote_id=quote.id, **snapshot))
    session.flush()
    result = _safe_quote(session, quote)
    idempotency.state = "COMPLETED"
    idempotency.response_status = 200
    idempotency.response_reference = result.model_dump(mode="json")
    return result
