"""Compatibility import for the recovered tracking helper."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aruco_pose.tracking.predictive_filter import PredictivePoseFilter
