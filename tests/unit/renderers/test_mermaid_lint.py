"""Tests for Mermaid input lint sandbox."""
import pytest

from mdpdf.errors import RendererError
from mdpdf.renderers.mermaid_lint import lint_mermaid_source


def test_clean_flowchart_passes():
    src = "graph TD\n  A --> B\n  B --> C\n"
    lint_mermaid_source(src)  # no exception


def test_rejects_oversized_source():
    src = "graph TD\n" + "  A --> B\n" * 10000
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_RESOURCE_LIMIT"
    assert "50000" in ei.value.user_message or "50K" in ei.value.user_message


def test_rejects_too_many_nodes():
    nodes = "  ".join(f"N{i} --> N{i+1}" for i in range(600))
    src = f"graph TD\n  {nodes}\n"
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_RESOURCE_LIMIT"


def test_rejects_deep_subgraph_nesting():
    deep = "graph TD\n"
    for i in range(15):
        deep += "  " * i + f"subgraph s{i}\n"
    deep += "    A --> B\n"
    for i in range(15):
        deep += "  " * (15 - i - 1) + "end\n"
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(deep)
    assert ei.value.code == "MERMAID_RESOURCE_LIMIT"


def test_rejects_click_callback_javascript():
    src = "graph TD\n  A --> B\n  click A callback javascript:alert(1)\n"
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_INVALID_SYNTAX"


def test_rejects_raw_script_tag():
    src = "graph TD\n  A --> B\n  <script>alert(1)</script>\n"
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_INVALID_SYNTAX"


def test_rejects_style_attribute_with_url():
    src = 'graph TD\n  A["foo" style="background:url(http://evil)"]\n'
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_INVALID_SYNTAX"


def test_rejects_img_remote_src():
    src = 'graph TD\n  A --> B\n  A --- img[<img src="http://evil/x.png" />]\n'
    with pytest.raises(RendererError) as ei:
        lint_mermaid_source(src)
    assert ei.value.code == "MERMAID_INVALID_SYNTAX"
