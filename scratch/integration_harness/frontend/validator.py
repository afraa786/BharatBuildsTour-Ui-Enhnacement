from typing import Dict, Any

def check_frontend_leakage(data: Any, path: str, errors: list):
    """
    Recursively checks for forbidden fields that should NEVER reach the frontend.
    """
    forbidden_keys = {
        'cost_unit_paise', 'min_margin_bps', 'internal_service_token', 
        'webhook_secret', 'provider_secret', 'internal_policy',
        'db_id', 'pk'
    }

    if isinstance(data, dict):
        for k, v in data.items():
            if k in forbidden_keys:
                errors.append(f"LEAK DETECTED at {path}.{k}: {k} is forbidden")
            
            if k.endswith('_paise'):
                if not isinstance(v, int):
                    errors.append(f"TYPE ERROR at {path}.{k}: expected int, got {type(v).__name__}")

            check_frontend_leakage(v, f"{path}.{k}", errors)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            check_frontend_leakage(item, f"{path}[{i}]", errors)

def validate_frontend_fixture(data: dict):
    errors = []
    check_frontend_leakage(data, "root", errors)
    
    if errors:
        for err in errors:
            print(err)
        raise ValueError(f"Frontend fixture validation failed with {len(errors)} errors.")
    return True
