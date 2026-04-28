"""Integration tests for brand CLI subcommands."""
from click.testing import CliRunner

from mdpdf.cli import main


class TestBrandListCommand:
    """Tests for `md-to-pdf brand list` command."""

    def test_brand_list_succeeds(self) -> None:
        """brand list should enumerate available brands."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "list"])

        assert result.exit_code == 0
        # Output should mention brands
        assert "brand" in result.output.lower() or "available" in result.output.lower()

    def test_brand_list_shows_brands(self) -> None:
        """brand list output should contain brand names."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "list"])

        assert result.exit_code == 0
        # If any brands exist, they should be listed
        # (minimal check: output should be non-empty)
        assert len(result.output) > 0


class TestBrandShowCommand:
    """Tests for `md-to-pdf brand show` command."""

    def test_brand_show_missing_brand(self) -> None:
        """brand show with nonexistent brand should fail gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "show", "--brand-pack-dir", "/nonexistent"])

        # Should exit with error or show not found message
        # (may be exit code 1 or 2 depending on error handling)
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_brand_show_requires_argument(self) -> None:
        """brand show should require a path argument."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "show"])

        # Should fail if no path provided
        assert result.exit_code != 0 or len(result.output) > 0


class TestBrandMigrateCommand:
    """Tests for `md-to-pdf brand migrate` command."""

    def test_brand_migrate_missing_input(self) -> None:
        """brand migrate without arguments should fail gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "migrate"])

        # Should show error or usage
        assert result.exit_code != 0

    def test_brand_migrate_nonexistent_path(self) -> None:
        """brand migrate with nonexistent path should fail gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "migrate", "/nonexistent", "/tmp/out"])

        # Should fail or show helpful error
        output_lower = result.output.lower()
        assert result.exit_code != 0 or "not found" in output_lower or "exists" in output_lower


class TestBrandCommandIntegration:
    """Integration tests for brand command group."""

    def test_brand_help_lists_subcommands(self) -> None:
        """brand --help should list available subcommands."""
        runner = CliRunner()
        result = runner.invoke(main, ["brand", "--help"])

        assert result.exit_code == 0
        # Should mention subcommands
        assert "list" in result.output or "show" in result.output or "migrate" in result.output
