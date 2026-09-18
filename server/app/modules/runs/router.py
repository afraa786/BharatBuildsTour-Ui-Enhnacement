from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.runs import service
from app.modules.runs.schemas import (
    AdminCommandIn,
    AgentCraftEventOut,
    ApprovalActionIn,
    OutboundMessageOut,
    RunOut,
    TimelineEventOut,
)
from app.modules.whatsapp.client import send_message

router = APIRouter(tags=["runs"])

DbSession = Annotated[Session, Depends(get_db)]


async def _deliver(db: Session, outbound: list) -> list[OutboundMessageOut]:
    for message in outbound:
        await send_message(
            to=message.to,
            message_type=message.message_type,
            text=message.text,
            media_id=message.media_id,
            link=message.link,
            caption=message.caption,
            filename=message.filename,
            latitude=message.latitude,
            longitude=message.longitude,
            name=message.name,
            address=message.address,
            contacts=message.contacts,
            interactive=message.interactive,
        )
    db.commit()
    return [
        OutboundMessageOut(
            to=m.to,
            text=m.text,
            message_type=m.message_type,
            media_id=m.media_id,
            link=m.link,
            caption=m.caption,
            filename=m.filename,
            latitude=m.latitude,
            longitude=m.longitude,
            name=m.name,
            address=m.address,
            contacts=m.contacts,
            interactive=m.interactive,
        )
        for m in outbound
    ]


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: DbSession, status_filter: str | None = None) -> list[RunOut]:
    return [RunOut.model_validate(r) for r in service.get_runs(db, status=status_filter)]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: DbSession) -> RunOut:
    run = service.get_run_snapshot(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{run_id} not found")
    return RunOut.model_validate(run)


@router.get("/runs/{run_id}/timeline", response_model=list[TimelineEventOut])
def get_run_timeline(run_id: str, db: DbSession) -> list[TimelineEventOut]:
    events = service.get_run_timeline(db, run_id)
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{run_id} not found")
    return [
        TimelineEventOut(
            time=e.created_at, role=e.role, event=e.event, run_id=run_id, metadata=e.event_metadata
        )
        for e in events
    ]


@router.get("/runs/{run_id}/agent-events", response_model=list[AgentCraftEventOut])
def get_run_agent_events(run_id: str, db: DbSession) -> list[AgentCraftEventOut]:
    events = service.get_agentcraft_events(db, run_id)
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{run_id} not found")
    return [AgentCraftEventOut.model_validate(event) for event in events]


@router.post("/runs/{run_id}/approve", response_model=list[OutboundMessageOut])
async def approve_run(
    run_id: str, body: ApprovalActionIn, db: DbSession
) -> list[OutboundMessageOut]:
    outbound = service.approve_run(db, run_id, actor=body.actor)
    return await _deliver(db, outbound)


@router.post("/runs/{run_id}/reject", response_model=list[OutboundMessageOut])
async def reject_run(
    run_id: str, body: ApprovalActionIn, db: DbSession
) -> list[OutboundMessageOut]:
    outbound = service.reject_run(db, run_id, actor=body.actor)
    return await _deliver(db, outbound)


@router.post("/admin/command", response_model=list[OutboundMessageOut])
async def admin_command(body: AdminCommandIn, db: DbSession) -> list[OutboundMessageOut]:
    outbound = service.process_admin_message(db, body.actor, body.text)
    return await _deliver(db, outbound)
