"""Exercise real Image/CameraInfo DDS input and acquisition-time output in Jazzy."""

import argparse
import copy
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rclpy
from builtin_interfaces.msg import Time
from diagnostic_msgs.msg import DiagnosticArray
from geometry_msgs.msg import PoseStamped
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image, CameraInfo
from tf2_msgs.msg import TFMessage

from target_pose_node import TargetPoseNode

ROOT = Path(__file__).resolve().parents[2]


def values(message):
    return {item.key: item.value for item in message.status[0].values}


def ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


class CameraGraph:
    def __init__(self, policy="exact", transient=False):
        kit = ROOT / "assets/dodecahedron"
        args = argparse.Namespace(
            image_topic="/test_camera/image_raw",
            camera_info_topic="/test_camera/camera_info",
            camera_info_policy=policy,
            camera_info_transient_local=transient,
            max_image_age=0.5,
            future_tolerance=0.05,
            image_timeout=0.5,
            model=str(kit / "model.json"),
            camera_frame="camera_optical_frame",
            target_frame="target",
            min_markers=2,
            no_tf=False,
        )
        self.node = TargetPoseNode(args)
        self.producer = Node("camera_topic_test")
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.executor.add_node(self.producer)
        self.poses, self.transforms, self.statuses = [], [], []
        self.image_pub = self.producer.create_publisher(
            Image,
            args.image_topic,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )
        self.info_pub = self.producer.create_publisher(
            CameraInfo,
            args.camera_info_topic,
            QoSProfile(
                depth=8,
                durability=(
                    DurabilityPolicy.TRANSIENT_LOCAL
                    if transient
                    else DurabilityPolicy.VOLATILE
                ),
            ),
        )
        self.subs = [
            self.producer.create_subscription(
                PoseStamped, "/aruco_target_tracker/pose", self.poses.append, 1000
            ),
            self.producer.create_subscription(
                DiagnosticArray,
                "/aruco_target_tracker/status",
                self.statuses.append,
                1000,
            ),
            self.producer.create_subscription(
                TFMessage,
                "/tf",
                lambda msg: self.transforms.extend(msg.transforms),
                1000,
            ),
        ]
        self.spin_until(
            lambda: self.image_pub.get_subscription_count()
            and self.info_pub.get_subscription_count()
            and self.node.pose_publisher.get_subscription_count()
            and self.node.status_publisher.get_subscription_count()
            and self.node.count_subscribers("/tf")
        )
        cap = cv2.VideoCapture(str(kit / "tracking.mp4"))
        ok, self.frame = cap.read()
        cap.release()
        assert ok

    def spin_until(self, predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            self.executor.spin_once(timeout_sec=0.01)
        assert predicate(), "Timed out waiting for ROS camera messages"

    def messages(self, *, encoding="bgr8", stamp=None):
        if stamp is None:
            acquisition = self.producer.get_clock().now().nanoseconds - 10_000_000
            stamp = Time(
                sec=acquisition // 1_000_000_000, nanosec=acquisition % 1_000_000_000
            )
        image = Image()
        image.header.frame_id = "camera_optical_frame"
        image.header.stamp = stamp
        image.width, image.height = self.frame.shape[1], self.frame.shape[0]
        image.encoding = encoding
        pixels = self.frame
        if encoding == "rgb8":
            pixels = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
        if encoding == "mono8":
            pixels = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
        if encoding == "rgba8":
            pixels = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGBA)
        if encoding == "bgra8":
            pixels = cv2.cvtColor(pixels, cv2.COLOR_BGR2BGRA)
        image.step = pixels.strides[0]
        image.data = pixels.tobytes()
        info = CameraInfo()
        info.header = copy.deepcopy(image.header)
        info.width, info.height = image.width, image.height
        info.distortion_model = "plumb_bob"
        sx, sy = image.width / 960, image.height / 720
        info.k = [
            1500.0 * sx,
            0.0,
            480.0 * sx,
            0.0,
            1500.0 * sy,
            360.0 * sy,
            0.0,
            0.0,
            1.0,
        ]
        info.d = [0.0] * 5
        return image, info

    def send(self, image, info=None):
        index = self.node.frame_index
        if info is not None:
            self.info_pub.publish(info)
        self.image_pub.publish(image)
        self.spin_until(lambda: self.node.frame_index > index)
        return index

    def measured(self, image):
        self.spin_until(
            lambda: any(
                ns(p.header.stamp) == ns(image.header.stamp) for p in self.poses
            )
            and any(
                ns(t.header.stamp) == ns(image.header.stamp) for t in self.transforms
            )
            and any(
                ns(s.header.stamp) == ns(image.header.stamp)
                and values(s)["measurement_valid"] == "true"
                for s in self.statuses
            )
        )

    def close(self):
        self.executor.shutdown()
        self.node.close()
        self.producer.destroy_node()


