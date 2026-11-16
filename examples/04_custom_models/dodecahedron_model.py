"""Compatibility imports for the canonical model implementation.

Edge lengths are expressed in meters; 0.025 produces 25 mm pentagon sides.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel, DodecahedronWithMarkers

__all__ = ['CleanDodecahedronModel', 'DodecahedronWithMarkers']
