<!-- Release notes and version history for md-to-pdf. -->
# Changelog

All notable changes to md-to-pdf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v0.2.1.0.html).

## [0.2.1] - 2026-04-29

Initial beta release of md-to-pdf — a modern Markdown→PDF converter for enterprise use.

### Features

**Core Rendering**
- AST-first architecture: markdown-it-py → internal Document AST → ReportLab engine
- CommonMark + GitHub Flavored Markdown support
- Syntax highlighting via Pygments (auto-detect language tags)
- Tables with column alignment and proper formatting
- Embedded images (auto-downsampling, SVG via cairosvg)
- Mermaid diagrams (Kroki, Puppeteer, or pure-Python renderer)
- PDF bookmarks and table of contents from markdown outline
- CJK text support (Noto Sans SC bundled)

**Brand System**
- Brand v2 YAML schema with Pydantic validation
- 3-layer registry: project-level → user-level → built-in brands
- Customizable themes: colors, fonts, logos, footers
- Compliance text and watermarks
- Brand pack authoring guide
- CLI commands: `brand list`, `brand show`, `brand migrate`, `brand validate`
- Brand pack migration tool for legacy formats

**Watermarking & Audit**
- L1 visible watermarks: diagonal text overlay (configurable)
- L2 XMP metadata watermarks (invisible, tamper-detectable)
- Audit logging: JSONL format audit trail
- User watermark tracking (`--watermark-user`)
- Deterministic rendering for reproducible PDFs

**CLI & Python API**
- Command: `md-to-pdf INPUT.md -o OUTPUT.pdf [options]`
- Options: `--brand-pack-dir`, `--watermark-user`, `--deterministic`, `--json`, `--allow-remote-assets`
- Subcommands: `brand list/show/migrate/validate`
- Python API: `Pipeline.render(RenderRequest) → RenderResult`
- JSON output mode for structured automation

**Quality & DevOps**
- 443 passing unit + integration tests (81% coverage)
- Mypy `--strict` type checking
- Ruff lint + format enforcement
- Multi-OS CI: Python 3.10–3.13 on Ubuntu / macOS / Windows
- GitHub Pages documentation (mkdocs-material)
- Comprehensive golden test suite (AST, XMP, text-layer, layout fingerprints)

### Requirements

- Python 3.10+
- ReportLab for PDF rendering
- markdown-it-py for Markdown parsing
- Pydantic v2 for schema validation

### Known Limitations

- ReportLab engine only (other engines planned)
- Generic template only (specialized templates planned)
- No PDF/A-2b compliance yet (planned for future release)

### Roadmap

**v0.3–v1.0:** Multiple rendering engines, template packs, advanced watermarking, MCP server, GitHub Actions

**v1.0+:** Policy-based brand locking, PDF/A-2b, encryption, digital signatures

See [roadmap spec](docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md) for full vision.

---

**License:** Apache-2.0 with explicit patent grant
