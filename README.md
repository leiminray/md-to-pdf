# md-to-pdf v0.2.1 (Beta)

A modern Markdown → PDF converter with brand-pack support, watermarking, and enterprise-grade features.

**Status:** Beta — core functionality complete, additional features in development.

## Quick Start

```bash
# Install
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Render a markdown file
.venv/bin/md-to-pdf input.md -o output.pdf

# With a brand pack
.venv/bin/md-to-pdf input.md -o output.pdf --brand-pack path/to/brand

# Check available brands
.venv/bin/md-to-pdf brand list
```

## Features (v0.2.1)

### ✅ Core Rendering
- **AST-first architecture** — markdown-it-py parser → internal AST → ReportLab renderer
- **English + CJK text** — Full Unicode support with CJK font management
- **Code blocks** — Syntax-highlighted code fences with language labels
- **Tables** — Multi-cell tables with proper formatting
- **Images** — Embedded images with alt text support
- **Mermaid diagrams** — Block diagrams rendered via Kroki / Puppeteer / pure JS
- **Links & bookmarks** — PDF bookmarks, internal links, table of contents

### ✅ Brand Packs
- **3-layer registry** — Project / User / Built-in brand resolution
- **Customizable themes** — Colors, fonts, logos, footers
- **Compliance text** — Watermarks, issuer information, certifications
- **Brand pack migration** — `md-to-pdf brand migrate` converts legacy brand kits

### ✅ Watermarking & Audit
- **L1 Visible watermark** — Diagonal overlay text
- **L2 XMP metadata** — Embedded EXIF/XMP watermark data
- **Audit logging** — JSON-format audit trails (user, timestamp, source hash)

### ✅ Deterministic Rendering
- `SOURCE_DATE_EPOCH` support for reproducible PDFs
- Platform-specific canonical testing (Linux/macOS/Windows)

### ✅ Documentation
- **mkdocs-material site** — Full user guide at https://leiminray.github.io/md-to-pdf/
- **Installation guide** — Setup and configuration
- **CLI reference** — Command-line options and workflows
- **Brand pack authoring** — Create and customize brand packs

## Installation

### From source (development)
```bash
git clone https://github.com/leiminray/md-to-pdf.git
cd md-to-pdf
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Run tests
```bash
.venv/bin/pytest -v              # Run all tests (443 passing)
.venv/bin/ruff check src/        # Lint
.venv/bin/mypy --strict src/     # Type check
```

## Architecture

```
markdown input
    ↓
markdown-it-py parser
    ↓
Internal AST (Document + outline)
    ↓
Transformer pipeline (strip frontmatter, collect headings, etc.)
    ↓
ReportLab renderer
    ↓
PDF output (with watermark/audit metadata)
```

## Python API

```python
from mdpdf.pipeline import Pipeline, RenderRequest, RenderFormat

# Render markdown to PDF
request = RenderRequest(
    markdown_path="input.md",
    output_path="output.pdf",
    brand_pack_dir="path/to/brand",  # optional
    watermark_user="alice@example.com",  # optional
)

pipeline = Pipeline()
result = pipeline.render(request)

if result.success:
    print(f"✓ Rendered to {result.output_path}")
else:
    print(f"✗ Error: {result.error_message}")
```

## CLI Commands

### Render
```bash
md-to-pdf INPUT.md -o OUTPUT.pdf [options]

Options:
  --brand-pack-dir PATH    Brand pack directory (theme, fonts, logos)
  --watermark-user NAME    User identifier for watermark
  --deterministic          Reproducible PDF output (SOURCE_DATE_EPOCH)
  --json                   Output structured JSON result
```

### Brand Management
```bash
md-to-pdf brand list                    # List available brands
md-to-pdf brand show BRAND_ID           # Show brand details
md-to-pdf brand migrate SRC DST         # Migrate  brand kit to v0.2 format
md-to-pdf brand validate PATH           # Validate brand pack schema
```

## What's Coming

**Planned for v0.3–v1.0:**
- Multiple rendering engines (WeasyPrint, etc.)
- Template packs (quote, user-manual, certificate, etc.)
- L3/L4/L5 advanced watermarking (steganography, encryption, signatures)
- MCP server, GitHub Action, Docker images
- GitHub Pages / PDF/A-2b compliance
- Policy-based brand locking, audit export

See [roadmap spec](docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md) for full vision.

## Development

### Contributing
- PRs welcome — see [CLAUDE.md](CLAUDE.md) for development guidelines
- Python 3.10+, mypy --strict, pytest
- Apache-2.0 licensed

### Project Structure
```
src/mdpdf/
├── cli/              # CLI entry points (brand, render, etc.)
├── pipeline/         # Orchestrator (render requests → PDFs)
├── markdown/         # Parser (markdown-it-py) + AST
├── render/           # ReportLab renderer engine
├── brand/            # Brand pack schema + registry
├── watermark/        # Watermark + audit logging
├── fonts/            # Font manager + CJK support
└── logging/          # Structured logging
```

## License

Apache-2.0 with explicit patent grant. See [LICENSE](LICENSE).

## Support

- **Documentation:** https://leiminray.github.io/md-to-pdf/
- **Issues:** [GitHub Issues](https://github.com/leiminray/md-to-pdf/issues)
- **Security:** See [SECURITY.md](SECURITY.md)

---

**Beta Note:** v0.2.1 is a new enterprise Markdown→PDF tool. Core features are stable. Additional functionality and optimizations are ongoing. Feedback welcome!
