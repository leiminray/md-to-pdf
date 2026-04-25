"""Mermaid caption text: YAML title vs ATX heading above fence (no i18n placeholder)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import md_to_pdf  # noqa: E402


def test_extract_mermaid_frontmatter_title() -> None:
    src = """---
title: 方案二：测试
---
flowchart TB
  A --> B
"""
    assert md_to_pdf.extract_mermaid_frontmatter_title(src) == "方案二：测试"


def test_find_preceding_atx_heading() -> None:
    lines = [
        "# Doc",
        "",
        "#### 方案一：abc",
        "",
        "```mermaid",
        "flowchart TB",
    ]
    idx = 4  # ```mermaid
    t = md_to_pdf.find_preceding_atx_heading_for_fence(lines, idx)
    assert t == "方案一：abc"


def test_resolve_mermaid_caption_yaml_wins() -> None:
    lines = ["#### 节标题A", "", "```mermaid", "x", "```"]
    src = '---\ntitle: YAML 标题\n---\nflowchart TB\n  A--x'
    t = md_to_pdf.resolve_mermaid_caption_text(lines, 2, src)
    assert t == "YAML 标题"


def test_resolve_mermaid_caption_heading_only() -> None:
    lines = ["#### 方案二：仅标题", "", "```mermaid", "flowchart TB", "  A-->B", "```"]
    t = md_to_pdf.resolve_mermaid_caption_text(lines, 2, "flowchart TB\n  A-->B")
    assert "方案二" in (t or "")
