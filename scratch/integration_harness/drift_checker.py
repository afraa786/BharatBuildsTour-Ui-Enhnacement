"""Small OpenAPI contract checker for the commercial HTTP acceptance client."""

from typing import Any

COMMERCIAL_OPERATIONS = {
    ("/catalog/match", "post"),
    ("/inventory/check", "post"),
    ("/pricing/quote", "post"),
    ("/payments/create-link", "post"),
    ("/invoice/generate", "post"),
}


class DriftChecker:
    @staticmethod
    def _resolve(openapi: dict, schema: dict | None) -> dict:
        if not schema:
            return {}
        reference = schema.get("$ref")
        if reference:
            node: Any = openapi
            for part in reference.removeprefix("#/").split("/"):
                node = node[part]
            return node
        return schema

    def request_contract(
        self, openapi: dict, path: str, method: str
    ) -> dict[str, set[str]]:
        operation = openapi["paths"][path][method.lower()]
        content = operation.get("requestBody", {}).get("content", {})
        schema = self._resolve(
            openapi, content.get("application/json", {}).get("schema")
        )
        return {
            "fields": set(schema.get("properties", {})),
            "required": set(schema.get("required", [])),
        }

    def response_fields(
        self, openapi: dict, path: str, method: str, status: str = "200"
    ) -> set[str]:
        operation = openapi["paths"][path][method.lower()]
        content = operation.get("responses", {}).get(status, {}).get("content", {})
        schema = self._resolve(
            openapi, content.get("application/json", {}).get("schema")
        )
        if schema.get("type") == "array":
            schema = self._resolve(openapi, schema.get("items"))
        return set(schema.get("properties", {}))

    def validate_request(
        self, openapi: dict, path: str, method: str, payload: dict
    ) -> list[str]:
        try:
            contract = self.request_contract(openapi, path, method)
        except KeyError:
            return [f"Missing OpenAPI operation: {method.upper()} {path}"]
        supplied = set(payload)
        missing = contract["required"] - supplied
        unknown = supplied - contract["fields"]
        errors = [
            f"Missing required field {field} for {method.upper()} {path}"
            for field in sorted(missing)
        ]
        errors.extend(
            f"Unknown field {field} for {method.upper()} {path}"
            for field in sorted(unknown)
        )
        return errors

    def capture_normalized_schema(self, openapi: dict) -> dict:
        normalized = {}
        for path, method in sorted(COMMERCIAL_OPERATIONS):
            if (
                path not in openapi.get("paths", {})
                or method not in openapi["paths"][path]
            ):
                continue
            normalized[f"{method.upper()} {path}"] = {
                "request": self.request_contract(openapi, path, method),
                "response": self.response_fields(openapi, path, method),
            }
        return normalized

    def compare(self, current_openapi: dict, baseline: dict) -> list[str]:
        current = self.capture_normalized_schema(current_openapi)
        expected = self.capture_normalized_schema(baseline)
        drifts = []
        for operation, contract in expected.items():
            if operation not in current:
                drifts.append(f"Missing operation: {operation}")
                continue
            if contract != current[operation]:
                drifts.append(f"Commercial schema changed: {operation}")
        return drifts
