class OutboxConsumerSimulator:
    def __init__(self):
        self.processed_events = set()
        self.delivered = []

    def consume(self, event_id: str, payload: dict):
        """Simulates Rehbar consuming a PaymentOutbox event."""
        # At-least-once delivery idempotency
        if event_id in self.processed_events:
            return {"status": "ignored", "reason": "duplicate"}

        self.processed_events.add(event_id)
        self.delivered.append({"event_id": event_id, "payload": payload})
        
        # Advance workflow conceptually
        return {"status": "processed", "workflow_advanced": True}
