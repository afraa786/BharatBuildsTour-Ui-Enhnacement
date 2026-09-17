import json
import os
import sys

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def validate_fixtures():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_dir = os.path.join(base_dir, 'fixtures')

    ids = load_json(os.path.join(fixtures_dir, 'ids.json'))
    quotes = load_json(os.path.join(fixtures_dir, 'quotes.json'))
    payments = load_json(os.path.join(fixtures_dir, 'payments.json'))
    invoices = load_json(os.path.join(fixtures_dir, 'invoices.json'))
    catalog = load_json(os.path.join(fixtures_dir, 'catalog_match.json'))

    errors = []

    # Validate Quotes
    for key, quote in quotes.items():
        if key.startswith('_'): continue

        # known business/run/buyer
        if quote['business_id'] != ids['business_id']:
            errors.append(f"Quote {key} has unknown business_id")
        if quote['run_id'] != ids['run_id'] and quote['run_id'] != "RFQ-1043-BETA": # Allow beta run for expired quote
            errors.append(f"Quote {key} has unknown run_id")
        if quote['buyer_id'] != ids['buyer_id']:
            errors.append(f"Quote {key} has unknown buyer_id")

        # quote total == subtotal + tax
        if quote['total_paise'] != quote['subtotal_paise'] + quote['tax_paise']:
            errors.append(f"Quote {key} totals don't match: {quote['total_paise']} != {quote['subtotal_paise']} + {quote['tax_paise']}")

        # line items
        calc_sub = 0
        calc_tax = 0
        for item in quote.get('items', []):
            if item['line_total_paise'] != item['taxable_paise'] + item['tax_paise']:
                errors.append(f"Quote {key} item {item['sku']} totals don't match")
            calc_sub += item['taxable_paise']
            calc_tax += item['tax_paise']

        if quote.get('items') and (calc_sub != quote['subtotal_paise'] or calc_tax != quote['tax_paise']):
            errors.append(f"Quote {key} items sum doesn't match quote totals")

        # ACCEPTED quote contains acceptance evidence
        if quote['status'] == 'ACCEPTED':
            if 'acceptance_evidence' not in quote or 'acceptance_id' not in quote:
                errors.append(f"ACCEPTED Quote {key} missing acceptance evidence")

        # approval-required GENERATED/ACCEPTED quote has valid approval evidence
        if quote['approval_required'] and quote['status'] in ['GENERATED', 'ACCEPTED']:
            if not quote.get('approval_satisfied') or 'approval_evidence' not in quote:
                errors.append(f"Quote {key} missing required approval evidence")

    # quote v1/v2 have different UUIDs
    v1_id = quotes['quote_v1_stale']['id']
    v2_id = quotes['quote_v2_draft']['id']
    if v1_id == v2_id:
        errors.append("Quote v1 and v2 share the same UUID!")

    # Validate Payments
    valid_payment = payments['VALID_ACCEPTED_QUOTE']
    if valid_payment['request']['amount_paise'] != quotes['quote_v2_accepted']['total_paise']:
        errors.append("Payment amount != accepted quote total")

    # Validate Invoices
    for key, inv in invoices.items():
        if key.startswith('_') or 'invoice_id' not in inv: continue # skip error responses

        if inv['payment_id'] != ids['payment_id']:
            errors.append(f"Invoice {key} payment_id mismatch")

        if inv['quote_id'] != ids['quote_id_v2']:
            errors.append(f"Invoice {key} quote_id mismatch")

        if inv['total_paise'] != payments['VALID_ACCEPTED_QUOTE']['request']['amount_paise']:
            errors.append(f"Invoice {key} amount mismatch")

        if inv['status'] == 'GENERATED':
            if not inv.get('artifact_key') or not inv.get('artifact_sha256'):
                errors.append(f"GENERATED Invoice {key} missing artifact metadata")

        if inv['status'] == 'PENDING_ARTIFACT':
            if inv.get('download_url') is not None:
                errors.append(f"PENDING_ARTIFACT Invoice {key} has a download_url")

    # Validate Catalog
    for key, match in catalog.items():
        if key.startswith('_'): continue
        if match['response'].get('status') == 'AMBIGUOUS':
            if match['response'].get('selected_product_id') is not None or match['response'].get('selected_sku') is not None:
                errors.append(f"AMBIGUOUS catalog match {key} contains selected product/sku!")

    if errors:
        print("Validation Failed:")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
    else:
        print("All fixtures passed validation successfully.")
        sys.exit(0)

if __name__ == '__main__':
    validate_fixtures()
