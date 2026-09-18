import json
import os
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def test_invoice_retry_invariant():
    invoices_path = os.path.join(FIXTURES_DIR, 'invoices.json')
    if not os.path.exists(invoices_path): return
    invoices = load_json(invoices_path)

    if 'PENDING_ARTIFACT' in invoices and 'PDF_RETRY' in invoices:
        pending = invoices['PENDING_ARTIFACT']
        retry_response = invoices['PDF_RETRY']['response']

        assert retry_response['invoice_id'] == pending['invoice_id']
        assert retry_response['invoice_number'] == pending['invoice_number']
