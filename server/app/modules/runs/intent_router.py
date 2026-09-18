import re
import string
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.modules.runs.state_machine import RunStatus


class ActorType(StrEnum):
    BUYER = "buyer"
    ADMIN = "admin"
    VENDOR = "vendor"
    UNKNOWN = "unknown"


class IntentType(StrEnum):
    REQUEST_QUOTE = "request_quote"
    REQUEST_ORDER = "request_order"
    CLARIFICATION_REPLY = "clarification_reply"
    NEGOTIATE_PRICE = "negotiate_price"
    ACCEPT_QUOTE = "accept_quote"
    CHANGE_REQUEST = "change_request"
    PAYMENT_CLAIM = "payment_claim"
    REQUEST_PAYMENT_LINK = "request_payment_link"
    REQUEST_INVOICE = "request_invoice"
    DELIVERY_QUERY = "delivery_query"
    IMPORTANT_UPDATES = "important_updates"
    APPROVE_QUOTE = "approve_quote"
    REJECT_QUOTE = "reject_quote"
    SHOW_RUN = "show_run"
    SHOW_LOW_STOCK = "show_low_stock"
    SHOW_PENDING_PAYMENTS = "show_pending_payments"
    VENDOR_PRICE_REVISION = "vendor_price_revision"
    VENDOR_STOCK_UPDATE = "vendor_stock_update"
    VENDOR_DELAY_NOTICE = "vendor_delay_notice"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RouteDecision:
    actor: ActorType
    intent: IntentType
    normalized_text: str
    matched_rule: str | None = None
    actor_source: str | None = None
    requires_exact_run_id: bool = False


class RouteState(TypedDict, total=False):
    text: str
    normalized_text: str
    actor_hint: str | None
    current_status: str | None
    wa_id: str | None
    admin_wa_ids: set[str]
    vendor_wa_ids: set[str]
    actor: str
    actor_source: str
    base_intent: str
    allowed_intent: str
    matched_rule: str | None
    requires_exact_run_id: bool


BUYER_ACCEPT_STATUSES = {RunStatus.QUOTE_SENT.value}
BUYER_PAYMENT_STATUSES = {
    RunStatus.PAYMENT_LINK_SENT.value,
    RunStatus.PAYMENT_PENDING.value,
}
BUYER_INVOICE_STATUSES = {
    RunStatus.PAYMENT_CONFIRMED.value,
    RunStatus.INVOICE_GENERATED.value,
}

PUNCT_TRANSLATION = str.maketrans({c: " " for c in string.punctuation + "“”‘’•·،।॥،"})
SHOW_RUN_RE = re.compile(r"\bshow\s+rfq-\S+")

