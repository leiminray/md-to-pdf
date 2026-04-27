"""Tests for i18n.strings — locale-keyed string lookup and date format."""
from __future__ import annotations

from datetime import date

import pytest

from mdpdf.i18n.strings import STRINGS, date_format, lookup


def test_lookup_en_confidential() -> None:
    assert lookup("en", "footer.confidential") == "Confidential"


def test_lookup_zh_cn_confidential() -> None:
    assert lookup("zh-CN", "footer.confidential") == "机密"


def test_lookup_en_page_format() -> None:
    result = lookup("en", "footer.page_format")
    assert "{n}" in result
    assert "{total}" in result


def test_lookup_zh_cn_page_format() -> None:
    result = lookup("zh-CN", "footer.page_format")
    assert "{n}" in result
    assert "{total}" in result
    assert "页" in result


def test_lookup_en_header_generated() -> None:
    result = lookup("en", "header.generated")
    assert "{date}" in result


def test_lookup_zh_cn_header_generated() -> None:
    result = lookup("zh-CN", "header.generated")
    assert "{date}" in result
    assert "生成" in result


def test_lookup_unknown_locale_falls_back_to_en() -> None:
    result = lookup("fr", "footer.confidential")
    assert result == "Confidential"


def test_lookup_missing_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="nonexistent.key"):
        lookup("en", "nonexistent.key")


def test_lookup_missing_key_in_unknown_locale_raises() -> None:
    with pytest.raises(KeyError):
        lookup("fr", "nonexistent.key")


def test_date_format_en() -> None:
    fmt = date_format("en")
    result = date(2026, 4, 27).strftime(fmt)
    assert "2026" in result
    assert "04" in result or "4" in result


def test_date_format_zh_cn() -> None:
    """zh-CN format string contains the CJK separators.

    Note: We cannot call ``strftime`` on the returned pattern on Windows
    + Python 3.10/3.11 — it raises UnicodeEncodeError from the locale
    codec. Use :func:`format_date_for_locale` for actual formatting; this
    test only asserts the pattern itself.
    """
    fmt = date_format("zh-CN")
    assert "年" in fmt
    assert "月" in fmt
    assert "日" in fmt


def test_format_date_for_locale_zh_cn() -> None:
    """Cross-platform CJK date formatting (no strftime)."""
    from mdpdf.i18n.strings import format_date_for_locale

    result = format_date_for_locale(date(2026, 4, 27), "zh-CN")
    assert result == "2026年04月27日"


def test_format_date_for_locale_en() -> None:
    from mdpdf.i18n.strings import format_date_for_locale

    result = format_date_for_locale(date(2026, 4, 27), "en")
    assert result == "2026-04-27"


def test_date_format_unknown_locale_falls_back_to_en() -> None:
    assert date_format("fr") == date_format("en")


def test_strings_has_all_required_keys() -> None:
    required = {"footer.confidential", "footer.page_format", "header.generated"}
    for locale in ("en", "zh-CN"):
        missing = required - set(STRINGS.get(locale, {}).keys())
        assert not missing, f"Locale '{locale}' missing keys: {missing}"
