# Quickstart

## Render a Markdown file

```bash
md-to-pdf README.md -o README.pdf
```

The CLI writes the absolute path of the produced PDF to stdout (single line).
Use `--json` to get a structured `RenderResult` object instead.

## Apply a brand pack

```bash
md-to-pdf README.md -o README.pdf --brand acme
```

Brand packs are resolved via the 3-layer registry:

1. Project — `./brand_packs/<id>/`
2. User — `~/.md-to-pdf/brand_packs/<id>/`
3. Built-in — bundled with the package

See [Brand packs](brand-packs.md) for the schema.

## Apply a watermark

```bash
md-to-pdf REPORT.md -o REPORT.pdf --watermark-user alice@example.com
```

The default watermark level is `L1+L2`:

- **L1** — visible diagonal text on every page
- **L2** — XMP metadata embedded in the PDF (12 keys per spec §5.3)

To skip the L1 visible stamp: `--no-watermark`. To customise the L1 text:
`--watermark-text "DRAFT // {user} // {render_date}"`.

## Deterministic mode

```bash
SOURCE_DATE_EPOCH=1714400000 \
  md-to-pdf REPORT.md -o REPORT.pdf \
  --deterministic --watermark-user alice@example.com
```

With `--deterministic` + `SOURCE_DATE_EPOCH`, the same input + same
options + same `--watermark-user` produces a **byte-for-byte identical
PDF** across runs. See [Determinism](determinism.md).

## Diagnostics

```bash
md-to-pdf doctor
```

Prints a structured environment report (Python version, mdpdf version,
fonts, Mermaid renderer availability, brand registry, audit log path,
temp-paths writability). Add `--json` for machine-readable output.

## Audit log

Every render writes one `render.start` and one `render.complete` (or
`render.error`) JSONL event to `~/.md-to-pdf/audit.jsonl` (configurable
via `MD_PDF_AUDIT_PATH`). Disable with `--no-audit`.
