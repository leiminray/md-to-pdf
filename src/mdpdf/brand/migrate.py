"""v1 → v2 brand pack migrator (spec §3.8).

Reads a v1 brand_kits/-style directory, produces a v2 pack at the target
location with the schema documented in spec §3.

CLI surface: `md-to-pdf brand migrate <v1-path> <v2-output-dir>`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from mdpdf.brand.legacy import load_legacy_brand_pack
from mdpdf.errors import BrandError
from mdpdf.fonts.manager import cjk_chars_present


def migrate_v1_to_v2(
    v1_path: Path,
    v2_output: Path,
    *,
    target_id: str | None = None,
    force: bool = False,
) -> Path:
    """Convert a v1 brand_kits directory to v2 layout at `v2_output`.

    Returns the resolved `v2_output` path on success.
    """
    v1_path = Path(v1_path).resolve()
    v2_output = Path(v2_output).resolve()
    if v2_output.exists() and any(v2_output.iterdir()) and not force:
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=(
                f"target {v2_output} is non-empty; pass force=True (or "
                "`--force` from CLI) to overwrite"
            ),
        )

    bp, _deprecation = load_legacy_brand_pack(v1_path)
    target_id = target_id or v1_path.name

    v2_output.mkdir(parents=True, exist_ok=True)
    assets_dir = v2_output / "assets"
    assets_dir.mkdir(exist_ok=True)

    for asset_name in ("logo.png", "icon.png", "logo-dark.png", "qr.png"):
        src = v1_path / asset_name
        if src.exists():
            shutil.copy2(src, assets_dir / asset_name)

    has_cn = cjk_chars_present(bp.compliance.footer.text + " " + bp.compliance.issuer.name)
    default_locale = "zh-CN" if has_cn else "en"

    brand_yaml = {
        "schema_version": "2.0",
        "id": target_id,
        "name": bp.name,
        "version": "1.0.0",
        "maintainer": "(migrated from v1; please set)",
        "theme": "./theme.yaml",
        "compliance": "./compliance.yaml",
        "default_locale": default_locale,
        "allows_inline_override": True,
        "allowed_override_fields": ["theme.colors.accent", "compliance.footer.subtitle"],
        "forbidden_override_fields": ["compliance.issuer", "security.watermark_min_level"],
        "security": {"watermark_min_level": "L1+L2", "allow_remote_assets": False},
        "audit": {"retain_render_log": True},
    }
    (v2_output / "brand.yaml").write_text(
        yaml.safe_dump(brand_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    theme_yaml = {
        "colors": bp.theme.colors.model_dump(),
        "typography": {
            "body": bp.theme.typography.body.model_dump(),
            "heading": bp.theme.typography.heading.model_dump(),
            "code": bp.theme.typography.code.model_dump(),
        },
        "layout": {
            "page_size": bp.theme.layout.page_size,
            "margins": bp.theme.layout.margins.model_dump(),
            "header_height": bp.theme.layout.header_height,
            "footer_height": bp.theme.layout.footer_height,
        },
        "assets": {
            "logo": (
                "./assets/logo.png"
                if (assets_dir / "logo.png").exists()
                else "./assets/logo-missing.png"
            ),
            "icon": (
                "./assets/icon.png"
                if (assets_dir / "icon.png").exists()
                else "./assets/icon-missing.png"
            ),
        },
    }
    (v2_output / "theme.yaml").write_text(
        yaml.safe_dump(theme_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    compliance_yaml = {
        "footer": bp.compliance.footer.model_dump(),
        "issuer": bp.compliance.issuer.model_dump(exclude_none=True),
        "watermark": bp.compliance.watermark.model_dump(),
        "disclaimer": bp.compliance.disclaimer,
    }
    (v2_output / "compliance.yaml").write_text(
        yaml.safe_dump(compliance_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    (v2_output / "LICENSE").write_text(
        "Apache-2.0 (placeholder; please replace with the actual licence "
        "appropriate to the brand assets).\n",
        encoding="utf-8",
    )
    (v2_output / "README.md").write_text(
        f"# Brand: {bp.name}\n\nMigrated from v1 layout at {v1_path}.\n"
        "Edit `brand.yaml`, `theme.yaml`, `compliance.yaml` to refine.\n",
        encoding="utf-8",
    )
    return v2_output
