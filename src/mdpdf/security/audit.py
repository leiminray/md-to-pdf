"""User-mode JSONL audit logger.

Appends one JSON line per event to ``~/.md-to-pdf/audit.jsonl`` (default).
The file is opened only in append mode so concurrent processes do not
interleave lines (POSIX ``O_APPEND`` is atomic for writes < PIPE_BUF ≈ 4KB).

File permissions: ``0640`` (owner rw, group r). Daily rotation: if the file's
last-modified UTC day differs from today, rename to ``audit-YYYY-MM-DD.jsonl``
and start fresh. Files older than ``retain_days`` are deleted on rotation.
"""
from __future__ import annotations

import contextlib
import json
import os
import stat
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mdpdf.errors import PipelineError

_DEFAULT_RETAIN_DAYS = 90


def _resolve_default_path() -> Path:
    """Resolve audit path: MD_PDF_AUDIT_PATH env var if set, else
    ``~/.md-to-pdf/audit.jsonl``.
    """
    env_path = os.environ.get("MD_PDF_AUDIT_PATH")
    if env_path:
        return Path(env_path)
    return Path.home() / ".md-to-pdf" / "audit.jsonl"


class AuditLogger:
    """Appends structured JSONL audit events to a log file.

    Creates the file lazily on first event so an idle AuditLogger does not
    pollute the filesystem. POSIX file mode is enforced to 0o640 after each
    write (touch + chmod, since Path.touch(mode=0o640) is masked by umask).
    Windows ACL hardening is deferred to v2.3 — emits a one-shot warning.
    """

    _WIN32_WARNED: bool = False

    def __init__(
        self,
        path: Path | None = None,
        retain_days: int = _DEFAULT_RETAIN_DAYS,
    ) -> None:
        self._path = path if path is not None else _resolve_default_path()
        self._retain_days = retain_days

    def log_start(
        self,
        *,
        render_id: str,
        user: str | None,
        host_hash: str,
        brand_id: str,
        brand_version: str,
        template: str,
        input_path: Path | None,
        input_size: int,
        input_sha256: str,
        watermark_level: str,
        deterministic: bool,
        locale: str,
    ) -> None:
        self._append({
            "event": "render.start",
            "timestamp": _now_iso(),
            "render_id": render_id,
            "user": user,
            "host_hash": host_hash,
            "brand_id": brand_id,
            "brand_version": brand_version,
            "template": template,
            "input_path": str(input_path) if input_path else None,
            "input_size": input_size,
            "input_sha256": input_sha256,
            "watermark_level": watermark_level,
            "deterministic": deterministic,
            "locale": locale,
        })

    def log_complete(
        self,
        *,
        render_id: str,
        duration_ms: int,
        output_path: Path,
        output_size: int,
        output_sha256: str,
        pages: int,
        renderers_used: dict[str, str],
        warnings: list[str],
    ) -> None:
        self._append({
            "event": "render.complete",
            "timestamp": _now_iso(),
            "render_id": render_id,
            "duration_ms": duration_ms,
            "output_path": str(output_path),
            "output_size": output_size,
            "output_sha256": output_sha256,
            "pages": pages,
            "renderers_used": renderers_used,
            "warnings": warnings,
        })

    def log_error(
        self,
        *,
        render_id: str,
        duration_ms: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._append({
            "event": "render.error",
            "timestamp": _now_iso(),
            "render_id": render_id,
            "duration_ms": duration_ms,
            "code": code,
            "message": message,
            "details": details,
        })

    def rotate_if_needed(self) -> None:
        if not self._path.exists():
            return

        mtime = self._path.stat().st_mtime
        file_day = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
        today = datetime.now(tz=timezone.utc).date()

        if file_day >= today:
            return

        archive_name = self._path.parent / f"audit-{file_day.isoformat()}.jsonl"
        try:
            self._path.rename(archive_name)
        except OSError:
            return

        cutoff = today.toordinal() - self._retain_days
        for candidate in self._path.parent.glob("audit-????-??-??.jsonl"):
            try:
                date_str = candidate.stem[len("audit-"):]
                candidate_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                ).date()
                if candidate_date.toordinal() < cutoff:
                    candidate.unlink()
            except (ValueError, OSError):
                continue

    def _append(self, event: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
            self._enforce_permissions()
        except OSError as exc:
            raise PipelineError(
                code="AUDIT_LOG_WRITE_FAILED",
                user_message=f"Cannot write to audit log at {self._path}: {exc}",
                technical_details=str(exc),
            ) from exc

    def _enforce_permissions(self) -> None:
        """Re-tighten the audit file mode to 0o640 (POSIX) or warn on Windows.

        Pass-2 patch P4-017: Windows ACL hardening is deferred to v2.3; emit
        a one-shot warning instead of importing pywin32.
        """
        if sys.platform.startswith("win"):
            if not AuditLogger._WIN32_WARNED:
                warnings.warn(
                    "audit log file permissions are POSIX-only in v0.2.1; "
                    "Windows ACL hardening lands in v2.3",
                    stacklevel=3,
                )
                AuditLogger._WIN32_WARNED = True
            return
        with contextlib.suppress(OSError):
            current_mode = stat.S_IMODE(self._path.stat().st_mode)
            if current_mode != 0o640:
                os.chmod(self._path, 0o640)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
