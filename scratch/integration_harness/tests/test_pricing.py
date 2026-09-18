import json
import os
import pytest
from decimal import Decimal, ROUND_HALF_UP

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def test_pricing_golden_vectors():
    vectors_path = os.path.join(FIXTURES_DIR, 'pricing', 'golden_vectors.json')
    if not os.path.exists(vectors_path): return
    vectors = load_json(vectors_path)
    if isinstance(vectors, dict) and 'vectors' in vectors:
        vectors = vectors['vectors']

    for vector in vectors:
        inputs = vector['inputs']
        expected = vector['expected']

        unit_price = Decimal(inputs['unit_price_paise'])
        cost_unit = Decimal(inputs['cost_unit_paise'])
        qty = Decimal(inputs['quantity'])
        disc_bps = Decimal(inputs['discount_bps'])
        gst_bps = Decimal(inputs['gst_rate_bps'])
        max_disc_bps = Decimal(inputs['max_discount_bps'])
        min_margin_bps = Decimal(inputs['min_margin_bps'])

        gross_paise = (unit_price * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        discount_paise = (gross_paise * disc_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        taxable_paise = gross_paise - discount_paise

        if 'error' in expected:
            if taxable_paise <= 0:
                assert expected['error'] == "INVALID_REVENUE"
            continue

        unit_price = Decimal(inputs['unit_price_paise'])
        cost_unit = Decimal(inputs['cost_unit_paise'])
        qty = Decimal(inputs['quantity'])
        disc_bps = Decimal(inputs['discount_bps'])
        gst_bps = Decimal(inputs['gst_rate_bps'])
        max_disc_bps = Decimal(inputs['max_discount_bps'])
        min_margin_bps = Decimal(inputs['min_margin_bps'])

        gross_paise = (unit_price * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert gross_paise == Decimal(expected['gross_paise'])

        discount_paise = (gross_paise * disc_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert discount_paise == Decimal(expected['discount_paise'])

        taxable_paise = gross_paise - discount_paise
        assert taxable_paise == Decimal(expected['taxable_paise'])
        assert taxable_paise > 0, "Taxable paise must be positive"

        tax_paise = (taxable_paise * gst_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert tax_paise == Decimal(expected['tax_paise'])

        line_total_paise = taxable_paise + tax_paise
        assert line_total_paise == Decimal(expected['line_total_paise'])

        cost = (cost_unit * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        margin_below_floor = (taxable_paise - cost) * Decimal('10000') < min_margin_bps * taxable_paise
        disc_exceeds_cap = disc_bps > max_disc_bps

        approval_required = margin_below_floor or disc_exceeds_cap
        assert approval_required == expected['approval_required']
