"""Generic history-aware WhatsApp reply graph, shared by every persona.

Loads recent turns for a given (wa_id, phone_number_id) thread from the
message log, then asks the LLM for a reply in that context. Without real
history, a persona has no idea it already said hello and reintroduces
itself on every message. History is scoped per business number -- each
number is a separate WhatsApp thread, so mixing them bleeds one
conversation's context into another's.

This graph only ever produces talk for a given system prompt; it never
decides or executes a business action itself.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runs.phrasing import chat_complete
from app.modules.whatsapp.models import WhatsAppMessage

_HISTORY_TURNS = 8


class ConversationState(TypedDict, total=False):
    db: Session | None
    wa_id: str
    phone_number_id: str | None
    system_prompt: str
    message: str
    fallback: str
    history: list[dict[str, str]]
    reply: str


def load_conversation_history(
    db: Session | None, wa_id: str, phone_number_id: str | None = None
) -> list[dict[str, str]]:
    """Last few turns of a (wa_id, phone_number_id) thread, oldest first.

    Each business number is a separate WhatsApp thread -- scope history to
    the number this conversation is on, or two numbers' chats bleed together.
    """
    if db is None:
        return []

    conditions = [WhatsAppMessage.wa_id == wa_id]
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
    return history


def _load_history(state: ConversationState) -> ConversationState:
    return {
        "history": load_conversation_history(
            state.get("db"), state["wa_id"], state.get("phone_number_id")
        )
    }


def _generate_reply(state: ConversationState) -> ConversationState:
    reply = chat_complete(
        state["system_prompt"],
        state.get("history", []),
        state["message"],
        fallback=state["fallback"],
    )
    return {"reply": reply}


_builder = StateGraph(ConversationState)
_builder.add_node("load_history", _load_history)
_builder.add_node("generate_reply", _generate_reply)
_builder.add_edge(START, "load_history")
_builder.add_edge("load_history", "generate_reply")
_builder.add_edge("generate_reply", END)
_graph = _builder.compile()


def run_conversation(
    db: Session | None,
    wa_id: str,
    system_prompt: str,
    message: str,
    fallback: str,
    phone_number_id: str | None = None,
) -> str:
    result = _graph.invoke(
        {
            "db": db,
            "wa_id": wa_id,
            "phone_number_id": phone_number_id,
            "system_prompt": system_prompt,
            "message": message,
            "fallback": fallback,
        }
    )
    return result.get("reply", fallback)
