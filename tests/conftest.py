"""Repo-level pytest configuration."""
import sys
from pathlib import Path

# Allow `from mdpdf import …` when running pytest from repo root with `pip install -e .`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
