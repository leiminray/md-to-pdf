"""Field-level brand override mechanism.

CLI passes `--override key=value` (may repeat). Applied AFTER the brand
payload is loaded as a dict but BEFORE pydantic validation, so type errors
on the override value surface as schema validation errors.

Rules (strictest wins):
- If `allows_inline_override: false` -> ALL overrides rejected.
- If `forbidden_override_fields` matches the key -> rejected.
- If `allowed_override_fields` is non-empty AND key not in it -> rejected.
- Otherwise: dotted-path key writes value into the dict.
"""
from __future__ import annotations

from typing import Any

from mdpdf.errors import BrandError


def parse_override(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise BrandError(
            code="BRAND_OVERRIDE_DENIED",
            user_message=f"--override must be 'key=value', got: {spec!r}",
        )
    key, _, value = spec.partition("=")
    return key, value


def apply_overrides(
    payload: dict[str, Any],
    overrides: list[tuple[str, str]],
) -> dict[str, Any]:
    if not overrides:
        return payload
    allows_inline = payload.get("allows_inline_override", True)
    allowed = payload.get("allowed_override_fields") or []
    forbidden = payload.get("forbidden_override_fields") or []

    if not allows_inline:
        raise BrandError(
            code="BRAND_OVERRIDE_DENIED",
            user_message="this brand sets allows_inline_override: false; --override rejected",
        )

    for key, value in overrides:
        for forbidden_prefix in forbidden:
            if key == forbidden_prefix or key.startswith(forbidden_prefix + "."):
                raise BrandError(
                    code="BRAND_OVERRIDE_DENIED",
                    user_message=f"override target '{key}' is in forbidden_override_fields",
                )
        if allowed:
            allowed_match = any(
                key == a or key.startswith(a + ".") for a in allowed
            )
            if not allowed_match:
                raise BrandError(
                    code="BRAND_OVERRIDE_DENIED",
                    user_message=(
                        f"override target '{key}' is not in allowed_override_fields; "
                        f"allowed: {allowed}"
                    ),
                )
        _set_dotted(payload, key, value)
    return payload


def _set_dotted(d: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    cursor = d
    for p in parts[:-1]:
        if p not in cursor or not isinstance(cursor[p], dict):
            cursor[p] = {}
        cursor = cursor[p]
    cursor[parts[-1]] = value
