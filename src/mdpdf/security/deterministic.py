"""Determinism helpers.

These functions ensure that with ``--deterministic`` + ``SOURCE_DATE_EPOCH``,
identical inputs produce bit-identical PDFs. The key primitives are:

- ``derive_render_id`` — sha256-based UUID-shaped render ID (deterministic).
- ``serialise_options`` — canonical sorted-JSON representation of stable
  ``RenderRequest`` fields.
- ``frozen_create_date`` — ISO 8601 datetime from an epoch integer.
- ``freeze_pdf_dates`` — rewrites ``/Info`` ``/CreationDate`` + ``/ModDate``
  in the PDF to a fixed value derived from the epoch.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pikepdf


def derive_render_id(
    *,
    input_bytes: bytes,
    brand_id: str,
    brand_version: str,
    options_serialised: str,
    watermark_user: str | None,
) -> str:
    """Return a deterministic UUID-shaped render ID derived from the inputs.

    The ID is a sha256 hex digest reshaped into UUID v4 format
    (8-4-4-4-12 hex chars). It is NOT random — it is deterministic.

    The hash covers: input content, brand id+version, serialised options, and
    the watermark user. Changing any input changes the render ID.
    """
    payload = json.dumps(
        {
            "input_hash": hashlib.sha256(input_bytes).hexdigest(),
            "brand_id": brand_id,
            "brand_version": brand_version,
            "options": options_serialised,
            "watermark_user": watermark_user or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    h = digest[:32]
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def serialise_options(
    *,
    template: str,
    locale: str,
    watermark_level: str,
    watermark_custom_text: str | None,
    brand_overrides: dict[str, Any] | None,
) -> str:
    """Return a canonical JSON string of stable RenderRequest fields.

    Output is deterministic regardless of dict insertion order because
    ``brand_overrides`` is sorted into a list of [key, value] pairs.
    """
    payload: dict[str, Any] = {
        "template": template,
        "locale": locale,
        "watermark_level": watermark_level,
        "watermark_custom_text": watermark_custom_text,
        "brand_overrides": sorted(brand_overrides.items()) if brand_overrides else [],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def frozen_create_date(epoch: int | None = None) -> str:
    """Return an ISO 8601 datetime string.

    If *epoch* is given, the datetime is derived from it (UTC). If *epoch* is
    ``None``, the current UTC time is used. ``SOURCE_DATE_EPOCH`` parsing
    happens at the call site, not here, to keep this function easily testable.
    """
    if epoch is not None:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    else:
        dt = datetime.now(tz=timezone.utc)
    return dt.isoformat()


def _epoch_to_pdf_date(epoch: int) -> str:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.strftime("D:%Y%m%d%H%M%S+00'00'")


def freeze_pdf_dates(pdf_path: Path, epoch: int) -> None:
    """Rewrite ``/CreationDate`` and ``/ModDate`` in the PDF ``/Info`` dict.

    Updated atomically (temp file → rename).
    """
    pdf_date = _epoch_to_pdf_date(epoch)

    dir_path = pdf_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=dir_path, prefix=pdf_path.name + ".dates.", suffix=".tmp"
    )
    os.close(fd)
    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            with pdf.open_metadata(set_pikepdf_as_editor=False):
                pass
            pdf.docinfo["/CreationDate"] = pikepdf.String(pdf_date)
            pdf.docinfo["/ModDate"] = pikepdf.String(pdf_date)
            pdf.save(tmp_path_str, deterministic_id=True)

        os.replace(tmp_path_str, pdf_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path_str)
        raise
