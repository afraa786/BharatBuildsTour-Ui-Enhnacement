"""The Sales Desk's conversational persona: buyer-facing greetings and
general questions, history-aware so it doesn't reintroduce itself.

Only reached for GREETING/CATALOGUE_QUERY and similar side-chat -- the
actual RFQ pipeline (item matching, stock, pricing, quote math) in
_run_pipeline stays fully deterministic and never goes through here.
"""

from sqlalchemy.orm import Session

from app.modules.runs.conversation_graph import run_conversation

_SYSTEM_PROMPT = (
    "You are the Sales Desk for StockAware, an electrical/hardware wholesaler's WhatsApp "
    "ordering assistant. You're talking to a buyer -- warm, concise, plain language. This is a "
    "continuing conversation: only greet/introduce yourself on the very first turn (when there "
    "is no prior history below) -- never repeat the introduction once you've already said "
    "hello. You cannot yourself check stock, price, or place an order in this reply -- to get a "
    "quote, tell them to send the item name and quantity, for example '20 rolls 1.5 sq mm "
    "wire'. Never invent a price, stock level, or product you don't have data for. Keep replies "
    "short, 1-3 sentences. Plain text only, no markdown."
)


def sales_desk_chat(
    db: Session | None,
    buyer_wa_id: str,
    message: str,
    fallback: str,
    phone_number_id: str | None = None,
) -> str:
    return run_conversation(
        db, buyer_wa_id, _SYSTEM_PROMPT, message, fallback, phone_number_id=phone_number_id
    )
