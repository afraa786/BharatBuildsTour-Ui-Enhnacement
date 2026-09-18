from decimal import Decimal, ROUND_HALF_UP

def price_quote_line(unit_price_paise: int, cost_unit_paise: int, quantity: Decimal, discount_bps: int, gst_rate_bps: int, max_discount_bps: int, min_margin_bps: int):
    """
    Pure Python harness pricing reference using Decimal and ROUND_HALF_UP.
    Follows Phase 3 contract exactly.
    """
    qty = Decimal(str(quantity)) # Ensure precise initialization
    unit_price = Decimal(str(unit_price_paise))
    cost_unit = Decimal(str(cost_unit_paise))
    disc_bps = Decimal(str(discount_bps))
    gst_bps = Decimal(str(gst_rate_bps))
    max_disc_bps = Decimal(str(max_discount_bps))
    min_margin = Decimal(str(min_margin_bps))

    # 1. Gross
    gross_paise = (unit_price * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    # 2. Discount
    discount_paise = (gross_paise * disc_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    # 3. Taxable
    taxable_paise = gross_paise - discount_paise
    if taxable_paise <= 0 and gross_paise > 0:
        # Invalid negative/zero revenue if not explicitly free
        pass
        
    # 4. Tax
    tax_paise = (taxable_paise * gst_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    # 5. Line Total
    line_total_paise = taxable_paise + tax_paise
    
    # 6. Margin and Approval
    cost = (cost_unit * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    margin_below_floor = False
    if taxable_paise > 0:
        # Cross-multiplication avoiding float
        margin_below_floor = (taxable_paise - cost) * Decimal('10000') < min_margin * taxable_paise
    else:
        margin_below_floor = True # Cannot satisfy margin on zero revenue

    disc_exceeds_cap = disc_bps > max_disc_bps
    
    reasons = []
    if disc_exceeds_cap:
        reasons.append("DISCOUNT_EXCEEDS_CAP")
    if margin_below_floor:
        reasons.append("MARGIN_BELOW_FLOOR")
        
    return {
        "gross_paise": int(gross_paise),
        "discount_paise": int(discount_paise),
        "taxable_paise": int(taxable_paise),
        "tax_paise": int(tax_paise),
        "line_total_paise": int(line_total_paise),
        "approval_required": len(reasons) > 0,
        "approval_reasons": reasons
    }
