import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def test_e2e_happy_path_correlation():
    e2e_path = os.path.join(FIXTURES_DIR, 'e2e', 'happy_path.json')
    if not os.path.exists(e2e_path): return
    e2e = load_json(e2e_path)
    
    happy = e2e['HAPPY_PATH']
    steps = happy['steps']
    
    # Assert Step 1 outputs product_id which is used in Step 2 and 3
    assert steps[0]['result_product_id'] == steps[1]['input_product_id']
    assert steps[0]['result_product_id'] == steps[2]['input_product_id']
    
    # Assert Quote ID correlation
    assert steps[2]['result_quote_id'] == steps[3]['input_quote_id']
    assert steps[2]['result_quote_id'] == steps[4]['input_quote_id']
    assert steps[2]['result_quote_id'] == steps[5]['input_quote_id']
    
    # Assert Approval ID correlation
    assert steps[3]['result_approval_id'] == steps[4]['input_approval_id']
    
    # Assert Acceptance ID correlation
    assert steps[4]['result_acceptance_id'] == steps[5]['input_acceptance_id']
    
    # Assert Payment ID correlation
    assert steps[5]['result_payment_id'] == steps[7]['input_payment_id']
