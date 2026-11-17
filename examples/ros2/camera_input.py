"""ROS-free validation and decoding for raw sensor_msgs camera messages."""

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


def raw_calibration(info, parent):
    """Use raw-image K/D only. Never guess rectification, cropping or binning."""
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
            "CameraInfo ROI/binning is unsupported; publish full-resolution raw images and matching calibration"
        )
    matrix = np.asarray(info.k, dtype=float).reshape(3, 3)
    distortion = np.asarray(info.d, dtype=float)
    expected = {"plumb_bob": 5, "rational_polynomial": 8}
    if (
        info.distortion_model not in expected
        or distortion.size != expected[info.distortion_model]
    ):
        raise ValueError(
            "Use calibrated plumb_bob (5 coefficients) or rational_polynomial (8); fisheye/rectified inputs are unsupported"
        )
    if (
        not np.isfinite(matrix).all()
        or not np.isfinite(distortion).all()
        or matrix[0, 0] <= 0
        or matrix[1, 1] <= 0
        or not np.allclose(matrix[2], [0, 0, 1])
        or not np.isclose(matrix[0, 1], 0)
        or not np.isclose(matrix[1, 0], 0)
    ):
        raise ValueError("CameraInfo K/D is invalid or uncalibrated")
    return matrix, distortion, (info.width, info.height)
