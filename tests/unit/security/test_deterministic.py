"""Tests for security.deterministic — determinism helpers."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import pikepdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.security.deterministic import (
    derive_render_id,
    freeze_pdf_dates,
    frozen_create_date,
    serialise_options,
)


def _make_test_pdf(path: Path) -> None:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 700, "Determinism test")
    c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


# ── derive_render_id ────────────────────────────────────────────────────────


def test_derive_render_id_stable() -> None:
    rid1 = derive_render_id(
        input_bytes=b"hello world",
        brand_id="acme",
        brand_version="1.0",
        options_serialised='{"template":"generic"}',
        watermark_user="alice",
    )
    rid2 = derive_render_id(
        input_bytes=b"hello world",
        brand_id="acme",
        brand_version="1.0",
        options_serialised='{"template":"generic"}',
        watermark_user="alice",
    )
    assert rid1 == rid2


def test_derive_render_id_uuid_shaped() -> None:
    rid = derive_render_id(
        input_bytes=b"test",
        brand_id="b",
        brand_version="1",
        options_serialised="{}",
        watermark_user=None,
    )
    parts = rid.split("-")
    assert len(parts) == 5
    assert len(parts[0]) == 8
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    assert len(parts[4]) == 12
    assert all(c in "0123456789abcdef" for p in parts for c in p)


def test_derive_render_id_differs_on_input_change() -> None:
    base: dict[str, Any] = {
        "brand_id": "a",
        "brand_version": "1",
        "options_serialised": "{}",
        "watermark_user": None,
    }
    rid1 = derive_render_id(input_bytes=b"aaa", **base)
    rid2 = derive_render_id(input_bytes=b"bbb", **base)
    assert rid1 != rid2


def test_derive_render_id_differs_on_user_change() -> None:
    base: dict[str, Any] = {
        "input_bytes": b"x",
        "brand_id": "a",
        "brand_version": "1",
        "options_serialised": "{}",
    }
    rid1 = derive_render_id(watermark_user="alice", **base)
    rid2 = derive_render_id(watermark_user="bob", **base)
    assert rid1 != rid2


# ── serialise_options ────────────────────────────────────────────────────────


def test_serialise_options_is_sorted_json() -> None:
    opts = serialise_options(
        template="generic",
        locale="en",
        watermark_level="L1+L2",
        watermark_custom_text=None,
        brand_overrides={"fonts.body": "Helvetica", "colors.accent": "#FF0000"},
    )
    parsed = json.loads(opts)
    assert parsed["template"] == "generic"
    assert parsed["locale"] == "en"
    assert parsed["brand_overrides"] == [
        ["colors.accent", "#FF0000"],
        ["fonts.body", "Helvetica"],
    ]


def test_serialise_options_deterministic_regardless_of_dict_order() -> None:
    opts1 = serialise_options(
        template="generic",
        locale="en",
        watermark_level="L1+L2",
        watermark_custom_text=None,
        brand_overrides={"b": "2", "a": "1"},
    )
    opts2 = serialise_options(
        template="generic",
        locale="en",
        watermark_level="L1+L2",
        watermark_custom_text=None,
        brand_overrides={"a": "1", "b": "2"},
    )
    assert opts1 == opts2


# ── frozen_create_date ──────────────────────────────────────────────────────


def test_frozen_create_date_from_epoch() -> None:
    result = frozen_create_date(epoch=0)
    assert result == "1970-01-01T00:00:00+00:00"


def test_frozen_create_date_known_epoch() -> None:
    result = frozen_create_date(epoch=1700000000)
    assert result.startswith("2023-11-14T")
    assert result.endswith("+00:00")


def test_frozen_create_date_none_returns_current() -> None:
    result = frozen_create_date(epoch=None)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result)


# ── freeze_pdf_dates ────────────────────────────────────────────────────────


def test_freeze_pdf_dates_sets_creation_and_mod_date(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    freeze_pdf_dates(pdf_path, epoch=0)

    with pikepdf.open(str(pdf_path)) as pdf:
        creation = str(pdf.docinfo.get("/CreationDate", ""))
        mod = str(pdf.docinfo.get("/ModDate", ""))

    assert creation.startswith("D:19700101")
    assert mod.startswith("D:19700101")


def test_freeze_pdf_dates_known_epoch(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    freeze_pdf_dates(pdf_path, epoch=1700000000)

    with pikepdf.open(str(pdf_path)) as pdf:
        creation = str(pdf.docinfo.get("/CreationDate", ""))

    assert "20231114" in creation