PHRASE_CATALOG: dict[ActorType, dict[IntentType, tuple[str, ...]]] = {
    ActorType.ADMIN: {
        IntentType.APPROVE_QUOTE: (
            "approve",
            "approve it",
            "approve kara",
            "approve kar do",
        ),
        IntentType.REJECT_QUOTE: (
            "reject",
            "reject it",
            "reject kar do",
        ),
        IntentType.SHOW_LOW_STOCK: (
            "low stock",
            "stock low",
            "stock kam",
            "कम स्टॉक",
            "कमी स्टॉक",
            "लो स्टॉक",
            "stock कमी",
            "குறைந்த stock",
            "తక్కువ stock",
            "কম stock",
            "stock ಕಡಿಮೆ",
        ),
        IntentType.SHOW_PENDING_PAYMENTS: (
            "pending payments",
            "payment pending",
            "did payment come",
            "payment aaya",
            "payment aya",
            "payment aaya kya",
            "payment आला",
            "payment झाला",
            "payment வந்த",
            "payment వచ్చ",
            "payment এসে",
            "payment ಬಂದ",
            "ಬಾಕಿ payment",
            "pending payment status",
        ),
        IntentType.IMPORTANT_UPDATES: (
            "what all stuck",
            "what needs attention",
            "important updates",
            "today summary",
            "todays summary",
            "today's summary",
            "what changed since",
            "today pending",
            "what is pending today",
            "आज pending",
            "क्या pending",
            "आज काय pending",
            "आज काय अडकलं",
            "இன்று pending",
            "இன்று என்ன என்ன pending",
            "இன்று update",
            "ఈరోజు summary",
            "ఇవాళ pending",
            "আজ pending",
            "আজ summary",
            "ಇಂದು summary",
            "ಇವತ್ತು pending",
        ),
    },
    ActorType.BUYER: {
        IntentType.REQUEST_QUOTE: (
            "quote",
            "quotation",
            "best rate",
            "best price",
            "bhav",
            "bhaav",
            "कोटेशन",
            "भाव",
            "रेट",
            "दर",
            "கோட்",
            "ధర",
            "দর",
            "ಬೆಲೆ",
        ),
        IntentType.REQUEST_ORDER: (
            "need",
            "want",
            "order",
            "book",
            "delivery",
            "deliver",
            "pickup",
            "dispatch",
            "stock available",
            "available next week",
            "today",
            "tomorrow",
            "kal",
            "sunday",
            "चाहिए",
            "चाहिये",
            "पाहिजे",
            "வேண்டும்",
            "காட்ட",
            "கிலோ",
            "కావాలి",
            "పంప",
            "চাই",
            "পাঠ",
            "ಬೇಕು",
            "ಕಳುಹ",
            "कल",
            "उद्या",
            "நாளைக்கு",
            "రేపు",
            "రేపటికి",
            "কাল",
            "কালকের",
            "ನಾಳೆ",
            "ನಾಳೆಗೆ",
        ),
        IntentType.NEGOTIATE_PRICE: (
            "kam karo",
            "thoda kam",
            "rate high",
            "better price",
            "discount",
            "final best",
            "थोड़ा कम",
            "जरा कम",
            "थोडं कमी",
            "கொஞ்சம் குறை",
            "తగ్గ",
            "একটু কম",
            "ಸ್ವಲ್ಪ ಕಡಿಮೆ",
        ),
        IntentType.ACCEPT_QUOTE: (
            "accept",
            "accepted",
            "okay send link",
            "ok send link",
            "share payment",
            "send payment",
            "done send payment",
            "confirm order",
            "proceed to payment",
            "payment link send karo",
        ),
        IntentType.CHANGE_REQUEST: (
            "change",
            "remove",
            "instead",
            "quantity to",
            "qty to",
            "revise",
            "same as last",
        ),
        IntentType.PAYMENT_CLAIM: (
            "i paid",
            "payment done",
            "done payment",
            "upi done",
            "sent payment",
            "payment kar diya",
            "पेमेंट कर दिया",
            "पेमेंट केले",
            "payment பண்ணிட்டேன்",
            "payment చేశాను",
            "payment করেছি",
            "payment ಮಾಡಿದ್ದೇನೆ",
        ),
        IntentType.REQUEST_PAYMENT_LINK: (
            "payment link",
            "send link again",
            "share link",
            "resend link",
            "send payment link",
            "dobara bhejo",
            "फिर से भेज",
            "पुन्हा पाठ",
            "மீண்டும் அனுப்பு",
            "మళ్లీ పంప",
            "আবার পাঠ",
            "ಮತ್ತೆ ಕಳಿಸಿ",
        ),
        IntentType.REQUEST_INVOICE: (
            "invoice",
            "invoice bhejo",
            "share invoice",
            "invoice pdf",
            "gst bill",
            "इनवॉइस",
            "बिल",
            "इनव्हॉइस",
            "இன்வாய்ஸ்",
            "ఇన్వాయిస్",
            "ইনভয়েস",
            "ಇನ್ವಾಯ್ಸ್",
        ),
        IntentType.DELIVERY_QUERY: (
            "delivery",
            "deliver",
            "pickup",
            "today",
            "tomorrow",
            "kal",
            "friday",
            "sunday",
            "कल",
            "उद्या",
            "நாளைக்கு",
            "ரெடி",
            "రేపు",
            "రేపటికి",
            "কাল",
            "কালকের",
            "ನಾಳೆ",
            "ನಾಳೆಗೆ",
        ),
    },
    ActorType.VENDOR: {
        IntentType.VENDOR_PRICE_REVISION: (
            "price list",
            "rate card",
            "revised rate",
            "revised rates",
            "new rate",
            "new rates",
            "effective from",
            "नया रेट",
            "नवीन रेट",
            "புதிய rate",
            "కొత్త rate",
            "নতুন rate",
            "ಹೊಸ rate",
        ),
        IntentType.VENDOR_STOCK_UPDATE: (
            "stock available",
            "available now",
            "back in stock",
            "in stock",
            "next lot",
            "ready stock",
            "स्टॉक उपलब्ध",
            "stock मध्ये",
            "stock இருக்கு",
            "stock ఉంది",
            "stock আছে",
            "stock ಇದೆ",
        ),
        IntentType.VENDOR_DELAY_NOTICE: (
            "dispatch delayed",
            "delivery delayed",
            "late dispatch",
            "delay by",
            "truck issue",
            "vehicle issue",
            "डिस्पैच लेट",
            "उशीर",
            "தாமதம்",
            "delay అయ్యింది",
            "দেরি",
            "ವಿಳಂಬ",
        ),
    },
}

