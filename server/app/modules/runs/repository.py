from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.runs.models import Approval, Run, RunEvent
from app.modules.runs.state_machine import TERMINAL_STATUSES, RunStatus

OPEN_STATUSES = [s.value for s in RunStatus if s not in TERMINAL_STATUSES]


def next_run_number(db: Session) -> int:
    return db.execute(text("SELECT nextval('run_number_seq')")).scalar_one()


def create_run(db: Session, buyer_wa_id: str, buyer_name: str | None, raw_text: str) -> Run:
    number = next_run_number(db)
    run = Run(
        run_id=f"RFQ-{number}",
        buyer_wa_id=buyer_wa_id,
        buyer_name=buyer_name,
        raw_text=raw_text,
        status=RunStatus.RECEIVED.value,
        line_items=[],
    )
    db.add(run)
    db.flush()
    return run


def get_open_run_for_buyer(db: Session, buyer_wa_id: str) -> Run | None:
    stmt = (
        select(Run)
        .where(Run.buyer_wa_id == buyer_wa_id, Run.status.in_(OPEN_STATUSES))
        .order_by(Run.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def get_run_by_run_id(db: Session, run_id: str) -> Run | None:
    stmt = select(Run).where(Run.run_id == run_id)
    return db.execute(stmt).scalars().first()


def list_runs(db: Session, status: str | None = None) -> list[Run]:
    stmt = select(Run).order_by(Run.created_at.desc())
    if status:
        stmt = stmt.where(Run.status == status)
    return list(db.execute(stmt).scalars().all())


def add_event(
    db: Session, run: Run, role: str, event: str, metadata: dict | None = None
) -> RunEvent:
    run_event = RunEvent(run_id=run.id, role=role, event=event, event_metadata=metadata)
    db.add(run_event)
    db.flush()
    return run_event


def get_timeline(db: Session, run: Run) -> list[RunEvent]:
    stmt = select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.created_at)
    return list(db.execute(stmt).scalars().all())


def create_approval(
    db: Session, run: Run, action: str = "approve_quote", ttl_hours: int = 24
) -> Approval:
    approval = Approval(
        run_id=run.id,
        action=action,
        bound_run_version=run.version,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    db.add(approval)
    db.flush()
    return approval


def get_pending_approval(db: Session, run: Run) -> Approval | None:
    stmt = (
        select(Approval)
        .where(Approval.run_id == run.id, Approval.status == "pending")
        .order_by(Approval.created_at.desc())
    )
    return db.execute(stmt).scalars().first()
