# Python API

## Basic Usage

```python
from mdpdf.pipeline import Pipeline, RenderRequest
from pathlib import Path

pipeline = Pipeline()
request = RenderRequest(
    source_path=Path("input.md"),
    brand_id="idimsum"
)
result = pipeline.render(request)
print(f"PDF: {result.output_path}")
```

## With Watermark

```python
request = RenderRequest(
    source_path=Path("input.md"),
    brand_id="idimsum",
    watermark_user="alice@example.com"
)
result = pipeline.render(request)
```

## Deterministic Rendering

```python
request = RenderRequest(
    source_path=Path("input.md"),
    deterministic=True
)
result = pipeline.render(request)
```
