import hashlib
import hmac

from app.modules.whatsapp.router import verify_meta_signature


def test_meta_signature_uses_raw_body_and_constant_time_contract() -> None:
    body = b'{"entry":[{"changes":[]}]}'
    signature = "sha256=" + hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, signature, "test-app-secret")
    assert not verify_meta_signature(body + b" ", signature, "test-app-secret")
    assert not verify_meta_signature(body, "sha256=" + "0" * 64, "test-app-secret")
    assert not verify_meta_signature(body, None, "test-app-secret")
    assert not verify_meta_signature(body, signature, "")
