"""L2 XMP metadata watermark (spec §5.3).

Writes 12 XMP keys into the PDF using pikepdf's ``open_metadata()`` context
manager. The ``mdpdf:`` namespace is registered via pikepdf's namespace registry.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pikepdf

_MDPDF_NS = "https://md-to-pdf.dev/xmp/1.0/"
_PRODUCER = "md-to-pdf 2.0"
_CREATOR_TOOL = "md-to-pdf 2.0"


def apply_l2_xmp(
    pdf_path: Path,
    *,
    dc_creator: str,
    dc_title: str,
    render_id: str,
    render_user: str,
    render_host: str,
    brand_id: str,
    brand_version: str,
    input_hash: str,
    create_date: str,
    watermark_level: str = "L1+L2",
) -> None:
    """Write all 12 L2 XMP metadata keys to *pdf_path* (in-place, atomically)."""
    dir_path = pdf_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=dir_path, prefix=pdf_path.name + ".xmp.", suffix=".tmp"
    )
    os.close(fd)
    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta.register_xml_namespace(_MDPDF_NS, "mdpdf")
                meta["dc:creator"] = dc_creator
                meta["dc:title"] = dc_title
                meta["pdf:Producer"] = _PRODUCER
                meta["xmp:CreatorTool"] = _CREATOR_TOOL
                meta["xmp:CreateDate"] = create_date
                meta["mdpdf:RenderId"] = render_id
                meta["mdpdf:RenderUser"] = render_user
                meta["mdpdf:RenderHost"] = render_host
                meta["mdpdf:BrandId"] = brand_id
                meta["mdpdf:BrandVersion"] = brand_version
                meta["mdpdf:InputHash"] = input_hash
                meta["mdpdf:WatermarkLevel"] = watermark_level

            pdf.save(tmp_path_str)

        os.replace(tmp_path_str, pdf_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path_str)
        raise
