"""Ground-truth tests for robust poses, frame semantics and planar branch selection."""

from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from aruco_pose import Pose, PoseResult, Tracker, TrackerConfig
from aruco_pose.models.aruco_pose_estimator import (
    ArucoPoseEstimatorFromJSON,
    ArucoPoseEstimatorFromModel,
)
from aruco_pose.models.aruco_pose_pipeline import ArucoPoseEstimator
from aruco_pose.models.dodecahedron_model import DodecahedronWithMarkers
from aruco_pose.pose import model_from_extrinsics
from aruco_pose.starter import board_model

ROOT = Path(__file__).resolve().parents[1]
K = np.array([[800.0, 0, 320.0], [0, 800.0, 240.0], [0, 0, 1.0]])
D = np.zeros(5)
RVEC = np.array([0.3, -0.2, 0.1])
TVEC = np.array([0.01, -0.02, 0.5])


def observations(model=None, rvec=RVEC, tvec=TVEC, noise=0.0):
    model = model or board_model()
    rng = np.random.default_rng(8)
    corners = []
    for marker in model["markers"]:
        points = cv2.projectPoints(
            np.array(marker["corners_m"]),
            np.array(rvec, dtype=float),
            np.array(tvec, dtype=float),
            K,
            D,
        )[0].reshape(1, 4, 2)
        corners.append(points + rng.normal(0, noise, points.shape))
    return corners, np.array([m["id"] for m in model["markers"]]).reshape(-1, 1)


def assert_pose(
    result, rvec=RVEC, tvec=TVEC, translation_tolerance=1e-5, angle_tolerance=1e-4
):
    assert result.status == "measured", result.reason
    np.testing.assert_allclose(
        result.pose.translation_m, tvec, atol=translation_tolerance
    )
    angle = (
        Rotation.from_quat(result.pose.quaternion_xyzw).inv()
        * Rotation.from_rotvec(rvec)
    ).magnitude()
    assert angle < angle_tolerance


def test_public_pose_transform_inverse_composition_and_serialization():
    camera_from_object = Pose.from_rvec(RVEC, TVEC, "camera", "object")
    world_from_camera = Pose.from_rvec(
        [-0.1, 0.2, -0.3], [1.0, 2.0, 3.0], "world", "camera"
    )
    world_from_object = world_from_camera.compose(camera_from_object)
    np.testing.assert_allclose(
        world_from_object.matrix,
        world_from_camera.matrix @ camera_from_object.matrix,
        atol=1e-14,
    )
    points = np.array([[0, 0, 0], [0.1, 0.2, 0.3]])
    np.testing.assert_allclose(
        camera_from_object.inverse().transform_points(
            camera_from_object.transform_points(points)
        ),
        points,
        atol=1e-14,
    )
    identity = camera_from_object.inverse().compose(camera_from_object)
    np.testing.assert_allclose(identity.matrix, np.eye(4), atol=1e-14)
    with pytest.raises(ValueError, match="mismatched frames"):
        camera_from_object.compose(world_from_camera)
    result = Tracker(board_model(), K, D).estimate(*observations(), timestamp_s=1.25)
    assert_pose(result)
    payload = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert payload["schema_version"] == 1 and payload["units"] == "meters"
    assert payload["pose"]["parent_frame"] == "camera_optical"
    assert payload["pose"]["child_frame"] == "starter_board"
    row = result.to_csv_row(8)
    assert row["frame"] == 8 and row["time_s"] == "1.250000"
    np.testing.assert_allclose([row[k] for k in ["tx_m", "ty_m", "tz_m"]], TVEC)


@pytest.mark.parametrize(
    "corruption,expected_count,expected_ids",
    [
        ("marker", 12, (0, 1, 2)),
        ("corner", 15, (0, 1, 2, 3)),
        ("one_corner_per_marker", 12, (0, 1, 2, 3)),
    ],
)
def test_corner_and_whole_marker_outliers_are_removed(
    corruption, expected_count, expected_ids
):
    corners, ids = observations(noise=0.05)
    if corruption == "marker":
        corners[-1] += [60, -45]
    elif corruption == "corner":
        corners[-1][0, 0] += [60, -45]
    else:
        for corner in corners:
            corner[0, 0] += [60, -45]
    result = Tracker(board_model(), K, D).estimate(corners, ids, 1.0)
    assert_pose(result, translation_tolerance=0.001, angle_tolerance=0.02)
    assert result.inlier_marker_ids == expected_ids
    assert result.inlier_corner_count == expected_count
    if corruption == "marker":
        assert result.rejected_marker_ids == (3,)
    else:
        assert result.observations[-1].inlier_corners == (1, 2, 3)
    assert result.reprojection_rmse_px < 0.2


