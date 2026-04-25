"""TOC bookmark map + internal links + --watermark resolution (no full PDF)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
import sys

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import md_to_pdf  # noqa: E402


def test_collect_and_lookup_toc() -> None:
    lines = [
        "# Main Title",
        "",
        "## 目录",
        "| ColA | ColB |",
        "| --- | --- |",
        "| Section A | extra |",
        "",
        "## Section A",
        "Body.",
    ]
    m = md_to_pdf.collect_bookmark_plain_to_key(lines)
    assert m.get("Main Title")
    assert m.get("Section A")
    k = md_to_pdf.lookup_toc_row_bookmark_key(["Section A", "extra"], m)
    assert k == m["Section A"]


def test_lookup_joined_cells() -> None:
    lines = ["# T", "", "## 目录", "| x |", "| - |", "| A · B |", "", "## A · B", "x"]
    m = md_to_pdf.collect_bookmark_plain_to_key(lines)
    k = md_to_pdf.lookup_toc_row_bookmark_key(["A", "B"], m)
    assert k == m.get("A · B", m.get("A"))


def test_resolve_watermark_text_user_only_when_no_company_in_compliance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No company in compliance → watermark text is the user only (``MD_PDF_COMPANY`` ignored)."""
    monkeypatch.delenv("MD_PDF_COMPANY", raising=False)
    monkeypatch.setenv("MD_PDF_WATERMARK_USER", "u1")
    monkeypatch.setattr(md_to_pdf, "watermark_company_name", lambda _p: None)
    assert md_to_pdf.resolve_watermark_text() == "u1"


def test_resolve_watermark_text_uses_issuer_line_without_env_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from brand_pack import load_brand_pack

    md_to_pdf.set_brand_pack(
        load_brand_pack(_SCRIPTS.parent / "brand_kits"),
    )
    monkeypatch.delenv("MD_PDF_COMPANY", raising=False)
    monkeypatch.setenv("MD_PDF_WATERMARK_USER", "user1")
    out = md_to_pdf.resolve_watermark_text()
    assert out is not None
    assert "HEXCLOUD" in (out or "")
    assert out.endswith("//user1")


def test_resolve_watermark_text_prefers_compliance_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """compliance.md company wins; MD_PDF_COMPANY must not override when pack has a name."""
    from brand_pack import load_brand_pack

    md_to_pdf.set_brand_pack(load_brand_pack(_SCRIPTS.parent / "brand_kits"))
    monkeypatch.setenv("MD_PDF_COMPANY", "ACME")
    monkeypatch.setenv("MD_PDF_WATERMARK_USER", "user1")
    out = md_to_pdf.resolve_watermark_text() or ""
    assert "ACME" not in out
    assert "HEXCLOUD" in out
    assert out.endswith("//user1")


def test_resolve_watermark_text_ignores_md_pdf_company_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``MD_PDF_COMPANY`` must not feed watermark text; user-only when compliance has no company."""
    monkeypatch.setattr(md_to_pdf, "watermark_company_name", lambda _p: None)
    monkeypatch.setenv("MD_PDF_COMPANY", "ACME")
    monkeypatch.setenv("MD_PDF_WATERMARK_USER", "user1")
    assert md_to_pdf.resolve_watermark_text() == "user1"


def test_resolve_watermark_text_none_without_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from brand_pack import load_brand_pack

    md_to_pdf.set_brand_pack(load_brand_pack(_SCRIPTS.parent / "brand_kits"))
    monkeypatch.delenv("MD_PDF_WATERMARK_USER", raising=False)
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(md_to_pdf.getpass, "getuser", lambda: "")

    assert md_to_pdf.resolve_watermark_text() is None


def test_watermark_company_name_from_default_brand_kit() -> None:
    from brand_pack import load_brand_pack, watermark_company_name

    p = load_brand_pack(_SCRIPTS.parent / "brand_kits")
    w = watermark_company_name(p)
    assert w and "HEXCLOUD" in w
