"""Compatibility imports; pose estimation lives in the shared package API."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aruco_pose.models.aruco_pose_estimator import (
    ArucoPoseEstimatorFromJSON,
    ArucoPoseEstimatorFromModel,
)

__all__ = ["ArucoPoseEstimatorFromJSON", "ArucoPoseEstimatorFromModel"]
