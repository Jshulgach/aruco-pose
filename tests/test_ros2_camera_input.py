"""Raw camera geometry/pixel/time checks also run on machines without ROS."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

path = Path(__file__).resolve().parents[1] / "examples/ros2/camera_input.py"
spec = importlib.util.spec_from_file_location("camera_input_contract", path)
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


@pytest.mark.parametrize(
    "encoding,values,expected",
    [
        ("mono8", [13], [13]),
        ("bgr8", [1, 2, 3], [1, 2, 3]),
        ("rgb8", [3, 2, 1], [1, 2, 3]),
        ("rgba8", [3, 2, 1, 9], [1, 2, 3]),
        ("bgra8", [1, 2, 3, 9], [1, 2, 3]),
    ],
)
def test_decode_padded_rows_and_color_channels(encoding, values, expected):
    row = bytes(values + [255, 255])
    message = NS(encoding=encoding, width=1, height=2, step=len(row), data=row * 2)
    actual = camera.decode_image(message)
    assert actual.shape == ((2, 1) if encoding == "mono8" else (2, 1, 3))
    np.testing.assert_array_equal(actual.reshape(2, -1), [expected, expected])


@pytest.mark.parametrize(
    "changes", [dict(encoding="mono16"), dict(step=1), dict(data=b""), dict(width=0)]
)
def test_invalid_image_buffers_are_rejected(changes):
    fields = dict(encoding="bgr8", width=1, height=1, step=3, data=b"abc")
    fields.update(changes)
    with pytest.raises(ValueError):
        camera.decode_image(NS(**fields))


def info():
    return NS(
        header=NS(frame_id="camera_optical_frame"),
        width=960,
        height=720,
        k=[1500.0, 0.0, 480.0, 0.0, 1500.0, 360.0, 0.0, 0.0, 1.0],
        d=[0.0] * 5,
        distortion_model="plumb_bob",
        binning_x=0,
        binning_y=0,
        roi=NS(x_offset=0, y_offset=0, width=0, height=0, do_rectify=False),
    )


@pytest.mark.parametrize(
    "fault",
    ["frame", "uncalibrated", "fisheye", "binning", "roi", "coefficients", "nan"],
)
def test_unsupported_or_mismatched_calibration_is_rejected(fault):
    message = info()
    if fault == "frame":
        message.header.frame_id = "base_link"
    if fault == "uncalibrated":
        message.k[0] = 0.0
    if fault == "fisheye":
        message.distortion_model = "equidistant"
    if fault == "binning":
        message.binning_x = 2
    if fault == "roi":
        message.roi.x_offset = 20
    if fault == "coefficients":
        message.d = []
    if fault == "nan":
        message.k[0] = float("nan")
    with pytest.raises(ValueError):
        camera.raw_calibration(message, "camera_optical_frame")


def test_raw_calibration_uses_k_and_d_without_guessing_p():
    message = info()
    message.p = [0.0] * 12  # Raw mode never derives intrinsics from P.
    matrix, distortion, size = camera.raw_calibration(message, "camera_optical_frame")
    assert size == (960, 720)
    assert matrix[0, 0] == 1500.0
    np.testing.assert_array_equal(distortion, [0.0] * 5)
    message.distortion_model = "rational_polynomial"
    message.d = [0.0] * 8
    assert len(camera.raw_calibration(message, "camera_optical_frame")[1]) == 8


@pytest.mark.parametrize(
    "sec,nanosec,now",
    [
        (0, 0, 1_000_000_000),
        (1, 1_000_000_000, 2_000_000_000),
        (1, 0, 0),
        (1, 0, 2_000_000_000),
        (3, 0, 2_000_000_000),
    ],
)
def test_bad_stale_or_future_acquisition_times_are_rejected(sec, nanosec, now):
    with pytest.raises(ValueError):
        camera.check_image_time(NS(sec=sec, nanosec=nanosec), now, 0.25, 0.05)


def test_integer_acquisition_stamp_is_preserved():
    assert (
        camera.check_image_time(NS(sec=123, nanosec=456), 123_001_000_000, 0.25, 0.05)
        == 123_000_000_456
    )
