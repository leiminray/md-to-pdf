# CLI Reference

## Commands

```
md-to-pdf [OPTIONS] INPUT_PATH       # render markdown → PDF
md-to-pdf render INPUT_PATH ...      # explicit form (same as above)
md-to-pdf version                    # print version
md-to-pdf doctor [--json]            # environment health report
md-to-pdf brand list                 # list available brands
md-to-pdf brand show --brand-pack-dir <PATH>
md-to-pdf brand validate <PATH>
md-to-pdf brand migrate <V1_PATH> <V2_OUTPUT>
md-to-pdf fonts list [--json]
md-to-pdf fonts install <NAME>       # download + install a known font
```

## Render flags

| Flag | Purpose |
|------|---------|
| `-o`, `--output` | Output PDF path (required) |
| `--template` | Template id (supports only `generic`) |
| `--locale` | Output locale: `en` (default) or `zh-CN` |
| `--brand` | Brand id (resolved via 3-layer registry) |
| `--brand-pack-dir` | Explicit brand pack directory |
| `--brand-config` | Inline brand YAML file |
| `--legacy-brand` | Accept v1 `brand_kits/`-style layout (deprecated, removed in v3.0) |
| `--override key=value` | Brand field override (repeatable) |
| `--deterministic` | Bit-identical PDF for identical inputs (set `SOURCE_DATE_EPOCH` too) |
| `--watermark-user` | User identity in L1 + L2 watermarks (default `$USER`) |
| `--no-watermark` | Skip the L1 visible stamp (sets level to L0) |
| `--watermark-text` | Override L1 template (`{brand_name}`, `{user}`, `{render_date}`) |
| `--no-audit` | Skip writing audit-log events |
| `--mermaid-renderer` | `auto` / `kroki` / `puppeteer` / `pure` |
| `--kroki-url` | Override `KROKI_URL` env var |
| `--allow-remote-assets` | Allow `http(s)://` image URLs and brand assets |
| `--json` | Emit `RenderResult` as JSON |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | `PipelineError` (catch-all) |
| 2 | `TemplateError` (template not found / Click usage) |
| 3 | `BrandError` / `SecurityError` (config / policy) |
| 4 | `FontError` |
| 5 | `RendererError` (Mermaid / image / code) |
