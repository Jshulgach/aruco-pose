"""Rectified pixel geometry must still publish the original optical-frame pose."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from aruco_pose import Tracker, Pose, PoseResult, PoseCandidate
from scripts.generate_dodecahedron_demo import make_target

path = Path(__file__).resolve().parents[1] / "examples/ros2/camera_input.py"
spec = importlib.util.spec_from_file_location("rectified_contract", path)
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


def info():
    return NS(
        header=NS(frame_id="camera_optical_frame"),
        width=960,
        height=720,
        k=[1500.0, 0.0, 480.0, 0.0, 1500.0, 360.0, 0.0, 0.0, 1.0],
        d=[-0.3, 0.08, 0.002, -0.001, 0.005],
        distortion_model="plumb_bob",
        binning_x=0,
        binning_y=0,
        roi=NS(x_offset=0, y_offset=0, width=0, height=0, do_rectify=False),
        r=Rotation.from_euler("xyz", [0.08, -0.1, 0.04]).as_matrix().ravel().tolist(),
        p=[1100.0, 0.0, 480.0, -110.0, 0.0, 1150.0, 360.0, 55.0, 0.0, 0.0, 1.0, 0.0],
    )


@pytest.mark.parametrize(
    "fault",
    [
        "zero_r",
        "reflection",
        "scale_r",
        "nan_r",
        "zero_p",
        "skew_p",
        "bottom_p",
        "nan_p",
        "uncalibrated_k",
        "roi",
    ],
)
def test_rectified_invalid_geometry_is_rejected(fault):
    message = info()
    if fault == "zero_r":
        message.r = [0.0] * 9
    if fault == "reflection":
        message.r = np.diag([-1.0, 1.0, 1.0]).ravel().tolist()
    if fault == "scale_r":
        message.r[0] *= 2
    if fault == "nan_r":
        message.r[0] = float("nan")
    if fault == "zero_p":
        message.p[0] = 0.0
    if fault == "skew_p":
        message.p[1] = 3.0
    if fault == "bottom_p":
        message.p[11] = 0.1
    if fault == "nan_p":
        message.p[3] = float("nan")
    if fault == "uncalibrated_k":
        message.k[0] = 0.0
    if fault == "roi":
        message.roi.x_offset = 10
    with pytest.raises(ValueError):
        camera.rectified_calibration(message, "camera_optical_frame")


def test_rectified_projection_returns_original_camera_pose_and_candidates():
    message = info()
    matrix, distortion, size, rectification = camera.rectified_calibration(
        message, "camera_optical_frame"
    )
    np.testing.assert_array_equal(distortion, np.zeros(5))
    assert matrix[0, 0] == 1100.0 and matrix[1, 1] == 1150.0
    _, model, _ = make_target()
    truth_rotation = Rotation.from_euler("xyz", [0.3, -0.15, 0.2]).as_matrix()
    truth_translation = np.array([0.01, -0.005, 0.3])
    rotation_rectified = rectification @ truth_rotation
    translation_rectified = rectification @ truth_translation
    corners = [
        cv2.projectPoints(
            np.array(marker["corners_m"]),
            cv2.Rodrigues(rotation_rectified)[0],
            translation_rectified,
            matrix,
            distortion,
        )[0].reshape(1, 4, 2)
        for marker in model["markers"]
    ]
    tracker = Tracker(
        model, matrix, distortion, parent_frame="rectified_internal", image_size=size
    )
    result = tracker.estimate(
        corners, np.array([m["id"] for m in model["markers"]]), timestamp_s=42.0
    )
    assert result.status == "measured"
    original = camera.original_camera_result(
        result, rectification, "camera_optical_frame"
    )
    np.testing.assert_allclose(
        original.pose.translation_m, truth_translation, atol=1e-7
    )
    assert (
        Rotation.from_rotvec(original.pose.rvec.ravel()).inv()
        * Rotation.from_matrix(truth_rotation)
    ).magnitude() < 1e-6
    assert original.parent_frame == original.pose.parent_frame == "camera_optical_frame"
    assert result.parent_frame == "rectified_internal"  # Retain this result for priors.
    candidate = PoseCandidate(
        Pose.from_rvec(
            cv2.Rodrigues(rotation_rectified)[0],
            translation_rectified,
            "rectified_internal",
            model["object_id"],
        ),
        0.2,
    )
    ambiguous = PoseResult(
        42.0,
        model["object_id"],
        "rectified_internal",
        model["object_id"],
        "ambiguous",
        "two branches",
        candidates=(candidate,),
    )
    converted = camera.original_camera_result(
        ambiguous, rectification, "camera_optical_frame"
    )
    assert converted.pose is None and converted.status == "ambiguous"
    np.testing.assert_allclose(
        converted.candidates[0].pose.translation_m, truth_translation, atol=1e-10
    )
    assert converted.candidates[0].pose.parent_frame == "camera_optical_frame"
    no_baseline = info()
    no_baseline.p[3] = no_baseline.p[7] = 0.0
    for a, b in zip(
        camera.rectified_calibration(message, "camera_optical_frame"),
        camera.rectified_calibration(no_baseline, "camera_optical_frame"),
    ):
        np.testing.assert_array_equal(a, b)


def test_detecting_rectified_pixels_recovers_camera_pose():
    import csv

    root = Path(__file__).resolve().parents[1]
    capture = cv2.VideoCapture(str(root / "assets/dodecahedron/tracking.mp4"))
    ok, ideal = capture.read()
    capture.release()
    assert ok
    message = info()
    k = np.array(message.k).reshape(3, 3)
    d = np.array(message.d)
    r = np.array(message.r).reshape(3, 3)
    p = np.array(message.p).reshape(3, 4)
    u, v = np.meshgrid(
        np.arange(960, dtype=np.float32), np.arange(720, dtype=np.float32)
    )
    grid = np.stack([u, v], axis=-1).reshape(-1, 1, 2)
    inverse = cv2.undistortPoints(grid, k, d, P=k).reshape(720, 960, 2)
    distorted = cv2.remap(ideal, inverse[:, :, 0], inverse[:, :, 1], cv2.INTER_LINEAR)
    maps = cv2.initUndistortRectifyMap(k, d, r, p, (960, 720), cv2.CV_32FC1)
    p_without_baseline = p.copy()
    p_without_baseline[:, 3] = 0
    maps_without_baseline = cv2.initUndistortRectifyMap(
        k, d, r, p_without_baseline, (960, 720), cv2.CV_32FC1
    )
    for actual, expected in zip(maps, maps_without_baseline):
        np.testing.assert_array_equal(actual, expected)
    pixels = cv2.remap(distorted, *maps, cv2.INTER_LINEAR)
    matrix, distortion, size, rectification = camera.rectified_calibration(
        message, "camera_optical_frame"
    )
    _, model, _ = make_target()
    result = Tracker(
        model, matrix, distortion, parent_frame="rectified_internal", image_size=size
    ).process(pixels, 1.0)
    assert result.status == "measured", result.reason
    original = camera.original_camera_result(
        result, rectification, "camera_optical_frame"
    )
    with (root / "assets/dodecahedron/ground_truth.csv").open() as stream:
        reference = next(csv.DictReader(stream))
    expected = np.array([float(reference[key]) for key in ("tx_m", "ty_m", "tz_m")])
    assert np.linalg.norm(np.array(original.pose.translation_m) - expected) < 0.002
    rotation = Rotation.from_rotvec(
        [float(reference[key]) for key in ("rx_rad", "ry_rad", "rz_rad")]
    )
    assert (
        np.degrees(
            (
                Rotation.from_rotvec(original.pose.rvec.ravel()).inv() * rotation
            ).magnitude()
        )
        < 1.5
    )