@pytest.fixture
def graph_factory():
    rclpy.init()
    graphs = []

    def create(**kwargs):
        graph = CameraGraph(**kwargs)
        graphs.append(graph)
        return graph

    try:
        yield create
    finally:
        for graph in graphs:
            graph.close()
        rclpy.shutdown()


def test_topic_images_use_acquisition_time_for_pose_tf_and_status(graph_factory):
    graph = graph_factory()
    for encoding in ("bgr8", "rgb8", "mono8", "rgba8", "bgra8"):
        image, info = graph.messages(encoding=encoding)
        graph.send(image, info)
        graph.measured(image)
        pose, transform = graph.poses[-1], graph.transforms[-1]
        assert pose.header.stamp == transform.header.stamp == image.header.stamp
        assert (
            pose.header.frame_id == "camera_optical_frame"
            and transform.child_frame_id == "target"
        )
        assert 0.245 < pose.pose.position.z < 0.255
        status = next(
            s
            for s in reversed(graph.statuses)
            if values(s)["measurement_valid"] == "true"
        )
        assert status.header.stamp == image.header.stamp
        assert values(status)["stamp_basis"] == "Image.header.stamp"
        assert values(status)["calibration_stamp_nanosec"] == str(
            image.header.stamp.nanosec
        )
    assert len(graph.poses) == len(graph.transforms) == 5


def test_image_before_info_waits_without_a_pose_then_recovers(graph_factory):
    graph = graph_factory()
    image, info = graph.messages()
    graph.send(image)
    graph.spin_until(
        lambda: any(
            values(s)["source_state"] == "waiting_calibration" for s in graph.statuses
        )
    )
    assert not graph.poses and not graph.transforms
    graph.info_pub.publish(info)
    graph.measured(image)
    assert graph.node.topic_input.pending is None


def test_latest_static_calibration_and_bounded_cache(graph_factory):
    graph = graph_factory(policy="latest", transient=True)
    image, info = graph.messages()
    info.header.stamp = Time()  # Explicitly supported only by latest policy.
    # Publish once before the info subscription exists; DDS must retain it.
    graph.node.destroy_subscription(graph.node.topic_input.info_subscription)
    graph.info_pub.publish(info)
    graph.node.topic_input.info_subscription = graph.node.create_subscription(
        CameraInfo,
        "/test_camera/camera_info",
        graph.node.topic_input.on_info,
        QoSProfile(
            depth=8,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        ),
    )
    graph.spin_until(lambda: 0 in graph.node.topic_input.infos)
    image, _ = graph.messages()  # Refresh acquisition time after DDS discovery.
    graph.send(image)
    graph.measured(image)
    for index in range(12):
        update = copy.deepcopy(info)
        update.header.stamp = Time(sec=1, nanosec=index)
        graph.node.topic_input.on_info(update)
    assert len(graph.node.topic_input.infos) == 8


def test_latest_does_not_apply_future_calibration(graph_factory):
    graph = graph_factory(policy="latest")
    image, info = graph.messages()
    info.header.stamp.sec += 2
    graph.send(image, info)
    graph.spin_until(
        lambda: any(
            values(s)["source_state"] == "waiting_calibration" for s in graph.statuses
        )
    )
    assert not graph.poses
    info.header.stamp = Time()
    graph.info_pub.publish(info)
    graph.measured(image)


def test_updated_full_resolution_calibration_is_used_without_restart(graph_factory):
    graph = graph_factory()
    image, info = graph.messages()
    graph.send(image, info)
    graph.measured(image)
    graph.frame = cv2.resize(graph.frame, (480, 360), interpolation=cv2.INTER_AREA)
    image, info = graph.messages()
    graph.send(image, info)
    graph.measured(image)
    assert 0.245 < graph.poses[-1].pose.position.z < 0.255
    assert graph.node.tracker.image_size == (480, 360)


