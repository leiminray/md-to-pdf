"""Tests for brand field overrides."""
import pytest

from mdpdf.brand.overrides import apply_overrides, parse_override
from mdpdf.errors import BrandError


def test_parse_override_simple():
    k, v = parse_override("theme.colors.accent=#FF0000")
    assert k == "theme.colors.accent"
    assert v == "#FF0000"


def test_parse_override_value_with_equals():
    k, v = parse_override("compliance.footer.text=Foo=Bar")
    assert k == "compliance.footer.text"
    assert v == "Foo=Bar"


def test_parse_override_invalid_no_equals():
    with pytest.raises(BrandError) as ei:
        parse_override("no-equals")
    assert ei.value.code == "BRAND_OVERRIDE_DENIED"


def _bp_dict(allowed=None, forbidden=None, allows_inline=True):
    return {
        "schema_version": "2.0",
        "id": "test",
        "name": "Test",
        "version": "1.0.0",
        "theme": {
            "colors": {
                "primary": "#000",
                "text": "#000",
                "muted": "#000",
                "accent": "#000",
                "background": "#fff",
            },
            "typography": {
                "body": {"family": "F", "size": 10, "leading": 12},
                "heading": {"family": "F", "weights": [700]},
                "code": {"family": "F", "size": 9, "leading": 12},
            },
            "layout": {
                "page_size": "A4",
                "margins": {"top": 10, "right": 10, "bottom": 10, "left": 10},
                "header_height": 10,
                "footer_height": 10,
            },
            "assets": {"logo": "./logo.png", "icon": "./icon.png"},
        },
        "compliance": {
            "footer": {"text": "x", "show_page_numbers": True, "show_render_date": True},
            "issuer": {"name": "X", "lines": ["a"]},
            "watermark": {"default_text": "x", "template": "x"},
            "disclaimer": "x",
        },
        "allows_inline_override": allows_inline,
        "allowed_override_fields": allowed or [],
        "forbidden_override_fields": forbidden or [],
    }


def test_apply_override_to_whitelisted_field():
    payload = _bp_dict(allowed=["theme.colors.accent"])
    out = apply_overrides(payload, [("theme.colors.accent", "#FF0000")])
    assert out["theme"]["colors"]["accent"] == "#FF0000"


def test_apply_override_to_forbidden_field_raises():
    payload = _bp_dict(allowed=[], forbidden=["compliance.issuer.name"])
    with pytest.raises(BrandError) as ei:
        apply_overrides(payload, [("compliance.issuer.name", "Other")])
    assert ei.value.code == "BRAND_OVERRIDE_DENIED"
    assert "forbidden" in ei.value.user_message.lower()


def test_apply_override_to_non_whitelisted_when_whitelist_set_raises():
    """If allowed_override_fields is non-empty, only those are permitted."""
    payload = _bp_dict(allowed=["theme.colors.accent"])
    with pytest.raises(BrandError) as ei:
        apply_overrides(payload, [("theme.colors.primary", "#FFFFFF")])
    assert ei.value.code == "BRAND_OVERRIDE_DENIED"


def test_apply_override_when_allows_inline_false_raises():
    payload = _bp_dict(allows_inline=False, allowed=["theme.colors.accent"])
    with pytest.raises(BrandError) as ei:
        apply_overrides(payload, [("theme.colors.accent", "#FF0000")])
    assert ei.value.code == "BRAND_OVERRIDE_DENIED"
    assert "inline" in ei.value.user_message.lower()


def test_apply_no_overrides_returns_payload():
    payload = _bp_dict()
    out = apply_overrides(payload, [])
    assert out == payload
