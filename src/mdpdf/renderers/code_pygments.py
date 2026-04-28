"""Pygments-backed code renderer.

Tokenises a CodeFence with Pygments and maps tokens to a small GitHub
Light palette. Returns a `CodeRenderResult` whose `lines` field is a
list of lists of `ColoredFragment` (one inner list per source line);
the caller (`FencedCodeCard` flowable, the FencedCodeCard flowable) lays them out
into a ReportLab paragraph.

Truncation env vars (compatible with  behaviour):
- MDPDF_FENCED_MAX_LINES (default 500)
- MDPDF_FENCED_MAX_CHARS (default 262144)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.token import Token, _TokenType
from pygments.util import ClassNotFound

from mdpdf.markdown.ast import CodeFence
from mdpdf.renderers.base import RenderContext, Renderer

# GitHub Light palette (subset — print-safe, accessible).
_DEFAULT_COLOR = "#1f2328"
_PALETTE: dict[_TokenType, str] = {
    Token.Keyword: "#cf222e",
    Token.Keyword.Constant: "#cf222e",
    Token.Keyword.Declaration: "#cf222e",
    Token.Keyword.Namespace: "#cf222e",
    Token.Keyword.Pseudo: "#cf222e",
    Token.Keyword.Reserved: "#cf222e",
    Token.Keyword.Type: "#0550ae",
    Token.Name.Builtin: "#0550ae",
    Token.Name.Function: "#8250df",
    Token.Name.Class: "#953800",
    Token.Name.Decorator: "#8250df",
    Token.Literal.String: "#0a3069",
    Token.Literal.Number: "#0550ae",
    Token.Comment: "#6e7781",
    Token.Comment.Single: "#6e7781",
    Token.Comment.Multiline: "#6e7781",
    Token.Operator: "#cf222e",
    Token.Punctuation: _DEFAULT_COLOR,
    Token.Error: "#82071e",
}


@dataclass(frozen=True)
class ColoredFragment:
    text: str
    color: str


@dataclass
class CodeRenderResult:
    lang: str
    lines: list[list[ColoredFragment]] = field(default_factory=list)
    truncated: bool = False


def _color_for(tok: _TokenType) -> str:
    cur: _TokenType | None = tok
    while cur is not None:
        if cur in _PALETTE:
            return _PALETTE[cur]
        # Fallback: walk up Pygments token hierarchy
        cur = cur.parent if hasattr(cur, "parent") else None
    return _DEFAULT_COLOR


def _max_lines() -> int:
    return int(os.environ.get("MDPDF_FENCED_MAX_LINES", "500"))


def _max_chars() -> int:
    return int(os.environ.get("MDPDF_FENCED_MAX_CHARS", "262144"))


def render_code_fence(fence: CodeFence, ctx: RenderContext) -> CodeRenderResult:
    """Tokenise a CodeFence and return a per-line list of ColoredFragments."""
    content = fence.content
    truncated = False
    if len(content) > _max_chars():
        content = content[: _max_chars()]
        truncated = True

    try:
        lexer = get_lexer_by_name(fence.lang) if fence.lang else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()

    lines: list[list[ColoredFragment]] = [[]]
    for tok, text in lex(content, lexer):
        if not text:
            continue
        colour = _color_for(tok)
        # Split tokens that span multiple lines.
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if part:
                lines[-1].append(ColoredFragment(text=part, color=colour))
            if i < len(parts) - 1:
                lines.append([])

    if len(lines) > _max_lines():
        lines = lines[: _max_lines()]
        lines.append([
            ColoredFragment(text=f"… (truncated to {_max_lines()} lines)", color="#6e7781"),
        ])
        truncated = True

    return CodeRenderResult(lang=fence.lang, lines=lines, truncated=truncated)


class CodeRenderer(Renderer[CodeFence, CodeRenderResult]):
    """Renderer-ABC entry point. Wraps the module-level function."""

    name = "pygments"

    def render(self, source: CodeFence, ctx: RenderContext) -> CodeRenderResult:
        return render_code_fence(source, ctx)
