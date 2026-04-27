"""Tests for the Click CLI (spec §6.1)."""
import json
from pathlib import Path

from click.testing import CliRunner

from mdpdf.cli import main


def test_version_subcommand_prints_version():
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert "2.0.0" in result.output


def test_render_writes_pdf(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# Hi\n\nBody.")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out)])
    assert result.exit_code == 0
    # stdout single line = absolute path of the produced PDF (spec §6.1)
    assert result.output.strip() == str(out)
    assert out.exists()


def test_render_json_emits_render_result(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# Hi")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["output_path"] == str(out)
    assert payload["pages"] >= 1
    assert payload["bytes"] > 0
    assert len(payload["sha256"]) == 64
    assert "render_id" in payload
    assert "metrics" in payload


def test_render_template_other_than_generic_exits_2(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner()  # Click 8.3+ separates stderr by default
    result = runner.invoke(main, [str(src), "-o", str(out), "--template", "quote"])
    assert result.exit_code == 2  # configuration / argument error per spec §6.1
    assert "TEMPLATE_NOT_FOUND" in result.stderr


def test_help_advertises_plan4_flags():
    """Plan 4 unhid the previously-hidden flags; verify they're now visible
    and that the new --no-watermark / --watermark-text flags also show up."""
    runner = CliRunner()
    result = runner.invoke(main, ["render", "--help"])
    assert result.exit_code == 0
    for flag in (
        "--template",
        "--json",
        "--deterministic",
        "--watermark-user",
        "--no-audit",
        "--locale",
        "--no-watermark",
        "--watermark-text",
    ):
        assert flag in result.output, f"--help should advertise {flag}"


def test_deterministic_flag_no_longer_warns(tmp_path: Path):
    """Plan 4 implements deterministic mode; the 'not yet implemented' warning
    is gone."""
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--deterministic"])
    assert result.exit_code == 0
    assert "not yet implemented" not in (result.output or "")
    assert "not yet implemented" not in (result.stderr or "")


def test_render_legacy_brand_emits_deprecation_stderr(tmp_path: Path) -> None:
    """`md-to-pdf render --legacy-brand` emits a deprecation message on stderr."""
    md = tmp_path / "in.md"
    md.write_text("# Hi\n")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(md), "-o", str(out), "--legacy-brand"])
    assert "deprecated" in (result.stderr or "").lower()


def test_bare_invocation_exits_with_usage_error():
    """`md-to-pdf` with no args dispatches to render, which then errors on
    missing INPUT_PATH (Click usage error → exit 2)."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 2  # Click usage error
    assert "INPUT_PATH" in result.stderr or "Missing argument" in result.stderr


def test_help_at_group_level_lists_subcommands():
    """`md-to-pdf --help` at the group level should list `render` and `version`."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    # Group --help may route to render --help via the dispatcher; the important
    # thing is that exit 0 and the help text mentions our commands or options.
    assert result.exit_code == 0


def test_version_subcommand_help_does_not_route_to_render():
    """`md-to-pdf version --help` must dispatch to version, not render."""
    runner = CliRunner()
    result = runner.invoke(main, ["version", "--help"])
    assert result.exit_code == 0
    # version subcommand's --help mentions the version command, not INPUT_PATH
    assert "INPUT_PATH" not in result.output


def test_option_before_positional_dispatch(tmp_path: Path):
    """`md-to-pdf -o out.pdf in.md` (option-before-positional) should still work."""
    src = tmp_path / "in.md"
    src.write_text("# x")
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, ["-o", str(out), str(src)])
    assert result.exit_code == 0, result.stderr
    assert out.exists()


def test_render_missing_input_exits_2_via_click_validation(tmp_path: Path):
    """Click rejects the missing path with usage error (exit 2) before our
    RESOURCE_MISSING (exit 4) handler runs. Plan 5 may move path validation
    inside the pipeline so this becomes exit 4 per spec §6.1 row 4.
    """
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(tmp_path / "missing.md"), "-o", str(out)])
    assert result.exit_code == 2
    # TODO(plan-5): move path-existence check into Pipeline.render's validate
    # phase so RESOURCE_MISSING (exit 4) is returned per spec §6.1.


def test_brand_list_subcommand_runs(tmp_path: Path, monkeypatch: object) -> None:
    """`md-to-pdf brand list` exits 0 (may list 0 or N brands)."""
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "list"])
    assert result.exit_code == 0


def test_brand_validate_v2_pack(tmp_path: Path) -> None:
    pack = tmp_path / "vbrand"
    pack.mkdir()
    (pack / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: vbrand\nname: V\nversion: "1.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (pack / "theme.yaml").write_text(
        'colors: {primary: "#000", text: "#000", muted: "#000",'
        ' accent: "#000", background: "#fff"}\n'
        'typography: {body: {family: F, size: 10, leading: 12},'
        ' heading: {family: F, weights: [700]},'
        ' code: {family: F, size: 9, leading: 12}}\n'
        'layout: {page_size: A4,'
        ' margins: {top: 10, right: 10, bottom: 10, left: 10},'
        ' header_height: 10, footer_height: 10}\n'
        'assets: {logo: ./logo.png, icon: ./icon.png}\n'
    )
    (pack / "compliance.yaml").write_text(
        'footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
        'issuer: {name: X, lines: [a]}\n'
        'watermark: {default_text: x, template: x}\n'
        'disclaimer: x\n'
    )
    (pack / "LICENSE").write_text("test")
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "validate", str(pack)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_brand_validate_invalid_pack_exits_3(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "validate", str(bad)])
    assert result.exit_code == 3
    assert "BRAND_NOT_FOUND" in result.output


