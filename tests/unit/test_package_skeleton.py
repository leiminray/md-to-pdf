"""Verify the package layout exists and exports __version__."""
import importlib


def test_package_imports():
    mdpdf = importlib.import_module("mdpdf")
    assert mdpdf is not None


def test_package_version_matches_pyproject():
    import mdpdf
    assert mdpdf.__version__ == "0.2.1"


def test_subpackages_import():
    importlib.import_module("mdpdf.markdown")
    importlib.import_module("mdpdf.render")
    importlib.import_module("mdpdf.cache")