@pytest.mark.parametrize(
    "fault",
    [
        "stale",
        "future",
        "zero",
        "frame",
        "info_frame",
        "size",
        "encoding",
        "data",
        "calibration",
        "roi",
        "binning",
        "fisheye",
    ],
)
def test_bad_camera_inputs_do_not_publish_pose_and_good_frames_recover(
    graph_factory, fault
):
    graph = graph_factory()
    image, info = graph.messages()
    if fault == "stale":
        image.header.stamp.sec -= 2
    if fault == "future":
        image.header.stamp.sec += 2
    if fault == "zero":
        image.header.stamp = Time()
    info.header.stamp = copy.deepcopy(image.header.stamp)
    if fault == "frame":
        image.header.frame_id = "base_link"
    if fault == "info_frame":
        info.header.frame_id = "base_link"
    if fault == "size":
        info.width = 640
    if fault == "encoding":
        image.encoding = "mono16"
    if fault == "data":
        image.data = b""
    if fault == "calibration":
        info.k = [0.0] * 9
    if fault == "roi":
        info.roi.x_offset = 8
    if fault == "binning":
        info.binning_x = 2
    if fault == "fisheye":
        info.distortion_model = "equidistant"
    index = graph.send(image, info)
    graph.spin_until(
        lambda: any(
            values(s)["frame_index"] == str(index)
            and values(s)["source_state"] in ("error", "stale")
            for s in graph.statuses
        )
    )
    assert not graph.poses and not graph.transforms
    fresh, valid = graph.messages()
    graph.send(fresh, valid)
    graph.measured(fresh)


def test_duplicate_stamps_no_calibration_match_and_timeout_are_invalid(graph_factory):
    graph = graph_factory()
    image, info = graph.messages()
    graph.send(image, info)
    graph.measured(image)
    index = graph.send(image, info)
    graph.spin_until(
        lambda: any(
            values(s)["frame_index"] == str(index)
            and "out-of-order" in values(s)["reason"]
            for s in graph.statuses
        )
    )
    assert len(graph.poses) == len(graph.transforms) == 1
    unmatched, calibration = graph.messages()
    calibration.header.stamp = Time()  # Exact mode must not use a static stamp.
    graph.send(unmatched, calibration)
    graph.spin_until(
        lambda: any(
            values(s)["source_state"] == "waiting_calibration" for s in graph.statuses
        )
    )
    graph.spin_until(
        lambda: any(values(s)["source_state"] == "timeout" for s in graph.statuses),
        timeout=3.0,
    )
    assert len(graph.poses) == len(graph.transforms) == 1
    assert graph.node.previous is None and graph.node.topic_input.pending is None


def test_topic_mode_accepts_simulated_clock_and_preserves_image_stamp(graph_factory):
    from rclpy.parameter import Parameter
    from rosgraph_msgs.msg import Clock

    graph = graph_factory()
    graph.node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
    publisher = graph.producer.create_publisher(Clock, "/clock", 10)
    graph.spin_until(lambda: publisher.get_subscription_count() > 0)
    publisher.publish(Clock(clock=Time(sec=100)))
    graph.spin_until(
        lambda: graph.node.get_clock().now().nanoseconds == 100_000_000_000
    )
    image, info = graph.messages(stamp=Time(sec=100))
    graph.send(image, info)
    graph.measured(image)
    assert graph.poses[-1].header.stamp == Time(sec=100)


def test_topic_cli_without_calibration_json_shuts_down_cleanly(graph_factory, tmp_path):
    import signal
    import subprocess

    graph = graph_factory()
    statuses = []
    subscription = graph.producer.create_subscription(
        DiagnosticArray, "/camera_cli_target/status", statuses.append, 10
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).with_name("target_pose_node.py")),
            "--image-topic",
            "/test_camera/image_raw",
            "--camera-info-topic",
            "/test_camera/camera_info",
            "--model",
            str(ROOT / "assets/dodecahedron/model.json"),
            "--no-tf",
            "--max-image-age",
            "1.0",
            "--ros-args",
            "-r",
            "__node:=camera_cli_target",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        graph.spin_until(
            lambda: graph.image_pub.get_subscription_count() >= 2
            and graph.info_pub.get_subscription_count() >= 2,
            timeout=15.0,
        )
        # A camera is a stream: one-shot best-effort delivery is not guaranteed.
        sent = set()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not any(
            values(s)["measurement_valid"] == "true" for s in statuses
        ):
            image, info = graph.messages()
            sent.add(ns(image.header.stamp))
            graph.info_pub.publish(info)
            graph.image_pub.publish(image)
            until = time.monotonic() + 0.1
            while time.monotonic() < until:
                graph.executor.spin_once(timeout_sec=0.01)
        if not any(values(s)["measurement_valid"] == "true" for s in statuses):
            process.send_signal(signal.SIGINT)
            output, _ = process.communicate(timeout=10.0)
            pytest.fail(
                f"CLI produced no measurement. Statuses: {[values(s) for s in statuses[-3:]]}; output: {output}"
            )
        measured = next(s for s in statuses if values(s)["measurement_valid"] == "true")
        assert ns(measured.header.stamp) in sent
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=10.0)
        assert process.returncode == 0 and "Traceback" not in output, output
        assert not list(tmp_path.iterdir())
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10.0)
