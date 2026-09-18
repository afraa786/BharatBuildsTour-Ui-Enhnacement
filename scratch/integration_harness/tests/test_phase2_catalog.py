import json
import os
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def test_catalog_ambiguity_invariant():
    """For any ambiguous candidate set size > 1: selected identity must never exist."""
    ambiguity_data = load_json(os.path.join(FIXTURES_DIR, 'catalog', 'ambiguity.json'))
    
    for case_name, data in ambiguity_data.items():
        if case_name.startswith('_'): continue
        
        resp = data['response']
        if resp.get('status') == 'AMBIGUOUS':
            assert resp.get('selected_product_id') is None, f"{case_name} leaked product_id"
            assert resp.get('selected_sku') is None, f"{case_name} leaked sku"
            assert len(resp.get('candidates', [])) >= 1, f"{case_name} has no candidates despite being ambiguous"

def test_business_isolation_invariant():
    """For any Business A request: Business B-only IDs must never appear in response."""
    isolation_data = load_json(os.path.join(FIXTURES_DIR, 'catalog', 'business_isolation.json'))
    
    for case_name, data in isolation_data.items():
        if case_name.startswith('_'): continue
        
        req = data['request']
        resp = data['response']
        
        if "B-ONLY" in case_name or "OTHER_BUSINESS" in req['requested_text'].upper():
            assert resp.get('status') == 'NOT_FOUND', f"{case_name} did not return NOT_FOUND"
            assert not resp.get('candidates'), f"{case_name} leaked candidates across businesses"
            
        # Ensure B's products don't appear in A's response
        if req['business_id'] == "b0000000-0000-4000-a000-000000000000":
            for cand in resp.get('candidates', []):
                assert "B00" not in cand['sku'], f"Business A saw Business B sku in {case_name}"
