"""Release audit regressions for previously broken legacy integration paths."""

import cv2
import numpy as np

from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel
from aruco_pose.tracking.dense_refinement import (
    estimate_pose_from_dodecahedron,
    estimate_pose_from_individual_markers,
    overlay_virtual_dodecahedron,
)
from aruco_pose.utils.logger import setup_logger


def test_legacy_geometry_helpers_use_model_ids_and_shared_pose():
    model = CleanDodecahedronModel(edge_length=0.025)
    matrix = np.array([[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]])
    distortion = np.zeros(5)
    rvec, tvec = np.array([0.2, -0.1, 0.15]), np.array([0.01, -0.02, 0.4])
    points = model.get_marker_corners(0.015)
    corners = [
        cv2.projectPoints(p, rvec, tvec, matrix, distortion)[0].reshape(1, 4, 2)
        for p in points[:3]
    ]
    ids = np.array([int(i) for i in model.aruco_id_order[:3]]).reshape(-1, 1)
    ok, _, position, pixel = estimate_pose_from_dodecahedron(
        model, corners, ids, matrix, distortion, 0.015
    )
    assert ok and np.isfinite(pixel).all()
    np.testing.assert_allclose(position.ravel(), tvec, atol=1e-5)
    ok, rotation, position, center = estimate_pose_from_individual_markers(
        model, corners, ids, matrix, distortion, 0.015
    )
    assert ok
    np.testing.assert_allclose(rotation, cv2.Rodrigues(rvec)[0], atol=1e-4)
    np.testing.assert_allclose(center, tvec, atol=1e-5)
    image = np.zeros((480, 640, 3), np.uint8)
    assert overlay_virtual_dodecahedron(
        image, model, corners, ids, matrix, distortion, 0.015
    ).any()


def test_reconfiguring_logger_releases_old_file_handle(tmp_path):
    path = tmp_path / "old.log"
    logger = setup_logger("release_audit", log_file=path, console=False)
    old_handler = logger.handlers[0]
    setup_logger("release_audit", console=False)
    assert old_handler.stream is None
    path.unlink()  # Fails on Windows if the removed handler wasn't closed.


def test_legacy_calibration_cli_passes_complete_settings(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from aruco_pose.cli import cli
    from aruco_pose.utils import legacy_utils

    monkeypatch.chdir(tmp_path)
    seen = []
    monkeypatch.setattr(
        legacy_utils,
        "save_frames_single_camera",
        lambda config, visualize: seen.append(config),
    )

    def solve(config, visualize):
        seen.append(config)
        return 0.1, np.eye(3), np.zeros(5)

    monkeypatch.setattr(legacy_utils, "calibrate_single_camera", solve)
    result = CliRunner().invoke(cli, ["calibrate", "--no-visualize"])
    assert result.exit_code == 0, result.output
    assert len(seen) == 2
    assert seen[0]["camera0"] == 0
    assert seen[0]["checkerboard_column_vertices"] == 7
    assert (tmp_path / "camera_intrinsics.npy").exists()


def test_standalone_marker_generation_supports_current_opencv(tmp_path):
    from aruco_pose.utils.marker_generator import generate_aruco_marker
    from aruco_pose.core.detector import UnifiedArucoDetector

    path = generate_aruco_marker(7, output_dir=tmp_path)
    marker = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    image = cv2.copyMakeBorder(marker, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    _, ids, _ = UnifiedArucoDetector().detect(image)
    assert ids.ravel().tolist() == [7]
