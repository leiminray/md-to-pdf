# SPDX-License-Identifier: MIT
"""
Fenced code → ReportLab ``Paragraph`` mini-XML: Pygments (limited palette) + language accents (GitHub-like).
CJK in monospace uses ``cjk_body_font`` (e.g. Noto Sans SC) for those runs — mono fonts often lack CJK.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

# --- GitHub light–inspired fixed palette (print-safe, few colors) ---
DEFAULT_TEXT = "#24292f"
COMMENT_GRAY = "#6e7781"
STRING_BLUE = "#0a3069"
KEYWORD_RED = "#cf222e"
NUMBER_BLUE = "#0550ae"
FUNC_PURP = "#8250df"
NAME_GREEN = "#116329"
ERROR_RED = "#a40e26"

# Left accent bar (language chip) by normalized fence first token
_LANG_ACCENT_HEX: dict[str, str] = {
    "python": "#3776ab",
    "go": "#00add8",
    "golang": "#00add8",
    "java": "#b07219",
    "javascript": "#d4a000",
    "js": "#d4a000",
    "typescript": "#3178c6",
    "ts": "#3178c6",
    "rust": "#dea584",
    "ruby": "#cc342d",
    "bash": "#3e3e3e",
    "shell": "#3e3e3e",
    "yaml": "#cb171e",
    "mermaid": "#ff3670",
    "mmd": "#ff3670",
    "json": "#292929",
    "text": "#57606a",
    "default": "#0f4c81",
}

# Map code fence to Pygments lexer name
_ALIAS: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "rs": "rust",
    "rb": "ruby",
    "yml": "yaml",
    "sh": "bash",
    "shell": "bash",
    "mmd": "mermaid",
}


def _esc(s: str) -> str:
    return escape(s)


# CJK + fullwidth forms (incl. CJK symbols / punctuation) — for mixed mono + body-font rendering
_CJK_RE = re.compile(
    r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\uffe0-\uffee]+", re.UNICODE
)


def fenced_cjk_mixed_line_xml(plain: str, cjk_body_font: str) -> str:
    """
    One logical line: default paragraph font = mono; CJK runs use ``<font name=cjk_body_font>``.
    ``plain`` is unescaped (will be escaped per segment).
    """
    if not plain:
        return ""
    if not cjk_body_font:
        return _esc(plain)
    out: list[str] = []
    i = 0
    for m in _CJK_RE.finditer(plain):
        if m.start() > i:
            out.append(_esc(plain[i : m.start()]))
        out.append(f'<font name="{cjk_body_font}">' + _esc(m.group(0)) + "</font>")
        i = m.end()
    if i < len(plain):
        out.append(_esc(plain[i:]))
    return "".join(out)


def _fragment_to_colored_xml(plain: str, col: str, cjk_body_font: str | None) -> str:
    """Single line fragment with Pygments color; optional CJK font for Han/fullwidth runs."""
    if not plain:
        return ""
    if not cjk_body_font:
        return f'<font color="{col}">' + _esc(plain) + "</font>"
    out: list[str] = []
    i = 0
    for m in _CJK_RE.finditer(plain):
        if m.start() > i:
            out.append(f'<font color="{col}">' + _esc(plain[i : m.start()]) + "</font>")
        out.append(
            f'<font name="{cjk_body_font}" color="{col}">'
            + _esc(m.group(0))
            + "</font>"
        )
        i = m.end()
    if i < len(plain):
        out.append(f'<font color="{col}">' + _esc(plain[i:]) + "</font>")
    return "".join(out)


def resolve_pygments_lexer_name(fence_lang: str) -> str:
    t = re.split(r"[\s{]", (fence_lang or "text"), maxsplit=1)[0].strip().lower() or "text"
    if t in _ALIAS:
        t = _ALIAS[t]
    if t in ("mermaid", "mmd"):
        return "text"
    return t


def lang_accent_hex(normalized_label: str) -> str:
    k = (normalized_label or "text").strip().lower() or "text"
    return _LANG_ACCENT_HEX.get(k, _LANG_ACCENT_HEX["default"])


def _color_for_ttype(ttype) -> str:
    try:
        from pygments.token import (
            Comment,
            Error,
            Keyword,
            Name,
            Number,
            Operator,
            Punctuation,
            String,
        )
        from pygments.token import is_token_subtype
    except ImportError:  # pragma: no cover
        return DEFAULT_TEXT

    if is_token_subtype(Comment, ttype):
        return COMMENT_GRAY
    if is_token_subtype(Keyword, ttype):
        return KEYWORD_RED
    if is_token_subtype(String, ttype):
        return STRING_BLUE
    if is_token_subtype(Number, ttype):
        return NUMBER_BLUE
    if is_token_subtype(Operator, ttype) or is_token_subtype(Punctuation, ttype):
        return DEFAULT_TEXT
    if is_token_subtype(Error, ttype):
        return ERROR_RED
    if is_token_subtype(Name.Function, ttype) or is_token_subtype(Name.Class, ttype) or is_token_subtype(Name.Builtin, ttype):
        return FUNC_PURP
    if is_token_subtype(Name, ttype):
        return NAME_GREEN
    return DEFAULT_TEXT


def pygments_to_reportlab_paragraph_xml(
    source: str, fence_raw_lang: str, cjk_body_font: str | None = None
) -> str:
    try:
        from pygments import lex
        from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
        from pygments.util import ClassNotFound
    except ImportError:  # pragma: no cover
        raise RuntimeError("pygments not installed")
    name = resolve_pygments_lexer_name(fence_raw_lang)
    try:
        lexer = get_lexer_by_name(name, stripall=False, stripnl=False)
    except ClassNotFound:
        if name in ("mermaid", "mmd", "md"):
            try:
                lexer = get_lexer_by_name("yaml")
            except ClassNotFound:
                lexer = TextLexer()
        else:
            try:
                lexer = guess_lexer(source)
            except ClassNotFound:
                lexer = TextLexer()
    parts: list[str] = []
    for ttype, value in lex(source, lexer):
        if not value:
            continue
        col = _color_for_ttype(ttype)
        for i, line in enumerate(value.split("\n")):
            if i:
                parts.append("<br/>")
            if line:
                parts.append(_fragment_to_colored_xml(line, col, cjk_body_font))
    return "".join(parts) if parts else _esc(source)
