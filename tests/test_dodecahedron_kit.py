"""Verify the print, saved model and decoded replay form one usable kit."""
from collections import defaultdict
import csv
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import cv2
from click.testing import CliRunner
import numpy as np
from scipy.spatial.transform import Rotation

from aruco_pose.cli import cli
from aruco_pose.core.detector import UnifiedArucoDetector
from scripts.build_dodecahedron_kit import face_layouts, printable_svg
from scripts.generate_dodecahedron_demo import make_target

KIT = Path(__file__).resolve().parents[1] / "assets/dodecahedron"


def test_print_pdf_is_a4_with_intact_byte_offsets():
    data = (KIT / "faces.pdf").read_bytes()
    assert data.startswith(b"%PDF-")
    # Text line-ending conversion corrupts PDF object offsets on Windows.
    offset = int(re.search(rb"startxref\s+(\d+)", data).group(1))
    assert data[offset:offset+4] == b"xref"
    bounds = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", data)
    assert np.allclose([float(bounds.group(1)), float(bounds.group(2))], np.array([210, 297])*72/25.4)


def test_print_has_consistent_edge_pairs_and_one_tab_each():
    layouts = face_layouts()
    geometry, model, _ = make_target()
    pairs = defaultdict(list)
    for layout in layouts:
        for side in layout["sides"]:
            pairs[side["label"]].append((layout["marker_id"], side))
    assert len(pairs) == 30
    for pair in pairs.values():
        assert len(pair) == 2
        (left_id, left), (right_id, right) = pair
        assert left["neighbor_marker_id"] == right_id
        assert right["neighbor_marker_id"] == left_id
        assert left["tab"] != right["tab"]
        # Outside print views must reverse along each seam when folded together.
        assert left["vertices"] == right["vertices"][::-1]
        a, b = geometry.vertices[left["vertices"]]
        assert np.isclose(np.linalg.norm(a-b), .025)
    saved = json.loads((KIT / "model.json").read_text())
    assert {key: value for key, value in saved.items() if key != "markers"} == {
        key: value for key, value in model.items() if key != "markers"
    }
    assert len(saved["markers"]) == len(model["markers"])
    for actual, expected in zip(saved["markers"], model["markers"]):
        assert actual["id"] == expected["id"]
        # Math-library implementations can differ in their last floating bit.
        np.testing.assert_allclose(actual["corners_m"], expected["corners_m"], rtol=0, atol=1e-12)
    saved_layouts = json.loads((KIT / "assembly.json").read_text())["faces"]
    assert len(saved_layouts) == len(layouts)
    for actual, expected in zip(saved_layouts, layouts):
        assert actual["marker_id"] == expected["marker_id"]
        assert actual["sides"] == expected["sides"]
        for key in ["polygon_mm", "marker_corners_mm"]:
            np.testing.assert_allclose(actual[key], expected[key], rtol=0, atol=1e-9)


def test_actual_printed_bits_decode_in_the_model_corner_orientation():
    layouts = face_layouts()
    artwork = printable_svg(layouts)
    assert artwork == (KIT / "faces.svg").read_text(encoding="utf-8")
    root = ET.fromstring(artwork)
    assert (root.attrib["width"], root.attrib["height"]) == ("210mm", "297mm")
    # Rasterize the print's actual black vector cells, not regenerated markers.
    pixels_per_mm = 10
    image = np.full((297*pixels_per_mm, 210*pixels_per_mm), 255, np.uint8)
    for element in root:
        if element.tag.endswith("rect") and element.attrib.get("fill") == "black":
            x, y, width, height = [float(element.attrib[key]) for key in ("x", "y", "width", "height")]
            x0, y0, x1, y1 = np.rint(np.array([x, y, x+width, y+height])*pixels_per_mm).astype(int)
            image[y0:y1, x0:x1] = 0
        if element.tag.endswith("polygon"):
            points = np.array([list(map(float, point.split(","))) for point in element.attrib["points"].split()])
            assert np.all(points > [10, 35]) and np.all(points < [200, 272])
    detector = UnifiedArucoDetector("DICT_5X5_100")
    corners, ids, _ = detector.detect(image)
    assert set(ids.ravel()) == {layout["marker_id"] for layout in layouts}
    observations = dict(zip(ids.ravel(), corners))
    for index, layout in enumerate(layouts):
        offset = np.array([40+65*(index % 3), 65+58*(index // 3)])
        expected = np.array(layout["marker_corners_mm"]) + offset
        actual = np.asarray(observations[layout["marker_id"]]).reshape(4, 2)/pixels_per_mm
        assert np.max(np.linalg.norm(actual-expected, axis=1)) < .2


def test_documented_replay_cli_recovers_the_saved_ground_truth(tmp_path):
    output = tmp_path / "replay.csv"
    result = CliRunner().invoke(cli, ["kit", "track", "--source", str(KIT / "tracking.mp4"),
        "--model", str(KIT / "model.json"), "--calibration", str(KIT / "replay_camera.json"),
        "--csv", str(output)])
    assert result.exit_code == 0, result.output
    with output.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with (KIT / "ground_truth.csv").open(encoding="utf-8") as stream:
        truth = list(csv.DictReader(stream))
    assert len(rows) == len(truth) == 240
    for index, (row, reference) in enumerate(zip(rows, truth)):
        assert row["status"] == "measured"
        assert row["object_id"] == "dodecahedron_25mm"
        assert int(row["marker_count"]) >= 2
        assert abs(float(row["time_s"])-index/24) < 1e-6
        actual = np.array([float(row[key]) for key in ("tx_m", "ty_m", "tz_m")])
        expected = np.array([float(reference[key]) for key in ("tx_m", "ty_m", "tz_m")])
        assert np.linalg.norm(actual-expected) < .0015
        quaternion = [float(row[key]) for key in ("qx", "qy", "qz", "qw")]
        rotation = [float(reference[key]) for key in ("rx_rad", "ry_rad", "rz_rad")]
        angle = (Rotation.from_quat(quaternion).inv()*Rotation.from_rotvec(rotation)).magnitude()
        assert np.degrees(angle) < 1.5
    summary = json.loads(output.with_suffix(".summary.json").read_text())
    assert summary["measured"] == 240
    assert summary["calibration"]["synthetic"] is True
    assert not (tmp_path / "replay.mp4").exists()
