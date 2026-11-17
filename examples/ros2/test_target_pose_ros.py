"""Run with ROS 2 Jazzy sourced. Uses real ROS messages and DDS, not ROS mocks."""

import argparse
import csv
from pathlib import Path
import sys
import time

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rclpy
from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import PoseStamped
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from tf2_msgs.msg import TFMessage

from aruco_pose import Pose, PoseResult
from target_pose_node import TargetPoseNode, messages_for

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("status", ["lost", "rejected", "ambiguous"])
def test_unmeasured_results_never_create_pose_or_tf(status):
    result = PoseResult(
        0.0, "target", "camera_optical_frame", "target", status, "test case"
    )
    pose, transform, diagnostic = messages_for(
        result,
        Time(sec=1),
        parent="camera_optical_frame",
        child="target",
        frame_index=5,
        source_time_s=0.2,
    )
    assert pose is None and transform is None
    assert diagnostic.status[0].level == DiagnosticStatus.WARN
    values = {value.key: value.value for value in diagnostic.status[0].values}
    assert values["tracking_status"] == status
    assert values["measurement_valid"] == "false"


def test_pose_tf_same_stamp_units_direction_and_quaternion():
    rotation = Rotation.from_euler("xyz", [0.2, -0.3, 0.4])
    pose = Pose(
        "camera_optical_frame", "target", (0.1, -0.2, 0.3), tuple(rotation.as_quat())
    )
    result = PoseResult(
        1.0, "target", pose.parent_frame, pose.child_frame, "measured", "", pose=pose
    )
    measured, tf, status = messages_for(
        result,
        Time(sec=42, nanosec=123),
        parent=pose.parent_frame,
        child=pose.child_frame,
        frame_index=1,
        source_time_s=1.0,
    )
    assert measured.header == tf.header == status.header
    assert tf.child_frame_id == "target"
    assert tf.header.frame_id == "camera_optical_frame"
    t, q = tf.transform.translation, tf.transform.rotation
    np.testing.assert_allclose([t.x, t.y, t.z], pose.translation_m)
    np.testing.assert_allclose([q.x, q.y, q.z, q.w], pose.quaternion_xyzw)
    point = np.array([0.02, -0.01, 0.04])
    np.testing.assert_allclose(
        Rotation.from_quat([q.x, q.y, q.z, q.w]).apply(point) + [t.x, t.y, t.z],
        pose.transform_points(point),
    )
    assert measured.pose.position.x == t.x and measured.pose.orientation.w == q.w


