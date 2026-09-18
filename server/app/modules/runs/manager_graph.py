"""The Manager's conversational persona, as a small LangGraph graph.

Loads recent WhatsApp turns for the admin from the message log, then asks
the LLM for a reply in that context. Giving it real history is what stops
it from re-introducing itself on every single message -- without this it
has no idea it already said hello. This graph never decides or executes a
business action (approve/reject/show); process_admin_message only reaches
it after every exact command has already failed to match, so it can only
ever produce talk.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runs.phrasing import chat_complete
from app.modules.whatsapp.models import WhatsAppMessage

_SYSTEM_PROMPT = (
    "You are the Manager for StockAware, an electrical/hardware wholesaler's WhatsApp business "
    "assistant. You're talking to the owner/admin directly, like their personal assistant -- warm, "
    "concise, plain language, no corporate tone. This is a continuing conversation: only introduce "
    "yourself as their Manager on the very first turn (when there is no prior history below) -- "
    "never repeat the introduction once you've already said hello. You cannot yourself approve, "
    "reject, or fetch live data -- for those, tell them the exact command to use: "
    "'Approve RFQ-1042', 'Reject RFQ-1042', 'Show RFQ-1042', 'Why was RFQ-1042 blocked?', or "
    "'Show open quotes today'. Never claim to have approved, rejected, or looked anything up "
    "yourself -- only point to the right command. Keep replies short, 1-3 sentences. Plain text "
    "only, no markdown."
)

_HISTORY_TURNS = 8


class ManagerState(TypedDict, total=False):
    db: Session | None
    admin_wa_id: str
    phone_number_id: str | None
    message: str
    fallback: str
    history: list[dict[str, str]]
    reply: str


def _load_history(state: ManagerState) -> ManagerState:
    db = state.get("db")
    if db is None:
        return {"history": []}

    # Each business number is a separate WhatsApp thread -- scope history to
    # the number this conversation is on, or two numbers' chats bleed together.
    conditions = [WhatsAppMessage.wa_id == state["admin_wa_id"]]
    phone_number_id = state.get("phone_number_id")
    if phone_number_id:
        conditions.append(WhatsAppMessage.phone_number_id == phone_number_id)

    stmt = (
        select(WhatsAppMessage)
        .where(*conditions)
        .order_by(WhatsAppMessage.created_at.desc())
        .limit(_HISTORY_TURNS)
    )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()

    history: list[dict[str, str]] = []
    for row in rows:
        text = (row.payload or {}).get("text") if row.payload else None
        if not text:
            continue
        role = "user" if row.direction == "in" else "assistant"
        history.append({"role": role, "content": text})
    return {"history": history}


def _generate_reply(state: ManagerState) -> ManagerState:
    reply = chat_complete(
        _SYSTEM_PROMPT,
        state.get("history", []),
        state["message"],
        fallback=state["fallback"],
    )
    return {"reply": reply}


_builder = StateGraph(ManagerState)
_builder.add_node("load_history", _load_history)
_builder.add_node("generate_reply", _generate_reply)
_builder.add_edge(START, "load_history")
_builder.add_edge("load_history", "generate_reply")
_builder.add_edge("generate_reply", END)
_graph = _builder.compile()


def manager_chat(
    db: Session | None,
    admin_wa_id: str,
    message: str,
    fallback: str,
    phone_number_id: str | None = None,
) -> str:
    result = _graph.invoke(
        {
            "db": db,
            "admin_wa_id": admin_wa_id,
            "phone_number_id": phone_number_id,
            "message": message,
            "fallback": fallback,
        }
    )
    return result.get("reply", fallback)
