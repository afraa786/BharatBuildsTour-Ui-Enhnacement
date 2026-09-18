from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.runs import service
from app.modules.runs.agent_team import agentcraft_events_from_run_events
from app.modules.runs.repository import create_run
from app.modules.runs.state_machine import RunStatus


@dataclass
class FakeRun:
    run_id: str = "RFQ-1042"
    business_id: object = field(default_factory=uuid4)
    status: str = RunStatus.QUOTE_SENT.value
    raw_text: str = "20 led bulb 9w"
    line_items: list = field(default_factory=list)
    created_at: datetime = datetime(2026, 9, 18, tzinfo=UTC)


@dataclass
class FakeRunEvent:
    role: str
    event: str
    created_at: datetime = datetime(2026, 9, 18, tzinfo=UTC)


def test_agentcraft_events_can_come_from_actual_run_events() -> None:
    events = agentcraft_events_from_run_events(
        run_id="RFQ-1042",
        run_events=[
            FakeRunEvent("Manager", "Run received from WhatsApp"),
            FakeRunEvent("Stock Desk", "Parsed line items"),
            FakeRunEvent("Pricing Desk", "Calculating quote"),
            FakeRunEvent("Sales Desk", "Quote sent to buyer"),
        ],
    )

    assert [event["from_agent"] for event in events] == ["manager", "inventory", "pricing"]
    assert [event["to_agent"] for event in events] == ["inventory", "pricing", "sales"]
    assert events[0]["message"] == "Parsed line items"


def test_agentcraft_events_are_business_scoped(monkeypatch) -> None:
    run = FakeRun()
    monkeypatch.setattr(service, "get_run_by_run_id", lambda db, run_id: run)
    monkeypatch.setattr(service, "get_timeline", lambda db, found_run: [])

    events = service.get_agentcraft_events(object(), "RFQ-1042", business_id=run.business_id)
    wrong_business = service.get_agentcraft_events(object(), "RFQ-1042", business_id=uuid4())

    assert events
    assert events[0]["run_id"] == "RFQ-1042"
    assert wrong_business is None


def test_create_run_accepts_business_scope(monkeypatch) -> None:
    business_id = uuid4()
    added = []

    class FakeDb:
        def execute(self, statement):
            class Result:
                def scalar_one(self):
                    return 1042

            return Result()

        def add(self, item):
            added.append(item)

        def flush(self):
            pass

    run = create_run(
        FakeDb(),
        buyer_wa_id="buyer-1",
        buyer_name=None,
        raw_text="20 led bulb 9w",
        business_id=business_id,
    )

    assert run.business_id == business_id
    assert added == [run]
