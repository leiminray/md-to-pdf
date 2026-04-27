"""Post-process pipeline: 5 sequential passes applied after the render engine.

Pass order (per spec §2.1.6):
  1. Issuer card  — last page only
  2. Footer       — all pages
  3. L1 watermark — diagonal visible stamp (skipped when level == "L0" or "L2")
  4. L2 XMP       — metadata injection (skipped when level == "L0")
  5. Date freeze  — only when deterministic=True or source_date_epoch is set

P4-001 + P4-013: imports use the real module names (watermark_l1, watermark_l2)
and `WatermarkOptions` comes from `mdpdf.pipeline`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from mdpdf.pipeline import WatermarkOptions
from mdpdf.post_process.footer import apply_footer
from mdpdf.post_process.issuer_card import apply_issuer_card
from mdpdf.security.deterministic import freeze_pdf_dates
from mdpdf.security.watermark_l1 import apply_l1_watermark
from mdpdf.security.watermark_l2 import apply_l2_xmp


@dataclass(frozen=True)
class PostProcessOptions:
    """All options required by the post-process pipeline."""

    brand_pack: object  # BrandPack | None — typed loosely to avoid circular import
    watermark: WatermarkOptions
    render_id: str
    render_user: str | None
    render_date: str
    render_host_hash: str
    input_hash: str
    document_title: str
    locale: str
    deterministic: bool
    source_date_epoch: int | None


class PostProcessPipeline:
    """Run the 5 post-process passes sequentially on a rendered PDF."""

    def run(self, pdf_path: Path, opts: PostProcessOptions) -> int:
        """Apply post-process passes to *pdf_path* (in-place); returns elapsed ms."""
        t_start = time.perf_counter()

        brand_name: str = ""
        confidential_text: str = "Confidential"
        issuer_name: str = ""
        issuer_lines: list[str] = []
        brand_id: str = ""
        brand_version: str = ""

        if opts.brand_pack is not None:
            bp = opts.brand_pack
            brand_id = str(getattr(bp, "id", "") or "")
            brand_version = str(getattr(bp, "version", "") or "")
            brand_name = (
                getattr(getattr(bp, "identity", None), "name", "") or brand_id or ""
            )
            compliance = getattr(bp, "compliance", None)
            if compliance is not None:
                confidential_text = (
                    getattr(compliance, "confidential_text", "Confidential")
                    or "Confidential"
                )
                issuer = getattr(compliance, "issuer", None)
                if issuer is not None:
                    issuer_name = getattr(issuer, "name", "") or ""
                    issuer_lines = list(getattr(issuer, "lines", []) or [])

        if issuer_name:
            apply_issuer_card(pdf_path, issuer_name=issuer_name, issuer_lines=issuer_lines)

        apply_footer(
            pdf_path,
            brand_name=brand_name,
            confidential_text=confidential_text,
            locale=opts.locale,
        )

        if opts.watermark.level != "L0":
            if opts.watermark.level in ("L1", "L1+L2"):
                apply_l1_watermark(
                    pdf_path,
                    brand_name=brand_name or "Document",
                    user=opts.render_user or "unknown",
                    render_date=opts.render_date,
                    template=opts.watermark.custom_text
                    or "{brand_name} // {user} // {render_date}",
                )
            apply_l2_xmp(
                pdf_path,
                dc_creator=brand_name,
                dc_title=opts.document_title,
                render_id=opts.render_id,
                render_user=opts.render_user or "",
                render_host=opts.render_host_hash,
                brand_id=brand_id,
                brand_version=brand_version,
                input_hash=opts.input_hash,
                create_date=opts.render_date,
                watermark_level=opts.watermark.level,
            )

        if opts.deterministic or opts.source_date_epoch is not None:
            epoch = opts.source_date_epoch if opts.source_date_epoch is not None else 0
            freeze_pdf_dates(pdf_path, epoch=epoch)

        return int((time.perf_counter() - t_start) * 1000)
