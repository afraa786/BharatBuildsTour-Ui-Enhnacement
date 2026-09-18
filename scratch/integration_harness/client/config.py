import os


class HarnessConfig:
    def __init__(self):
        self.base_url = os.environ.get("STOCKAWARE_BASE_URL", "http://localhost:8000")
        self.internal_service_token = os.environ.get(
            "STOCKAWARE_INTERNAL_TOKEN", "fake_internal_test_token"
        )
        self.webhook_secret = os.environ.get(
            "STOCKAWARE_WEBHOOK_SECRET", "fake_webhook_secret_key"
        )
        self.provider_account_id = os.environ.get(
            "STOCKAWARE_PROVIDER_ACCOUNT_ID", "acc_stockaware_http_acceptance"
        )

        # Deterministic demo identities. HTTP mode still requires explicit opt-in.
        self.default_business_id = os.environ.get(
            "STOCKAWARE_BUSINESS_ID", "ff720599-56e8-53f4-9279-27ae059da37f"
        )
        self.default_buyer_id = os.environ.get(
            "STOCKAWARE_BUYER_ID", "b890a599-66c8-53f4-8279-27ae059da333"
        )
        self.http_acceptance_enabled = (
            os.environ.get("STOCKAWARE_HTTP_ACCEPTANCE") == "1"
        )
        self.fixture_injection_enabled = (
            os.environ.get("STOCKAWARE_TEST_FIXTURE_INJECTION") == "1"
        )

    def missing_http_configuration(self) -> list[str]:
        required = {
            "STOCKAWARE_BASE_URL": os.environ.get("STOCKAWARE_BASE_URL"),
            "STOCKAWARE_INTERNAL_TOKEN": os.environ.get("STOCKAWARE_INTERNAL_TOKEN"),
            "STOCKAWARE_WEBHOOK_SECRET": os.environ.get("STOCKAWARE_WEBHOOK_SECRET"),
            "STOCKAWARE_BUSINESS_ID": os.environ.get("STOCKAWARE_BUSINESS_ID"),
            "STOCKAWARE_BUYER_ID": os.environ.get("STOCKAWARE_BUYER_ID"),
        }
        if not self.http_acceptance_enabled:
            required["STOCKAWARE_HTTP_ACCEPTANCE=1"] = None
        return [name for name, value in required.items() if not value]


config = HarnessConfig()
