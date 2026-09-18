"""Exact INR paise calculations for immutable quote snapshots."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

MAX_PAISE = 2**63 - 1


def half_up_paise(value: Decimal) -> int:
    rounded = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if abs(rounded) > MAX_PAISE:
        raise ValueError("Amount exceeds signed BIGINT paise range.")
    return rounded


@dataclass(frozen=True)
class PricedLine:
    gross_paise: int
    discount_paise: int
    taxable_paise: int
    tax_paise: int
    line_total_paise: int
    cost_total_paise: int
    approval_reasons: tuple[str, ...]


def price_line(
    *,
    unit_price_paise: int,
    cost_unit_paise: int,
    quantity: Decimal,
    discount_bps: int,
    gst_rate_bps: int,
    max_discount_bps: int,
    min_margin_bps: int,
) -> PricedLine:
    with localcontext() as context:
        context.prec = 60
        return _price_line_impl(
            unit_price_paise=unit_price_paise,
            cost_unit_paise=cost_unit_paise,
            quantity=quantity,
            discount_bps=discount_bps,
            gst_rate_bps=gst_rate_bps,
            max_discount_bps=max_discount_bps,
            min_margin_bps=min_margin_bps,
        )


def _price_line_impl(
    *,
    unit_price_paise: int,
    cost_unit_paise: int,
    quantity: Decimal,
    discount_bps: int,
    gst_rate_bps: int,
    max_discount_bps: int,
    min_margin_bps: int,
) -> PricedLine:
    if unit_price_paise <= 0 or cost_unit_paise < 0 or quantity <= 0:
        raise ValueError("Price, cost, or quantity is invalid.")
    if not all(
        0 <= rate <= 10000
        for rate in (discount_bps, gst_rate_bps, max_discount_bps, min_margin_bps)
    ):
        raise ValueError("A basis-point rate is outside 0..10000.")

    gross = half_up_paise(Decimal(unit_price_paise) * quantity)
    if gross <= 0:
        raise ValueError("The rounded gross amount must be positive.")
    discount = half_up_paise(Decimal(gross) * Decimal(discount_bps) / Decimal(10000))
    discount = min(max(discount, 0), gross)
    taxable = gross - discount
    if taxable <= 0:
        raise ValueError("Zero or negative taxable revenue is invalid.")
    tax = half_up_paise(Decimal(taxable) * Decimal(gst_rate_bps) / Decimal(10000))
    cost = half_up_paise(Decimal(cost_unit_paise) * quantity)

    reasons: list[str] = []
    if discount_bps > max_discount_bps:
        reasons.append("DISCOUNT_EXCEEDS_CAP")
    if (taxable - cost) * 10000 < min_margin_bps * taxable:
        reasons.append("MARGIN_BELOW_FLOOR")

    if taxable + tax > MAX_PAISE:
        raise ValueError("Amount exceeds signed BIGINT paise range.")
    return PricedLine(
        gross_paise=gross,
        discount_paise=discount,
        taxable_paise=taxable,
        tax_paise=tax,
        line_total_paise=taxable + tax,
        cost_total_paise=cost,
        approval_reasons=tuple(reasons),
    )
