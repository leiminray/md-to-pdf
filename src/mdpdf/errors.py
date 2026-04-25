"""Structured exception hierarchy.

See spec §7.5. CLI maps `.code` → exit code; Python API just raises.
Each `.code` will correspond to a docs page at `docs/errors/<CODE>.md`
once the error-docs directory lands (later plan).
"""
from __future__ import annotations


class MdpdfError(Exception):
    """Base for all md-to-pdf errors."""

    def __init__(
        self,
        code: str,
        user_message: str,
        technical_details: str | None = None,
        render_id: str | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.technical_details = technical_details
        self.render_id = render_id

    def __str__(self) -> str:
        return f"[{self.code}] {self.user_message}"


class BrandError(MdpdfError):
    """Brand pack resolution / validation errors.

    Codes: BRAND_NOT_FOUND, BRAND_VALIDATION_FAILED, BRAND_OVERRIDE_DENIED.
    """


class TemplateError(MdpdfError):
    """Template resolution errors. Codes: TEMPLATE_NOT_FOUND."""


class FontError(MdpdfError):
    """Font availability / licence errors.

    Codes: FONT_NOT_INSTALLED, FONT_LICENSE_MISSING.
    """


class RendererError(MdpdfError):
    """Base for content-renderer errors (Mermaid, image, code)."""


class SecurityError(MdpdfError):
    """Sandbox / safe-path violations.

    Codes: PATH_ESCAPE, REMOTE_ASSET_DENIED.
    """


class PipelineError(MdpdfError):
    """Catch-all for pipeline-orchestration errors."""
