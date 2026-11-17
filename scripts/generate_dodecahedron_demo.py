"""Render a synthetic target and track its pixels with the public pose API.

Run from the repository root with the development environment. Web encoding also
requires the optional asset-generation tool: pip install imageio-ffmpeg.
This model's marker orientations are generated here; they do not describe an
existing physical target or replace the physical-target config files.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from aruco_pose import Tracker, TrackerConfig
from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel
from aruco_pose.pose import draw_pose_result

ROOT = Path(__file__).resolve().parents[1]
SIZE = (960, 720)
K = np.array([[1500., 0, 480], [0, 1500., 360], [0, 0, 1]])
D = np.zeros(5)


def make_target():
    geometry = CleanDodecahedronModel(edge_length=0.025)
    markers, normals = [], []
    half = 0.015 / 2
    for marker_id, face in zip(geometry.aruco_id_order, geometry.pentagon_faces):
        vertices = geometry.vertices[face]
        center = vertices.mean(axis=0)
        normal = center / np.linalg.norm(center)
        x = vertices[1] - vertices[0]
        x /= np.linalg.norm(x)
        # Image coordinates: x right, y down, corner winding into the solid.
        y = np.cross(x, normal)
        corners = np.array([center - half*x - half*y, center + half*x - half*y,
                            center + half*x + half*y, center - half*x + half*y])
        markers.append({"id": int(marker_id), "corners_m": corners.tolist()})
        normals.append(normal)
    model = {"object_id": "synthetic_dodecahedron", "units": "meters",
             "dictionary": "DICT_5X5_100", "markers": markers}
    return geometry, model, np.array(normals)


def trajectory(phase):
    rotation = Rotation.from_euler("xyz", [0.34 + 0.15*np.sin(phase), phase, 0.17])
    return rotation.as_rotvec(), np.array([0.009*np.sin(phase), 0.006*np.cos(phase), 0.25])


def render_frame(phase):
    """Return unannotated pixels plus ground truth, never a tracker observation."""
    geometry, model, normals = make_target()
    rvec, tvec = trajectory(phase)
    rotation = Rotation.from_rotvec(rvec).as_matrix()
    scale = 2  # Supersample face edges and printed marker textures.
    camera = K.copy()
    camera[:2] *= scale
    frame = np.full((SIZE[1]*scale, SIZE[0]*scale, 3), (48, 61, 53), np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    faces = []
    for index, face in enumerate(geometry.pentagon_faces):
        center_camera = rotation @ geometry.vertices[face].mean(axis=0) + tvec
        normal_camera = rotation @ normals[index]
        if np.dot(normal_camera, center_camera) < 0:
            faces.append((center_camera[2], index, normal_camera))
    for _, index, normal in sorted(faces, key=lambda face: -face[0]):
        face = geometry.pentagon_faces[index]
        polygon = cv2.projectPoints(geometry.vertices[face], rvec, tvec, camera, D)[0]
        shade = int(215 + 30*max(0, -normal[2]))
        cv2.fillConvexPoly(frame, np.rint(polygon).astype(np.int32), (shade,)*3)
        cv2.polylines(frame, [np.rint(polygon).astype(np.int32)], True, (120, 137, 125), 2)
        marker = model["markers"][index]
        texture = cv2.aruco.generateImageMarker(dictionary, marker["id"], 140)
        destination = cv2.projectPoints(np.array(marker["corners_m"]), rvec, tvec, camera, D)[0].reshape(4, 2)
        homography = cv2.getPerspectiveTransform(np.float32([[0, 0], [139, 0], [139, 139], [0, 139]]), destination.astype(np.float32))
        warped = cv2.warpPerspective(texture, homography, (SIZE[0]*scale, SIZE[1]*scale))
        mask = cv2.warpPerspective(np.full_like(texture, 255), homography, (SIZE[0]*scale, SIZE[1]*scale))
        frame[mask > 0] = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)[mask > 0]
    return cv2.resize(frame, SIZE, interpolation=cv2.INTER_AREA), rvec, tvec


def annotate(frame, result, geometry):
    draw_pose_result(frame, result, K, D, axis_length=0.045)
    if result.pose is not None:
        projected = cv2.projectPoints(geometry.vertices, result.pose.rvec, result.pose.tvec, K, D)[0]
        # Visible face edges only, based on the estimated pose.
        rotation = Rotation.from_rotvec(result.pose.rvec.ravel()).as_matrix()
        for face in geometry.pentagon_faces:
            center = geometry.vertices[face].mean(axis=0)
            if np.dot(rotation @ center, rotation @ center + result.pose.tvec.ravel()) < 0:
                cv2.polylines(frame, [np.rint(projected[face]).astype(np.int32)], True, (134, 238, 212), 2, cv2.LINE_AA)
    cv2.rectangle(frame, (0, 0), (SIZE[0], 49), (48, 61, 53), -1)
    cv2.putText(frame, "SYNTHETIC / 12-FACE TARGET", (24, 31), cv2.FONT_HERSHEY_SIMPLEX, .6, (225, 237, 222), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{result.status.upper()} | {len(result.inlier_marker_ids)} markers", (24, 657), cv2.FONT_HERSHEY_SIMPLEX, .65, (134, 238, 212), 1, cv2.LINE_AA)
    cv2.putText(frame, "25 mm edges / axes + outline from estimated pose", (24, 690), cv2.FONT_HERSHEY_SIMPLEX, .52, (225, 237, 222), 1, cv2.LINE_AA)
    return frame


def generate(output, *, fps=24, seconds=10):
    import imageio_ffmpeg  # Optional developer tool; not a package dependency.
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / "output/dodecahedron-demo"
    work.mkdir(parents=True, exist_ok=True)
    geometry, model, _ = make_target()
    tracker = Tracker(model, K, D, config=TrackerConfig(min_markers=2), image_size=SIZE)
    raw = work / "annotated.mp4"
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, SIZE)
    if not writer.isOpened():
        raise RuntimeError("Cannot create intermediate video")
    statuses, errors, angle_errors, counts = Counter(), [], [], []
    try:
        for index in range(fps*seconds):
            frame, rvec, tvec = render_frame(2*np.pi*index/(fps*seconds))
            result = tracker.process(frame, timestamp_s=index/fps)
            statuses[result.status] += 1
            counts.append(len(result.inlier_marker_ids))
            if result.pose is not None:
                errors.append(float(np.linalg.norm(result.pose.tvec.ravel() - tvec)*1000))
                angle_errors.append(float(np.degrees((Rotation.from_rotvec(result.pose.rvec.ravel()).inv()*Rotation.from_rotvec(rvec)).magnitude())))
            writer.write(annotate(frame, result, geometry))
    finally:
        writer.release()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = output / "dodecahedron-demo.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-an", "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video)], check=True)
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "1.5", "-i", str(video), "-frames:v", "1", str(output / "dodecahedron-preview.jpg")], check=True)
    report = {"source": "Entirely synthetic; markers detected from rendered pixels by Tracker.process, without a pose prior.",
              "fps": fps, "seconds": seconds, "frames": fps*seconds, "statuses": dict(statuses),
              "edge_length_m": .025, "marker_size_m": .015,
              "minimum_inlier_markers": min(counts), "maximum_inlier_markers": max(counts),
              "max_translation_error_mm": max(errors) if errors else None,
              "max_rotation_error_degrees": max(angle_errors) if angle_errors else None,
              "note": "Synthetic software verification, not physical tracking accuracy."}
    (output / "dodecahedron-demo.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/assets")
    args = parser.parse_args()
    generate(args.output)