def test_no_majority_consensus_never_publishes_a_pose():
    corners, ids = observations()
    for corner in corners[2:]:
        corner += [60, -45]
    result = Tracker(board_model(), K, D).estimate(corners, ids, 1.0)
    assert result.status == "rejected"
    assert result.pose is None
    assert "tx_m" not in result.to_csv_row(0)


@pytest.mark.parametrize(
    "rvec,tvec",
    [
        ([0.0, 0.0, 0.0], [0.0, 0.0, 0.5]),
        ([0.3, -0.2, 0.1], [0.0, 0.0, 0.5]),
        ([3.0, 0.1, 0.2], [0.0, 0.0, 0.5]),
    ],
)
def test_planar_frontal_tilted_and_rotated_views(rvec, tvec):
    result = Tracker(board_model(), K, D).estimate(
        *observations(rvec=rvec, tvec=tvec), 1.0
    )
    assert_pose(result, np.array(rvec), tvec)
    assert all(
        np.all(
            candidate.pose.transform_points(
                np.concatenate([m["corners_m"] for m in board_model()["markers"]])
            )[:, 2]
            > 0
        )
        for candidate in result.candidates
    )


def test_planar_model_in_arbitrary_object_plane():
    model = board_model()
    rotation = Rotation.from_rotvec([0.4, -0.2, 0.3])
    for marker in model["markers"]:
        marker["corners_m"] = (
            rotation.apply(marker["corners_m"]) + [0.1, -0.1, 0.04]
        ).tolist()
    result = Tracker(model, K, D).estimate(*observations(model), 1.0)
    assert_pose(result)


def ambiguous_observation():
    return observations(rvec=[0.2, 0.1, 0.0], tvec=[0.0, 0.0, 4.0])


def test_ambiguous_planar_frame_exposes_both_branches_without_pose():
    result = Tracker(board_model(), K, D).estimate(*ambiguous_observation(), 1.0)
    assert result.status == "ambiguous"
    assert result.pose is None
    assert len(result.candidates) == 2
    assert (
        result.candidates[1].reprojection_rmse_px
        - result.candidates[0].reprojection_rmse_px
        < 0.05
    )
    assert "qx" not in result.to_csv_row(0)
    json.dumps(result.to_dict(), allow_nan=False)


def test_recent_measured_prior_can_select_either_current_branch():
    tracker = Tracker(board_model(), K, D)
    unresolved = tracker.estimate(*ambiguous_observation(), 1.0)
    for candidate in unresolved.candidates:
        prior = replace(
            unresolved, timestamp_s=0.9, status="measured", pose=candidate.pose
        )
        result = tracker.estimate(*ambiguous_observation(), 1.0, previous=prior)
        assert result.status == "measured"
        assert result.ambiguity_resolved_by == "recent_measurement"
        # A local refinement must not silently jump to the competing branch.
        distances = [
            (
                Rotation.from_quat(result.pose.quaternion_xyzw).inv()
                * Rotation.from_quat(c.pose.quaternion_xyzw)
            ).magnitude()
            for c in unresolved.candidates
        ]
        chosen_index = unresolved.candidates.index(candidate)
        assert distances[chosen_index] < distances[1 - chosen_index]


def test_refinement_cannot_cross_to_the_other_planar_branch(monkeypatch):
    tracker = Tracker(board_model(), K, D)
    unresolved = tracker.estimate(*ambiguous_observation(), 1.0)
    selected, alternate = unresolved.candidates
    prior = replace(unresolved, timestamp_s=0.9, status="measured", pose=selected.pose)
    monkeypatch.setattr(
        cv2,
        "solvePnPRefineLM",
        lambda *args: (alternate.pose.rvec, alternate.pose.tvec),
    )
    result = tracker.estimate(*ambiguous_observation(), 1.0, previous=prior)
    assert result.status == "measured"
    np.testing.assert_allclose(result.pose.matrix, selected.pose.matrix, atol=1e-12)


