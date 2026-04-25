"""Tests for structlog configuration helper."""
import json
import logging

import structlog

from mdpdf.logging import configure_logging


def test_human_mode_renders_human_lines(capsys):
    configure_logging(json_output=False, level="INFO")
    log = structlog.get_logger("test")
    log.info("hello", key="value")
    captured = capsys.readouterr()
    assert "hello" in captured.err or "hello" in captured.out


def test_json_mode_emits_parseable_json(capsys):
    configure_logging(json_output=True, level="INFO")
    log = structlog.get_logger("test")
    log.info("event_name", custom_field="x")
    captured = capsys.readouterr()
    line = (captured.err or captured.out).strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "event_name"
    assert payload["custom_field"] == "x"


def test_level_filtering(capsys):
    configure_logging(json_output=True, level="WARNING")
    log = structlog.get_logger("test")
    log.info("filtered_out")
    log.warning("kept")
    captured = capsys.readouterr().err + capsys.readouterr().out
    assert "kept" in captured
    assert "filtered_out" not in captured
