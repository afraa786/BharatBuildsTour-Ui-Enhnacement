"""Explicit operator command; never runs as part of startup or migrations."""

import argparse
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import transaction_session
from app.modules.identity.models import Business
from app.modules.whatsapp.models import WhatsAppNumberBinding
from app.modules.whatsapp.routing import WhatsAppExperience


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind a configured WhatsApp receiving number to a business."
    )
    number_source = parser.add_mutually_exclusive_group(required=True)
    number_source.add_argument("--credential-slot", choices=("biz", "test"))
    number_source.add_argument("--phone-number-id")
    parser.add_argument("--business-id", required=True, type=UUID)
    parser.add_argument(
        "--experience", required=True, choices=[e.value for e in WhatsAppExperience]
    )
    parser.add_argument("--waba-id")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    phone_number_id = args.phone_number_id
    if args.credential_slot == "biz":
        phone_number_id = settings.whatsapp_biz_phone_number_id
    elif args.credential_slot == "test":
        phone_number_id = settings.whatsapp_test_phone_number_id
    if not phone_number_id:
        raise SystemExit("receiving phone number ID is not configured")

    with transaction_session() as db:
        if db.get(Business, args.business_id) is None:
            raise SystemExit("business not found")
        binding = db.scalar(
            select(WhatsAppNumberBinding).where(
                WhatsAppNumberBinding.provider == "meta_whatsapp",
                WhatsAppNumberBinding.phone_number_id == phone_number_id,
            )
        )
        if binding is None:
            db.add(
                WhatsAppNumberBinding(
                    phone_number_id=phone_number_id,
                    business_id=args.business_id,
                    experience=args.experience,
                    waba_id=args.waba_id,
                )
            )
        else:
            desired_waba_id = args.waba_id if args.waba_id is not None else binding.waba_id
            if (
                binding.business_id != args.business_id
                or binding.experience != args.experience
                or binding.waba_id != desired_waba_id
                or not binding.enabled
            ):
                if not args.replace_existing:
                    raise SystemExit("binding already exists; use --replace-existing to change it")
                binding.business_id = args.business_id
                binding.experience = args.experience
                binding.waba_id = desired_waba_id
                binding.enabled = True
    print("WhatsApp receiving-number binding saved.")


if __name__ == "__main__":
    main()
