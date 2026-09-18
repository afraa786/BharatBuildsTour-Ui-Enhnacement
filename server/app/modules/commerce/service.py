import logging
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.commerce.tools import build_commerce_tools
from app.modules.identity.service import resolve_or_create_whatsapp_buyer
from app.modules.runs.conversation_graph import load_conversation_history
from app.modules.runs.service import OutboundMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful and competent salesperson for StockAware/BharatBuilds. "
    "You understand Hinglish naturally (e.g. 'bhai wire chahiye', 'stock?'). "
    "Use your tools to search the real catalog and check real inventory. "
    "DO NOT hallucinate prices, stock, GST, SKUs, availability, or any product attributes. "
    "If a customer asks for a product, search the catalog. "
    "If they ask for stock, check the inventory using the product ID. "
    "Keep responses concise and conversational."
)


def process_customer_commerce_message(
    db: Session,
    business_id: UUID,
    phone_number_id: str,
    wa_id: str,
    text_body: str,
) -> list[OutboundMessage]:
    """
    Entry point for real catalog/inventory commerce.
    Isolated from legacy RFQ mock_desks.
    """
    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None

    # Task 2: Resolve or Create Buyer Lead
    resolve_or_create_whatsapp_buyer(db, business_id, wa_id)

    # Task 11: Conversational sales behavior
    fallback_msg = "Sorry, I am having trouble connecting to the catalog right now."
    if not api_key:
        return [OutboundMessage(wa_id, fallback_msg)]

    try:
        # Load conversation history scoped by wa_id and phone_number_id
        history = load_conversation_history(db, wa_id, phone_number_id, business_id=business_id)
        # The transport persists inbound before dispatch; avoid presenting the
        # current user turn twice while retaining all prior identical turns.
        if history and history[-1] == {"role": "user", "content": text_body}:
            history = history[:-1]

        lc_history = [
            HumanMessage(content=turn["content"])
            if turn["role"] == "user"
            else AIMessage(content=turn["content"])
            for turn in history
        ]

        # Build tools scoped strictly to the business_id
        tools = build_commerce_tools(db, business_id)

        # Invoke agent
        model = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.3)
        agent = create_react_agent(model, tools, prompt=_SYSTEM_PROMPT)

        result = agent.invoke({"messages": [*lc_history, HumanMessage(content=text_body)]})
        final_message = result["messages"][-1]
        text = (final_message.content or "").strip()

        return [OutboundMessage(wa_id, text or fallback_msg)]
    except Exception:
        logger.exception("Commerce agent call failed")
        return [OutboundMessage(wa_id, fallback_msg)]
