"""The Manager's conversational persona: admin-facing, history-aware, and
able to actually call tools instead of telling the admin to type a
command it isn't sure exists.

process_admin_message reaches this only after every exact command
(Approve/Reject/Show/Why/Show-open-quotes) has already failed to match, so
casual phrasing still gets a real answer instead of "I didn't recognize
that command." There is no approve/reject tool -- those two mutating
actions stay gated behind the admin typing the exact command themselves.
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.runs.conversation_graph import load_conversation_history
from app.modules.runs.manager_tools import build_tools

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Manager for StockAware, an electrical/hardware wholesaler's WhatsApp business "
    "assistant. You're talking to the owner/admin directly, like their personal assistant -- warm, "
    "concise, plain language, no corporate tone. This is a continuing conversation: only introduce "
    "yourself as their Manager on the very first turn (when there is no prior history) -- never "
    "repeat the introduction once you've already said hello. "
    "You have tools to look up real run status, why a run is blocked, the full inventory, low "
    "stock, pending payments, and today's open quotes. When the admin asks about any of these, "
    "call the right tool immediately and answer with what it returns -- do not ask for "
    "permission first, do not say you can't, and do not tell them to type a command instead. "
    "Never state a number, status, or fact about the business without getting it from a tool "
    "call first -- never guess or invent one, and never invent a command that isn't real. "
    "You do NOT have a tool to approve or reject a quote -- those are the only two actions that "
    "still require the admin to type the exact command themselves: 'Approve RFQ-1042' or "
    "'Reject RFQ-1042'. Never claim to have approved or rejected anything yourself. "
    "Keep replies short, 1-3 sentences, plain text only, no markdown."
)


def manager_chat(
    db: Session | None,
    admin_wa_id: str,
    message: str,
    fallback: str,
    phone_number_id: str | None = None,
) -> str:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        return fallback

    try:
        history = load_conversation_history(db, admin_wa_id, phone_number_id)
        lc_history = [
            HumanMessage(content=turn["content"])
            if turn["role"] == "user"
            else AIMessage(content=turn["content"])
            for turn in history
        ]

        tools = build_tools(db) if db is not None else []
        model = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.3)
        agent = create_react_agent(model, tools, prompt=_SYSTEM_PROMPT)

        result = agent.invoke({"messages": [*lc_history, HumanMessage(content=message)]})
        final_message = result["messages"][-1]
        text = (final_message.content or "").strip()
        return text or fallback
    except Exception:
        logger.exception("manager agent call failed, falling back to plain text")
        return fallback
