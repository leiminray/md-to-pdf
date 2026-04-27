"""Tests for content-weighted column-width algorithm (spec §2.1.5)."""
from mdpdf.render.tables import compute_column_widths


def test_uniform_content_yields_equal_widths() -> None:
    cells = [["a", "a", "a"], ["b", "b", "b"]]
    widths = compute_column_widths(cells, available_width_pt=300, min_pct=17, max_pct=70)
    assert len(widths) == 3
    assert all(abs(w - 100) < 1 for w in widths)


def test_long_first_column_grabs_more_width() -> None:
    cells = [
        ["very long header that needs lots of space", "x", "y"],
        ["another long entry here too please", "1", "2"],
    ]
    widths = compute_column_widths(cells, available_width_pt=300, min_pct=17, max_pct=70)
    assert widths[0] > widths[1]
    assert widths[0] > widths[2]


def test_no_column_starves_below_min_pct() -> None:
    cells = [["x" * 200, "a", "b"]]
    widths = compute_column_widths(cells, available_width_pt=300, min_pct=17, max_pct=70)
    for w in widths:
        assert w >= 0.17 * 300 - 0.5  # tolerance for rounding


def test_no_column_exceeds_max_pct() -> None:
    cells = [["x" * 200, "a", "b"]]
    widths = compute_column_widths(cells, available_width_pt=300, min_pct=17, max_pct=70)
    for w in widths:
        assert w <= 0.70 * 300 + 0.5


def test_widths_sum_to_available_width() -> None:
    cells = [["a", "b"], ["c", "d"]]
    widths = compute_column_widths(cells, available_width_pt=400, min_pct=17, max_pct=70)
    assert abs(sum(widths) - 400) < 1


def test_six_column_table_distributes_proportionally() -> None:
    cells = [
        ["h1", "h2", "h3", "header4", "h5", "h6"],
        ["short", "x", "y", "longer text here", "z", "w"],
    ]
    widths = compute_column_widths(cells, available_width_pt=540, min_pct=10, max_pct=70)
    assert len(widths) == 6
    assert widths[3] > widths[1]  # column 3 has the longest cell


def test_min_pct_infeasible_does_not_yield_negative_widths() -> None:
    """6 columns × 17% min_pct = 102% — infeasible. Algorithm must clamp the
    minimum to available_width / n_cols rather than producing a negative width
    via residual misdistribution. Previously triggered a ReportLab TypeError
    when the negative width hit RLTable.wrap().
    """
    cells = [
        ["col1", "col2", "col3", "col4", "col5", "col6"],
        ["short", "longer text", "medium", "x", "y", "z"],
        ["a", "b", "c", "d", "e", "f"],
        ["header here", "more", "content", "more text", "x", "y"],
    ]
    widths = compute_column_widths(
        cells, available_width_pt=493.0, min_pct=17, max_pct=70
    )
    assert len(widths) == 6
    assert all(w > 0 for w in widths)
    assert abs(sum(widths) - 493.0) < 1.0
