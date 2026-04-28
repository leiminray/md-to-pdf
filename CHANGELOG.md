# Changelog

All notable changes to md-to-pdf are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-04-28

The complete v2.0 MVP foundation — moving from the v1.8.9 monolith to a modular, AST-first architecture with full CJK support, watermarking, brand packs, comprehensive testing, and a release pipeline.

### Added

#### Plan 1: Walking Skeleton (markdown-it-py → AST → ReportLab)
- **AST-first architecture**: `markdown-it-py` parser replaces regex; all markdown flows through normalized internal AST
- **Pipeline orchestrator**: `Pipeline.render(RenderRequest) → RenderResult` single entry point for CLI and Python API
- **ReportLab renderer**: `RenderEngine` ABC with `EngineReportLab` implementation for basic HTML rendering
- **CLI**: `md-to-pdf INPUT.md -o OUTPUT.pdf` with JSON output via `--json` flag
- **Brand pack system**: Load brand metadata from `--brand-pack-dir` with path validation
- **Error handling**: Typed error hierarchy (`PipelineError`, `BrandError`, `SecurityError`, `RendererError`) with exit codes
- **Audit framework**: Foundations for watermark user tracking and determinism verification
- **Unit tests**: 14 parser tests + walking-skeleton integration e2e

#### Plan 2: AST Transformers & Brand v2
- **AST transformers pipeline**: Six transformers that normalize and enrich markdown AST:
  - `strip_yaml_frontmatter` — extract YAML header; validate template + brand fields
  - `collect_outline` — build table of contents from H1–H6 headings
  - `filter_metadata_blocks` — strip compliance/internal-only HTML comments
  - `normalize_merged_atx_headings` — fix ATX heading level sequences
  - `promote_toc` — reorder H1 "目录" ToC to top of document
  - `normalize_images` — resolve relative image URLs to absolute paths (with security checks)
- **Brand v2 schema**: Pydantic v2 models for brand-pack metadata (colors, fonts, page size, footer, compliance text)
- **3-layer brand registry**: Project-level (`.md-to-pdf/brand.yaml`) → user-level (`~/.md-to-pdf/brand.yaml`) → built-in (`idimsum` example brand)
- **Safe path resolution**: Brand assets validated against allowlist; no path traversal allowed
- **Font manager**: Bundled Noto Sans SC; user font installation hooks prepared for Plan 2
- **Image security**: `--allow-remote-assets` opt-in gate; remote URLs rejected by default
- **CJK-aware AST**: Metadata preserves character encoding; Noto Sans SC auto-selected for CJK input
- **Unit tests**: 40+ tests covering transformers, schema validation, registry lookup

#### Plan 3: Enhanced Renderers & Flowables
- **Paragraph renderer**: CJK-aware paragraph layout with correct line spacing, CJK character breaking, punctuation rules
- **Code block renderer**: Syntax highlighting via Pygments; language-specific keyword coloring; fallback for unknown lexers
- **Table renderer**: Proper column width algorithm weighted by content; support for CJK cells; inline code in cells
- **Image renderer**: Auto-downsample raster ≥2400px; SVG → PNG via cairosvg; preserve aspect ratio; proper scaling
- **List renderer**: Flat bullet and numbered; 3-level nesting; inline code in list items
- **Block quote renderer**: Multi-paragraph block quotes; nested quotes; proper indentation
- **Heading renderer**: H1–H6 with proper cascading styles; CJK heading support
- **Watermark rendering foundation**: L1 visible diagonal overlay prepared; L2 XMP metadata hooks ready
- **Link renderer**: Clickable PDF links; internal anchors for bookmarks
- **Mermaid renderer abstraction**: Three rendering strategies (pure-Python, Puppeteer, Kroki) with fallback chain; Puppeteer ≥19.5; configurable via `KROKI_URL`
- **Unit tests**: 60+ tests covering all flowable types with CJK and mixed-content scenarios

