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


def _complete_messages(messages: list[dict[str, str]], fallback: str) -> str:
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        return fallback

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4,
        )
        text = response.choices[0].message.content
        return text.strip() if text else fallback
    except Exception:
        logger.exception("LLM call failed, falling back to plain text")
        return fallback


def chat_complete(
    system_prompt: str, history: list[dict[str, str]], user_text: str, fallback: str
) -> str:
    """Multi-turn completion: system prompt + prior turns + the new message."""
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_text},
    ]
    return _complete_messages(messages, fallback)


def phrase(facts: str) -> str:
    return _complete_messages(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": facts},
        ],
        fallback=facts,
    )
