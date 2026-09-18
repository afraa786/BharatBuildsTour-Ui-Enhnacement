"""The Manager's conversational persona: admin-facing, history-aware talk only.

process_admin_message reaches this only after every exact command
(Approve/Reject/Show/etc.) has already failed to match, so this can never
be used to take an action -- it can only produce conversational text.
"""

from sqlalchemy.orm import Session

from app.modules.runs.conversation_graph import run_conversation

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


def manager_chat(
    db: Session | None,
    admin_wa_id: str,
    message: str,
    fallback: str,
    phone_number_id: str | None = None,
) -> str:
    return run_conversation(
        db, admin_wa_id, _SYSTEM_PROMPT, message, fallback, phone_number_id=phone_number_id
    )
