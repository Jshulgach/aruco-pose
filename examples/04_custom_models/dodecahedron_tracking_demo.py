"""Dodecahedron example using the shared robust pose API and CSV semantics."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from examples.pose_api_demo import run_tracker
from aruco_pose.models.aruco_pose_estimator import ArucoPoseEstimatorFromJSON
from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel
from aruco_pose.pose import TrackerConfig
from aruco_pose.utils.dodecahedron_overlay import draw_dodecahedron


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="0")
    parser.add_argument("--k-matrix", type=Path, default=ROOT / "camera_intrinsics.npy")
    parser.add_argument("--d-coeff", type=Path, default=ROOT / "camera_distortion.npy")
    parser.add_argument(
        "--model", type=Path, default=ROOT / "config/dodecahedron_with_markers.json"
    )
    parser.add_argument(
        "--marker-size", type=float, default=0.015, help="Printed square side in meters"
    )
    parser.add_argument("--min-markers", type=int, default=2)
    parser.add_argument(
        "--csv", type=Path, default=ROOT / "output/dodecahedron_poses.csv"
    )
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    matrix, distortion = np.load(args.k_matrix), np.load(args.d_coeff)
    estimator = ArucoPoseEstimatorFromJSON(
        matrix,
        distortion,
        args.marker_size,
        args.model,
        config=TrackerConfig(min_markers=args.min_markers),
    )
    data = json.loads(args.model.read_text(encoding="utf-8"))
    model = CleanDodecahedronModel(edge_length=data["edge_length"])

    def overlay(frame, pose):
        draw_dodecahedron(frame, pose.rvec, pose.tvec, model, matrix, distortion)

    count = run_tracker(
        estimator.tracker, args.source, args.csv, not args.no_preview, overlay
    )
    print(f"Wrote {count} shared pose rows to {args.csv}")


if __name__ == "__main__":
    main()
