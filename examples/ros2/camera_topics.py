"""Bounded raw or rectified Image/CameraInfo input for the optional ROS node."""

from collections import OrderedDict
import math
import time

import cv2
import numpy as np
from rclpy.clock import Clock, ClockType
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image, CameraInfo

from aruco_pose import Tracker, TrackerConfig
from camera_input import (
    StaleImageError,
    check_image_time,
    decode_image,
    raw_calibration,
    rectified_calibration,
    original_camera_result,
    stamp_ns,
)


class TopicInput:
    def __init__(self, node, args):
        self.node = node
        self.policy = args.camera_info_policy
        self.image_space = getattr(args, "image_space", "raw")
        if self.image_space not in ("raw", "rectified"):
            raise ValueError("Image space must be raw or rectified")
        self.max_age = args.max_image_age
        self.future_tolerance = args.future_tolerance
        self.timeout = args.image_timeout
        if not all(math.isfinite(v) and v > 0 for v in (self.max_age, self.timeout)):
            raise ValueError("Image age and timeout limits must be finite and positive")
        if not math.isfinite(self.future_tolerance) or self.future_tolerance < 0:
            raise ValueError(
                "Future timestamp tolerance must be finite and nonnegative"
            )
        self.infos = OrderedDict()
        self.pending = None  # Only the latest image may wait for CameraInfo.
        self.last_image_stamp = None
        self.last_arrival = None
        self.last_idle_publish = 0.0
        self.fingerprint = None
        self.last_state = "waiting_image"
        self.min_markers = args.min_markers
        image_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        info_qos = QoSProfile(
            depth=8,
            reliability=(
                ReliabilityPolicy.RELIABLE
                if args.camera_info_transient_local
                else ReliabilityPolicy.BEST_EFFORT
            ),
            durability=(
                DurabilityPolicy.TRANSIENT_LOCAL
                if args.camera_info_transient_local
                else DurabilityPolicy.VOLATILE
            ),
        )
        self.image_subscription = node.create_subscription(
            Image, args.image_topic, self.on_image, image_qos
        )
        self.info_subscription = node.create_subscription(
            CameraInfo, args.camera_info_topic, self.on_info, info_qos
        )
        self.watchdog_timer = node.create_timer(
            0.1, self.watchdog, clock=Clock(clock_type=ClockType.STEADY_TIME)
        )
        node.get_logger().info(
            f"{self.image_space} Image={args.image_topic}; CameraInfo={args.camera_info_topic}; pairing={self.policy}; output optical frame={node.parent}"
        )

    def invalid(self, state, reason, image=None, index=None):
        self.node.previous = None
        self.last_state = state
        stamp = (
            self.node.get_clock().now().to_msg()
            if image is None
            else image.header.stamp
        )
        self.node.publish(
            None,
            stamp,
            source_time_s=None if image is None else stamp_ns(image.header.stamp) / 1e9,
            source_state=state,
            reason=reason,
            frame_index=index,
            stamp_basis=(
                "ROS status time (no acquisition)"
                if image is None
                else "Image.header.stamp"
            ),
        )

    def on_info(self, info):
        try:
            key = stamp_ns(info.header.stamp)
        except ValueError as error:
            self.invalid("error", str(error))
            return
        self.infos[key] = info
        self.infos.move_to_end(key)
        while len(self.infos) > 8:
            self.infos.popitem(last=False)
        self.try_pending()

    def on_image(self, image):
        index = self.node.frame_index
        self.node.frame_index += 1
        self.last_arrival = time.monotonic()
        self.pending = None  # Do not accumulate a delayed image queue.
        try:
            key = check_image_time(
                image.header.stamp,
                self.node.get_clock().now().nanoseconds,
                self.max_age,
                self.future_tolerance,
            )
            if self.last_image_stamp is not None and key <= self.last_image_stamp:
                raise ValueError(
                    "Duplicate/out-of-order image acquisition timestamp; restart after a backward clock jump"
                )
            self.last_image_stamp = key
            if image.header.frame_id != self.node.parent:
                raise ValueError("Image optical frame differs from --camera-frame")
        except ValueError as error:
            self.invalid(
                "stale" if isinstance(error, StaleImageError) else "error",
                str(error),
                index=index,
            )
            return
        self.pending = (image, index)
        self.try_pending()

    def try_pending(self):
        if self.pending is None:
            return
        image, index = self.pending
        key = stamp_ns(image.header.stamp)
        if self.policy == "exact":
            info = self.infos.get(key)
        else:
            candidates = [stamp for stamp in self.infos if stamp <= key]
            info = self.infos[max(candidates)] if candidates else None
        if info is None:
            self.invalid(
                "waiting_calibration",
                "No matching CameraInfo; check pairing policy, timestamps and QoS",
                image,
                index,
            )
            return
        try:
            check_image_time(
                image.header.stamp,
                self.node.get_clock().now().nanoseconds,
                self.max_age,
                self.future_tolerance,
            )
            if self.image_space == "rectified":
                matrix, distortion, size, rectification = rectified_calibration(
                    info, self.node.parent
                )
            else:
                matrix, distortion, size = raw_calibration(info, self.node.parent)
                rectification = np.eye(3)
            if (image.width, image.height) != size:
                raise ValueError(
                    "Image resolution differs from CameraInfo; no implicit resizing"
                )
            fingerprint = (
                matrix.tobytes(),
                distortion.tobytes(),
                size,
                rectification.tobytes(),
                self.image_space,
            )
            if self.fingerprint != fingerprint:
                self.node.previous = None
                self.node.tracker = Tracker(
                    self.node.model,
                    matrix,
                    distortion,
                    config=TrackerConfig(min_markers=self.min_markers),
                    parent_frame=(
                        self.node.parent
                        if self.image_space == "raw"
                        else self.node.parent + "_rectified_internal"
                    ),
                    child_frame=self.node.child,
                    image_size=size,
                )
                self.fingerprint = fingerprint
            frame = decode_image(image)
            result = self.node.tracker.process(
                frame, timestamp_s=key / 1e9, previous=self.node.previous
            )
            # An expensive processing callback must not publish an already stale pose.
            check_image_time(
                image.header.stamp,
                self.node.get_clock().now().nanoseconds,
                self.max_age,
                self.future_tolerance,
            )
            self.node.previous = result if result.pose is not None else None
            if self.image_space == "rectified":
                result = original_camera_result(result, rectification, self.node.parent)
            self.node.publish(
                result,
                image.header.stamp,
                key / 1e9,
                frame_index=index,
                extra_values={
                    "camera_info_policy": self.policy,
                    "image_space": self.image_space,
                    "pose_axes": "original CameraInfo optical frame",
                    "calibration_stamp_sec": str(info.header.stamp.sec),
                    "calibration_stamp_nanosec": str(info.header.stamp.nanosec),
                },
            )
            self.last_state = "active"
        except (ValueError, cv2.error) as error:
            self.invalid(
                "stale" if isinstance(error, StaleImageError) else "error",
                str(error),
                image,
                index,
            )
        finally:
            self.pending = None

    def watchdog(self):
        if self.node.terminal is not None:
            return
        wall = time.monotonic()
        if self.pending is not None:
            image, index = self.pending
            try:
                check_image_time(
                    image.header.stamp,
                    self.node.get_clock().now().nanoseconds,
                    self.max_age,
                    self.future_tolerance,
                )
            except ValueError as error:
                self.pending = None
                self.invalid("stale", str(error), image, index)
        if self.last_arrival is None or wall - self.last_arrival > self.timeout:
            self.node.previous = None
            self.pending = None
            state = "waiting_image" if self.last_arrival is None else "timeout"
            if state != self.last_state or wall - self.last_idle_publish >= 1.0:
                self.last_idle_publish = wall
                self.invalid(
                    state,
                    "No recent Image messages; no current measurement",
                )
