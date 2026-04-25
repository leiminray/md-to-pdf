"""Tests for the RenderEngine ABC (spec §1.3, §2.1.5)."""
from pathlib import Path

import pytest

from mdpdf.markdown.ast import Document
from mdpdf.render.engine_base import RenderEngine


class _Fake(RenderEngine):
    name = "fake"

    def render(self, document: Document, output: Path) -> int:
        output.write_bytes(b"%PDF-1.4 fake\n%%EOF\n")
        return 1


def test_engine_must_implement_render():
    with pytest.raises(TypeError):
        RenderEngine()  # type: ignore[abstract]


def test_engine_subclass_can_render(tmp_path):
    engine = _Fake()
    out = tmp_path / "x.pdf"
    pages = engine.render(Document(children=[]), out)
    assert pages == 1
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
