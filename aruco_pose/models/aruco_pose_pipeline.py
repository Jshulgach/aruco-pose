"""Legacy tag-group adapter backed by the shared multi-marker pose API."""

import json
from pathlib import Path
import cv2
import numpy as np
from ..pose import Tracker, TrackerConfig, model_from_extrinsics
from .aruco_pose_estimator import _dictionary_name


class ArucoPoseEstimator:
    def __init__(
        self,
        camera_matrix,
        dist_coeffs,
        aruco_dict=cv2.aruco.DICT_5X5_100,
        tag_data_path="aruco_group.json",
        *,
        config=None,
    ):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.tag_data = self._load_tag_data(tag_data_path)
        markers = []
        for marker_id, tag in self.tag_data.items():
            model = model_from_extrinsics(
                {int(marker_id): tag["extrinsics"]}, tag["size"]
            )
            markers.extend(model["markers"])
        model = {
            "object_id": "tag_group",
            "units": "meters",
            "dictionary": _dictionary_name(aruco_dict),
            "markers": markers,
        }
        self.tracker = Tracker(
            model,
            camera_matrix,
            dist_coeffs,
            config=config or TrackerConfig(min_markers=1),
        )
        self.last_result = None

    def _load_tag_data(self, json_path):
        if not Path(json_path).exists():
            raise FileNotFoundError(f"Could not find {json_path} for ArUco extrinsics.")
        return json.loads(Path(json_path).read_text(encoding="utf-8"))["tags"]

    def get_tag_extrinsics(self, tag_id):
        value = np.asarray(self.tag_data[str(tag_id)]["extrinsics"], dtype=float)
        return value[3:].reshape(3, 1), value[:3].reshape(3, 1)

    def get_tag_object_points(self, size):
        return (
            np.array([[-1, 1, 0], [1, 1, 0], [1, -1, 0], [-1, -1, 0]], dtype=float)
            * size
            / 2
        )

    def transform_marker_corners(self, obj_pts, transformation):
        rotation = cv2.Rodrigues(transformation[0])[0]
        return (rotation @ np.asarray(obj_pts).T).T + np.asarray(
            transformation[1]
        ).reshape(1, 3)

    def process(self, frame, timestamp_s, *, previous=None):
        self.last_result = self.tracker.process(frame, timestamp_s, previous=previous)
        return self.last_result

    def detect_and_estimate_pose(self, image):
        result = self.process(image, timestamp_s=0.0)
        valid = [o for o in result.observations if o.corners_px]
        corners = [
            np.array(o.corners_px, dtype=np.float32).reshape(1, 4, 2) for o in valid
        ]
        ids = (
            np.array([o.marker_id for o in valid], dtype=np.int32).reshape(-1, 1)
            if valid
            else None
        )
        return (
            result.pose.rvec if result.pose else None,
            result.pose.tvec if result.pose else None,
            corners,
            ids,
        )

    def draw_debug_overlay(self, image, rvec, tvec):
        cv2.drawFrameAxes(image, self.camera_matrix, self.dist_coeffs, rvec, tvec, 0.02)
        return image
