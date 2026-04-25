"""Click CLI (spec §6.1).

Plan 1 implements only `render` (the no-subcommand default) and `version`.
Other subcommands (`brand`, `fonts`, `doctor`) and flags (`--brand`,
`--watermark-user`, `--legacy-brand`, etc.) land in plans 2-5.
"""
from __future__ import annotations

import json
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

# Spec §6.1 exit-code table.
_EXIT_BY_CODE: dict[type[MdpdfError], int] = {
    PipelineError: 1,
    TemplateError: 2,
    BrandError: 3,
    FontError: 4,
    RendererError: 5,
    SecurityError: 3,  # treated as a config/policy issue in v2.0
}


class _DefaultRenderGroup(click.Group):
    """Group that routes to `render` when no subcommand is named.

    The bare invocation `md-to-pdf <input.md> -o <output.pdf>` (spec §6.1)
    must work alongside `md-to-pdf version`. Click's stock Group treats the
    first non-option token as a subcommand name, so we inject `render` when
    that token does not match a registered subcommand.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Find the first non-option token to decide subcommand dispatch.
        first_non_opt: str | None = None
        skip_next = False
        for tok in args:
            if skip_next:
                skip_next = False
                continue
            if tok.startswith("-"):
                # Group-level options would be consumed by the parent here,
                # but we have none; everything is on `render`. Treat any
                # leading `-X value` as an option pair to skip past.
                if "=" not in tok:
                    skip_next = True
                continue
            first_non_opt = tok
            break

        if first_non_opt is None or first_non_opt not in self.commands:
            # Default to `render` subcommand.
            args = ["render", *args]
        return super().parse_args(ctx, args)


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
@click.option("--locale", default="en", show_default=True)
@click.option("--deterministic", is_flag=True, default=False)
@click.option(
    "--no-audit",
    is_flag=True,
    default=False,
    help="Disable audit log for this render.",
)
@click.option(
    "--watermark-user",
    default=None,
    help="Override watermark user (default: $USER).",
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
        for cls, code in _EXIT_BY_CODE.items():
            if isinstance(e, cls):
                ctx.exit(code)
        ctx.exit(1)
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


def _resolve_default_user() -> str | None:
    import getpass
    import os
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
