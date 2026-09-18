from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    cors_origins: list[str] = ["http://localhost:3000"]
    internal_business_id: str = ""
    internal_service_token: SecretStr = SecretStr("")
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr = SecretStr("")
    razorpay_webhook_secret: SecretStr = SecretStr("")
    razorpay_previous_webhook_secret: SecretStr = SecretStr("")
    razorpay_account_id: str = ""
    artifact_dir: str = "artifacts"

    whatsapp_biz_phone_number_id: str = ""
    whatsapp_biz_access_token: SecretStr = SecretStr("")
    whatsapp_biz_verify_token: str = ""
    whatsapp_test_phone_number_id: str = ""
    whatsapp_test_access_token: SecretStr = SecretStr("")
    whatsapp_test_verify_token: str = ""
    admin_whatsapp_numbers: str = ""
    admin_whatsapp_phone_number_ids: str = ""
    vendor_whatsapp_numbers: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr = SecretStr("")
    razorpay_webhook_secret: SecretStr = SecretStr("")
    razorpay_callback_url: str = ""
    invoice_artifact_root: str = "artifacts"
    public_artifact_base_url: str = ""
    openai_api_key: SecretStr = SecretStr("")
    jwt_secret: SecretStr

    @model_validator(mode="after")
    def reject_placeholder_password(self) -> "Settings":
        password = self.postgres_password.get_secret_value()
        if not password or password.startswith("replace-with-"):
            raise ValueError("Set a unique POSTGRES_PASSWORD in .env before starting the API")
        return self

    @property
    def admin_wa_ids(self) -> set[str]:
        return {n.strip() for n in self.admin_whatsapp_numbers.split(",") if n.strip()}

    @property
    def admin_phone_number_ids(self) -> set[str]:
        return {
            n.strip() for n in self.admin_whatsapp_phone_number_ids.split(",") if n.strip()
        }

    @property
    def vendor_wa_ids(self) -> set[str]:
        return {n.strip() for n in self.vendor_whatsapp_numbers.split(",") if n.strip()}

    @property
    def whatsapp_verify_tokens(self) -> set[str]:
        return {t for t in (self.whatsapp_biz_verify_token, self.whatsapp_test_verify_token) if t}

    @property
    def whatsapp_number_credentials(self) -> dict[str, tuple[str, str]]:
        credentials: dict[str, tuple[str, str]] = {}
        if self.whatsapp_biz_phone_number_id:
            credentials[self.whatsapp_biz_phone_number_id] = (
                self.whatsapp_biz_phone_number_id,
                self.whatsapp_biz_access_token.get_secret_value(),
            )
        if self.whatsapp_test_phone_number_id:
            credentials[self.whatsapp_test_phone_number_id] = (
                self.whatsapp_test_phone_number_id,
                self.whatsapp_test_access_token.get_secret_value(),
            )
        return credentials


@lru_cache
def get_settings() -> Settings:
    return Settings()