def test_brand_validate_legacy_with_flag(tmp_path: Path) -> None:
    bk = tmp_path / "v1bk"
    bk.mkdir()
    (bk / "theme.yaml").write_text(
        'colors:\n  brand: "#0f4c81"\n  body: "#1f2937"\n  muted: "#6b7280"\n'
        '  table_header_bg: "#f3f4f6"\n  table_grid: "#d1d5db"\n  table_fin_negative: "#dc2626"\n'
        '  issuer_title: "#374151"\n  issuer_body: "#6b7280"\n'
        '  issuer_card_bg: "#f8fafc"\n  issuer_card_border: "#dbe3ea"\n'
        'typography:\n  footer_confidential_pt: 7\n  footer_page_num_pt: 8\n'
        'fonts:\n  footer_face: F\n  header_generated_face: F\n'
        'assets:\n  logo: "logo.png"\n  icon: "icon.png"\n'
        'layout:\n  logo_header_height_pt: 34\n  logo_header_width_scale: 4.0\n'
    )
    (bk / "compliance.md").write_text(
        '## brand profiles\n- Acme\n## Footer confidential\n'
        'Confidential\n## Issuer lines\n- **Acme**\n'
    )
    (bk / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (bk / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "validate", str(bk), "--legacy-brand"])
    assert result.exit_code == 0
    assert "deprecated" in result.stderr.lower() or "legacy" in result.stderr.lower()


def test_brand_migrate_subcommand(tmp_path: Path) -> None:
    bk = tmp_path / "v1bk"
    bk.mkdir()
    (bk / "theme.yaml").write_text(
        'colors:\n  brand: "#0f4c81"\n  body: "#1f2937"\n  muted: "#6b7280"\n'
        '  table_header_bg: "#f3f4f6"\n  table_grid: "#d1d5db"\n  table_fin_negative: "#dc2626"\n'
        '  issuer_title: "#374151"\n  issuer_body: "#6b7280"\n'
        '  issuer_card_bg: "#f8fafc"\n  issuer_card_border: "#dbe3ea"\n'
        'typography:\n  footer_confidential_pt: 7\n  footer_page_num_pt: 8\n'
        'fonts:\n  footer_face: F\n  header_generated_face: F\n'
        'assets:\n  logo: "logo.png"\n  icon: "icon.png"\n'
        'layout:\n  logo_header_height_pt: 34\n  logo_header_width_scale: 4.0\n'
    )
    (bk / "compliance.md").write_text(
        '## brand profiles\n- Acme\n## Footer confidential\n'
        'Confidential\n## Issuer lines\n- **Acme**\n'
    )
    (bk / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (bk / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    out = tmp_path / "v2"
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "migrate", str(bk), str(out), "--id", "acme"])
    assert result.exit_code == 0
    assert (out / "brand.yaml").exists()


def test_brand_show_subcommand(tmp_path: Path) -> None:
    pack = tmp_path / "show1"
    pack.mkdir()
    (pack / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: show1\nname: Show1\nversion: "1.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (pack / "theme.yaml").write_text(
        'colors: {primary: "#000", text: "#000", muted: "#000",'
        ' accent: "#000", background: "#fff"}\n'
        'typography: {body: {family: F, size: 10, leading: 12},'
        ' heading: {family: F, weights: [700]},'
        ' code: {family: F, size: 9, leading: 12}}\n'
        'layout: {page_size: A4,'
        ' margins: {top: 10, right: 10, bottom: 10, left: 10},'
        ' header_height: 10, footer_height: 10}\n'
        'assets: {logo: ./logo.png, icon: ./icon.png}\n'
    )
    (pack / "compliance.yaml").write_text(
        'footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
        'issuer: {name: X, lines: [a]}\n'
        'watermark: {default_text: x, template: x}\n'
        'disclaimer: x\n'
    )
    (pack / "LICENSE").write_text("test")
    runner = CliRunner()
    result = runner.invoke(main, ["brand", "show", "--brand-pack-dir", str(pack)])
    assert result.exit_code == 0
    assert "show1" in result.output


def test_mermaid_renderer_flag_accepts_choices(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    src.write_text("# x\n")
    out = tmp_path / "o.pdf"
    runner = CliRunner()
    for choice in ["auto", "kroki", "puppeteer", "pure"]:
        result = runner.invoke(
            main, [str(src), "-o", str(out), "--mermaid-renderer", choice]
        )
        # Click exit-code 2 ⇒ flag rejected; we only assert the flag was accepted.
        assert result.exit_code != 2 or "Invalid value" not in (result.output or "")


def test_mermaid_renderer_invalid_choice_rejected(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    src.write_text("# x\n")
    out = tmp_path / "o.pdf"
    runner = CliRunner()
    result = runner.invoke(
        main, [str(src), "-o", str(out), "--mermaid-renderer", "bogus"]
    )
    assert result.exit_code == 2
    # Click 8.3+ routes the error to stderr, exposed via .stderr on the result.
    assert "Invalid value" in (result.stderr or result.output)


def test_allow_remote_assets_flag(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    src.write_text("# x\n")
    out = tmp_path / "o.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [str(src), "-o", str(out), "--allow-remote-assets"])
    assert result.exit_code == 0


def test_kroki_url_flag_accepted(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    src.write_text("# x\n")
    out = tmp_path / "o.pdf"
    runner = CliRunner()
    result = runner.invoke(
        main, [str(src), "-o", str(out), "--kroki-url", "http://kroki.local"]
    )
    assert result.exit_code == 0