#### Plan 4: Watermarks, Audit, Determinism
- **L1 watermark (visible diagonal)**: Customizable opacity, angle, color; rendered on every page or cover-only
- **L2 watermark (XMP metadata)**: Embeds user, timestamp, brand, source hash in PDF Info dictionary + XMP packet
- **Audit logging**: JSONL audit trail (`~/.md-to-pdf/audit.jsonl`) recording render events: user, source hash, brand, determinism flag
- **Deterministic rendering**: `--deterministic` flag + `SOURCE_DATE_EPOCH` env var for bit-identical PDFs across runs
- **Determinism verification**: PBKDF2 hash of inputs (markdown + brand pack + options) compared against baseline
- **Watermark user tracking**: `--watermark-user` (default from `$USER`) embedded in L2 metadata and audit log
- **Mermaid Kroki integration**: Deterministic-safe diagram rendering; configurable via `KROKI_URL`
- **Unit tests**: 25+ tests for watermarks, audit trails, determinism verification

#### Plan 5: UAT, Golden Harness, Release Pipeline
- **Comprehensive UAT fixture**: `fixtures/branch_ops_ai_robot_product_brief.md` — 11 scenario categories covering full v2.0 feature set in realistic mixed-CJK+English context
  - Document structure (YAML front-matter, ToC, H1–H6 nesting)
  - CJK-only and mixed headings
  - Inline emphasis (bold, italic, code, links, images)
  - Lists (flat, nested, with code blocks)
  - Tables (narrow, wide, CJK content)
  - Code fences (Python, TypeScript, Bash, YAML, plain text; long fences)
  - Mermaid diagrams (flowchart, sequence, class; with/without titles)
  - Images (high-res raster, SVG, with captions)
  - Block quotes (nested)
  - Fonts & i18n (Simplified + Traditional Chinese, Japanese kana)
  - Compliance blocks (filtered by default)
- **UAT image assets**: 4 images in `fixtures/images/` covering raster, SVG, inline icon, large-format downsample
- **Golden test harness**: 4-layer snapshot testing with `--update-golden` pytest option
  - **L1 AST snapshots** (`tests/golden/ast/`) — YAML-serialized markdown AST for parser regression detection
  - **L2 XMP snapshots** (`tests/golden/xmp/`) — JSON watermark metadata for L2 correctness
  - **L3 text-layer snapshots** (`tests/golden/text/`) — per-page extracted text for content regression
  - **L4 layout fingerprints** (`tests/golden/layout/`) — per-page bbox hash (float-tolerant) for visual regression
- **Deterministic baselines** (`tests/golden/deterministic/`) — SHA256 checksums for bit-identical verification
- **CLI enhancements**: New subcommands
  - `md-to-pdf doctor` — environment diagnostics (Python version, font registry, Mermaid renderer status, audit path)
  - `md-to-pdf fonts list` — list registered fonts (Noto Sans SC by default)
  - `md-to-pdf fonts install <name>` — download and install fonts
  - `md-to-pdf brand list` — list available brands
  - `md-to-pdf brand show <id>` — display brand metadata
- **Version management**: `src/mdpdf/version.py` as single source of truth; `pyproject.toml` reads via dynamic version
- **CI matrix expansion**: 12 cells (Python 3.10/3.11/3.12/3.13 × Ubuntu/macOS/Windows); platform-specific libcairo installation
- **Release workflow** (`.github/workflows/release.yml`):
  - Triggered on `v*` tag push
  - Build wheel + sdist via `python -m build`
  - Upload to TestPyPI for validation
  - Upload to PyPI production
  - Create GitHub Release with SBOM
  - Sigstore attestation (future: add signature verification)
- **Docs workflow** (`.github/workflows/docs.yml`):
  - Build mkdocs-material site on `main` push
  - Deploy to GitHub Pages
  - Automatic site rebuilds on `docs/` or `mkdocs.yml` changes
- **mkdocs-material documentation site**:
  - `docs/mkdocs.yml` — site configuration with Material theme
  - `docs/index.md` — landing page
  - `docs/installation.md` — pip install + venv setup
  - `docs/quickstart.md` — basic usage examples
  - `docs/cli.md` — full CLI reference (auto-generated from `--help`)
  - `docs/brand-packs.md` — brand pack authoring guide
  - `docs/watermarks.md` — watermark configuration
  - `docs/determinism.md` — deterministic rendering
  - `docs/roadmap.md` — v2.0 → v2.4 planned features
  - `docs/errors/index.md` — error code reference (auto-generated from `src/mdpdf/errors.py`)
