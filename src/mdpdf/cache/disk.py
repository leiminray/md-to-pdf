"""sha256-keyed on-disk cache for renderer outputs (spec §2.1.4)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from mdpdf.cache.tempfiles import atomic_write


@dataclass
class DiskCache:
    """Maps an arbitrary string key to a cached file under `root`."""

    root: Path
    suffix: str

    def path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}{self.suffix}"

    def get(self, key: str) -> Path | None:
        p = self.path_for(key)
        return p if p.exists() else None

    def put(self, key: str, payload: bytes) -> Path:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        with atomic_write(p) as fp:
            fp.write(payload)
        return p

    def clear(self) -> None:
        if not self.root.is_dir():
            return
        for child in self.root.iterdir():
            if child.is_file():
                child.unlink()
