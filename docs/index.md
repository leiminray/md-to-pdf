# md-to-pdf

A **Markdown → PDF** conversion engine for enterprise use:

- Brand kits (logo, colours, fonts, footer, compliance text)
- Watermarks for data security (L1 visible diagonal + L2 XMP metadata)
- Mermaid diagrams (sandboxed; Kroki / Puppeteer / pure-Python)
- Syntax-highlighted code (Pygments)
- Embedded images (auto-downsample raster + cairosvg SVG)
- CJK text (Noto Sans SC bundled)
- PDF bookmarks + table of contents
- Deterministic mode for bit-identical reproducible output
- JSONL audit log
- CLI + Python API + GitHub Actions distribution

## Install

```bash
pip install md-to-pdf
```

Optional extras:

| Extra | Purpose |
|-------|---------|
| `[mermaid-pure]` | Pure-Python Mermaid renderer (no Kroki / Node required) |
| `[dev]` | Development tools (pytest, ruff, mypy) |

## Quickstart

```bash
md-to-pdf input.md -o output.pdf
md-to-pdf input.md -o output.pdf --brand acme --deterministic
md-to-pdf doctor                       # verify your environment
md-to-pdf brand list                   # list available brands
md-to-pdf fonts list                   # list available fonts
```

See [Quickstart](quickstart.md) for the full guide.
