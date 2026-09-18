import json
import os
import sys

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def load_all_jsons(directory):
    data = {}
    if not os.path.exists(directory):
        return data
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            data[filename] = load_json(filepath)
    return data

def check_forbidden_fields(obj, path, errors):
    forbidden = {'cost_unit_paise', 'min_margin_bps', 'max_discount_bps'}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in forbidden:
                errors.append(f"Forbidden field '{k}' exposed in response at {path}")
            check_forbidden_fields(v, f"{path}.{k}", errors)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            check_forbidden_fields(item, f"{path}[{i}]", errors)

def validate_catalog_match(match, key, errors):
    if 'response' not in match: return
    resp = match['response']
    if 'error' in resp: return # skip error responses for strict catalog checks

    status = resp.get('status')
    if status not in ['MATCHED', 'AMBIGUOUS', 'NOT_FOUND']:
        errors.append(f"Catalog {key} has invalid status: {status}")

    if status == 'AMBIGUOUS' or status == 'NOT_FOUND':
        if resp.get('selected_product_id') is not None or resp.get('selected_sku') is not None:
            errors.append(f"{status} catalog match {key} contains selected product/sku!")

    if status == 'MATCHED':
        if not resp.get('selected_product_id') or not resp.get('selected_sku'):
            errors.append(f"MATCHED catalog {key} is missing selected product/sku")

def validate_inventory_check(check, key, errors):
    if 'response' not in check: return
    resp = check['response']
    if 'error' in resp: return

    status = resp.get('status')
    if status not in ['AVAILABLE', 'LOW_STOCK', 'INSUFFICIENT_STOCK', 'OUT_OF_STOCK']:
        errors.append(f"Inventory {key} has invalid status: {status}")

    # Validate substitutes rank
    subs = resp.get('substitutes', [])
    if isinstance(subs, list) and subs and not isinstance(subs[0], str):
        ranks = [s.get('rank') for s in subs if isinstance(s, dict)]
        if len(ranks) != len(set(ranks)):
            errors.append(f"Inventory {key} has duplicate substitute ranks")
        for r in ranks:
            if r is None or r < 1:
                errors.append(f"Inventory {key} has invalid substitute rank {r}")

def validate_fixtures():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fixtures_dir = os.path.join(base_dir, 'fixtures')

    errors = []
    # Recursive Validation for Forbidden Fields in ALL Fixtures
    for root, _, files in os.walk(fixtures_dir):
        for filename in files:
            if filename.endswith('.json') and not filename.endswith('.raw.json'):
                filepath = os.path.join(root, filename)
                data = load_json(filepath)
                rel_path = os.path.relpath(filepath, fixtures_dir)
                if filename in ['products.json', 'quotes.json', 'golden_vectors.json']:                    continue
                check_forbidden_fields(data, f"{rel_path}", errors)



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
