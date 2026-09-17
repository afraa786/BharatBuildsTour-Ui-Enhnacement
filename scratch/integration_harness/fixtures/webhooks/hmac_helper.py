import hmac
import hashlib
import json
import os

TEST_SECRET = "stockaware_test_webhook_secret"

def calculate_signature(raw_bytes: bytes, secret: str = TEST_SECRET) -> str:
    """Calculates the Razorpay HMAC-SHA256 signature from raw bytes."""
    return hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

def verify_signature(raw_bytes: bytes, signature: str, secret: str = TEST_SECRET) -> bool:
    """Verifies a signature using constant-time comparison."""
    expected_signature = calculate_signature(raw_bytes, secret)
    return hmac.compare_digest(expected_signature, signature)

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    trap_file = os.path.join(current_dir, "formatting_trap.raw.json")

    with open(trap_file, "rb") as f:
        raw_bytes = f.read()

    sig_raw = calculate_signature(raw_bytes)

    # Simulate a bad implementation that parses and re-dumps
    parsed = json.loads(raw_bytes)
    re_serialized = json.dumps(parsed).encode("utf-8")
    sig_re_serialized = calculate_signature(re_serialized)

    print(f"Signature on raw bytes: {sig_raw}")
    print(f"Signature on re-serialized bytes: {sig_re_serialized}")

    if sig_raw != sig_re_serialized:
        print("SUCCESS: The signatures do not match! This proves that re-serializing destroys the signature.")
    else:
        print("FAIL: The signatures matched, which shouldn't happen with formatting_trap.raw.json")
