"""ROS-free pixel validation and raw/rectified CameraInfo geometry."""

from dataclasses import replace

import cv2
import numpy as np


class StaleImageError(ValueError):
    """An acquisition is too old to publish as a current measurement."""


def stamp_ns(stamp):
    if stamp.sec < 0 or not 0 <= stamp.nanosec < 1_000_000_000:
        raise ValueError("Invalid acquisition timestamp")
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def check_image_time(stamp, now_ns, max_age_s, future_tolerance_s):
    acquisition = stamp_ns(stamp)
    if acquisition == 0 or now_ns <= 0:
        raise ValueError(
            "Image and ROS clock must have nonzero timestamps; check /clock and clock domains"
        )
    age_s = (now_ns - acquisition) / 1e9
    if age_s > max_age_s:
        raise StaleImageError("Image acquisition timestamp is stale")
    if age_s < -future_tolerance_s:
        raise ValueError(
            "Image timestamp is in the future; check camera/ROS clock synchronization"
        )
    return acquisition


def decode_image(message):
    """Decode supported uint8 encodings, including padded rows, without cv_bridge."""
    channels = {"mono8": 1, "bgr8": 3, "rgb8": 3, "bgra8": 4, "rgba8": 4}
    if message.encoding not in channels:
        raise ValueError(
            "Unsupported image encoding; use mono8, bgr8, rgb8, bgra8 or rgba8"
        )
    count = channels[message.encoding]
    width, height = message.width, message.height
    if width <= 0 or height <= 0 or message.step < width * count:
        raise ValueError("Invalid image dimensions or row stride")
    data = np.frombuffer(message.data, dtype=np.uint8)
    if data.size != height * message.step:
        raise ValueError("Image data length differs from height * step")
    pixels = data.reshape(height, message.step)[:, : width * count]
    pixels = (
        pixels.reshape(height, width)
        if count == 1
        else pixels.reshape(height, width, count)
    )
    conversion = {
        "rgb8": cv2.COLOR_RGB2BGR,
        "rgba8": cv2.COLOR_RGBA2BGR,
        "bgra8": cv2.COLOR_BGRA2BGR,
    }
    # Endianness has no effect on single-byte channels. Own the returned buffer.
    return (
        cv2.cvtColor(pixels, conversion[message.encoding])
        if message.encoding in conversion
        else pixels.copy()
    )


def _validate_camera_geometry(info, parent):
    if info.header.frame_id != parent:
        raise ValueError("CameraInfo optical frame differs from --camera-frame")
    if info.width <= 0 or info.height <= 0:
        raise ValueError("CameraInfo needs positive image dimensions")
    roi = info.roi
    if (
        info.binning_x not in (0, 1)
        or info.binning_y not in (0, 1)
        or roi.x_offset
        or roi.y_offset
        or roi.do_rectify
        or roi.width not in (0, info.width)
        or roi.height not in (0, info.height)
    ):
        raise ValueError(
            "CameraInfo ROI/binning is unsupported; publish full-resolution images and matching calibration"
        )


def _validate_intrinsics(matrix, name):
    if (
        not np.isfinite(matrix).all()
        or matrix[0, 0] <= 0
        or matrix[1, 1] <= 0
        or not np.allclose(matrix[2], [0, 0, 1], rtol=0, atol=1e-9)
        or not np.isclose(matrix[0, 1], 0, rtol=0, atol=1e-9)
        or not np.isclose(matrix[1, 0], 0, rtol=0, atol=1e-9)
    ):
        raise ValueError(f"CameraInfo {name} is invalid or uncalibrated")


def raw_calibration(info, parent):
    """Use raw-image K/D only. Never guess rectification, cropping or binning."""
    _validate_camera_geometry(info, parent)
    matrix = np.asarray(info.k, dtype=float).reshape(3, 3)
    distortion = np.asarray(info.d, dtype=float)
    expected = {"plumb_bob": 5, "rational_polynomial": 8}
    if (
        info.distortion_model not in expected
        or distortion.size != expected[info.distortion_model]
    ):
        raise ValueError(
            "Raw input requires plumb_bob (5 coefficients) or rational_polynomial (8); use explicit rectified mode for already rectified pixels"
        )
    _validate_intrinsics(matrix, "K")
    if not np.isfinite(distortion).all():
        raise ValueError("CameraInfo K/D is invalid or uncalibrated")
    return matrix, distortion, (info.width, info.height)


def rectified_calibration(info, parent):
    """P's left 3x3 describes rectified pixels; R maps original -> rectified axes.

    P's fourth column is a stereo reference-origin offset, not a camera mounting
    transform. Camera-local PnP therefore uses only its left 3x3, as OpenCV's
    rectification maps do. No raw D is applied to rectified pixels.
    """
    _validate_camera_geometry(info, parent)
    _validate_intrinsics(np.asarray(info.k, dtype=float).reshape(3, 3), "K")
    projection = np.asarray(info.p, dtype=float).reshape(3, 4)
    rotation = np.asarray(info.r, dtype=float).reshape(3, 3)
    if not np.isfinite(projection).all() or not np.allclose(
        projection[2], [0, 0, 1, 0], rtol=0, atol=1e-9
    ):
        raise ValueError(
            "CameraInfo P must be finite with canonical third row [0,0,1,0]"
        )
    _validate_intrinsics(projection[:, :3], "P intrinsics")
    if (
        not np.isfinite(rotation).all()
        or not np.allclose(rotation.T @ rotation, np.eye(3), rtol=0, atol=1e-6)
        or not np.isclose(np.linalg.det(rotation), 1.0, rtol=0, atol=1e-6)
    ):
        raise ValueError(
            "CameraInfo R must be a finite proper rotation; zero, reflected or nonorthonormal R is invalid"
        )
    return projection[:, :3].copy(), np.zeros(5), (info.width, info.height), rotation


def original_camera_result(result, rotation, parent):
    """Convert all rectified candidates/accepted pose back to header axes.

    The caller must retain the unconverted result as the Tracker's prior.
    """
    from aruco_pose import Pose

    camera_from_rectified = Pose.from_rvec(
        cv2.Rodrigues(rotation.T)[0], np.zeros(3), parent, result.parent_frame
    )
    return replace(
        result,
        parent_frame=parent,
        pose=camera_from_rectified.compose(result.pose) if result.pose else None,
        candidates=tuple(
            replace(candidate, pose=camera_from_rectified.compose(candidate.pose))
            for candidate in result.candidates
        ),
    )
