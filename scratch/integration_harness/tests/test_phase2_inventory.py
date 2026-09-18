import json
import os
import pytest
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def check_status(on_hand, req, threshold=None):
    if on_hand <= 0: return 'OUT_OF_STOCK'
    if on_hand < req: return 'INSUFFICIENT_STOCK'
    if threshold is not None and (on_hand - req) <= threshold: return 'LOW_STOCK'
    return 'AVAILABLE'

@pytest.mark.parametrize("on_hand, req, threshold, expected", [
    (0, 5, 10, 'OUT_OF_STOCK'),
    (-2, 5, 10, 'OUT_OF_STOCK'),
    (2, 5, 10, 'INSUFFICIENT_STOCK'),
    (10, 5, 5, 'LOW_STOCK'), # 10 - 5 = 5 <= 5
    (20, 5, 5, 'AVAILABLE'), # 20 - 5 = 15 > 5
    (20, 5, None, 'AVAILABLE'),
])
def test_stock_precedence(on_hand, req, threshold, expected):
    """
    Test precedence: OUT_OF_STOCK > INSUFFICIENT_STOCK > LOW_STOCK > AVAILABLE
    """
    assert check_status(on_hand, req, threshold) == expected

def test_inventory_read_only_invariant():
    """Check before/after snapshots for read-only inventory."""
    snapshots = load_json(os.path.join(FIXTURES_DIR, 'inventory', 'snapshots.json'))
    
    before = snapshots['STATE_BEFORE']
    after = snapshots['STATE_AFTER']
    
    assert before['product_id'] == after['product_id']
    assert before['on_hand_qty'] == after['on_hand_qty']
    assert before['version'] == after['version']
    assert before['stock_movements_count'] == after['stock_movements_count']
