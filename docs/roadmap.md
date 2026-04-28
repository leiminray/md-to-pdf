# Roadmap

## v0.2.1 — shipped (current release)

Core features in this release:

- **Markdown engine** — markdown-it-py → AST → ReportLab pipeline
- **AST transformers** — frontmatter strip, outline collection, run-on heading split, TOC promotion, metadata block filtering
- **Brand pack v2** — Pydantic schema with 3-layer registry (project / user / built-in)
- **Renderers** — Pygments syntax highlighting, Mermaid chain (Kroki / Puppeteer / pure-Python), image renderer with auto-downsampling
- **Custom flowables** — FencedCodeCard, MermaidImage, CalloutBox, ListBlock, PDF outline
- **Watermarks** — L1 visible diagonal overlay + L2 XMP metadata
- **Audit log** — JSONL format audit trail
- **Determinism** — `--deterministic` + `SOURCE_DATE_EPOCH` → byte-identical PDF
- **Post-process** — footer + issuer card pipeline
- **CLI** — `render`, `brand list/show/migrate/validate`, `doctor`, `fonts list/install`
- **Quality** — 443 passing tests, multi-OS CI (Python 3.10–3.13 × Linux/macOS/Windows)
- **Documentation** — mkdocs-material site

## v0.3 — planned

- Template-pack system (typed front-matter, computed fields, registry)
- `quote` / `user-manual` / `certificate` templates
- Multiple rendering engines (e.g. WeasyPrint)

## v0.4 — planned

- MCP server / Skill bundle
- GitHub Action for `md-to-pdf` in CI
- Docker images

## v1.0 — planned

- L3 steganographic / L4 encrypted / L5 signed watermarks
- `policy.yaml` brand-lock / template-lock
- PDF/A-2b output
- `forensics extract` / `forensics verify` subcommands
- HMAC tamper-protection on XMP

## Long-term

- Removal of deprecated `--legacy-brand` and `mdpdf.brand.legacy` adapter
- Refinement of brand schema based on user feedback
- Performance optimization for large documents

See `docs/superpowers/specs/` in the repo for detailed long-form specifications.