INTENT_PRIORITY: dict[ActorType, tuple[IntentType, ...]] = {
    ActorType.ADMIN: (
        IntentType.SHOW_RUN,
        IntentType.SHOW_PENDING_PAYMENTS,
        IntentType.SHOW_LOW_STOCK,
        IntentType.IMPORTANT_UPDATES,
        IntentType.APPROVE_QUOTE,
        IntentType.REJECT_QUOTE,
    ),
    ActorType.BUYER: (
        IntentType.REQUEST_PAYMENT_LINK,
        IntentType.PAYMENT_CLAIM,
        IntentType.REQUEST_INVOICE,
        IntentType.ACCEPT_QUOTE,
        IntentType.NEGOTIATE_PRICE,
        IntentType.CHANGE_REQUEST,
        IntentType.REQUEST_ORDER,
        IntentType.REQUEST_QUOTE,
        IntentType.DELIVERY_QUERY,
    ),
    ActorType.VENDOR: (
        IntentType.VENDOR_PRICE_REVISION,
        IntentType.VENDOR_DELAY_NOTICE,
        IntentType.VENDOR_STOCK_UPDATE,
    ),
}

SHORT_PHRASES = {
    "quote": "quote",
    "quotation": "quote",
    "quotations": "quote",
    "qty": "quantity",
    "inv": "invoice",
    "gst inv": "gst invoice",
    "pmt": "payment",
    "paymnt": "payment",
    "txn": "transaction",
}


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    for source, target in SHORT_PHRASES.items():
        normalized = normalized.replace(source, target)
    normalized = normalized.translate(PUNCT_TRANSLATION)
    return " ".join(normalized.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = _normalize_text(phrase)
    return bool(phrase) and phrase in text


def _match_catalog(text: str, actor: ActorType) -> tuple[IntentType, str | None]:
    for intent in INTENT_PRIORITY.get(actor, tuple(PHRASE_CATALOG.get(actor, {}))):
        for phrase in PHRASE_CATALOG.get(actor, {}).get(intent, ()):
            if _contains_phrase(text, phrase):
                return intent, phrase
    return IntentType.UNKNOWN, None


def _normalize_message(state: RouteState) -> RouteState:
    return {"normalized_text": _normalize_text(state.get("text") or "")}


def _identify_actor(state: RouteState) -> RouteState:
    hint = state.get("actor_hint")
    if hint:
        return {"actor": ActorType(hint).value, "actor_source": "hint"}

    wa_id = state.get("wa_id")
    admin_wa_ids = state.get("admin_wa_ids", set())
    vendor_wa_ids = state.get("vendor_wa_ids", set())
    if wa_id and wa_id in admin_wa_ids:
        return {"actor": ActorType.ADMIN.value, "actor_source": "trusted_admin"}
    if wa_id and wa_id in vendor_wa_ids:
        return {"actor": ActorType.VENDOR.value, "actor_source": "trusted_vendor"}

    text = state.get("normalized_text", "")
    for intent in (
        IntentType.VENDOR_PRICE_REVISION,
        IntentType.VENDOR_STOCK_UPDATE,
        IntentType.VENDOR_DELAY_NOTICE,
    ):
        for phrase in PHRASE_CATALOG[ActorType.VENDOR][intent]:
            if _contains_phrase(text, phrase):
                buyer_hint, _ = _match_catalog(text, ActorType.BUYER)
                if buyer_hint in {IntentType.REQUEST_QUOTE, IntentType.REQUEST_ORDER}:
                    return {"actor": ActorType.BUYER.value, "actor_source": "lexical_buyer"}
                return {"actor": ActorType.VENDOR.value, "actor_source": "lexical_vendor"}

    if text:
        return {"actor": ActorType.BUYER.value, "actor_source": "default_buyer"}
    return {"actor": ActorType.UNKNOWN.value, "actor_source": "unknown"}


def _detect_base_intent(state: RouteState) -> RouteState:
    text = state.get("normalized_text", "")
    actor = ActorType(state.get("actor", ActorType.UNKNOWN.value))

    if actor is ActorType.ADMIN and SHOW_RUN_RE.search(text):
        return {
            "base_intent": IntentType.SHOW_RUN.value,
            "matched_rule": "show rfq",
        }

    intent, matched = _match_catalog(text, actor)
    return {
        "base_intent": intent.value,
        "matched_rule": matched,
    }


def _apply_state_guards(state: RouteState) -> RouteState:
    actor = ActorType(state.get("actor", ActorType.UNKNOWN.value))
    base_intent = IntentType(state.get("base_intent", IntentType.UNKNOWN.value))
    current_status = state.get("current_status")
    text = state.get("normalized_text", "")
    requires_exact_run_id = False

    if actor is ActorType.ADMIN:
        if base_intent in {IntentType.APPROVE_QUOTE, IntentType.REJECT_QUOTE}:
            requires_exact_run_id = True
        return {
            "allowed_intent": base_intent.value,
            "requires_exact_run_id": requires_exact_run_id,
        }

    if actor is ActorType.VENDOR:
        return {"allowed_intent": base_intent.value, "requires_exact_run_id": False}

    if current_status == RunStatus.WAITING_FOR_CLARIFICATION.value and text:
        return {
            "allowed_intent": IntentType.CLARIFICATION_REPLY.value,
            "requires_exact_run_id": False,
        }

    if base_intent is IntentType.REQUEST_PAYMENT_LINK and current_status in BUYER_ACCEPT_STATUSES:
        base_intent = IntentType.ACCEPT_QUOTE
    elif base_intent is IntentType.ACCEPT_QUOTE and current_status not in BUYER_ACCEPT_STATUSES:
        base_intent = IntentType.UNKNOWN
    elif base_intent is IntentType.PAYMENT_CLAIM and current_status not in BUYER_PAYMENT_STATUSES:
        base_intent = IntentType.UNKNOWN
    elif base_intent is IntentType.REQUEST_PAYMENT_LINK and current_status not in (
        BUYER_PAYMENT_STATUSES | BUYER_ACCEPT_STATUSES
    ):
        base_intent = IntentType.UNKNOWN
    elif base_intent is IntentType.REQUEST_INVOICE and current_status not in (
        BUYER_INVOICE_STATUSES | BUYER_PAYMENT_STATUSES
    ):
        base_intent = IntentType.UNKNOWN
    elif base_intent is IntentType.REQUEST_ORDER and not text:
        base_intent = IntentType.UNKNOWN

    return {
        "allowed_intent": base_intent.value,
        "requires_exact_run_id": False,
    }


_builder = StateGraph(RouteState)
_builder.add_node("normalize_message", _normalize_message)
_builder.add_node("identify_actor", _identify_actor)
_builder.add_node("detect_base_intent", _detect_base_intent)
_builder.add_node("apply_state_guards", _apply_state_guards)
_builder.add_edge(START, "normalize_message")
_builder.add_edge("normalize_message", "identify_actor")
_builder.add_edge("identify_actor", "detect_base_intent")
_builder.add_edge("detect_base_intent", "apply_state_guards")
_builder.add_edge("apply_state_guards", END)
_graph = _builder.compile()


def route_message(
    text: str,
    *,
    actor_hint: ActorType | None = None,
    current_status: str | None = None,
    wa_id: str | None = None,
    admin_wa_ids: set[str] | None = None,
    vendor_wa_ids: set[str] | None = None,
) -> RouteDecision:
    result = _graph.invoke(
        {
            "text": text,
            "actor_hint": actor_hint.value if actor_hint else None,
            "current_status": current_status,
            "wa_id": wa_id,
            "admin_wa_ids": admin_wa_ids or set(),
            "vendor_wa_ids": vendor_wa_ids or set(),
        }
    )
    return RouteDecision(
        actor=ActorType(result.get("actor", ActorType.UNKNOWN.value)),
        intent=IntentType(result.get("allowed_intent", IntentType.UNKNOWN.value)),
        normalized_text=result.get("normalized_text", ""),
        matched_rule=result.get("matched_rule"),
        actor_source=result.get("actor_source"),
        requires_exact_run_id=result.get("requires_exact_run_id", False),
    )
