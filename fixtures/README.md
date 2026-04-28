# Fixtures

Sample Markdown documents and assets used by md-to-pdf tests.

## Layout

```
fixtures/
├── branch_ops_ai_robot_product_brief.md  # Comprehensive UAT fixture (11 scenarios)
├── fenced-mermaid-smoke.md               # Smoke test for Mermaid rendering
├── mermaid-noto-presets.md               # Mermaid + CJK font presets
├── images/                               # Image assets referenced by fixtures
│   ├── architecture.png
│   ├── architecture-large.png
│   ├── icon-256.png
│   └── system-flow.svg
└── out/                                  # Local render outputs (gitignored)
```

## Purpose

Fixtures exercise end-to-end behavior of the Markdown→PDF pipeline:
- **branch_ops_ai_robot_product_brief.md** — comprehensive 11-scenario UAT covering tables, code, Mermaid, images, watermarks, CJK
- **fenced-mermaid-smoke.md** — minimal Mermaid block to verify the renderer chain
- **mermaid-noto-presets.md** — Mermaid + Noto Sans SC font interaction tests

## Adding a fixture

When adding a new fixture, also add a corresponding test in `tests/integration/` or `tests/golden/` that asserts the expected rendered behavior. Keep fixture sizes reasonable so test runs stay fast.

## Image assets

Referenced PNG/SVG assets live under `images/`. SVG assets are converted to PNG via cairosvg during rendering — install `libcairo` if you need to test SVG locally.
