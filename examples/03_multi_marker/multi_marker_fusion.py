"""Compatibility import for the shared multi-marker tag-group adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aruco_pose.models.aruco_pose_pipeline import ArucoPoseEstimator

__all__ = ["ArucoPoseEstimator"]
