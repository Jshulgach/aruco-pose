"""The published site must be self-contained and use only synthetic demo media."""
from pathlib import Path
import zipfile

import pytest

from scripts.build_project_page import build_page, validate_page


def test_project_page_builds_with_valid_local_links(tmp_path):
    output = build_page(tmp_path / "page")
    validate_page(output)
    assert (output / "assets/tracking-demo.mp4").stat().st_size > 1000
    assert (output / "assets/preview.jpg").exists()
    assert (output / "assets/dodecahedron-demo.mp4").stat().st_size > 1000
    assert (output / "assets/dodecahedron-preview.jpg").exists()
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "Synthetic" in html or "synthetic" in html
    assert "pip install aruco-pose" in html
    assert "https://pypi.org/project/aruco-pose/" in html
    with zipfile.ZipFile(output / "downloads/starter-kit.zip") as archive:
        names = archive.namelist()
        assert "starter/tracking.mp4" in names and "starter/board.json" in names
        assert not any("WIN_20250404" in name or name.endswith(".npy") for name in names)


def test_project_page_detects_broken_download(tmp_path):
    output = build_page(tmp_path / "page")
    (output / "assets/marker_board.svg").unlink()
    with pytest.raises(ValueError, match="Missing/invalid page resource"):
        validate_page(output)


def test_project_page_rejects_source_as_output():
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="separate"):
        build_page(root / "site")
