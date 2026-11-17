"""Printable rigid-board starter workflow. Distances are meters, pixels are unscaled."""

import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

from .pose import Tracker, TrackerConfig, draw_pose_result

DICTIONARY = "DICT_5X5_100"
CSV_FIELDS = [
    "frame",
    "time_s",
    "object_id",
    "status",
    "marker_ids",
    "marker_count",
    "tx_m",
    "ty_m",
    "tz_m",
    "qx",
    "qy",
    "qz",
    "qw",
    "reprojection_rmse_px",
    "reason",
    "observed_marker_ids",
    "rejected_marker_ids",
    "inlier_corner_count",
    "candidate_count",
    "ambiguity_resolved_by",
    "parent_frame",
    "child_frame",
]


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def marker_image(marker_id, pixels=280):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    return cv2.aruco.generateImageMarker(dictionary, marker_id, pixels)


def board_model():
    """2x2 board: 40 mm black squares, 20 mm gaps, origin at board center."""
    markers = []
    for marker_id, (x, y) in enumerate(
        [(-0.03, -0.03), (0.03, -0.03), (-0.03, 0.03), (0.03, 0.03)]
    ):
        corners = np.array(
            [[-0.02, -0.02, 0], [0.02, -0.02, 0], [0.02, 0.02, 0], [-0.02, 0.02, 0]]
        )
        markers.append({"id": marker_id, "corners_m": (corners + [x, y, 0]).tolist()})
    return {
        "schema_version": 1,
        "object_id": "starter_board",
        "units": "meters",
        "dictionary": DICTIONARY,
        "corner_order": "top_left,top_right,bottom_right,bottom_left",
        "frame": "origin at board center; +x printed right, +y printed down, +z into paper",
        "markers": markers,
    }


def _svg_start():
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
        '<rect width="210" height="297" fill="white"/>',
    ]


