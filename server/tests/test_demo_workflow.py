from fastapi.testclient import TestClient

from app.main import app


def test_demo_quote_to_cash_is_idempotent() -> None:
    payload = {
        "source_message_id": "wamid.test.101",
        "buyer_name": "Acme Electrical Contractors",
        "buyer_phone": "+919811111111",
        "lines": [
            {"requested_name": "32 amp MCB", "quantity": 2, "unit": "each"},
            {"requested_name": "1.5 sq red wire", "quantity": 10, "unit": "metre"},
        ],
    }
    with TestClient(app) as client:
        intake = client.post("/demo/webhook/whatsapp", json=payload)
        assert intake.status_code == 201
        run_id = intake.json()["run"]["id"]
        duplicate = client.post("/demo/webhook/whatsapp", json=payload)
        assert duplicate.json()["duplicate"] is True
        assert client.post(f"/demo/runs/{run_id}/accept").status_code == 200
        payment = client.post("/demo/payments/create-link", json={"run_id": run_id}).json()
        assert client.post("/demo/invoice/generate", json={"payment_id": payment["id"]}).status_code == 409
        assert client.post(f"/demo/payments/{payment['id']}/confirm").json()["status"] == "PAID"
        invoice = client.post("/demo/invoice/generate", json={"payment_id": payment["id"]}).json()
        assert invoice["idempotent"] is False
        assert client.post("/demo/invoice/generate", json={"payment_id": payment["id"]}).json()["idempotent"] is True
