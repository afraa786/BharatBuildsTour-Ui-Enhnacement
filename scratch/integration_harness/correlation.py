"""Cross-step identity correlation for offline and real HTTP journeys."""


class CorrelationTraceValidator:
    CORRELATED_FIELDS = (
        "business_id",
        "run_id",
        "buyer_id",
        "product_id",
        "quote_id",
        "quote_version",
        "payment_id",
        "invoice_id",
    )

    def __init__(self):
        self.trace = []

    def record_step(self, step_name: str, payload: dict):
        self.trace.append({"step": step_name, "data": payload})

    def validate(self):
        if not self.trace:
            return False, "Correlation trace is empty."

        expected = {}
        errors = []
        for event in self.trace:
            data = event["data"]
            step = event["step"]
            for field in self.CORRELATED_FIELDS:
                value = data.get(field)
                if value is None:
                    continue
                if field not in expected:
                    expected[field] = value
                elif value != expected[field]:
                    errors.append(
                        f"[{step}] {field} drift: expected {expected[field]}, got {value}"
                    )
            if step == "invoice_generated":
                if not data.get("invoice_number"):
                    errors.append("[invoice_generated] Missing invoice number")
                if not data.get("download_url"):
                    errors.append("[invoice_generated] Missing artifact download URL")

        required = {
            "business_id",
            "run_id",
            "product_id",
            "quote_id",
            "payment_id",
            "invoice_id",
        }
        for field in sorted(required - expected.keys()):
            errors.append(f"Journey never established {field}")
        if errors:
            return False, "\n".join(errors)
        return True, "Trace perfectly correlated."