def print_kit(output):
    """SVG coordinates are millimeters; no external font or image assets required."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    model = board_model()
    svg = _svg_start()
    for marker in model["markers"]:
        image = marker_image(marker["id"], 7)
        x, y = np.array(marker["corners_m"][0])[:2] * 1000 + [105, 120]
        cell = 40 / 7
        for row, col in zip(*np.where(image == 0)):
            svg.append(
                f'<rect x="{x+col*cell:.8f}" y="{y+row*cell:.8f}" width="{cell:.8f}" height="{cell:.8f}" fill="black"/>'
            )
    svg += [
        '<text x="20" y="200" font-size="5">Starter board: DICT_5X5_100, IDs 0-3</text>',
        '<text x="20" y="210" font-size="4">Black marker squares: 40 mm. Gap: 20 mm.</text>',
        '<text x="20" y="220" font-size="4">Print at 100% / actual size. Disable fit-to-page.</text>',
        '<path d="M20 245 H70 M20 242 V248 M70 242 V248" stroke="black" fill="none"/>',
        '<text x="20" y="255" font-size="4">Measure this line: 50 mm</text>',
        "</svg>",
    ]
    (output / "marker_board.svg").write_text("\n".join(svg), encoding="utf-8")
    svg = _svg_start()
    for row in range(7):
        for col in range(10):
            if (row + col) % 2 == 0:
                svg.append(
                    f'<rect x="{5+20*col}" y="{40+20*row}" width="20" height="20" fill="black"/>'
                )
    svg += [
        '<text x="10" y="210" font-size="4">Calibration: 9 x 6 INNER corners, 20 mm squares.</text>',
        '<text x="10" y="220" font-size="4">Print at actual size. Measure a square before use.</text>',
        "</svg>",
    ]
    (output / "checkerboard.svg").write_text("\n".join(svg), encoding="utf-8")
    save_json(output / "board.json", model)
    return output


def load_model(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("units") != "meters" or not data.get("markers"):
        raise ValueError("Model must define units=meters and nonempty markers")
    ids = [m["id"] for m in data["markers"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Model marker IDs must be unique")
    for marker in data["markers"]:
        points = np.asarray(marker["corners_m"], dtype=float)
        if points.shape != (4, 3) or not np.isfinite(points).all():
            raise ValueError("Each marker needs four finite 3D corners in meters")
    return data


def open_capture(source):
    text = str(source)
    cap = cv2.VideoCapture(int(text) if text.isdecimal() else text)
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Cannot open video source: {source}")
    return cap, text.isdecimal()


def calibrate(
    source,
    output,
    cols=9,
    rows=6,
    square_size=0.02,
    stride=10,
    max_views=40,
    preview=False,
):
    if cols < 3 or rows < 3 or square_size <= 0 or stride < 1 or max_views < 8:
        raise ValueError(
            "Use at least 3x3 corners, positive square size/stride, and at least 8 views"
        )
    cap, live = open_capture(source)
    if live and not preview:
        cap.release()
        raise ValueError(
            "Camera calibration requires --preview: press SPACE to capture each view"
        )
    objects = np.zeros((cols * rows, 3), np.float32)
    objects[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size
    object_views, image_views = [], []
    size, frame_index = None, 0
    try:
        while len(image_views) < max_views:
            ok, frame = cap.read()
            if not ok:
                break
            current_size = (frame.shape[1], frame.shape[0])
            if size is not None and current_size != size:
                raise ValueError("Video resolution changed during calibration")
            size = current_size
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCornersSB(gray, (cols, rows))
            key = -1
            if preview:
                view = frame.copy()
                if found:
                    cv2.drawChessboardCorners(view, (cols, rows), corners, found)
                cv2.putText(
                    view,
                    f"Views: {len(image_views)}  SPACE=capture  Q=finish",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 100, 255),
                    2,
                )
                cv2.imshow("Calibration", view)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
            capture = key == 32 if live else frame_index % stride == 0
            if found and capture:
                object_views.append(objects.copy())
                image_views.append(corners)
            frame_index += 1
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()
    if len(image_views) < 8:
        raise ValueError(
            f"Only {len(image_views)} usable views; need at least 8 diverse checkerboard views"
        )
    # Repeated/near-identical observations do not constrain a useful calibration.
    descriptors = np.array(
        [p.reshape(-1, 2)[[0, cols - 1, -1, -cols]].ravel() for p in image_views]
    )
    diverse = []
    for descriptor in descriptors:
        if not diverse or min(np.linalg.norm(descriptor - d) for d in diverse) > 10:
            diverse.append(descriptor)
    if len(diverse) < 8:
        raise ValueError(
            "Need at least 8 distinct views: move/tilt the board across the image"
        )
    rms, matrix, distortion, _, _ = cv2.calibrateCamera(
        object_views, image_views, size, None, None
    )
    if (
        not np.isfinite(matrix).all()
        or not np.isfinite(distortion).all()
        or not np.isfinite(rms)
    ):
        raise ValueError("Calibration failed: nonfinite solution")
    result = {
        "schema_version": 1,
        "image_width": size[0],
        "image_height": size[1],
        "camera_matrix": matrix.tolist(),
        "distortion_coefficients": distortion.ravel().tolist(),
        "rms_px": float(rms),
        "views": len(image_views),
        "square_size_m": square_size,
        "inner_corners": [cols, rows],
    }
    save_json(output, result)
    return result


def load_calibration(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    matrix = np.array(data["camera_matrix"], dtype=float)
    distortion = np.array(data["distortion_coefficients"], dtype=float)
    if (
        matrix.shape != (3, 3)
        or not np.isfinite(matrix).all()
        or matrix[0, 0] <= 0
        or matrix[1, 1] <= 0
        or not np.isfinite(distortion).all()
        or distortion.size not in (4, 5, 8, 12, 14)
    ):
        raise ValueError("Invalid camera matrix or distortion coefficients")
    return data, matrix, distortion


def estimate_board(
    model, corners, ids, matrix, distortion, min_markers=2, max_error=3.0
):
    """Legacy tuple wrapper; new callers should consume Tracker.estimate/PoseResult."""
    tracker = Tracker(
        model,
        matrix,
        distortion,
        config=TrackerConfig(
            min_markers=min_markers, max_reprojection_rmse_px=max_error
        ),
    )
    result = tracker.estimate(corners, ids, timestamp_s=0.0)
    return (
        result.pose.rvec if result.pose else None,
        result.pose.tvec if result.pose else None,
        list(result.inlier_marker_ids),
        result.reprojection_rmse_px,
        result.status,
    )


def track(
    source,
    model_path,
    calibration_path,
    csv_path,
    preview=False,
    output_video=None,
    min_markers=2,
    max_error=3.0,
    outlier_threshold=3.0,
    ambiguity_gap=0.05,
):
    model = load_model(model_path)
    calibration, matrix, distortion = load_calibration(calibration_path)
    if not 1 <= min_markers <= len(model["markers"]) or max_error <= 0:
        raise ValueError("Invalid minimum marker count or reprojection threshold")
    config = TrackerConfig(
        min_markers=min_markers,
        max_reprojection_rmse_px=max_error,
        outlier_threshold_px=outlier_threshold,
        ambiguity_gap_px=ambiguity_gap,
    )
    tracker = Tracker(
        model,
        matrix,
        distortion,
        config=config,
        image_size=(calibration["image_width"], calibration["image_height"]),
    )
    cap, live = open_capture(source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not np.isfinite(fps) or fps <= 0:
        cap.release()
        raise ValueError(
            "Source has no valid FPS; convert the video to a fixed frame rate"
        )
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    frame_index = 0
    counts = dict.fromkeys(["measured", "lost", "rejected", "ambiguous"], 0)
    previous = None
    start = time.monotonic()
    try:
        with path.open("w", newline="", encoding="utf-8") as stream:
            csv_writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            csv_writer.writeheader()
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                size = (frame.shape[1], frame.shape[0])
                if size != (calibration["image_width"], calibration["image_height"]):
                    raise ValueError(
                        f"Frame size {size} differs from calibration; recalibrate at this resolution"
                    )
                if output_video and writer is None:
                    Path(output_video).parent.mkdir(parents=True, exist_ok=True)
                    codec = (
                        "MJPG"
                        if Path(output_video).suffix.lower() == ".avi"
                        else "mp4v"
                    )
                    writer = cv2.VideoWriter(
                        str(output_video), cv2.VideoWriter_fourcc(*codec), fps, size
                    )
                    if not writer.isOpened():
                        raise ValueError(f"Cannot create output video: {output_video}")
                timestamp = time.monotonic() - start if live else frame_index / fps
                result = tracker.process(
                    frame, timestamp_s=timestamp, previous=previous
                )
                counts[result.status] += 1
                if result.status == "measured":
                    previous = result
                csv_writer.writerow(result.to_csv_row(frame_index))
                if writer is not None or preview:
                    draw_pose_result(frame, result, matrix, distortion)
                    if writer is not None:
                        writer.write(frame)
                frame_index += 1
                if preview:
                    cv2.imshow("Rigid target tracking", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        if preview:
            cv2.destroyAllWindows()
    if frame_index == 0:
        raise ValueError("Source contains no readable frames")
    summary = {
        "schema_version": 2,
        "pose_api_schema_version": 1,
        "frames": frame_index,
        **counts,
        "csv": str(path),
        "time_basis": "monotonic_since_start" if live else "frame_index/fps",
        "pose_transform": "p_camera = R_object_to_camera @ p_object + t_object_to_camera",
        "camera_frame": "+x right, +y down, +z forward",
        "quaternion_order": "x,y,z,w",
        "units": "meters",
        "model": model,
        "calibration": calibration,
        "tracker_config": dict(config.__dict__),
        "min_markers": min_markers,
        "max_reprojection_rmse_px": max_error,
    }
    save_json(path.with_suffix(".summary.json"), summary)
    return summary
