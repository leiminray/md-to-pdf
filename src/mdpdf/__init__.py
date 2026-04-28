"""md-to-pdf: Enterprise Markdown → PDF converter.

Public API entry point. The main pipeline is exposed via `mdpdf.pipeline.Pipeline`,
and the CLI entry point lives at `mdpdf.cli:main` (registered as the `md-to-pdf`
console script in pyproject.toml).
"""

__version__ = "0.2.1"
