"""Rewrites deterministic Manager output into natural WhatsApp replies.

The facts (items, quantities, prices, stock, status) are computed entirely
by mock_desks/service.py before this module ever sees them. This layer only
rephrases already-decided facts into conversational text -- it never
generates or alters a number, SKU, or business decision. If the OpenAI call
fails or no key is configured, callers get the plain facts back untouched,
so a style layer outage can never block the core quote-to-cash flow.
"""

import logging

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Sales Desk for StockAware, a WhatsApp assistant for an electrical/hardware "
    "wholesaler. Rewrite the given facts as a short, warm, natural WhatsApp message to the "
    "buyer. Keep every number, item name, quantity, price, URL, and ID exactly as given, "
    "character for character -- do not add, remove, round, or invent any fact. No greetings "
    "like 'Dear Sir'. Plain text only, no markdown."
)


def _complete(system_prompt: str, user_text: str, fallback: str) -> str:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        return fallback

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.4,
        )
        text = response.choices[0].message.content
        return text.strip() if text else fallback
    except Exception:
        logger.exception("LLM call failed, falling back to plain text")
        return fallback


def phrase(facts: str) -> str:
    return _complete(_SYSTEM_PROMPT, facts, fallback=facts)


_MANAGER_SYSTEM_PROMPT = (
    "You are the Manager for StockAware, an electrical/hardware wholesaler's WhatsApp business "
    "assistant. You're talking to the owner/admin directly, like their personal assistant -- warm, "
    "concise, plain language, no corporate tone. If they greet you, introduce yourself briefly as "
    "their Manager and what you can help with. You cannot yourself approve, reject, or fetch live "
    "data -- for those, tell them the exact command to use: 'Approve RFQ-1042', 'Reject RFQ-1042', "
    "'Show RFQ-1042', 'Why was RFQ-1042 blocked?', or 'Show open quotes today'. Never claim to "
    "have approved, rejected, or looked anything up yourself -- only point to the right command. "
    "Keep replies short, 1-3 sentences. Plain text only, no markdown."
)


def manager_reply(admin_message: str, fallback: str) -> str:
    return _complete(_MANAGER_SYSTEM_PROMPT, admin_message, fallback=fallback)
