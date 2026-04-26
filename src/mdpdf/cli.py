"""Click CLI (spec §6.1).

Plan 1 implements only `render` (the no-subcommand default) and `version`.
Other subcommands (`brand`, `fonts`, `doctor`) and flags (`--brand`,
`--watermark-user`, `--legacy-brand`, etc.) land in plans 2-5.
"""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

import click

from mdpdf import __version__
from mdpdf.errors import (
    BrandError,
    FontError,
    MdpdfError,
    PipelineError,
    RendererError,
    SecurityError,
    TemplateError,
)
from mdpdf.logging import configure_logging
from mdpdf.pipeline import Pipeline, RenderRequest, RenderResult, WatermarkOptions

# Spec §6.1 exit-code table. Lookup walks `__mro__` so subclasses (e.g.,
# Plan 3's MermaidError(RendererError) → exit 5) are matched correctly
# regardless of dict insertion order.
_EXIT_BY_CODE: dict[type[MdpdfError], int] = {
    PipelineError: 1,
    TemplateError: 2,
    BrandError: 3,
    FontError: 4,
    RendererError: 5,
    SecurityError: 3,  # treated as a config/policy issue in v2.0
}


def _exit_code_for(err: MdpdfError) -> int:
    """Map an MdpdfError to the spec §6.1 exit code via MRO walk."""
    for cls in type(err).__mro__:
        if cls in _EXIT_BY_CODE:
            return _EXIT_BY_CODE[cls]
    return 1


class _DefaultRenderGroup(click.Group):
    """Group that routes to `render` when no subcommand is named.

    The bare invocation `md-to-pdf <input.md> -o <output.pdf>` (spec §6.1)
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
    help="Template id; v2.0 supports only 'generic'.",
)
@click.option(
    "--locale",
    default="en",
    show_default=True,
    hidden=True,
    help="(v2.0a1: no-op; locale-aware header/footer lands in Plan 2+.)",
)
@click.option(
    "--deterministic",
    is_flag=True,
    default=False,
    hidden=True,
    help="(v2.0a1: no-op; deterministic mode lands in Plan 4.)",
)
@click.option(
    "--no-audit",
    is_flag=True,
    default=False,
    hidden=True,
    help="(v2.0a1: no-op; audit log lands in Plan 4.)",
)
@click.option(
    "--watermark-user",
    default=None,
    hidden=True,
    help="(v2.0a1: no-op; watermarking lands in Plan 4.)",
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
    json_output: bool,
) -> None:
    """Render INPUT_PATH (markdown) to a PDF."""
    # In human mode keep the CLI quiet (spec §6.1: stdout is the output path
    # only); JSON mode emits structured logs to stderr at INFO.
    configure_logging(
        json_output=json_output,
        level="INFO" if json_output else "WARNING",
    )

    if deterministic:
        click.echo(
            "warning: --deterministic accepted but not yet implemented (lands in Plan 4)",
            err=True,
        )
    if watermark_user:
        click.echo(
            "warning: --watermark-user accepted but watermarking not yet "
            "implemented (lands in Plan 4)",
            err=True,
        )

    pipeline = Pipeline.from_env()
    req = RenderRequest(
        source=input_path,
        source_type="path",
        output=output,
        template=template,
        watermark=WatermarkOptions(user=watermark_user or _resolve_default_user()),
        deterministic=deterministic,
        locale=locale,
        audit_enabled=not no_audit,
    )

    try:
        result = pipeline.render(req)
    except MdpdfError as e:
        # Print the structured error to stderr; map to exit code per spec §6.1.
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
    help="Accept v1 brand_kits/-style layout.",
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
    """Convert a v1 brand_kits/-style layout into a v2 brand pack."""
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
