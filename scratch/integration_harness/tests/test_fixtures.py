import json
import os
import pytest
import hmac
import hashlib
from decimal import Decimal, ROUND_HALF_UP

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def test_pricing_golden_vectors():
    vectors = load_json(os.path.join(FIXTURES_DIR, 'pricing', 'golden_vectors.json'))

    for vector in vectors:
        if 'error' in vector['expected']:
            # Invalid revenue check
            continue

        inputs = vector['inputs']
        expected = vector['expected']

        unit_price = Decimal(inputs['unit_price_paise'])
        cost_unit = Decimal(inputs['cost_unit_paise'])
        qty = Decimal(inputs['quantity'])
        disc_bps = Decimal(inputs['discount_bps'])
        gst_bps = Decimal(inputs['gst_rate_bps'])
        max_disc_bps = Decimal(inputs['max_discount_bps'])
        min_margin_bps = Decimal(inputs['min_margin_bps'])

        # Step 1: gross
        gross_paise = (unit_price * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert gross_paise == Decimal(expected['gross_paise'])

        # Step 2: discount
        discount_paise = (gross_paise * disc_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert discount_paise == Decimal(expected['discount_paise'])

        # Step 3: taxable
        taxable_paise = gross_paise - discount_paise
        assert taxable_paise == Decimal(expected['taxable_paise'])

        # Step 4: tax
        tax_paise = (taxable_paise * gst_bps / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        assert tax_paise == Decimal(expected['tax_paise'])

        # Step 5: total
        line_total_paise = taxable_paise + tax_paise
        assert line_total_paise == Decimal(expected['line_total_paise'])

        # Margin Check
        cost = (cost_unit * qty).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        margin_below_floor = (taxable_paise - cost) * Decimal('10000') < min_margin_bps * taxable_paise

        # Discount cap check
        disc_exceeds_cap = disc_bps > max_disc_bps

        approval_required = margin_below_floor or disc_exceeds_cap
        assert approval_required == expected['approval_required']

        reasons = []
        if disc_exceeds_cap: reasons.append("DISCOUNT_EXCEEDS_CAP")
        if margin_below_floor: reasons.append("MARGIN_BELOW_FLOOR")

        assert set(reasons) == set(expected['approval_reasons'])


def test_hmac_raw_body_behavior():
    webhook_dir = os.path.join(FIXTURES_DIR, 'webhooks')
    trap_file = os.path.join(webhook_dir, 'formatting_trap.raw.json')

    with open(trap_file, 'rb') as f:
        raw_bytes = f.read()

    secret = "stockaware_test_webhook_secret".encode('utf-8')
    sig_raw = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    # Simulate bad framework behavior
    parsed = json.loads(raw_bytes)
    re_serialized = json.dumps(parsed).encode('utf-8')
    sig_re_serialized = hmac.new(secret, re_serialized, hashlib.sha256).hexdigest()

    assert sig_raw != sig_re_serialized, "Test suite proves that re-serializing destroys the signature."

def test_invoice_retry_invariant():
    invoices = load_json(os.path.join(FIXTURES_DIR, 'invoices.json'))

    pending = invoices['PENDING_ARTIFACT']
    retry_response = invoices['PDF_RETRY']['response']

    # Must reuse the exact same invoice_id and invoice_number
    assert retry_response['invoice_id'] == pending['invoice_id']
    assert retry_response['invoice_number'] == pending['invoice_number']

def test_ambiguous_match_invariant():
    catalog = load_json(os.path.join(FIXTURES_DIR, 'catalog_match.json'))
    ambiguous = catalog['AMBIGUOUS_ALIAS']['response']

    assert ambiguous['status'] == 'AMBIGUOUS'
    assert ambiguous['selected_product_id'] is None
    assert ambiguous['selected_sku'] is None
    assert len(ambiguous['candidates']) > 1
