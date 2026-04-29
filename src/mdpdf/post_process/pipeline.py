"""Post-process pipeline: 5 sequential passes applied after the render engine.

Pass order:
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

        from pathlib import Path as _Path

        brand_name: str = ""
        confidential_text: str = "Confidential"
        issuer_name: str = ""
        issuer_lines: list[str] = []
        issuer_qr: str | None = None
        icon_path: _Path | None = None
        logo_path: _Path | None = None
        brand_id: str = ""
        brand_version: str = ""
        pack_root: _Path | None = None

        if opts.brand_pack is not None:
            bp = opts.brand_pack
            brand_id = str(getattr(bp, "id", "") or "")
            brand_version = str(getattr(bp, "version", "") or "")
            brand_name = (
                getattr(getattr(bp, "identity", None), "name", "") or brand_id or ""
            )
            pack_root_raw = getattr(bp, "pack_root", None)
            if pack_root_raw is not None:
                pack_root = _Path(str(pack_root_raw))
            theme = getattr(bp, "theme", None)
            assets = getattr(theme, "assets", None) if theme is not None else None
            if assets is not None and pack_root is not None:
                icon_rel = getattr(assets, "icon", None)
                if icon_rel:
                    cand = (pack_root / str(icon_rel)).resolve()
                    if cand.exists():
                        icon_path = cand
                logo_rel = getattr(assets, "logo", None)
                if logo_rel:
                    cand = (pack_root / str(logo_rel)).resolve()
                    if cand.exists():
                        logo_path = cand
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
                    qr = getattr(issuer, "qr", None)
                    if qr is not None:
                        issuer_qr = getattr(qr, "value", None)

        if issuer_name:
            apply_issuer_card(
                pdf_path,
                issuer_name=issuer_name,
                issuer_lines=issuer_lines,
                icon_path=icon_path,
                qr_payload=issuer_qr,
            )

        apply_footer(
            pdf_path,
            brand_name=brand_name,
            confidential_text=confidential_text,
            locale=opts.locale,
            logo_path=logo_path,
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
