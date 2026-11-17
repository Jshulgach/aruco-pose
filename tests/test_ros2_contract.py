"""The optional ROS example's frame/status contract stays testable without ROS."""

import importlib.util
from pathlib import Path

import pytest

from aruco_pose import PoseResult

path = Path(__file__).resolve().parents[1] / "examples/ros2/protocol.py"
spec = importlib.util.spec_from_file_location("ros2_protocol", path)
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)


@pytest.mark.parametrize(
    "parent,child",
    [
        ("/camera", "target"),
        ("camera", "camera"),
        ("camera//optical", "target"),
        ("camera", ""),
        ("camera frame", "target"),
    ],
)
def test_invalid_frames_cannot_be_published(parent, child):
    with pytest.raises(ValueError):
        protocol.validate_frames(parent, child)


def test_terminal_status_is_not_a_measurement():
    values = protocol.status_values(
        None,
        parent="camera_optical_frame",
        child="target",
        frame_index=240,
        source_time_s=None,
        source_state="eof",
        reason="End of video",
    )
    assert values["tracking_status"] == "lost"
    assert values["measurement_valid"] == "false"
    assert values["source_state"] == "eof"
    assert values["source_time_s"] == "unavailable"


def test_frame_relabeling_is_rejected():
    result = PoseResult(
        0.0, "target", "camera_optical_frame", "target", "lost", "No markers"
    )
    with pytest.raises(ValueError, match="frames"):
        protocol.status_values(
            result, parent="base_link", child="target", frame_index=0, source_time_s=0.0
        )
