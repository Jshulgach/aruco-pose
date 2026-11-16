"""Repository-only compatibility wrapper; prefer python -m aruco_pose."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aruco_pose.cli import cli

if __name__ == "__main__":
    cli()
