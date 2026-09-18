import uuid
from typing import Dict, Optional, Any

class RehbarSimulator:
    def __init__(self, commercial_client=None):
        self.client = commercial_client
        self.state = {}

    def start_rfq(self, business_id: str, buyer_id: str, run_id: Optional[str] = None):
        if not run_id:
            run_id = f"RFQ-{uuid.uuid4().hex[:8]}"
        self.state[run_id] = {
            "business_id": business_id,
            "buyer_id": buyer_id,
            "quote_id": None,
            "quote_version": None,
            "approval_id": None,
            "acceptance_id": None,
            "payment_id": None
        }
        return run_id

    def simulate_approval(self, run_id: str, quote_id: str, quote_version: int, decision: str = "APPROVED"):
        """Generates approval evidence per Phase 3 contract."""
        run_data = self.state[run_id]
        approval_id = f"APP-{uuid.uuid4().hex[:8]}"
        
        evidence = {
            "business_id": run_data["business_id"],
            "run_id": run_id,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "approval_id": approval_id,
            "action_id": "approve_quote",
            "actor_id": "admin_actor_1",
            "decision": decision,
            "timestamp": "2026-09-18T10:00:00Z"
        }
        
        # In a real environment, Rehbar calls a Fareed adapter endpoint.
        # But per the prompt: "If no HTTP transport exists yet: DO NOT invent one... create an adapter interface with NOT_IMPLEMENTED_TRANSPORT"
        if self.client:
            try:
                self.client.apply_approval(
                    business_id=run_data["business_id"],
                    run_id=run_id,
                    quote_id=quote_id,
                    quote_version=quote_version,
                    approval_id=approval_id
                )
            except NotImplementedError:
                # Production transport deferred
                pass
                
        run_data["approval_id"] = approval_id
        return evidence

    def simulate_acceptance(self, run_id: str, quote_id: str, quote_version: int):
        """Generates buyer acceptance evidence."""
        run_data = self.state[run_id]
        acceptance_id = f"ACC-{uuid.uuid4().hex[:8]}"
        
        evidence = {
            "business_id": run_data["business_id"],
            "run_id": run_id,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "acceptance_id": acceptance_id,
            "actor_id": run_data["buyer_id"],
            "channel": "whatsapp",
            "timestamp": "2026-09-18T10:05:00Z"
        }
        
        if self.client:
            try:
                self.client.apply_acceptance(
                    business_id=run_data["business_id"],
                    run_id=run_id,
                    quote_id=quote_id,
                    quote_version=quote_version,
                    acceptance_id=acceptance_id
                )
            except NotImplementedError:
                pass
                
        run_data["acceptance_id"] = acceptance_id
        return evidence
