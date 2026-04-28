"""PDF bookmark / outline generation.

Consumes `Document.outline` (a list of OutlineEntry produced by the
`collect_outline` transformer) and emits ReportLab `bookmarkPage` +
`addOutlineEntry` calls at heading flowable positions.

The Plan-3 approach: the engine wraps each Heading flowable in a
`HeadingBookmark` proxy that adds the bookmark when drawn. This avoids
the more complex `outlineEntry` / `bookmark` collection on canvas.
"""
from __future__ import annotations

from dataclasses import dataclass

from reportlab.platypus.flowables import Flowable

from mdpdf.markdown.ast import OutlineEntry


@dataclass
class HeadingBookmark(Flowable):
    """Wraps an inner Flowable, adds a PDF bookmark + outline entry on draw."""

    inner: Flowable
    entry: OutlineEntry

    def __post_init__(self) -> None:
        Flowable.__init__(self)

    def wrap(self, aW: float, aH: float) -> tuple[float, float]:  # noqa: N803 — ReportLab API
        return self.inner.wrap(aW, aH)

    def drawOn(  # type: ignore[no-untyped-def]  # noqa: N802 — ReportLab API name
        self,
        canvas,
        x: float,
        y: float,
        _sW: float = 0,  # noqa: N803 — ReportLab API name
    ) -> None:
        canvas.bookmarkPage(self.entry.bookmark_id)
        canvas.addOutlineEntry(
            self.entry.plain_text,
            self.entry.bookmark_id,
            level=self.entry.level - 1,
            closed=False,
        )
        self.inner.drawOn(canvas, x, y, _sW)  # type: ignore[call-arg]

    def draw(self) -> None:
        # Not invoked when drawOn is overridden.
        pass
