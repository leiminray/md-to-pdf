"""Pipeline contracts (RenderRequest, RenderResult, RenderMetrics).

See spec §2.1.1, §2.1.7. The Pipeline class itself is added in Task 11;
this file ships the dataclasses first so other modules can import them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class WatermarkOptions:
    """Watermark configuration (Plan 1: stored only; applied in Plan 4).

    `level` is a literal string per spec §2.4 — values: 'L0', 'L1', 'L1+L2'.
    L3-L5 land in v2.3.
    """

    user: str | None = None
    level: Literal["L0", "L1", "L1+L2"] = "L1+L2"
    custom_text: str | None = None


@dataclass(frozen=True)
class RenderRequest:
    """Unified input contract for CLI and Python API (spec §2.1.1)."""

    source: str | Path
    source_type: Literal["content", "path"]
    output: Path
    brand: str | dict[str, Any] | None = None
    brand_overrides: dict[str, Any] = field(default_factory=dict)
    template: str = "generic"
    watermark: WatermarkOptions = field(default_factory=WatermarkOptions)
    deterministic: bool = False
    locale: str = "en"
    audit_enabled: bool = True


@dataclass(frozen=True)
class RenderMetrics:
    """Per-phase timing in milliseconds (spec §2.1.7)."""

    parse_ms: int
    asset_resolve_ms: int
    render_ms: int
    post_process_ms: int
    total_ms: int


@dataclass(frozen=True)
class RenderResult:
    """Pipeline.render() return value (spec §2.1.7)."""

    output_path: Path
    render_id: str
    pages: int
    bytes: int
    sha256: str
    warnings: list[str]
    metrics: RenderMetrics
