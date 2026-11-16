import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2
import json
import numpy as np
from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel

def rotation_matrix_z(degrees):
    radians = np.deg2rad(degrees)
    c, s = np.cos(radians), np.sin(radians)
    return np.array([
        [c, -s, 0],
        [s,  c, 0],
        [0,  0, 1]
    ])

# Optional: rotation correction per face (degrees around face Z)
rotation_offsets = {0: 18,
                    1: -18,
                    3: -18,
                    4: -18,
                    5: -80,
                    6: -90,
                    7: -126,
                    8: -62,
                    9: -62,
                    10: -62,
                    11: -126,
                    12: 0}  # You can specify rotation offsets for specific faces here

def generate_model(edge_length=0.017):
    """Build a face model with physical pentagon edges in meters."""
    model = CleanDodecahedronModel(edge_length=edge_length)
    faces_output = []

    for idx, face in enumerate(model.pentagon_faces):
        aruco_id = int(model.aruco_id_order[idx])
        face_verts = model.vertices[face]
        center = np.mean(face_verts, axis=0)

        # Coordinate frame for marker
        x_axis = face_verts[1] - face_verts[0]
        x_axis /= np.linalg.norm(x_axis)
        v2 = face_verts[2] - face_verts[0]
        z_axis = np.cross(x_axis, v2)
        z_axis /= np.linalg.norm(z_axis)
        y_axis = np.cross(z_axis, x_axis)

        R = np.stack([x_axis, y_axis, z_axis], axis=1)

        # Optional Z-axis correction
        correction = rotation_matrix_z(rotation_offsets.get(aruco_id, 0))
        R = R @ correction

        rvec, _ = cv2.Rodrigues(R)
        extrinsics = list(center) + list(rvec.flatten())

        faces_output.append({
            "face_index": idx,
            "aruco_id": aruco_id,
            "vertices": face_verts.tolist(),
            "center": center.tolist(),
            "extrinsics": extrinsics
        })

    return {"faces": faces_output, "edge_length": edge_length, "units": "meters"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export a dodecahedron with correctly scaled edges")
    parser.add_argument("--edge-length", type=float, default=0.017,
                        help="Pentagon edge length in meters (0.025 = 25 mm)")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "config" / "dodecahedron_with_markers.json")
    args = parser.parse_args()
    data = generate_model(args.edge_length)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.edge_length * 1000:g} mm edge model to {args.output}")
