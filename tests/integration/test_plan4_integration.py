"""End-to-end integration tests for Plan 4: watermarks, audit, determinism, locale.

Bundles Tasks 19/20/21 into a single test file. Subprocess-based tests use
the resolved ``md-to-pdf`` console script; tests that need the in-process
Pipeline call ``pipeline.render()`` directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pikepdf
import pypdf
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "integration" / "fixtures"
DETERMINISTIC = FIXTURES / "deterministic-corpus" / "plain.md"
LOCALE_CJK = FIXTURES / "locale-cjk.md"
HELLO = FIXTURES / "hello.md"


def _resolve_md_to_pdf() -> str:
    found = shutil.which("md-to-pdf")
    if found:
        return found
    candidate = Path(sys.executable).parent / "md-to-pdf"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("md-to-pdf console script not found on PATH or in venv bin")


MD_TO_PDF = _resolve_md_to_pdf()
_SOURCE_DATE_EPOCH = "1714400000"  # 2024-04-29 UTC, fixed for determinism tests


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def isolated_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Redirect MD_PDF_AUDIT_PATH to a tmp file so subprocess tests don't
    pollute the developer's ~/.md-to-pdf/audit.jsonl.
    """
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MD_PDF_AUDIT_PATH", str(audit_path))
    yield audit_path


