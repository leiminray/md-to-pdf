# Determinism

With `--deterministic` + `SOURCE_DATE_EPOCH`, the same input + same
brand + same options + same `--watermark-user` produces a **byte-for-byte
identical PDF** across runs.

## How it works

- **render-id** — `sha256(input || brand || options || user)` reshaped
  into UUID v4 form, instead of random `uuid4()`.
- **create-date** — derived from `SOURCE_DATE_EPOCH` instead of
  `datetime.now()`.
- **PDF /ID** — `pikepdf.Pdf.save(deterministic_id=True)` derives the
  trailer `/ID` from a sha256 of the saved bytes instead of a random
  instance ID.
- **Mermaid renderer** — `pure` is rejected in deterministic mode (the
  pure-Python `mermaid-py` renderer is non-deterministic). Use `kroki`
  or `puppeteer`.

## Verify

```bash
SOURCE_DATE_EPOCH=1714400000 \
  md-to-pdf input.md -o /tmp/a.pdf --deterministic --watermark-user alice@example.com

SOURCE_DATE_EPOCH=1714400000 \
  md-to-pdf input.md -o /tmp/b.pdf --deterministic --watermark-user alice@example.com

shasum -a 256 /tmp/a.pdf /tmp/b.pdf
# Both digests must be identical.
```

The CI golden harness asserts this contract continuously across the
committed UAT fixtures.

## Deterministic golden suite

`tests/golden/` contains layered snapshot tests (AST + text-layer in
v0.2.1; XMP / layout / sha256 in follow-ups). Run with:

```bash
pytest tests/golden/                    # assert against committed baselines
pytest tests/golden/ --update-golden    # rewrite baselines (intentional change)
```
