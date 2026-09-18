from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.modules.identity.models import Business, Buyer
from app.modules.identity.service import promote_buyer_to_customer, resolve_or_create_whatsapp_buyer
from app.seed import DEMO_BUSINESS_ID

pytest_plugins = ["test_phase1_postgres"]


def test_resolve_or_create_whatsapp_buyer(pg_session: Session):
    # Test unknown sender creates Lead
    wa_id = "919999999999"
    buyer1 = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, wa_id, "Test Sender")

    assert buyer1 is not None
    assert buyer1.is_customer is False
    assert buyer1.whatsapp_e164 == wa_id
    assert buyer1.display_name == "Test Sender"

    # Test returning sender resolves same Buyer
    buyer2 = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, wa_id, "Different Name")

    assert buyer2.id == buyer1.id
    assert buyer2.is_customer is False  # Does not downgrade or upgrade


def test_promote_buyer_to_customer(pg_session: Session):
    wa_id = "918888888888"
    buyer = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, wa_id, "To Promote")
    assert buyer.is_customer is False

    # Promote
    promoted = promote_buyer_to_customer(pg_session, DEMO_BUSINESS_ID, buyer.id)
    assert promoted.is_customer is True

    # Idempotency
    promoted_again = promote_buyer_to_customer(pg_session, DEMO_BUSINESS_ID, buyer.id)
    assert promoted_again.is_customer is True


def test_same_identity_cannot_cross_tenant(pg_session: Session):
    # Create another business
    other_business_id = uuid4()
    pg_session.execute(insert(Business).values(id=other_business_id, display_name="Other Business"))
    pg_session.commit()

    wa_id = "917777777777"
    buyer1 = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, wa_id)
    buyer2 = resolve_or_create_whatsapp_buyer(pg_session, other_business_id, wa_id)

    assert buyer1.id != buyer2.id
    assert buyer1.business_id == DEMO_BUSINESS_ID
    assert buyer2.business_id == other_business_id


def test_whatsapp_identity_canonical_and_existing_customer_not_downgraded(
    pg_session: Session,
):
    from app.modules.identity.service import normalize_whatsapp_identity

    assert normalize_whatsapp_identity("+91 98765-43210") == "919876543210"
    assert normalize_whatsapp_identity("919876543210") == "919876543210"
    buyer = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, "+91 98765-43210")
    promote_buyer_to_customer(pg_session, DEMO_BUSINESS_ID, buyer.id)
    again = resolve_or_create_whatsapp_buyer(pg_session, DEMO_BUSINESS_ID, "919876543210")
    assert again.id == buyer.id
    assert again.is_customer is True


def test_concurrent_first_message_creates_one_buyer(pg_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import func, select

    wa_id = "919" + str(uuid4().int)[:9]
    barrier = Barrier(2)

    def first_message():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            buyer = resolve_or_create_whatsapp_buyer(session, DEMO_BUSINESS_ID, wa_id)
            buyer_id = buyer.id
            session.commit()
            return buyer_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first_message) for _ in range(2)]
        ids = [future.result(timeout=15) for future in futures]

    assert ids[0] == ids[1]
    with Session(pg_engine) as session:
        count = session.scalar(
            select(func.count())
            .select_from(Buyer)
            .where(
                Buyer.business_id == DEMO_BUSINESS_ID,
                Buyer.whatsapp_e164 == wa_id,
            )
        )
        assert count == 1
