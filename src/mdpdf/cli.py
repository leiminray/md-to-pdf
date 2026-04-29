"""Click CLI.

The CLI provides `render` (the no-subcommand default) and `version`.
Other subcommands (`brand`, `fonts`, `doctor`) and flags (`--brand`,
`--watermark-user`, `--legacy-brand`, etc.) land in plans 2-5.
"""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Literal, cast

import click
from reportlab.pdfbase import pdfmetrics

from mdpdf import __version__
from mdpdf.diagnostics.doctor import run_doctor
from mdpdf.errors import (
    BrandError,
    FontError,
    MdpdfError,
    PipelineError,
    RendererError,
    SecurityError,
    TemplateError,
)
from mdpdf.fonts.installer import install_font
from mdpdf.logging import configure_logging
from mdpdf.pipeline import Pipeline, RenderRequest, RenderResult, WatermarkOptions

# Spec §6.1 exit-code table. Lookup walks `__mro__` so subclasses (e.g.,
# MermaidError(RendererError) → exit 5) are matched correctly
# regardless of dict insertion order.
_EXIT_BY_CODE: dict[type[MdpdfError], int] = {
    PipelineError: 1,
    TemplateError: 2,
    BrandError: 3,
    FontError: 4,
    RendererError: 5,
    SecurityError: 3,  # treated as a config/policy issue in v0.2.1
}


def _exit_code_for(err: MdpdfError) -> int:
    """Map an MdpdfError to the exit code via MRO walk."""
    for cls in type(err).__mro__:
        if cls in _EXIT_BY_CODE:
            return _EXIT_BY_CODE[cls]
    return 1


