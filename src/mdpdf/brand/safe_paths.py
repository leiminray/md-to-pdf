"""Path-sandbox utilities (spec §3, §5.4).

`safe_join(root, path)` resolves `path` (relative to `root`) and verifies
the resolved real path stays inside `root`. Rejects:
- `../` traversal
- absolute paths outside `root`
- `file://` URLs
- `http(s)://` URLs (unless `--allow-remote-assets`, not yet wired)
- symlinks pointing outside `root`
"""
from __future__ import annotations

from pathlib import Path

from mdpdf.errors import SecurityError


def safe_join(root: Path, target: str) -> Path:
    """Resolve `target` against `root` and confirm it stays inside.

    Raises `SecurityError` (code `PATH_ESCAPE` or `REMOTE_ASSET_DENIED`)
    on violation.
    """
    if target.startswith(("http://", "https://")):
        raise SecurityError(
            code="REMOTE_ASSET_DENIED",
            user_message=f"remote URL not allowed: {target}",
        )
    if target.startswith("file://"):
        raise SecurityError(
            code="PATH_ESCAPE",
            user_message=f"file:// URL not allowed: {target}",
        )

    root_resolved = Path(root).resolve()
    if Path(target).is_absolute():
        candidate = Path(target).resolve()
    else:
        candidate = (root_resolved / target).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise SecurityError(
            code="PATH_ESCAPE",
            user_message=f"path resolves outside brand root: {target}",
            technical_details=f"resolved to {candidate}, root is {root_resolved}",
        ) from e
    return candidate
