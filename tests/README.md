# Tests

Test suite for md-to-pdf — covers unit, integration, and golden tests.

## Layout

```
tests/
├── unit/              # Unit tests for individual modules
│   ├── brand/         # Brand pack schema, registry, migration
│   ├── cache/         # Atomic write + temp file management
│   ├── fonts/         # Font manager + CJK detection
│   ├── markdown/      # Parser + AST + transformers
│   ├── render/        # ReportLab engine + flowables
│   └── renderers/     # Mermaid, code, image renderers
├── integration/       # End-to-end pipeline tests
│   └── fixtures/      # Sample markdown files
└── golden/            # Golden snapshot tests (AST, XMP, text-layer, layout)
```

## Run

From repository root:

```bash
# All tests
.venv/bin/pytest -v

# Just unit tests
.venv/bin/pytest tests/unit -v

# Just integration tests
.venv/bin/pytest tests/integration -v

# Coverage report
.venv/bin/pytest --cov=src/mdpdf --cov-report=term-missing
```

## Skipped tests

Some tests skip on platforms missing optional dependencies:

- **libcairo** required for SVG rendering — install via `brew install cairo` (macOS) or `apt install libcairo2-dev` (Linux)
- **KROKI_URL** required for Kroki Mermaid renderer integration tests — set if testing against a Kroki server
- **Platform-specific golden tests** for deterministic SHA256 only run on Linux (canonical platform for byte-identical output)

## Adding new tests

- **Unit tests**: Place under `tests/unit/<module>/` mirroring the source layout
- **Integration tests**: Place under `tests/integration/` for end-to-end behavior
- **Golden tests**: Use `tests/golden/conftest.py` helpers for AST/XMP/text-layer comparisons

Test naming: `test_<feature>_<scenario>` (e.g., `test_pipeline_renders_cjk_with_noto`).

## CI

Tests run on every push via GitHub Actions:
- Python 3.10–3.13
- Ubuntu, macOS, Windows
- Lint (ruff) + type check (mypy --strict)
- Golden + UAT suite on Linux (canonical platform)

See `.github/workflows/ci.yml` for the full matrix.
