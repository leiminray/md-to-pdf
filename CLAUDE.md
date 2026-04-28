# CLAUDE.md — md-to-pdf v0.2.1

Project guidance for AI agents working in this repo. Read this first.

## What this project is

A **Markdown → PDF** conversion engine with enterprise features:
- Brand packs (logo, colours, fonts, footer, compliance text)
- Watermarks (L1 visible + L2 XMP) and audit logging
- CJK text support (Chinese, Japanese, Korean)
- Mermaid diagrams, syntax-highlighted code, embedded images
- PDF bookmarks and table of contents
- AST-first architecture (markdown-it-py → ReportLab)

**Status:** v0.2.1 Beta — Core features complete. Additional functionality planned for v0.3–v1.0.

## Repository state

**Current version:** `0.2.1` (Beta)

| Layer | Status | Location |
|---|---|---|
| **Core engine** | ✅ Stable | `src/mdpdf/` (pipeline, cli, markdown/parser, render/reportlab, etc.) |
| **Brand packs** | ✅ Complete | `examples/brands/` (schema + 3-layer registry) |
| **Watermarking** | ✅ Complete | L1 (visible) + L2 (XMP metadata) |
| **CJK fonts** | ✅ Complete | Noto Sans SC + font manager in `src/mdpdf/fonts/` |
| **Tests** | ✅ 443 passing | `tests/unit/`, `tests/integration/`, `tests/golden/` |
| **Documentation** | ✅ Live | https://leiminray.github.io/md-to-pdf/ (mkdocs-material) |
| **CI/CD** | ✅ 16/16 passing | `.github/workflows/` (Python 3.10–3.13 × Linux/macOS/Windows) |

## Development conventions

- **Language:** Python 3.10+ (CI: 3.10–3.13)
- **Lint:** `ruff` (format + lint) + `mypy --strict` + `pyright`
- **Test:** `pytest` — target ≥80% coverage on `src/mdpdf/`
- **License:** Apache-2.0 (patent grant clause; do not change without discussion)
- **Commits:** Conventional Commits + DCO sign-off required
- **Branch protection:** PRs to `main` require passing CI

## Common commands

### Development environment

```bash
# Create venv
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Render a markdown file
.venv/bin/md-to-pdf input.md -o output.pdf

# With brand pack
.venv/bin/md-to-pdf input.md -o output.pdf --brand-pack path/to/brand

# List available brands
.venv/bin/md-to-pdf brand list

# Migrate v1 brand kit to v0.2.1
.venv/bin/md-to-pdf brand migrate /old/brand_kits/idimsum /new/location
```

### Testing & quality

```bash
# Run tests (443 passing)
.venv/bin/pytest -v

# Lint
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/

# Type check
.venv/bin/mypy --strict src/mdpdf

# Get coverage
.venv/bin/pytest --cov=src/mdpdf
```

## Architectural principles

- **AST-first.** All markdown → markdown-it-py → internal AST → render. Never regex-based markdown.
- **Single orchestrator.** Every render path goes through `Pipeline.render(RenderRequest) → RenderResult`.
- **Engine abstraction.** `RenderEngine` ABC with one concrete `engine_reportlab.py`; design for adding engines later.
- **Schema validation.** Brand packs + requests validate via Pydantic v2 before parsing.
- **CJK loudly.** Fail with clear error if CJK input found but fonts missing. No silent tofu.
- **No remote by default.** Remote assets rejected unless `--allow-remote-assets` flag set.
- **Atomic writes.** PDFs written to temp file, fsync'd, then renamed atomically.
- **Determinism contract.** With `SOURCE_DATE_EPOCH` + same input/brand/options, output is bit-identical.

## Where to put new things

| Artifact | Path |
|---|---|
| New source code | `src/mdpdf/<module>/` |
| New unit tests | `tests/unit/<module>/` |
| New integration tests | `tests/integration/` |
| Golden/UAT tests | `tests/golden/` |
| Example brands | `examples/brands/` |
| Example inputs | `examples/inputs/` |
| Feature specs | `docs/superpowers/specs/` |
| Implementation plans | `docs/superpowers/plans/` |
| User docs | `docs/` (mkdocs-material) |

## Roadmap

**v0.2.1 (current):** AST core, brand v2, watermarks, CJK support, audit logging ✅

**v0.3–v1.0:** Multiple rendering engines, template packs, advanced watermarking, MCP server, GitHub Actions

**Future (v0.2.1+):** Policy-based brand locking, PDF/A-2b, encryption, digital signatures

See [roadmap spec](docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md) for full vision.

## Working with the user

- User works on macOS, VS Code + Claude Code, Cursor
- Chinese (Simplified) + English — CJK rendering quality is critical
- Appreciates detailed spec discussions
- Prefers focused scope over premature features
- Respects the boundary between current release and future roadmap

## When you're unsure

1. Prefer simplicity over features
2. Ask before implementing things not in the current version
3. Check tests first — they document expected behavior
4. Reference the docs site for user-facing behavior
5. Minimal changes for bugs; surgical edits only

---

## Appendix · General LLM Behavioural Guidelines

Guidelines from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills).

### 1. Think Before Coding

Don't assume. State assumptions explicitly. Surface tradeoffs before implementing.

### 2. Simplicity First

Minimum code that solves the problem. No speculative features, abstractions, or error handling for impossible scenarios.

### 3. Surgical Changes

Touch only what you must. Match existing style. Remove only the orphans your changes created.

### 4. Goal-Driven Execution

Define success criteria. Turn vague requests ("make it work") into verifiable goals ("write a test, make it pass").

---

**These guidelines work if:** fewer unnecessary changes, fewer rewrites, and clarifying questions come before coding.
