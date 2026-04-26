"""Inline brand loading (spec §3.6).

`--brand-config <path>` accepts a single YAML file containing the full
brand+theme+compliance content inline. The directory of the file becomes
the brand's `pack_root` so any relative asset paths still resolve safely.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from mdpdf.brand.schema import BrandPack
from mdpdf.errors import BrandError


def load_inline_brand(yaml_path: Path) -> BrandPack:
    yaml_path = Path(yaml_path).resolve()
    if not yaml_path.exists():
        raise BrandError(
            code="BRAND_NOT_FOUND",
            user_message=f"inline brand YAML not found: {yaml_path}",
        )
    with yaml_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    payload["pack_root"] = yaml_path.parent
    payload.setdefault("locales", {})
    try:
        return BrandPack(**payload)
    except ValidationError as ve:
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"inline brand validation failed: {ve.errors()[0]['msg']}",
            technical_details=str(ve),
        ) from ve