def test_nonfinite_refinement_is_a_rejection_not_a_nan_pose(monkeypatch):
    monkeypatch.setattr(
        cv2,
        "solvePnPRefineLM",
        lambda *args: (np.full((3, 1), np.nan), np.ones((3, 1))),
    )
    result = Tracker(board_model(), K, D).estimate(*observations(), 1.0)
    assert result.status == "rejected" and result.pose is None
    assert result.reason == "refinement_numerical_failure"
    json.dumps(result.to_dict(), allow_nan=False)


def test_equally_close_and_large_rotation_priors_do_not_force_a_branch():
    tracker = Tracker(board_model(), K, D)
    unresolved = tracker.estimate(*ambiguous_observation(), 1.0)
    first, second = [c.pose for c in unresolved.candidates]
    rotation = Rotation.from_quat(first.quaternion_xyzw)
    delta = rotation.inv() * Rotation.from_quat(second.quaternion_xyzw)
    midpoint = Pose(
        first.parent_frame,
        first.child_frame,
        tuple((np.array(first.translation_m) + second.translation_m) / 2),
        tuple((rotation * Rotation.from_rotvec(delta.as_rotvec() / 2)).as_quat()),
    )
    prior = replace(unresolved, timestamp_s=0.9, status="measured", pose=midpoint)
    assert (
        tracker.estimate(*ambiguous_observation(), 1.0, previous=prior).status
        == "ambiguous"
    )
    far_rotation = replace(
        first, quaternion_xyzw=tuple(Rotation.from_rotvec([3.0, 0.0, 0.0]).as_quat())
    )
    prior = replace(prior, pose=far_rotation)
    assert (
        tracker.estimate(*ambiguous_observation(), 1.0, previous=prior).status
        == "ambiguous"
    )


@pytest.mark.parametrize("timestamp", [0.5, 1.0, 1.1])
def test_stale_equal_time_and_future_priors_cannot_resolve_ambiguity(timestamp):
    tracker = Tracker(board_model(), K, D)
    unresolved = tracker.estimate(*ambiguous_observation(), 1.0)
    prior = replace(
        unresolved,
        timestamp_s=timestamp,
        status="measured",
        pose=unresolved.candidates[0].pose,
    )
    assert (
        tracker.estimate(*ambiguous_observation(), 1.0, previous=prior).status
        == "ambiguous"
    )


def test_wrong_object_frame_or_large_motion_prior_cannot_resolve_ambiguity():
    tracker = Tracker(board_model(), K, D)
    unresolved = tracker.estimate(*ambiguous_observation(), 1.0)
    prior = replace(
        unresolved,
        timestamp_s=0.9,
        status="measured",
        pose=unresolved.candidates[0].pose,
    )
    assert (
        tracker.estimate(
            *ambiguous_observation(), 1.0, previous=replace(prior, object_id="other")
        ).status
        == "ambiguous"
    )
    wrong_pose = replace(prior.pose, parent_frame="other_camera")
    assert (
        tracker.estimate(
            *ambiguous_observation(),
            1.0,
            previous=replace(prior, parent_frame="other_camera", pose=wrong_pose)
        ).status
        == "ambiguous"
    )
    distant = replace(prior.pose, translation_m=(0.0, 0.0, 5.0))
    assert (
        tracker.estimate(
            *ambiguous_observation(), 1.0, previous=replace(prior, pose=distant)
        ).status
        == "ambiguous"
    )
    assert (
        tracker.estimate(*ambiguous_observation(), 1.0, previous=unresolved).status
        == "ambiguous"
    )


def test_missing_observations_never_return_prior_or_prediction():
    tracker = Tracker(board_model(), K, D)
    prior = tracker.estimate(*observations(), 0.9)
    lost = tracker.estimate([], None, 1.0, previous=prior)
    assert lost.status == "lost" and lost.pose is None and lost.candidates == ()
    assert lost.to_csv_row(1)["inlier_corner_count"] == 0


