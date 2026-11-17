"""
aruco-pose: rigid marker pose estimation
A robust toolkit for ArUco marker detection, pose estimation, and custom 3D model tracking.
"""

__version__ = "0.3.0"
__author__ = "Jonathan Shulgach"

from .core.detector import UnifiedArucoDetector
from .pose import Tracker, TrackerConfig, Pose, PoseResult, PoseCandidate, MarkerObservation
from .utils.visualization import ArucoVisualizer
from .utils.config import ProjectConfig, CameraConfig, CalibrationConfig, ArucoConfig
from .utils.performance import PerformanceMonitor
from .utils.logger import setup_logger

__all__ = [
    'Tracker', 'TrackerConfig', 'Pose', 'PoseResult', 'PoseCandidate', 'MarkerObservation',
    'UnifiedArucoDetector',
    'ArucoVisualizer',
    'ProjectConfig',
    'CameraConfig',
    'CalibrationConfig',
    'ArucoConfig',
    'PerformanceMonitor',
    'setup_logger',
]
