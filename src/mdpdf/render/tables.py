"""Content-weighted column-width algorithm (spec §2.1.5).

Inspired by v1.8.9's algorithm in `scripts/md_to_pdf.py`. For each column:
- raw_weight = max(cell length) * 0.6 + sum(cell length) / row_count * 0.4
Then normalise weights to sum to 1.0, multiply by available width, clamp
each column to [min_pct, max_pct] of available width, and re-distribute
the residual.
"""
from __future__ import annotations


def compute_column_widths(
    cells: list[list[str]],
    *,
    available_width_pt: float,
    min_pct: float = 17,
    max_pct: float = 70,
) -> list[float]:
    """Return per-column widths (pt) summing to `available_width_pt`."""
    if not cells:
        return []
    n_cols = max(len(row) for row in cells)
    if n_cols == 0:
        return []

    max_lens = [0] * n_cols
    sum_lens = [0] * n_cols
    n_rows = len(cells)
    for row in cells:
        for i, cell in enumerate(row):
            length = len(cell)
            if length > max_lens[i]:
                max_lens[i] = length
            sum_lens[i] += length

    raw_weights = [
        max_lens[i] * 0.6 + (sum_lens[i] / max(n_rows, 1)) * 0.4
        for i in range(n_cols)
    ]
    total_weight = sum(raw_weights) or float(n_cols)
    widths = [(w / total_weight) * available_width_pt for w in raw_weights]

    # Cap min_w when n_cols * min_pct > 100% — otherwise the minimum is
    # infeasible and the residual-distribution loop produces negative widths.
    min_w = min((min_pct / 100.0) * available_width_pt, available_width_pt / n_cols)
    max_w = (max_pct / 100.0) * available_width_pt

    # Iterate to convergence (≤ 6 passes per spec §2.1.5 reference)
    for _ in range(6):
        residual = 0.0
        clamped: list[bool] = [False] * n_cols
        for i in range(n_cols):
            if widths[i] < min_w:
                residual += widths[i] - min_w  # negative — debt to repay
                widths[i] = min_w
                clamped[i] = True
            elif widths[i] > max_w:
                residual += widths[i] - max_w  # positive — surplus to redistribute
                widths[i] = max_w
                clamped[i] = True
        if abs(residual) < 0.5:
            break
        free_total = sum(widths[i] for i in range(n_cols) if not clamped[i])
        if free_total <= 0:
            break
        for i in range(n_cols):
            if not clamped[i]:
                share = (widths[i] / free_total) * residual
                widths[i] += share

    # Final normalisation to handle floating drift — distribute among non-clamped
    # columns when possible; only fall back to widths[0] when every column is
    # clamped (so dropping below min_w there is unavoidable).
    drift = available_width_pt - sum(widths)
    if abs(drift) > 0.01 and widths:
        free_idx = [i for i in range(n_cols) if min_w < widths[i] < max_w]
        if free_idx:
            per = drift / len(free_idx)
            for i in free_idx:
                widths[i] += per
        else:
            widths[0] += drift
    return widths