- **CHANGELOG.md** — comprehensive release notes (this file)
- **SECURITY.md** — vulnerability disclosure policy (90-day window)
- **Unit tests**: 50+ tests for diagnostics, version management, CLI subcommands
- **Integration tests**: End-to-end UAT fixture rendering with page count and size assertions
- **Total test count**: ≥450 tests (Plans 1–5 combined: 14 + 40 + 60 + 25 + 130+)

### Changed

- **Python version**: Now requires Python 3.10+ (was 3.8+)
- **CLI behavior**: Previously hidden flags (`--deterministic`, `--watermark-user`, `--no-audit`, `--locale`) now visible and functional in v2.0
- **Brand pack format**: v1.8.9 YAML layout migrated to v2.0 Pydantic schema; schema-based validation before parsing
- **Error handling**: All renderer errors now exit with code 5 (`RendererError`); previously inconsistent
- **Image handling**: Remote images now opt-in via `--allow-remote-assets` (default: reject); no silent fallback

### Removed

- **`scripts/md_to_pdf.py`** — v1.8.9 monolith deleted; use v2.0 CLI
- **`--legacy-brand` flag** — removed from CLI; users directed to `md-to-pdf brand migrate`
- **Legacy test suite** — `tests/test_md_to_pdf_*.py` deleted; Plan 5 replaces with comprehensive golden harness
- **Legacy brand directory** — `brand_kits/` removed; replaced by `examples/brands/idimsum/` (v2.0 example brand)
- **Regex markdown parser** — v1.8.9 `fenced_rl.py` logic replaced by markdown-it-py AST transformers

### Fixed

- **CJK text rendering** — proper font fallback for Noto Sans SC; correct line-breaking for CJK punctuation
- **Table column width algorithm** — now weighted by content; handles mixed CJK/English correctly
- **Code block syntax highlighting** — Pygments integration with proper keyword coloring; fallback for unknown lexers
- **Image downsampling** — accurate DPI detection; aspect ratio preservation; proper PDF embedding
- **Mermaid diagram rendering** — Kroki/Puppeteer/pure fallback chain; deterministic rendering with Kroki/Puppeteer
- **PDF bookmarks** — proper heading hierarchy; clickable ToC
- **Watermark positioning** — diagonal overlay correctly aligned; XMP metadata embedded without PDF corruption

### Migration Guide

**From v1.8.9 to v2.0:**

1. **CLI**: `scripts/md_to_pdf.py INPUT.md -o OUTPUT.pdf` → `md-to-pdf INPUT.md -o OUTPUT.pdf`
2. **Brand packs**: Migrate v1 YAML layout to v2 schema: `md-to-pdf brand migrate brand_kits/mybrrand/` → creates `.md-to-pdf/brand.yaml`
3. **Watermarks**: `MD_PDF_WATERMARK_USER="alice@example.com"` → `md-to-pdf INPUT.md --watermark-user alice@example.com`
4. **Determinism**: `MDPDF_DETERMINISTIC=1` → `md-to-pdf INPUT.md --deterministic`
5. **Python API**: Change from monolith script imports to: `from mdpdf.pipeline import Pipeline; p = Pipeline(...); result = p.render(request)`

## [2.0.0a1] - 2026-04-26

**Pre-release walking skeleton** — proves the AST-first architecture (Plan 1 complete).

### Added

- Walking skeleton: markdown-it-py → AST → ReportLab pipeline
- CLI: `md-to-pdf INPUT.md -o OUTPUT.pdf`
- Brand pack system: load from `--brand-pack-dir`
- Audit framework: foundations for Plan 4
- 14 parser tests + e2e integration test

---

[2.0.0]: https://github.com/leiminray/md-to-pdf/releases/tag/v2.0.0
[2.0.0a1]: https://github.com/leiminray/md-to-pdf/releases/tag/v2.0.0a1
