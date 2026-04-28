# CLI Reference

## Rendering

```bash
md-to-pdf INPUT.md -o OUTPUT.pdf [OPTIONS]
```

### Options

- `--brand BRAND` — use named brand
- `--watermark-user EMAIL` — add user watermark  
- `--deterministic` — produce bit-identical PDF
- `--json` — output JSON metadata

## Brand Management

```bash
md-to-pdf brand list
md-to-pdf brand show BRAND_ID
md-to-pdf brand migrate OLD_PATH NEW_PATH
```

## System Diagnostics

```bash
md-to-pdf doctor        # Show environment info
md-to-pdf fonts list    # List available fonts
md-to-pdf fonts install FONT  # Install a font
```
