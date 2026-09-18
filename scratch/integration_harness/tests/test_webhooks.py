import os
import pytest
import hmac
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, 'fixtures')

def test_hmac_raw_body_behavior():
    trap_file = os.path.join(FIXTURES_DIR, 'webhooks', 'formatting_trap.raw.json')
    if not os.path.exists(trap_file): return

    with open(trap_file, 'rb') as f:
        raw_bytes = f.read()

    secret = "stockaware_test_webhook_secret".encode('utf-8')
    sig_raw = hmac.new(secret, raw_bytes, hashlib.sha256).hexdigest()

    import json
    parsed = json.loads(raw_bytes)
    re_serialized = json.dumps(parsed).encode('utf-8')
    sig_re_serialized = hmac.new(secret, re_serialized, hashlib.sha256).hexdigest()

    assert sig_raw != sig_re_serialized, "Test suite proves that re-serializing destroys the signature."