def test_bad_observations_are_auditable_and_cannot_inflate_support():
    tracker = Tracker(board_model(), K, D)
    corners, ids = observations()
    corners.append(corners[0].copy())
    result = tracker.estimate(corners, np.append(ids, 0), 1.0)
    assert result.status == "measured"
    assert result.inlier_marker_ids == (1, 2, 3)
    assert (
        result.observations[0].reason
        == result.observations[-1].reason
        == "duplicate_id"
    )
    corners, ids = observations()
    corners[0][0, 0] = np.nan
    result = tracker.estimate(corners, ids, 1.0)
    assert result.status == "measured"
    assert result.observations[0].reason == "invalid_corners"
    json.dumps(result.to_dict(), allow_nan=False)
    unknown = tracker.estimate(corners[1:], [40, 41, 42], 1.0)
    assert unknown.status == "lost"
    assert all(o.reason == "unknown_id" for o in unknown.observations)
    with pytest.raises(ValueError, match="matching"):
        tracker.estimate(corners, [0], 1.0)
    with pytest.raises(ValueError, match="finite"):
        tracker.estimate(corners, ids, float("nan"))


def test_degenerate_image_data_is_rejected():
    result = Tracker(board_model(), K, D).estimate(
        [np.full((1, 4, 2), 20.0)] * 4, np.arange(4), 1.0
    )
    assert result.status == "rejected" and result.pose is None


def test_nonplanar_legacy_model_and_json_adapters_use_same_results():
    model = DodecahedronWithMarkers(edge_length=0.025)
    adapter = ArucoPoseEstimatorFromModel(
        K, D, 0.015, model, config=TrackerConfig(min_markers=2)
    )
    # Project all 12 modeled faces as abstract correspondences; not a visibility test.
    data = model_from_extrinsics(adapter.extrinsics, 0.015, object_id="dodecahedron")
    corners, ids = observations(data)
    result = adapter.estimate_result(corners, ids, 1.0)
    assert_pose(result)
    direct = adapter.tracker.estimate(corners, ids, 1.0)
    assert direct.to_dict() == result.to_dict()
    rvec, tvec, inliers = adapter.estimate_pose(corners, ids)
    np.testing.assert_allclose(tvec.ravel(), TVEC, atol=1e-6)
    assert inliers == list(result.inlier_marker_ids)
    json_adapter = ArucoPoseEstimatorFromJSON(
        K, D, 0.015, ROOT / "config/dodecahedron_with_markers.json"
    )
    assert_pose(
        json_adapter.estimate_result(
            *observations(
                {
                    "markers": [
                        {"id": mid, "corners_m": points.tolist()}
                        for mid, points in json_adapter.tracker.markers.items()
                    ]
                }
            ),
            timestamp_s=1.0
        )
    )


def test_tag_group_adapter_uses_markers_other_than_zero():
    adapter = ArucoPoseEstimator(
        K,
        D,
        tag_data_path=ROOT / "config/aruco_group.json",
        config=TrackerConfig(min_markers=2),
    )
    data = {
        "markers": [
            {"id": mid, "corners_m": points.tolist()}
            for mid, points in adapter.tracker.markers.items()
            if mid != 0
        ]
    }
    result = adapter.tracker.estimate(*observations(data), 1.0)
    assert_pose(result)
    assert 0 not in result.inlier_marker_ids


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outlier_threshold_px": float("nan")},
        {"ambiguity_gap_px": -1},
        {"min_markers": 0},
        {"min_inlier_fraction": 0.5},
        {"prior_max_age_s": float("inf")},
    ],
)
def test_invalid_tracker_config_fails_fast(kwargs):
    with pytest.raises(ValueError):
        TrackerConfig(**kwargs)


def test_model_camera_and_pose_validation():
    with pytest.raises(ValueError, match="Quaternion"):
        Pose("a", "b", (0, 0, 0), (0, 0, 0, 0))
    with pytest.raises(ValueError, match="Only measured"):
        PoseResult(1.0, "object", "a", "b", "measured", "invalid")
    model = board_model()
    model["markers"][1]["id"] = 0
    with pytest.raises(ValueError, match="unique"):
        Tracker(model, K, D)
    model = board_model()
    model["markers"][0]["corners_m"] = [[0, 0, 0]] * 4
    with pytest.raises(ValueError, match="nondegenerate"):
        Tracker(model, K, D)
    with pytest.raises(ValueError, match="intrinsics"):
        Tracker(board_model(), np.zeros((3, 3)), D)
