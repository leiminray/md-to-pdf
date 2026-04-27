# Roadmap

## v2.0 — shipped

Plans 1–5 (this release):

- **Plan 1** — walking skeleton: markdown-it-py → AST → ReportLab.
- **Plan 2** — AST transformers + brand v2 schema + 3-layer registry.
- **Plan 3** — renderers (Pygments / Mermaid chain / image) + custom
  Flowables (FencedCodeCard / MermaidImage / CalloutBox / ListBlock /
  PDF outline).
- **Plan 4** — L1 visible + L2 XMP watermarks, JSONL audit log,
  deterministic mode (`--deterministic` + `SOURCE_DATE_EPOCH` →
  byte-for-byte identical PDF), post-process pipeline (footer +
  issuer card).
- **Plan 5** — comprehensive UAT fixture, golden harness foundation,
  `doctor` + `fonts list/install` subcommands, CI matrix expansion
  (Python 3.10–3.13 × Ubuntu/macOS/Windows + libcairo + Kroki),
  `--legacy-brand` deprecation, mkdocs-material site scaffold.

## v2.1 — planned

- Template-pack system (typed front-matter, computed fields, registry)
- `quote` / `user-manual` / `certificate` templates
- Additional golden-harness layers (XMP / layout fingerprint / sha256)

## v2.2 — planned

- MCP server / Skill bundle
- GitHub Action for `md-to-pdf` in CI
- Docker images

## v2.3 — planned

- L3 steganographic / L4 encrypted / L5 signed watermarks
- `policy.yaml` brand-lock / template-lock
- PDF/A-2b output
- `forensics extract` / `forensics verify` subcommands
- HMAC tamper-protection on XMP

## v3.0 — planned

- Remove `--legacy-brand` and `mdpdf.brand.legacy` (deprecated since v2.0)
- Remove the v1.8.9 monolith remnants (already removed in v2.0 if the
  parity gate is met)

See `docs/superpowers/specs/2026-04-25-md-to-pdf-v2.x-roadmap.md` in the
repo for the full long-form roadmap.
