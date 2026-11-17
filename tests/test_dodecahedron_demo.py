"""Exercise the showcase's actual image detection and nonplanar pose recovery."""
import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from aruco_pose import Tracker, TrackerConfig
from scripts.generate_dodecahedron_demo import D, K, SIZE, make_target, render_frame


def test_demo_has_true_25mm_edges_and_outward_readable_markers():
    geometry, model, normals = make_target()
    for face, marker, normal in zip(geometry.pentagon_faces, model["markers"], normals):
        vertices = geometry.vertices[face]
        assert np.allclose(np.linalg.norm(vertices - np.roll(vertices, -1, axis=0), axis=1), .025)
        corners = np.array(marker["corners_m"])
        assert np.allclose(corners.mean(axis=0), vertices.mean(axis=0))
        assert np.allclose(np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1), .015)
        # The ArUco image's clockwise corner order points into the object.
        assert np.dot(np.cross(corners[1]-corners[0], corners[2]-corners[1]), normal) < 0
        # Entire printed square lies within its pentagonal face.
        basis = np.stack([(vertices[1]-vertices[0])/.025, np.cross(normal, (vertices[1]-vertices[0])/.025)])
        polygon = (vertices @ basis.T).astype(np.float32)
        assert all(cv2.pointPolygonTest(polygon, tuple(point), False) >= 0 for point in (corners @ basis.T))


@pytest.mark.parametrize("phase", [0., 1.1, 2.4, 3.7, 5.2])
def test_rendered_dodecahedron_recovers_pose_without_ground_truth_prior(phase):
    _, model, _ = make_target()
    frame, truth_rotation, truth_translation = render_frame(phase)
    tracker = Tracker(model, K, D, config=TrackerConfig(min_markers=2), image_size=SIZE)
    result = tracker.process(frame, timestamp_s=0.)
    assert result.status == "measured", result.reason
    assert len(result.inlier_marker_ids) >= 2
    assert np.linalg.norm(result.pose.tvec.ravel() - truth_translation) < .001
    error = Rotation.from_rotvec(result.pose.rvec.ravel()).inv()*Rotation.from_rotvec(truth_rotation)
    assert np.degrees(error.magnitude()) < 1.
