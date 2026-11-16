"""Exercise the documented CLI on decoded videos, not precomputed detections."""

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from click.testing import CliRunner
from scipy.spatial.transform import Rotation

from aruco_pose.cli import cli
from aruco_pose.starter import board_model, estimate_board

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "assets/starter"


@pytest.fixture(scope="module")
def camera_free_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("starter")
    runner = CliRunner()
    calibration = output / "calibration.json"
    result = runner.invoke(
        cli,
        [
            "kit",
            "calibrate",
            "--source",
            str(SAMPLE / "calibration.mp4"),
            "--stride",
            "1",
            "--output",
            str(calibration),
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        cli,
        [
            "kit",
            "track",
            "--source",
            str(SAMPLE / "tracking.mp4"),
            "--model",
            str(SAMPLE / "board.json"),
            "--calibration",
            str(calibration),
            "--csv",
            str(output / "poses.csv"),
            "--output-video",
            str(output / "annotated.mp4"),
        ],
    )
    assert result.exit_code == 0, result.output
    return output


def test_printed_targets_have_physical_dimensions(tmp_path):
    import xml.etree.ElementTree as ET

    result = CliRunner().invoke(cli, ["kit", "print", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    for name in ["marker_board.svg", "checkerboard.svg"]:
        svg = ET.parse(tmp_path / name).getroot()
        assert svg.attrib["width"] == "210mm"
        assert svg.attrib["height"] == "297mm"
    model = json.loads((tmp_path / "board.json").read_text())
    for marker in model["markers"]:
        points = np.array(marker["corners_m"])
        np.testing.assert_allclose(
            np.linalg.norm(points - np.roll(points, -1, axis=0), axis=1), 0.04
        )


def test_calibration_recovers_reference_intrinsics(camera_free_run):
    actual = json.loads((camera_free_run / "calibration.json").read_text())
    reference = json.loads((SAMPLE / "reference_camera.json").read_text())
    assert actual["views"] == 30
    assert actual["rms_px"] < 0.3
    np.testing.assert_allclose(
        actual["camera_matrix"], reference["camera_matrix"], atol=5
    )


def test_csv_accuracy_loss_and_video(camera_free_run):
    with (camera_free_run / "poses.csv").open() as stream:
        poses = list(csv.DictReader(stream))
    with (SAMPLE / "ground_truth.csv").open() as stream:
        truth = list(csv.DictReader(stream))
    assert len(poses) == len(truth) == 120
    errors, angles = [], []
    for i, (actual, expected) in enumerate(zip(poses, truth)):
        assert int(actual["frame"]) == i
        assert float(actual["time_s"]) == pytest.approx(i / 20, abs=1e-6)
        if 50 <= i < 60:
            assert actual["status"] == "lost"
            assert actual["tx_m"] == actual["qw"] == ""
        if actual["status"] == "measured":
            position = np.array([float(actual[k]) for k in ["tx_m", "ty_m", "tz_m"]])
            expected_position = np.array(
                [float(expected[k]) for k in ["tx_m", "ty_m", "tz_m"]]
            )
            errors.append(np.linalg.norm(position - expected_position))
            quaternion = np.array([float(actual[k]) for k in ["qx", "qy", "qz", "qw"]])
            assert np.linalg.norm(quaternion) == pytest.approx(1.0)
            expected_rotation = Rotation.from_rotvec(
                [float(expected[k]) for k in ["rx_rad", "ry_rad", "rz_rad"]]
            )
            angles.append(
                (Rotation.from_quat(quaternion).inv() * expected_rotation).magnitude()
            )
            assert float(actual["reprojection_rmse_px"]) <= 3.0
    assert len(errors) >= 105
    assert np.median(errors) < 0.008
    assert np.median(angles) < 0.05
    assert all(
        p["status"] == "measured" and p["marker_count"] == "2" for p in poses[85:100]
    )
    cap = cv2.VideoCapture(str(camera_free_run / "annotated.mp4"))
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 120
    cap.release()
    summary = json.loads((camera_free_run / "poses.summary.json").read_text())
    assert summary["frames"] == 120
    assert summary["lost"] == 10
    assert summary["ambiguous"] == 0
    assert summary["schema_version"] == 2
    assert all(
        p["parent_frame"] == "camera_optical" and p["child_frame"] == "starter_board"
        for p in poses
    )


def test_direct_api_example_matches_cli(camera_free_run):
    import subprocess
    import sys

    output = camera_free_run / "example.csv"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples/pose_api_demo.py"),
            "--once",
            "--calibration",
            str(camera_free_run / "calibration.json"),
            "--csv",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    with output.open() as stream:
        example = list(csv.DictReader(stream))
    with (camera_free_run / "poses.csv").open() as stream:
        command = list(csv.DictReader(stream))
    assert len(example) == len(command)
    for first, second in zip(example, command):
        for key in [
            "status",
            "marker_ids",
            "reason",
            "time_s",
            "inlier_corner_count",
            "ambiguity_resolved_by",
        ]:
            assert first[key] == second[key]
        if first["status"] == "measured":
            np.testing.assert_allclose(
                [float(first[k]) for k in ["tx_m", "ty_m", "tz_m"]],
                [float(second[k]) for k in ["tx_m", "ty_m", "tz_m"]],
                atol=1e-10,
            )


def test_resolution_mismatch_is_an_error(camera_free_run, tmp_path):
    data = json.loads((camera_free_run / "calibration.json").read_text())
    data["image_width"] = 800
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps(data))
    result = CliRunner().invoke(
        cli,
        [
            "kit",
            "track",
            "--source",
            str(SAMPLE / "tracking.mp4"),
            "--model",
            str(SAMPLE / "board.json"),
            "--calibration",
            str(path),
            "--csv",
            str(tmp_path / "poses.csv"),
        ],
    )
    assert result.exit_code != 0
    assert "differs from calibration" in result.output


def test_insufficient_calibration_views_fail(tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "kit",
            "calibrate",
            "--source",
            str(SAMPLE / "calibration.mp4"),
            "--stride",
            "100",
            "--output",
            str(tmp_path / "camera.json"),
        ],
    )
    assert result.exit_code != 0
    assert "need at least 8" in result.output
    assert not (tmp_path / "camera.json").exists()


def test_unrelated_markers_are_ignored_and_one_bad_marker_is_rejected():
    matrix = np.array([[700.0, 0, 320.0], [0, 700.0, 240.0], [0, 0, 1.0]])
    model = board_model()
    corners = [
        cv2.projectPoints(
            np.array(m["corners_m"]),
            np.zeros(3),
            np.array([0.0, 0.0, 0.4]),
            matrix,
            np.zeros(5),
        )[0].reshape(1, 4, 2)
        for m in model["markers"]
    ]
    result = estimate_board(
        model, corners, np.array([[40], [41], [42], [43]]), matrix, np.zeros(5)
    )
    assert result[-1] == "lost"
    corners[-1] += 50
    result = estimate_board(
        model, corners, np.arange(4).reshape(-1, 1), matrix, np.zeros(5)
    )
    assert result[-1] == "measured"
    assert result[2] == [0, 1, 2]
    np.testing.assert_allclose(result[1].ravel(), [0, 0, 0.4], atol=1e-6)
