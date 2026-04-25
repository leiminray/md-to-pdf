"""Atomic file writes and managed temporary directories (spec §2.1.7, §5.6).

`atomic_write(target)` writes to `target.tmp.<random>` and renames on
successful close, guaranteeing readers never see a partial PDF.

`TempContext` is a context manager that creates a temp directory under
`tmpfs` (or system tmp) and removes it on success **and** exception.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO


@contextmanager
def atomic_write(target: Path) -> Iterator[IO[bytes]]:
    """Open a file for binary write, finalising via atomic rename.

    On exception, the partial file is removed and the original (if any) is
    untouched.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = secrets.token_hex(8)
    tmp_path = target.with_suffix(target.suffix + f".tmp.{suffix}")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            yield f
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
        raise


def _tmpfs_root() -> Path:
    """Prefer tmpfs (`/dev/shm` on Linux) when available; else fall back to system tmp."""
    if sys.platform == "linux":
        shm = Path("/dev/shm")  # noqa: S108  # deliberate Linux tmpfs choice, not insecure-temp
        if shm.is_dir() and os.access(shm, os.W_OK):
            return shm
    return Path(tempfile.gettempdir())


@dataclass
class TempContext:
    """Managed temp directory, cleaned on exit (success and exception).

    Naming convention: `mdpdf-tmp-<prefix><random>`. The `atexit` orphan
    sweeper (added later in this plan via Pipeline) targets this prefix.
    """

    prefix: str = "mdpdf-tmp-"
    path: Path = Path("/uninitialised")

    def __enter__(self) -> TempContext:
        root = _tmpfs_root()
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=root))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
