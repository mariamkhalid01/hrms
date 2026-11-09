"""UUID-scoped local storage with atomic JSON commits and per-dataset locks."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from threading import Lock, RLock
from uuid import UUID, uuid4

from app.services.ingestion.errors import DatasetError


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            value.update(chunk)
    return value.hexdigest()


class DatasetStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._locks: dict[str, RLock] = {}
        self._locks_guard = Lock()

    def path(self, dataset_id: str) -> Path:
        try:
            identifier = str(UUID(dataset_id))
        except ValueError as exc:
            raise DatasetError(404, "DATASET_NOT_FOUND", "The dataset was not found.") from exc
        return self.root / identifier

    def lock(self, dataset_id: str) -> RLock:
        with self._locks_guard:
            return self._locks.setdefault(dataset_id, RLock())

    def create(self) -> tuple[str, Path]:
        identifier = str(uuid4())
        path = self.path(identifier)
        path.mkdir(parents=True, exist_ok=False)
        return identifier, path

    def discard(self, dataset_id: str) -> None:
        path = self.path(dataset_id)
        if path.parent != self.root:
            raise RuntimeError("Invalid dataset directory")
        shutil.rmtree(path, ignore_errors=True)
        with self._locks_guard:
            self._locks.pop(dataset_id, None)

    def read(self, dataset_id: str, filename: str = "metadata.json") -> dict:
        path = self.path(dataset_id) / filename
        if not path.is_file():
            raise DatasetError(404, "DATASET_NOT_FOUND", "The dataset was not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, dataset_id: str, filename: str, value: dict) -> None:
        folder = self.path(dataset_id)
        temporary = folder / f".{filename}.{uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as target:
                json.dump(value, target, ensure_ascii=False, allow_nan=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, folder / filename)
        finally:
            temporary.unlink(missing_ok=True)
