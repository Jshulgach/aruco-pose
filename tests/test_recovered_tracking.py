"""Exercise the recovered tracking path without cameras or calibration files."""
from pathlib import Path

import cv2
import numpy as np

from aruco_pose.models.aruco_pose_estimator import ArucoPoseEstimatorFromJSON
from aruco_pose.tracking.pose_refiner import PoseRefiner
from aruco_pose.tracking.predictive_filter import PredictivePoseFilter
from aruco_pose.utils.dodecahedron_overlay import draw_dodecahedron


ROOT = Path(__file__).resolve().parents[1]
K = np.array([[800., 0., 320.], [0., 800., 240.], [0., 0., 1.]])
D = np.zeros(5)


def test_json_pose_and_refinement_recover_synthetic_pose():
    estimator = ArucoPoseEstimatorFromJSON(
        K, D, 0.015, ROOT / 'config' / 'dodecahedron_with_markers.json')
    expected_r = np.array([[0.15], [-0.1], [0.05]])
    expected_t = np.array([[0.01], [0.02], [0.4]])
    ids = list(estimator.extrinsics)[:3]
    local = np.array([[-1, 1, 0], [1, 1, 0], [1, -1, 0], [-1, -1, 0]]) * 0.0075
    object_points, corners = [], []
    for marker_id in ids:
        r, t = estimator.extrinsics[marker_id]
        world = (cv2.Rodrigues(r)[0] @ local.T).T + t
        image = cv2.projectPoints(world, expected_r, expected_t, K, D)[0]
        object_points.extend(world)
        corners.append(image.reshape(1, 4, 2).astype(np.float32))
    r, t, used = estimator.estimate_pose(corners, np.array(ids).reshape(-1, 1))
    assert used == ids
    np.testing.assert_allclose(t, expected_t, atol=1e-5)
    np.testing.assert_allclose(r, expected_r, atol=1e-4)
    objects = np.array(object_points)
    images = np.concatenate(corners).reshape(-1, 2)
    rr, tt, cost = PoseRefiner(K, D).refine_pose(objects, images, r + 0.02, t + 0.01)
    assert cost < 1e-5
    np.testing.assert_allclose(tt, expected_t, atol=1e-5)
    np.testing.assert_allclose(rr, expected_r, atol=1e-4)


def test_prediction_and_reset():
    predictor = PredictivePoseFilter(alpha=0.5)
    assert predictor.predict() == (None, None)
    predictor.update(np.zeros((3, 1)), np.ones((3, 1)))
    predictor.update(np.ones((3, 1)), np.full((3, 1), 2.))
    r, t = predictor.predict()
    np.testing.assert_allclose(r, 1.5)
    np.testing.assert_allclose(t, 2.5)
    predictor.reset()
    assert predictor.predict() == (None, None)


def test_overlay_uses_width_and_height_separately():
    class Model:
        # Valid polygon at x > image height, on a wide image.
        vertices = np.array([[200., 10., 1.], [250., 10., 1.], [225., 50., 1.]])
        pentagon_faces = [[0, 1, 2]]

    frame = np.zeros((100, 400, 3), dtype=np.uint8)
    result = draw_dodecahedron(frame, np.zeros(3), np.zeros(3), Model(), np.eye(3), D)
    assert result.any()
