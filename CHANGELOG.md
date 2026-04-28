# Changelog

All notable changes to md-to-pdf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-04-28

v2.0.0 is the first release of the modular, AST-first md-to-pdf v2 architecture. It replaces the v1.8.9 monolith with a pipeline-based renderer supporting markdown-it-py parsing, brand v2 schema, watermarks, and deterministic output.

### Added

**Architecture & Parsing**
- AST-first rendering pipeline: markdown-it-py → internal Document AST → ReportLab engine
- Transformer system for AST manipulation: `strip_yaml_frontmatter`, `collect_outline`, `filter_metadata_blocks`, etc.
- Multi-step validation: Pydantic schemas for brand packs, requests, and configuration
- Structured error handling with specific error codes and CLI hints

**Brand System (v2)**
- Brand v2 schema: YAML with Pydantic validation (metadata, colors, fonts, logo, footer, compliance text)
- 3-layer registry: project-level → user-level → built-in brands
- Brand pack authoring guide in docs
- `md-to-pdf brand list`, `brand show`, `brand migrate` commands
- Auto-detection of brand pack from directory structure

**Rendering & Content**
- ReportLab engine with enhanced flowables for improved layout
- Syntax highlighting via Pygments (HTML language tags auto-detect)
- Improved table handling with column alignment and spans
- CJK text support (Noto Sans SC bundled; Plan 2 adds font manager)
- Embedded image auto-downsampling (raster) and SVG via cairosvg
- Mermaid diagrams (sandboxed via Kroki, Puppeteer, or pure-Python renderer)
- PDF bookmarks and table of contents from markdown outline

**Watermarks & Security**
- **L1 watermarks**: Visible diagonal text overlay (configurable size/opacity/color)
- **L2 watermarks**: XMP metadata watermarks (invisible, tamper-detectable)
- Audit logging: JSONL audit trail for deterministic renders (`--no-audit` flag to skip)
- User watermark tracking (`--watermark-user EMAIL`)

**Determinism & Reproducibility**
- `--deterministic` flag for bit-identical PDF output (with reproducible random seed)
- `SOURCE_DATE_EPOCH` environment variable support for build timestamps
- Audit log captures render environment and input hashes for reproducibility verification

**CLI & API**
- CLI: `md-to-pdf INPUT.md -o OUTPUT.pdf [options]`
- Options: `--brand`, `--watermark-user`, `--deterministic`, `--json`, `--audit-log`, `--allow-remote-assets`
- Subcommands: `doctor`, `fonts list/install`, `brand list/show/migrate`
- Python API: `Pipeline.render(RenderRequest) → RenderResult`
- JSON output mode for structured automation

**DevOps & Quality**
- Multi-OS CI matrix: Python 3.10–3.13 on Ubuntu / macOS / Windows
- 443 passing unit + integration tests (81% coverage on src/mdpdf/)
- Mypy `--strict` type checking across codebase
- Ruff lint + format enforcement
- GitHub Actions: CI (lint + test + golden) + Docs (mkdocs → GitHub Pages)
- Comprehensive UAT fixture (`branch_ops_ai_robot_product_brief.md`) with 11 scenarios
- Golden harness with L1 (AST), L2 (XMP), L3 (text layer), and L4 (layout fingerprint) checks

**Documentation & Community**
- mkdocs-material site with Quickstart, CLI Reference, Brand Authoring, Roadmap
- Automated doc publishing to GitHub Pages on push-to-main
- Apache-2.0 license with explicit patent grant
- Repository with branch protection and DCO sign-off

### Changed

- **Requires Python 3.10+** (was 3.8+)
- Brand pack YAML format: v1.8.9 layout → v2.0 schema (migration tool provided)
- CLI output format: human-readable progress + structured JSON metadata on request
- Test paths scoped to v2 only (`testpaths = ["tests/unit", "tests/integration", "tests/golden"]`)

### Removed

- v1.8.9 monolith (`scripts/md_to_pdf.py`) — will be deleted in Plan 5 cleanup
- Legacy brand directory layout (`brand_kits/`) — replaced by distributed brand system
- v1.8.9 regex-based markdown parser — replaced by markdown-it-py AST
- Regex-based content extraction — all content now goes through AST transformers
- `--legacy-brand` CLI flag (v1 brand packs must be migrated via `brand migrate`)
- Legacy test suite (`tests/test_md_to_pdf_*.py`) — preserved on disk for reference but not run

### Known Limitations (Addressed in Plans 2–5)

- **CJK rendering**: Noto Sans SC bundled but Plan 2 adds font manager for other fonts
- **Mermaid diagrams**: Only pure-Python and Kroki renderers in v2.0a1; Puppeteer support added in Plan 3
- **Remote assets**: Disabled by default; requires `--allow-remote-assets` flag (Plan 4 adds network policy)
- **Watermarks**: L1 and L2 only; L3 (steganographic), L4 (encryption), L5 (signature) planned for v2.3
- **Determinism**: Kroki and Puppeteer Mermaid only; pure-Python renderer not yet deterministic
- **Templates**: Only `generic` template in v2.0; `quote`, `certificate`, `user-manual` planned for v2.1
- **Audit log**: User-mode JSONL only; system-wide audit policy planned for v2.3

### Security

- No remote network access by default; `--allow-remote-assets` is opt-in
- Atomic PDF writes with fsync + rename to prevent partial output
- Watermark XMP tamper-detection (verified in L2 golden suite)
- Mermaid rendering sandboxed via Kroki (remote) or Puppeteer (isolated process)

## [2.0.0a1] - 2026-04-26

Initial alpha release of the v2 walking skeleton.

### Added

- Markdown-it-py parser and internal AST representation
- ReportLab-based PDF rendering engine
- Basic brand pack support
- CLI framework with subcommand structure
- Audit logging foundations
- 81 unit + integration tests
- Golden test harness (L1 AST snapshots)

---

[2.0.0]: https://github.com/leiminray/md-to-pdf/releases/tag/v2.0.0
[2.0.0a1]: https://github.com/leiminray/md-to-pdf/releases/tag/v2.0.0a1
