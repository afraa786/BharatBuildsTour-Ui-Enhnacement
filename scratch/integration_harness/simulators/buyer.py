class BuyerSimulator:
    def __init__(self, rehbar_sim):
        self.rehbar_sim = rehbar_sim

    def review_quote(self, quote_data: dict):
        """SIMULATED TRUSTED TEST ACTION: Buyer reviews quote"""
        # Validate quote is GENERATED before accepting
        if quote_data.get("status") != "GENERATED":
            raise ValueError(f"Buyer cannot accept quote in state {quote_data.get('status')}")
        return True

    def accept_quote(self, run_id: str, quote_id: str, quote_version: int):
        """SIMULATED TRUSTED TEST ACTION: Buyer accepts quote"""
        # Triggers the rehbar simulator to generate Acceptance Evidence
        return self.rehbar_sim.simulate_acceptance(run_id, quote_id, quote_version)
