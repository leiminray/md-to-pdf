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
    """Renderer (Mermaid, image, code) errors.

    Codes:
    - MERMAID_TIMEOUT — kroki / mmdc / pure took longer than 30s
    - MERMAID_INVALID_SYNTAX — sandbox rejected the source (XSS pattern)
    - MERMAID_RESOURCE_LIMIT — source too large, too many nodes, too deep, or output > 10MB
    - MERMAID_RENDERER_UNAVAILABLE — neither kroki, mmdc, nor mermaid-py is reachable
    - RENDERER_NON_DETERMINISTIC — pure-Python mermaid renderer used in --deterministic mode
    - IMAGE_RENDERER_UNAVAILABLE — cairosvg / libcairo missing for SVG rasterisation
    """


class SecurityError(MdpdfError):
    """Sandbox / safe-path violations and watermark policy errors.

    Codes: PATH_ESCAPE, REMOTE_ASSET_DENIED, WATERMARK_DENIED,
    WATERMARK_CONTRAST_TOO_LOW.
    """


class PipelineError(MdpdfError):
    """Catch-all for pipeline-orchestration errors.

    Codes: AUDIT_LOG_WRITE_FAILED, DETERMINISTIC_VIOLATION.
    """
