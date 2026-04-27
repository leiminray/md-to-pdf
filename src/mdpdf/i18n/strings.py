"""Locale-keyed string table for footer, header, and UI labels (spec §2.4).

Supported locales in v2.0: ``en`` (default) and ``zh-CN``.
"""
from __future__ import annotations

from datetime import date

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "footer.confidential": "Confidential",
        "footer.page_format": "Page {n} of {total}",
        "header.generated": "Generated {date}",
    },
    "zh-CN": {
        "footer.confidential": "机密",
        "footer.page_format": "第 {n} 页，共 {total} 页",
        "header.generated": "生成于 {date}",
    },
}

_DATE_FORMATS: dict[str, str] = {
    "en": "%Y-%m-%d",
    "zh-CN": "%Y年%m月%d日",
}

_FALLBACK_LOCALE = "en"


def lookup(locale: str, key: str) -> str:
    """Return the localised string for *key* in *locale*.

    Falls back to ``en`` if *locale* is not in :data:`STRINGS`. Raises
    ``KeyError`` if *key* is missing in both *locale* and the fallback.
    """
    table = STRINGS.get(locale) or STRINGS.get(_FALLBACK_LOCALE, {})
    if key in table:
        return table[key]
    fallback_table = STRINGS.get(_FALLBACK_LOCALE, {})
    if key in fallback_table:
        return fallback_table[key]
    raise KeyError(f"String key '{key}' not found in locale '{locale}' or fallback 'en'.")


def date_format(locale: str) -> str:
    """Return a strftime pattern for rendering dates in *locale*.

    Note: On Windows + Python 3.10/3.11, ``strftime`` of a format string
    containing CJK characters can fail with ``UnicodeEncodeError`` from
    the locale codec. Callers that may run on those platforms should
    prefer :func:`format_date_for_locale` instead.
    """
    return _DATE_FORMATS.get(locale, _DATE_FORMATS[_FALLBACK_LOCALE])


def format_date_for_locale(d: date, locale: str) -> str:
    """Format *d* for *locale* without going through strftime for CJK.

    Avoids the Windows + Python 3.10/3.11 ``UnicodeEncodeError: 'locale'
    codec can't encode character '\\u5e74'`` that surfaces when strftime
    sees CJK literals like ``年`` in the format string.
    """
    if locale == "zh-CN":
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"
    return d.strftime(_DATE_FORMATS.get(locale, _DATE_FORMATS[_FALLBACK_LOCALE]))
