"""Legacy JSON/model adapters backed by the shared pose API.

New code should use estimate_result/process. estimate_pose retains the historical
(rvec, tvec, inlier_ids) tuple, with None poses for lost/rejected/ambiguous frames.
"""

import json
import cv2
import numpy as np
from ..core.detector import ARUCO_DICT, UnifiedArucoDetector
from ..pose import Tracker, TrackerConfig, model_from_extrinsics


def _dictionary_name(value):
    if isinstance(value, str):
        return value
    return next(name for name, number in ARUCO_DICT.items() if number == value)


class _SharedEstimator:
    def _initialize(
        self, matrix, distortion, marker_size, extrinsics, aruco_dict, config, object_id
    ):
        self.k = np.array(matrix)
        self.d = np.array(distortion)
        self.marker_size = marker_size
        dictionary = _dictionary_name(aruco_dict)
        model = model_from_extrinsics(
            extrinsics, marker_size, object_id=object_id, dictionary=dictionary
        )
        self.tracker = Tracker(
            model, self.k, self.d, config=config or TrackerConfig(min_markers=1)
        )
        self.detector = UnifiedArucoDetector(dictionary)
        self.last_result = None

    def detect(self, frame):
        corners, ids, _ = self.detector.detect(frame)
        return corners, ids

    def estimate_result(self, corners, ids, timestamp_s=0.0, *, previous=None):
        self.last_result = self.tracker.estimate(
            corners, ids, timestamp_s, previous=previous
        )
        return self.last_result

    def process(self, frame, timestamp_s, *, previous=None):
        self.last_result = self.tracker.process(frame, timestamp_s, previous=previous)
        return self.last_result

    def estimate_pose(self, corners, ids):
        result = self.estimate_result(corners, ids)
        return (
            result.pose.rvec if result.pose else None,
            result.pose.tvec if result.pose else None,
            list(result.inlier_marker_ids),
        )


class ArucoPoseEstimatorFromJSON(_SharedEstimator):
    def __init__(
        self,
        k_matrix,
        d_coeffs,
        marker_size,
        json_path,
        aruco_dict=cv2.aruco.DICT_5X5_100,
        *,
        config=None
    ):
        with open(json_path, encoding="utf-8") as stream:
            faces = json.load(stream)["faces"]
        raw = {int(face["aruco_id"]): face["extrinsics"] for face in faces}
        self.extrinsics = {
            mid: (
                np.array(value[3:], dtype=np.float32),
                np.array(value[:3], dtype=np.float32),
            )
            for mid, value in raw.items()
        }
        self._initialize(
            k_matrix, d_coeffs, marker_size, raw, aruco_dict, config, "dodecahedron"
        )


class ArucoPoseEstimatorFromModel(_SharedEstimator):
    def __init__(
        self,
        k_matrix,
        d_coeffs,
        marker_size,
        model,
        aruco_dict=cv2.aruco.DICT_5X5_100,
        *,
        config=None
    ):
        self.model = model
        self.extrinsics = {
            int(face["aruco_id"]): face["extrinsics"] for face in model.extrinsics
        }
        self._initialize(
            k_matrix,
            d_coeffs,
            marker_size,
            self.extrinsics,
            aruco_dict,
            config,
            "dodecahedron",
        )
