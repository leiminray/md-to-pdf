"""Tests for post_process.pipeline — orchestrated post-process passes.

Per pass-2 patch P4-013: mock targets use the renamed callees
``apply_l1_watermark`` and ``apply_l2_xmp`` (not the fabricated
``apply_watermark`` / ``inject_xmp``); ``WatermarkOptions`` is imported from
``mdpdf.pipeline``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mdpdf.pipeline import WatermarkOptions
from mdpdf.post_process.pipeline import PostProcessOptions, PostProcessPipeline


def _make_pdf(tmp_path: Path, num_pages: int = 3) -> Path:
    out = tmp_path / "source.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    for i in range(num_pages):
        c.drawString(72, 700, f"Page {i + 1}")
        c.showPage()
    c.save()
    return out


def _default_opts(
    *, deterministic: bool = False, watermark_level: str = "L1+L2"
) -> PostProcessOptions:
    return PostProcessOptions(
        brand_pack=None,
        watermark=WatermarkOptions(user="test@example.com", level=watermark_level),
        render_id="test-render-id-001",
        render_user="test@example.com",
        render_date="2026-04-27",
        render_host_hash="abc123",
        input_hash="def456",
        document_title="Test Document",
        locale="en",
        deterministic=deterministic,
        source_date_epoch=None,
    )


class TestPostProcessPipelineHappyPath:
    def test_run_returns_non_negative_ms(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        elapsed = pipeline.run(pdf, _default_opts())
        assert elapsed >= 0

    def test_run_modifies_pdf_in_place(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        pipeline.run(pdf, _default_opts())
        assert pdf.stat().st_size > 0

    def test_run_with_brand_pack_none(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        pipeline.run(pdf, _default_opts())  # should not raise


class TestPostProcessPipelineWatermarkLevels:
    def test_l0_skips_l1_and_l2(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        opts = _default_opts(watermark_level="L0")

        with (
            patch("mdpdf.post_process.pipeline.apply_l1_watermark") as mock_l1,
            patch("mdpdf.post_process.pipeline.apply_l2_xmp") as mock_l2,
        ):
            pipeline.run(pdf, opts)
            mock_l1.assert_not_called()
            mock_l2.assert_not_called()

    def test_l1_plus_l2_runs_both(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        opts = _default_opts(watermark_level="L1+L2")

        with (
            patch("mdpdf.post_process.pipeline.apply_l1_watermark") as mock_l1,
            patch("mdpdf.post_process.pipeline.apply_l2_xmp") as mock_l2,
        ):
            pipeline.run(pdf, opts)
            mock_l1.assert_called_once()
            mock_l2.assert_called_once()

    def test_l2_only_runs_xmp_only(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        opts = _default_opts(watermark_level="L2")

        with (
            patch("mdpdf.post_process.pipeline.apply_l1_watermark") as mock_l1,
            patch("mdpdf.post_process.pipeline.apply_l2_xmp") as mock_l2,
        ):
            pipeline.run(pdf, opts)
            mock_l1.assert_not_called()
            mock_l2.assert_called_once()


class TestPostProcessPipelineDeterministic:
    def test_deterministic_triggers_date_freeze(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        opts = _default_opts(deterministic=True)

        with patch("mdpdf.post_process.pipeline.freeze_pdf_dates") as mock_freeze:
            pipeline.run(pdf, opts)
            mock_freeze.assert_called_once()

    def test_non_deterministic_skips_date_freeze(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path)
        pipeline = PostProcessPipeline()
        opts = _default_opts(deterministic=False)

        with patch("mdpdf.post_process.pipeline.freeze_pdf_dates") as mock_freeze:
            pipeline.run(pdf, opts)
            mock_freeze.assert_not_called()
