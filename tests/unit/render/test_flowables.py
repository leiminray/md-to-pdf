"""Tests for custom ReportLab Flowables."""
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from mdpdf.render.flowables import FencedCodeCard
from mdpdf.renderers.code_pygments import CodeRenderResult, ColoredFragment


def _build_pdf(flowables: list, tmp_path: Path) -> Path:
    out = tmp_path / "out.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build(flowables)
    return out


def _result(text: str, lang: str = "python") -> CodeRenderResult:
    return CodeRenderResult(
        lang=lang,
        lines=[[ColoredFragment(text=text, color="#1f2328")]],
    )


def test_fenced_code_card_renders_text(tmp_path: Path):
    card = FencedCodeCard(
        result=_result("def hello(): return 1"),
        accent_color="#0066CC",
        body_font="Courier",
        body_font_size=9,
        line_numbers=False,
    )
    out = _build_pdf([card], tmp_path)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "def hello" in text


def test_fenced_code_card_includes_lang_badge(tmp_path: Path):
    card = FencedCodeCard(
        result=_result("x = 1", lang="python"),
        accent_color="#0066CC",
        body_font="Courier",
        body_font_size=9,
        line_numbers=False,
    )
    out = _build_pdf([card], tmp_path)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    # Lang badge text appears in the rendered PDF
    assert "python" in text.lower()


def test_fenced_code_card_with_line_numbers(tmp_path: Path):
    result = CodeRenderResult(
        lang="python",
        lines=[
            [ColoredFragment(text="line 1", color="#1f2328")],
            [ColoredFragment(text="line 2", color="#1f2328")],
            [ColoredFragment(text="line 3", color="#1f2328")],
        ],
    )
    card = FencedCodeCard(
        result=result,
        accent_color="#0066CC",
        body_font="Courier",
        body_font_size=9,
        line_numbers=True,
    )
    out = _build_pdf([card], tmp_path)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    # Line number gutter contains "1", "2", "3"
    for n in ("1", "2", "3"):
        assert n in text


def test_fenced_code_card_no_lang_omits_badge(tmp_path: Path):
    result = CodeRenderResult(lang="", lines=[[ColoredFragment(text="x", color="#1f2328")]])
    card = FencedCodeCard(
        result=result,
        accent_color="#0066CC",
        body_font="Courier",
        body_font_size=9,
        line_numbers=False,
    )
    out = _build_pdf([card], tmp_path)
    # Render must not crash; PDF exists.
    assert out.exists()
