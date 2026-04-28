"""Mermaid renderer chain selector.

Auto-selection order:
  1. KROKI_URL env (or --kroki-url override) → Kroki
  2. mmdc on PATH → Puppeteer
  3. mermaid-py installed → pure
  4. Else → MERMAID_RENDERER_UNAVAILABLE
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from mdpdf.errors import RendererError
from mdpdf.renderers import mermaid_puppeteer, mermaid_pure
from mdpdf.renderers.base import RenderContext, Renderer
from mdpdf.renderers.mermaid_kroki import KrokiMermaidRenderer
from mdpdf.renderers.mermaid_puppeteer import PuppeteerMermaidRenderer
from mdpdf.renderers.mermaid_pure import PureMermaidRenderer

Preference = Literal["auto", "kroki", "puppeteer", "pure"]


def select_mermaid_renderer(
    *,
    preference: Preference,
    ctx: RenderContext,
    kroki_url_override: str | None = None,
) -> Renderer[str, Path]:
    kroki_url = kroki_url_override or os.environ.get("KROKI_URL")

    if preference == "kroki":
        if not kroki_url:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message="--mermaid-renderer kroki requires KROKI_URL or --kroki-url",
            )
        return KrokiMermaidRenderer(base_url=kroki_url)

    if preference == "puppeteer":
        if mermaid_puppeteer._find_mmdc() is None:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message="mmdc not found on PATH",
            )
        return PuppeteerMermaidRenderer()

    if preference == "pure":
        if ctx.deterministic:
            raise RendererError(
                code="RENDERER_NON_DETERMINISTIC",
                user_message="--mermaid-renderer pure rejected in --deterministic mode",
            )
        return PureMermaidRenderer()

    # auto
    if kroki_url:
        return KrokiMermaidRenderer(base_url=kroki_url)
    if mermaid_puppeteer._find_mmdc() is not None:
        return PuppeteerMermaidRenderer()
    if mermaid_pure._import_mermaid() is not None and not ctx.deterministic:
        return PureMermaidRenderer()
    # If deterministic mode excluded the only available renderer, raise the
    # determinism-specific error so the message points at the right fix
    # rather than suggesting "install mmdc" (P4-015 pass-2 patch).
    if ctx.deterministic and mermaid_pure._import_mermaid() is not None:
        raise RendererError(
            code="RENDERER_NON_DETERMINISTIC",
            user_message=(
                "deterministic mode requires a deterministic mermaid renderer "
                "(kroki or puppeteer); install one or drop --deterministic"
            ),
        )
    raise RendererError(
        code="MERMAID_RENDERER_UNAVAILABLE",
        user_message=(
            "no mermaid renderer available. Install one of: "
            "(a) set KROKI_URL or --kroki-url, "
            "(b) install mmdc via npm, "
            "(c) install md-to-pdf[mermaid-pure]"
        ),
    )