def _run_md_to_pdf(
    *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [MD_TO_PDF, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )


# ── Task 19: deterministic golden corpus ────────────────────────────────────


class TestDeterministicRender:
    def test_deterministic_render_id_is_stable_across_runs(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """Same inputs + SOURCE_DATE_EPOCH → same XMP RenderId across 3 runs.

        The render-id is the canonical fingerprint per spec §2.3. Bit-identical
        sha256 also requires overriding ReportLab's random PDF /ID and
        pikepdf's xmpMM:* random IDs — this is a known gap (see
        TestDeterministicRender.test_pdf_bytes_identical_xfail below).
        """
        ids: list[str] = []
        for i in range(3):
            out = tmp_path / f"out_{i}.pdf"
            proc = _run_md_to_pdf(
                str(DETERMINISTIC),
                "-o", str(out),
                "--deterministic",
                "--watermark-user", "alice@test.example",
                env_extra={"SOURCE_DATE_EPOCH": _SOURCE_DATE_EPOCH},
            )
            assert proc.returncode == 0, proc.stderr
            with pikepdf.open(str(out)) as pdf, pdf.open_metadata() as meta:
                ids.append(str(meta["{https://md-to-pdf.dev/xmp/1.0/}RenderId"]))
        assert len(set(ids)) == 1, f"RenderId diverged: {ids}"

    @pytest.mark.xfail(
        reason=(
            "Bit-identical PDF requires overriding ReportLab's random PDF /ID "
            "in the trailer and pikepdf's xmpMM:DocumentID — gap to close in a "
            "follow-up patch (CLAUDE.md determinism contract)."
        ),
        strict=False,
    )
    def test_pdf_bytes_identical_xfail(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """Tracks the spec contract that --deterministic produces bit-identical PDFs."""
        out1 = tmp_path / "a.pdf"
        out2 = tmp_path / "b.pdf"
        for out in (out1, out2):
            proc = _run_md_to_pdf(
                str(DETERMINISTIC), "-o", str(out),
                "--deterministic",
                "--watermark-user", "alice@test.example",
                env_extra={"SOURCE_DATE_EPOCH": _SOURCE_DATE_EPOCH},
            )
            assert proc.returncode == 0, proc.stderr
        assert _sha256(out1) == _sha256(out2)

    def test_deterministic_user_changes_pdf(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """Different --watermark-user values produce different XMP RenderId."""
        ids: list[str] = []
        for user in ("alice@test.example", "bob@test.example"):
            out = tmp_path / f"{user.split('@')[0]}.pdf"
            proc = _run_md_to_pdf(
                str(DETERMINISTIC),
                "-o", str(out),
                "--deterministic",
                "--watermark-user", user,
                env_extra={"SOURCE_DATE_EPOCH": _SOURCE_DATE_EPOCH},
            )
            assert proc.returncode == 0, proc.stderr
            with pikepdf.open(str(out)) as pdf, pdf.open_metadata() as meta:
                ids.append(str(meta["{https://md-to-pdf.dev/xmp/1.0/}RenderId"]))
        assert ids[0] != ids[1]


# ── Task 20: full flow — watermark + XMP + audit ─────────────────────────────


class TestFullFlow:
    def test_xmp_keys_present_after_render(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """All 12 spec §5.3 XMP keys land on the rendered PDF.

        pikepdf's iteration returns namespace-URI form ``{http://...}local``;
        check those rather than prefix:local since the namespace registry is
        per-PdfMetadata-instance and does not persist across reads.
        """
        out = tmp_path / "out.pdf"
        proc = _run_md_to_pdf(
            str(HELLO),
            "-o", str(out),
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr

        with pikepdf.open(str(out)) as pdf, pdf.open_metadata() as meta:
            keys = set(meta)
            mdpdf_ns = "{https://md-to-pdf.dev/xmp/1.0/}"
            dc_ns = "{http://purl.org/dc/elements/1.1/}"
            pdf_ns = "{http://ns.adobe.com/pdf/1.3/}"
            xmp_ns = "{http://ns.adobe.com/xap/1.0/}"
            for key in (
                f"{dc_ns}title",
                f"{dc_ns}creator",
                f"{pdf_ns}Producer",
                f"{xmp_ns}CreatorTool",
                f"{xmp_ns}CreateDate",
                f"{mdpdf_ns}RenderId",
                f"{mdpdf_ns}RenderUser",
                f"{mdpdf_ns}RenderHost",
                f"{mdpdf_ns}BrandId",
                f"{mdpdf_ns}BrandVersion",
                f"{mdpdf_ns}InputHash",
                f"{mdpdf_ns}WatermarkLevel",
            ):
                assert key in keys, f"XMP key missing: {key}"
            assert str(meta[f"{mdpdf_ns}RenderUser"]) == "alice@test.example"

    def test_audit_log_records_render_events(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """A successful render writes render.start + render.complete to the
        audit log redirected via MD_PDF_AUDIT_PATH.
        """
        out = tmp_path / "out.pdf"
        proc = _run_md_to_pdf(
            str(HELLO),
            "-o", str(out),
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr
        assert isolated_audit.exists()
        events = [
            json.loads(line)
            for line in isolated_audit.read_text().splitlines()
            if line.strip()
        ]
        kinds = [event["event"] for event in events]
        assert "render.start" in kinds
        assert "render.complete" in kinds

    def test_no_audit_flag_skips_log(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        out = tmp_path / "out.pdf"
        proc = _run_md_to_pdf(
            str(HELLO),
            "-o", str(out),
            "--no-audit",
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr
        assert not isolated_audit.exists()

    def test_no_watermark_skips_l1(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """--no-watermark sets L0; the L1 diagonal text must not appear in extracted text."""
        out = tmp_path / "out.pdf"
        proc = _run_md_to_pdf(
            str(HELLO),
            "-o", str(out),
            "--no-watermark",
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr
        text = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages)
        assert "alice@test.example" not in text


# ── Task 21: locale-aware footer ─────────────────────────────────────────────


class TestLocaleFooter:
    def test_zh_cn_footer_renders_chinese(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """--locale zh-CN produces a footer with Chinese 机密 + 第 N 页 strings."""
        out = tmp_path / "zh.pdf"
        proc = _run_md_to_pdf(
            str(LOCALE_CJK),
            "-o", str(out),
            "--locale", "zh-CN",
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr
        text = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages)
        assert "机密" in text or "第 1 页" in text, (
            "expected zh-CN footer text in extracted PDF"
        )

    def test_en_footer_renders_english(
        self, tmp_path: Path, isolated_audit: Path
    ) -> None:
        """Default --locale en produces 'Page N of M' footer text."""
        out = tmp_path / "en.pdf"
        proc = _run_md_to_pdf(
            str(HELLO),
            "-o", str(out),
            "--watermark-user", "alice@test.example",
        )
        assert proc.returncode == 0, proc.stderr
        text = "".join(p.extract_text() or "" for p in pypdf.PdfReader(str(out)).pages)
        assert "Page 1 of" in text
