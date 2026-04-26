"""3-layer brand registry (spec §3.5).

Resolution order (highest priority wins; layers do NOT merge — they replace):
  1. Explicit `--brand-pack-dir <path>` (if provided)
  2. `<project_root>/.md-to-pdf/brands/<id>/`
  3. `<user_home>/.md-to-pdf/brands/<id>/`
  4. `<repo_builtin_root>/examples/brands/<id>/`

System-wide `/etc/md-to-pdf/brands/<id>/` lookup ships in v2.3 with policy.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mdpdf.brand.schema import BrandPack, load_brand_pack
from mdpdf.errors import BrandError


def _default_builtin_root() -> Path:
    """Locate `<repo>/examples/brands` from this file's location."""
    # src/mdpdf/brand/registry.py → src/mdpdf/brand → src/mdpdf → src → repo
    return Path(__file__).resolve().parents[3] / "examples" / "brands"


@dataclass
class BrandRegistry:
    """Encapsulates the lookup paths. Inject overrides for testing."""

    brand_id: str | None = None
    explicit_path: Path | None = None
    project_root: Path = field(default_factory=Path.cwd)
    user_home: Path = field(default_factory=Path.home)
    builtin_root: Path = field(default_factory=_default_builtin_root)

    def candidates(self) -> list[Path]:
        """Ordered list of candidate paths for the brand_id."""
        if not self.brand_id:
            return []
        return [
            self.project_root / ".md-to-pdf" / "brands" / self.brand_id,
            self.user_home / ".md-to-pdf" / "brands" / self.brand_id,
            self.builtin_root / self.brand_id,
        ]

    def list_brands(self) -> list[BrandPack]:
        """Enumerate all unique brand ids across layers (highest priority wins)."""
        seen: dict[str, BrandPack] = {}
        for layer in [
            self.project_root / ".md-to-pdf" / "brands",
            self.user_home / ".md-to-pdf" / "brands",
            self.builtin_root,
        ]:
            if not layer.is_dir():
                continue
            for child in sorted(layer.iterdir()):
                if not child.is_dir():
                    continue
                if child.name in seen:
                    continue
                if not (child / "brand.yaml").exists():
                    continue
                try:
                    seen[child.name] = load_brand_pack(child)
                except BrandError:
                    continue
        return list(seen.values())


def resolve_brand(reg: BrandRegistry) -> BrandPack:
    """Resolve `reg.brand_id` to a BrandPack via the 3-layer overlay."""
    if reg.explicit_path is not None:
        return load_brand_pack(reg.explicit_path)
    if reg.brand_id is None:
        raise BrandError(
            code="BRAND_NOT_FOUND",
            user_message="no brand_id provided and no explicit_path",
        )
    for cand in reg.candidates():
        if (cand / "brand.yaml").exists():
            return load_brand_pack(cand)
    raise BrandError(
        code="BRAND_NOT_FOUND",
        user_message=(
            f"brand '{reg.brand_id}' not found in any registry layer; "
            f"searched: " + ", ".join(str(c) for c in reg.candidates())
        ),
    )