class _DefaultRenderGroup(click.Group):
    """Group that routes to `render` when no subcommand is named.

    The bare invocation `md-to-pdf <input.md> -o <output.pdf>`
    must work alongside `md-to-pdf version`. Click's stock Group treats the
    first non-option token as a subcommand name, so we inject `render` when
    no token matches a registered subcommand.

    Detection rule: the FIRST non-dash token whose name matches a
    registered subcommand wins. Anything else (no positional, or first
    positional is a path) falls through to the default `render` command.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Look for any token that exactly matches a known subcommand.
        # Over-counting (treating a path as a token) is harmless because
        # paths almost never match subcommand names; under-counting only
        # falls back to the default `render` dispatch, which is correct.
        for tok in args:
            if not tok.startswith("-") and tok in self.commands:
                # Real subcommand invocation; let Click handle it normally.
                return super().parse_args(ctx, args)
        # No subcommand found — prepend `render` and let it consume the rest.
        return super().parse_args(ctx, ["render", *args])


@click.group(cls=_DefaultRenderGroup, invoke_without_command=False)
def main() -> None:
    """md-to-pdf — Markdown → PDF."""


@main.command(name="render")
@click.argument(
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--template",
    default="generic",
    show_default=True,
    help="Template id; supports only 'generic'.",
)
@click.option(
    "--locale",
    default="en",
    show_default=True,
    help="Output locale for footer + watermark text (e.g. en, zh-CN).",
)
@click.option(
    "--deterministic",
    is_flag=True,
    default=False,
    help=(
        "Produce bit-identical PDFs for identical inputs. Set "
        "SOURCE_DATE_EPOCH to fix the create-date too."
    ),
)
@click.option(
    "--no-audit",
    is_flag=True,
    default=False,
    help="Skip writing render.start / render.complete / render.error audit events.",
)
@click.option(
    "--watermark-user",
    default=None,
    help="User identity embedded in L1 + L2 watermarks (default: $USER).",
)
@click.option(
    "--watermark",
    "watermark_on",
    is_flag=True,
    default=False,
    help=(
        "Enable L1 visible + L2 XMP watermarks "
        "(default: off; brand security policy may force on)."
    ),
)
@click.option(
    "--no-watermark",
    is_flag=True,
    default=False,
    help="Explicitly disable watermarks. Errors if brand requires watermarks.",
)
@click.option(
    "--watermark-text",
    default=None,
    help=(
        "Override the L1 watermark text template. "
        "Available keys: {brand_name}, {user}, {render_date}."
    ),
)
@click.option(
    "--brand",
    default=None,
    help="Brand id; resolved via the 3-layer registry.",
)
@click.option(
    "--brand-pack-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Explicit brand pack directory.",
)
@click.option(
    "--brand-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Inline brand YAML.",
)
@click.option(
    "--override",
    "overrides",
    multiple=True,
    help="Brand field override 'key=value' (repeatable).",
)
@click.option(
    "--legacy-brand",
    is_flag=True,
    default=False,
    help="Accept legacy brand_kits/-style layout.",
)
@click.option(
    "--mermaid-renderer",
    type=click.Choice(["auto", "kroki", "puppeteer", "pure"]),
    default="auto",
    show_default=True,
    help="Mermaid renderer preference.",
)
@click.option(
    "--kroki-url",
    default=None,
    help="Override KROKI_URL env var for Mermaid rendering.",
)
@click.option(
    "--allow-remote-assets",
    is_flag=True,
    default=False,
    help="Allow http(s):// image URLs and brand assets.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Emit RenderResult as JSON to stdout.",
)
@click.pass_context
def render_cmd(
    ctx: click.Context,
    input_path: Path,
    output: Path,
    template: str,
    locale: str,
    deterministic: bool,
    no_audit: bool,
    watermark_user: str | None,
    brand: str | None,
    brand_pack_dir: Path | None,
    brand_config: Path | None,
    overrides: tuple[str, ...],
    legacy_brand: bool,
    watermark_on: bool,
    no_watermark: bool,
    watermark_text: str | None,
    mermaid_renderer: str,
    kroki_url: str | None,
    allow_remote_assets: bool,
    json_output: bool,
) -> None:
    """Render INPUT_PATH (markdown) to a PDF."""
    # In human mode keep the CLI quiet (stdout is the output path
    # only); JSON mode emits structured logs to stderr at INFO.
    configure_logging(
        json_output=json_output,
        level="INFO" if json_output else "WARNING",
    )

    if legacy_brand:
        click.echo(
            "Warning: --legacy-brand is deprecated and will be removed in v3.0. "
            "Run 'md-to-pdf brand migrate <path>' to upgrade your brand pack.",
            err=True,
        )

    pipeline = Pipeline.from_env()
    from mdpdf.brand.overrides import parse_override
    parsed_overrides = [parse_override(o) for o in overrides]
    if no_watermark and watermark_on:
        click.echo("Error: --watermark and --no-watermark are mutually exclusive.", err=True)
        raise SystemExit(2)
    watermark_level: Literal["L0", "L1", "L2", "L1+L2"] = (
        "L1+L2" if watermark_on else "L0"
    )
    req = RenderRequest(
        source=input_path,
        source_type="path",
        output=output,
        template=template,
        brand=brand,
        brand_pack_dir=brand_pack_dir,
        brand_config=brand_config,
        brand_overrides=parsed_overrides,
        legacy_brand=legacy_brand,
        watermark=WatermarkOptions(
            user=watermark_user or _resolve_default_user(),
            level=watermark_level,
            custom_text=watermark_text,
            force_disabled=no_watermark,
        ),
        deterministic=deterministic,
        locale=locale,
        audit_enabled=not no_audit,
        mermaid_renderer=cast(
            Literal["auto", "kroki", "puppeteer", "pure"], mermaid_renderer
        ),
        kroki_url=kroki_url,
        allow_remote_assets=allow_remote_assets,
    )

    try:
        result = pipeline.render(req)
    except MdpdfError as e:
        # Print the structured error to stderr; map to exit code.
        click.echo(f"{e.code}: {e.user_message}", err=True)
        if e.technical_details:
            click.echo(f"  details: {e.technical_details}", err=True)
        ctx.exit(_exit_code_for(e))
    except Exception as e:  # noqa: BLE001 — last-ditch unexpected failure
        click.echo(f"INTERNAL_ERROR: {e}", err=True)
        ctx.exit(1)

    if json_output:
        click.echo(_render_result_to_json(result))
    else:
        click.echo(str(result.output_path))


@main.command()
def version() -> None:
    """Print the md-to-pdf version."""
    click.echo(f"md-to-pdf {__version__}")


_BUNDLED_FONTS_DIR = Path(__file__).resolve().parents[2] / "fonts"
_USER_FONTS_DIR = Path.home() / ".md-to-pdf" / "fonts"


@main.group("fonts")
def fonts_group() -> None:
    """Font management commands."""


@fonts_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit results as JSON.")
def fonts_list(as_json: bool) -> None:
    """List built-in, bundled, and user-installed fonts."""
    entries: list[dict[str, str]] = []
    for name in sorted(pdfmetrics.getRegisteredFontNames()):
        entries.append({"name": name, "source": "built-in"})
    for source_dir, source_label in (
        (_BUNDLED_FONTS_DIR, "bundled"),
        (_USER_FONTS_DIR, "user"),
    ):
        if not source_dir.is_dir():
            continue
        for f in sorted(source_dir.iterdir()):
            if f.suffix.lower() in {".ttf", ".otf"}:
                entries.append({"name": f.stem, "source": source_label})

    if as_json:
        click.echo(json.dumps(entries, indent=2))
    else:
        click.echo(f"{'Name':<40} {'Source'}")
        click.echo("-" * 50)
        for entry in entries:
            click.echo(f"{entry['name']:<40} {entry['source']}")


@fonts_group.command("install")
@click.argument("name")
@click.option(
    "--target-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory to save the font (default: ~/.md-to-pdf/fonts/).",
)
def fonts_install(name: str, target_dir: Path | None) -> None:
    """Download and install a known font by NAME (e.g. noto-sans-sc)."""
    try:
        path = install_font(name, target_dir=target_dir)
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        raise SystemExit(_exit_code_for(e)) from e
    click.echo(f"Installed: {path}")


@main.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit report as JSON.")
def doctor_cmd(as_json: bool) -> None:
    """Print an environment health report."""
    report = run_doctor()
    if as_json:
        click.echo(json.dumps(report, indent=2))
    else:
        for section, data in report.items():
            click.echo(f"\n[{section}]")
            if isinstance(data, dict):
                for k, v in data.items():
                    click.echo(f"  {k}: {v}")
            else:
                click.echo(f"  {data}")


@main.group()
def brand() -> None:
    """Brand pack management."""


@brand.command(name="list")
def brand_list() -> None:
    """List all available brands across the registry layers."""
    from mdpdf.brand.registry import BrandRegistry

    reg = BrandRegistry()
    brands = reg.list_brands()
    if not brands:
        click.echo("(no brands found)")
        return
    for b in brands:
        click.echo(f"{b.id}\t{b.name}\t{b.version}\t{b.pack_root}")


@brand.command(name="show")
@click.option(
    "--brand-pack-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
def brand_show(brand_pack_dir: Path) -> None:
    """Print the resolved brand config (YAML)."""
    import yaml

    from mdpdf.brand.schema import load_brand_pack

    try:
        bp = load_brand_pack(brand_pack_dir)
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        raise SystemExit(_exit_code_for(e)) from e
    click.echo(
        yaml.safe_dump(bp.model_dump(exclude={"pack_root"}), sort_keys=False, allow_unicode=True)
    )


@brand.command(name="validate")
@click.argument("brand_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--legacy-brand",
    is_flag=True,
    default=False,
    help="Accept legacy brand_kits/-style layout.",
)
def brand_validate(brand_path: Path, legacy_brand: bool) -> None:
    """Validate a brand pack against the v2 schema."""
    from mdpdf.brand.legacy import load_legacy_brand_pack
    from mdpdf.brand.schema import load_brand_pack

    try:
        if legacy_brand:
            bp, deprecation = load_legacy_brand_pack(brand_path)
            click.echo(deprecation, err=True)
        else:
            bp = load_brand_pack(brand_path)
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        raise SystemExit(_exit_code_for(e)) from e
    click.echo(f"valid: brand '{bp.id}' v{bp.version} (schema {bp.schema_version})")


@brand.command(name="migrate")
@click.argument("v1_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("v2_output", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--id",
    "target_id",
    default=None,
    help="Override the v2 brand id (defaults to v1 dir name).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite a non-empty target dir.",
)
def brand_migrate(
    v1_path: Path, v2_output: Path, target_id: str | None, force: bool
) -> None:
    """Convert a legacy brand_kits/-style layout into a v2 brand pack."""
    from mdpdf.brand.migrate import migrate_v1_to_v2

    try:
        out = migrate_v1_to_v2(v1_path, v2_output, target_id=target_id, force=force)
    except MdpdfError as e:
        click.echo(f"{e.code}: {e.user_message}", err=True)
        raise SystemExit(_exit_code_for(e)) from e
    click.echo(str(out))


def _resolve_default_user() -> str | None:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return os.environ.get("USER") or os.environ.get("USERNAME")


def _render_result_to_json(result: RenderResult) -> str:
    return json.dumps(
        {
            "output_path": str(result.output_path),
            "render_id": result.render_id,
            "pages": result.pages,
            "bytes": result.bytes,
            "sha256": result.sha256,
            "warnings": result.warnings,
            "metrics": {
                "parse_ms": result.metrics.parse_ms,
                "asset_resolve_ms": result.metrics.asset_resolve_ms,
                "render_ms": result.metrics.render_ms,
                "post_process_ms": result.metrics.post_process_ms,
                "total_ms": result.metrics.total_ms,
            },
        },
        indent=None,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