def test_real_replay_publishes_matching_pose_tf_status_then_eof():
    rclpy.init()
    sender = receiver = executor = None
    try:
        kit = ROOT / "assets/dodecahedron"
        args = argparse.Namespace(
            source=str(kit / "tracking.mp4"),
            model=str(kit / "model.json"),
            calibration=str(kit / "replay_camera.json"),
            camera_frame="camera_optical_frame",
            target_frame="dodecahedron_25mm",
            min_markers=2,
            loop=False,
            no_tf=False,
        )
        sender = TargetPoseNode(args)
        sender.timer.cancel()
        receiver = Node("aruco_replay_test_receiver")
        poses, transforms, statuses = [], [], []
        subscriptions = [
            receiver.create_subscription(
                PoseStamped, "/aruco_target_tracker/pose", poses.append, 1000
            ),
            receiver.create_subscription(
                TFMessage,
                "/tf",
                lambda message: transforms.extend(message.transforms),
                1000,
            ),
            receiver.create_subscription(
                DiagnosticArray, "/aruco_target_tracker/status", statuses.append, 1000
            ),
        ]
        executor = SingleThreadedExecutor()
        executor.add_node(sender)
        executor.add_node(receiver)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (
                all(
                    receiver.count_publishers(subscription.topic_name)
                    for subscription in subscriptions
                )
                and sender.pose_publisher.get_subscription_count()
                and sender.status_publisher.get_subscription_count()
                and sender.count_subscribers("/tf")
            ):
                break
            executor.spin_once(timeout_sec=0.05)
        else:
            pytest.fail("ROS publishers/subscribers did not discover one another")
        sender.timer.reset()
        deadline = time.monotonic() + 30
        eof = None
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
            if statuses:
                values = {v.key: v.value for v in statuses[-1].status[0].values}
                if values["source_state"] == "eof":
                    eof = statuses[-1]
                    if len(poses) == len(transforms) == 240:
                        break
        assert eof is not None
        assert sender.frame_index == 240
        assert len(poses) == len(transforms) == 240
        measured = [
            status
            for status in statuses
            if status.status[0].level == DiagnosticStatus.OK
        ]
        assert len(measured) == 240
        stamps = lambda header: (header.stamp.sec, header.stamp.nanosec)
        assert (
            [stamps(p.header) for p in poses]
            == [stamps(t.header) for t in transforms]
            == [stamps(s.header) for s in measured]
        )
        assert all(
            stamps(b.header) > stamps(a.header) for a, b in zip(poses, poses[1:])
        )
        with (kit / "ground_truth.csv").open() as stream:
            truth = list(csv.DictReader(stream))
        for pose, reference in zip(poses, truth):
            t, q = pose.pose.position, pose.pose.orientation
            expected = np.array(
                [float(reference[key]) for key in ("tx_m", "ty_m", "tz_m")]
            )
            assert np.linalg.norm(np.array([t.x, t.y, t.z]) - expected) < 0.0015
            expected_rotation = Rotation.from_rotvec(
                [float(reference[key]) for key in ("rx_rad", "ry_rad", "rz_rad")]
            )
            assert (
                np.degrees(
                    (
                        Rotation.from_quat([q.x, q.y, q.z, q.w]).inv()
                        * expected_rotation
                    ).magnitude()
                )
                < 1.5
            )
        assert {v.key: v.value for v in eof.status[0].values}[
            "measurement_valid"
        ] == "false"
        # EOF heartbeats must not refresh the last measured pose/TF.
        deadline = time.monotonic() + 1.2
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        assert len(poses) == len(transforms) == 240
        assert statuses[-1].header.stamp.sec >= eof.header.stamp.sec
    finally:
        if executor is not None:
            executor.shutdown()
        if sender is not None:
            sender.close()
        if receiver is not None:
            receiver.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_loop_clears_prior_and_no_tf_option(tmp_path):
    import cv2

    rclpy.init()
    sender = None
    try:
        kit = ROOT / "assets/dodecahedron"
        cap = cv2.VideoCapture(str(kit / "tracking.mp4"))
        ok, first = cap.read()
        cap.release()
        assert ok
        video = tmp_path / "one_frame.avi"
        writer = cv2.VideoWriter(
            str(video), cv2.VideoWriter_fourcc(*"MJPG"), 24.0, (960, 720)
        )
        assert writer.isOpened()
        writer.write(first)
        writer.release()
        args = argparse.Namespace(
            source=str(video),
            model=str(kit / "model.json"),
            calibration=str(kit / "replay_camera.json"),
            camera_frame="camera_optical_frame",
            target_frame="target",
            min_markers=2,
            loop=True,
            no_tf=True,
        )
        sender = TargetPoseNode(args)
        sender.timer.cancel()
        assert sender.broadcaster is None
        sender.tick()
        assert sender.previous is not None
        sender.tick()  # EOF loops, without publishing a stale pose.
        assert sender.previous is None and sender.cycle_index == 0
        sender.tick()
        assert sender.frame_index == 2
        assert sender.previous is not None
    finally:
        if sender is not None:
            sender.close()
        rclpy.shutdown()


def test_cli_remapping_and_clean_sigint_without_output_files(tmp_path):
    import signal
    import subprocess

    rclpy.init()
    receiver = executor = process = None
    try:
        receiver = Node("aruco_cli_test_receiver")
        statuses = []
        subscription = receiver.create_subscription(
            DiagnosticArray, "/aruco_cli_test/status", statuses.append, 10
        )
        executor = SingleThreadedExecutor()
        executor.add_node(receiver)
        kit = ROOT / "assets/dodecahedron"
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("target_pose_node.py")),
                "--source",
                str(kit / "tracking.mp4"),
                "--model",
                str(kit / "model.json"),
                "--calibration",
                str(kit / "replay_camera.json"),
                "--loop",
                "--ros-args",
                "-r",
                "__node:=aruco_cli_test",
            ],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 20
        while not statuses and time.monotonic() < deadline and process.poll() is None:
            executor.spin_once(timeout_sec=0.05)
        assert statuses, "CLI did not publish to its remapped private status topic"
        assert statuses[-1].status[0].level == DiagnosticStatus.OK
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=10)
        assert process.returncode == 0, output
        assert "Traceback" not in output
        assert list(tmp_path.iterdir()) == []
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        if executor is not None:
            executor.shutdown()
        if receiver is not None:
            receiver.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
