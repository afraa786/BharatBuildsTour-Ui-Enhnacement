"""Opaque local artifact storage for demo PDF invoices."""

import hashlib
import os
import tempfile
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings


def artifact_key(business_id: UUID, invoice_id: UUID) -> str:
    return f"{business_id}/{invoice_id}.pdf"


class LocalArtifactStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().artifact_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path.suffix != ".pdf":
            raise ValueError("Invalid artifact key.")
        return path

    def write(self, key: str, content: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        checksum = hashlib.sha256(content).hexdigest()
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == checksum:
            return checksum
        descriptor, temp_name = tempfile.mkstemp(prefix=".invoice-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_name, path)
            return checksum
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def path(self, key: str) -> Path:
        return self._path(key)
