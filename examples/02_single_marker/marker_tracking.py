"""Legacy tag-group model, now using every visible marker and the shared pose API."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from examples.pose_api_demo import run_tracker
from aruco_pose.models.aruco_pose_pipeline import ArucoPoseEstimator
from aruco_pose.pose import TrackerConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="0")
    parser.add_argument("--k-matrix", type=Path, default=ROOT / "camera_intrinsics.npy")
    parser.add_argument("--d-coeff", type=Path, default=ROOT / "camera_distortion.npy")
    parser.add_argument("--model", type=Path, default=ROOT / "config/aruco_group.json")
    parser.add_argument("--min-markers", type=int, default=2)
    parser.add_argument("--csv", type=Path, default=ROOT / "output/tag_group_poses.csv")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    estimator = ArucoPoseEstimator(
        np.load(args.k_matrix),
        np.load(args.d_coeff),
        tag_data_path=args.model,
        config=TrackerConfig(min_markers=args.min_markers),
    )
    count = run_tracker(estimator.tracker, args.source, args.csv, not args.no_preview)
    print(f"Wrote {count} shared pose rows to {args.csv}")


if __name__ == "__main__":
    main()
