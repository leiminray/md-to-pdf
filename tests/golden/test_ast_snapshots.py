"""L1 golden: AST snapshot per fixture.

Asserts the AST produced by markdown-it-py + transformers is stable across
runs. A diff here means a parser/transformer regression.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mdpdf.markdown.parser import parse_markdown
from mdpdf.markdown.transformers import run_transformers
from mdpdf.markdown.transformers.collect_outline import collect_outline
from mdpdf.markdown.transformers.filter_metadata_blocks import filter_metadata_blocks
from mdpdf.markdown.transformers.normalize_merged_atx_headings import (
    normalize_merged_atx_headings,
)
from mdpdf.markdown.transformers.promote_toc import promote_toc
from mdpdf.markdown.transformers.strip_yaml_frontmatter import strip_yaml_frontmatter
from tests.golden.conftest import (
    BASELINES_DIR,
    assert_or_update_golden,
    discover_uat_fixtures,
)


def _ast_snapshot(source: str) -> str:
    """Return a stable, deterministic textual rendering of the AST."""
    document = parse_markdown(source)
    document = run_transformers(
        document,
        [
            strip_yaml_frontmatter,
            normalize_merged_atx_headings,
            filter_metadata_blocks,
            promote_toc,
            collect_outline,
        ],
    )
    lines: list[str] = []
    for i, node in enumerate(document.children):
        lines.append(f"[{i:03d}] {type(node).__name__}")
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(
    "fixture",
    discover_uat_fixtures(),
    ids=lambda p: p.stem,
)
def test_ast_snapshot(fixture: Path, update_golden: bool, strict_golden: bool) -> None:
    actual = _ast_snapshot(fixture.read_text(encoding="utf-8"))
    baseline = BASELINES_DIR / "ast" / f"{fixture.stem}.txt"
    assert_or_update_golden(baseline, actual, update_golden, strict=strict_golden)
