"""Optional ROS 2 Jazzy example: OpenCV or camera topics -> Tracker -> pose/TF/status."""

import argparse
import math
import time

import cv2
import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped, TransformStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile
from tf2_ros import TransformBroadcaster

from aruco_pose import Tracker, TrackerConfig
from aruco_pose.starter import load_calibration, load_model, open_capture
from protocol import status_values, validate_frames


def messages_for(
    result,
    stamp,
    *,
    parent,
    child,
    frame_index,
    source_time_s,
    source_state="active",
    reason="",
):
    """Produce real ROS messages; TF is parent <- child, with no inversion."""
    values = status_values(
        result,
        parent=parent,
        child=child,
        frame_index=frame_index,
        source_time_s=source_time_s,
        source_state=source_state,
        reason=reason,
    )
    status = DiagnosticStatus()
    status.name = "aruco_pose/target"
    status.hardware_id = values["object_id"]
    status.level = (
        DiagnosticStatus.ERROR
        if source_state == "error"
        else (
            DiagnosticStatus.OK
            if values["measurement_valid"] == "true"
            else DiagnosticStatus.WARN
        )
    )
    status.message = f"{source_state}: {values['tracking_status']}"
    status.values = [KeyValue(key=key, value=value) for key, value in values.items()]
    diagnostics = DiagnosticArray()
    diagnostics.header.stamp = stamp
    diagnostics.header.frame_id = parent
    diagnostics.status = [status]
    if result is None or result.pose is None:
        return None, None, diagnostics
    pose = PoseStamped()
    pose.header.stamp = stamp
    pose.header.frame_id = parent
    pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = (
        result.pose.translation_m
    )
    q = result.pose.quaternion_xyzw
    (
        pose.pose.orientation.x,
        pose.pose.orientation.y,
        pose.pose.orientation.z,
        pose.pose.orientation.w,
    ) = q
    transform = TransformStamped()
    transform.header.stamp = stamp
    transform.header.frame_id = parent
    transform.child_frame_id = child
    (
        transform.transform.translation.x,
        transform.transform.translation.y,
        transform.transform.translation.z,
    ) = result.pose.translation_m
    (
        transform.transform.rotation.x,
        transform.transform.rotation.y,
        transform.transform.rotation.z,
        transform.transform.rotation.w,
    ) = q
    return pose, transform, diagnostics


class TargetPoseNode(Node):
    def __init__(self, args):
        super().__init__("aruco_target_tracker")
        self.cap = None
        try:
            self._configure(args)
        except Exception:
            if self.cap is not None:
                self.cap.release()
            self.destroy_node()
            raise

    def _configure(self, args):
        topic_mode = bool(getattr(args, "image_topic", None))
        if self.get_parameter("use_sim_time").value and not topic_mode:
            raise ValueError(
                "This OpenCV replay example requires use_sim_time=false; it does not publish /clock"
            )
        self.parent = args.camera_frame or "camera_optical_frame"
        self.model = model = load_model(args.model)
        if not 1 <= args.min_markers <= len(model["markers"]):
            raise ValueError(
                "Minimum marker count must be between 1 and the model's marker count"
            )
        self.child = args.target_frame or model["object_id"]
        validate_frames(self.parent, self.child)
        self.previous = None
        self.frame_index = self.cycle_index = 0
        self.start = time.monotonic()
        self.terminal = None
        self.last_stamp_ns = None
        self.timer = self.tracker = None
        self.live = False
        self.stamp_basis = (
            "Image.header.stamp"
            if topic_mode
            else "ROS time at OpenCV read completion; not hardware exposure"
        )
        self.source_time_basis = (
            "Image.header.stamp seconds"
            if topic_mode
            else "frame index / FPS within replay cycle"
        )
        qos = QoSProfile(depth=1)  # Reliable, volatile, keep-last: no latched pose.
        self.pose_publisher = self.create_publisher(PoseStamped, "~/pose", qos)
        self.status_publisher = self.create_publisher(DiagnosticArray, "~/status", qos)
        self.broadcaster = None if args.no_tf else TransformBroadcaster(self, qos=qos)
        self.heartbeat = self.create_timer(1.0, self.publish_terminal)
        if topic_mode:
            from camera_topics import TopicInput

            self.topic_input = TopicInput(self, args)
            return
        calibration, matrix, distortion = load_calibration(args.calibration)
        self.size = (calibration["image_width"], calibration["image_height"])
        self.tracker = Tracker(
            model,
            matrix,
            distortion,
            config=TrackerConfig(min_markers=args.min_markers),
            parent_frame=self.parent,
            child_frame=self.child,
            image_size=self.size,
        )
        self.source = args.source
        self.cap, self.live = open_capture(self.source)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(self.fps) or self.fps <= 0:
            raise ValueError("Source needs a valid FPS")
        self.loop = args.loop
        if self.loop and self.live:
            raise ValueError("--loop is only for recorded video")
        if self.live:
            self.source_time_basis = "monotonic since start"
        self.timer = self.create_timer(1 / self.fps, self.tick)
        self.get_logger().info(
            f"{self.parent} <- {self.child}; {self.fps:g} FPS; pose + status; TF={not args.no_tf}"
        )

    def publish(
        self,
        result,
        stamp,
        source_time_s=None,
        source_state="active",
        reason="",
        *,
        frame_index=None,
        stamp_basis=None,
        extra_values=None,
    ):
        pose, transform, diagnostic = messages_for(
            result,
            stamp,
            parent=self.parent,
            child=self.child,
            frame_index=self.frame_index if frame_index is None else frame_index,
            source_time_s=source_time_s,
            source_state=source_state,
            reason=reason,
        )
        if not diagnostic.status[0].hardware_id:
            diagnostic.status[0].hardware_id = self.model["object_id"]
            for value in diagnostic.status[0].values:
                if value.key == "object_id":
                    value.value = self.model["object_id"]
        diagnostic.status[0].values.extend(
            [
                KeyValue(
                    key="stamp_basis",
                    value=stamp_basis or self.stamp_basis,
                ),
                KeyValue(
                    key="source_time_basis",
                    value=self.source_time_basis,
                ),
            ]
        )
        if extra_values:
            diagnostic.status[0].values.extend(
                KeyValue(key=key, value=value) for key, value in extra_values.items()
            )
        if pose is not None:
            self.pose_publisher.publish(pose)
            if self.broadcaster is not None:
                self.broadcaster.sendTransform(transform)
        self.status_publisher.publish(diagnostic)

    def stop_source(self, state, reason):
        self.terminal = (state, reason)
        self.previous = None
        if self.timer is not None:
            self.timer.cancel()
        if self.cap is not None:
            self.cap.release()
        self.get_logger().info(reason)
        self.publish_terminal()

    def publish_terminal(self):
        if self.terminal is not None:
            state, reason = self.terminal
            self.publish(
                None,
                self.get_clock().now().to_msg(),
                source_state=state,
                reason=reason,
                stamp_basis="ROS status time (no acquisition)",
            )

    def tick(self):
        if self.terminal is not None:
            return
        try:
            ok, frame = self.cap.read()
            if not ok:
                if self.loop and self.cycle_index:
                    self.cap.release()
                    self.cap, _ = open_capture(self.source)
                    self.cycle_index = 0
                    self.previous = (
                        None  # Never carry an ambiguity prior across a loop.
                    )
                    return
                state = "error" if self.live or self.frame_index == 0 else "eof"
                self.stop_source(
                    state,
                    (
                        "Camera read failed"
                        if self.live
                        else "End of video; no current measurement"
                    ),
                )
                return
            # Approximate read-completion time, not a hardware exposure timestamp.
            now = self.get_clock().now()
            if self.last_stamp_ns is not None and now.nanoseconds <= self.last_stamp_ns:
                self.stop_source(
                    "error", "ROS clock moved backward or stalled; restart the node"
                )
                return
            self.last_stamp_ns = now.nanoseconds
            if (frame.shape[1], frame.shape[0]) != self.size:
                raise ValueError(
                    "Image resolution differs from calibration; do not resize to conceal it"
                )
            source_time_s = (
                time.monotonic() - self.start
                if self.live
                else self.cycle_index / self.fps
            )
            result = self.tracker.process(
                frame, timestamp_s=source_time_s, previous=self.previous
            )
            self.previous = result if result.pose is not None else None
            self.publish(result, now.to_msg(), source_time_s)
            self.frame_index += 1
            self.cycle_index += 1
        except (ValueError, OSError, cv2.error) as error:
            self.stop_source("error", str(error))

    def close(self):
        if self.terminal is None:
            self.stop_source("stopped", "Node stopped; no current measurement")
        if self.cap is not None:
            self.cap.release()
        self.destroy_node()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", help="Video path or camera index")
    inputs.add_argument(
        "--image-topic", help="Raw, unrectified sensor_msgs/Image topic"
    )
    parser.add_argument(
        "--camera-info-topic", help="Matching sensor_msgs/CameraInfo topic"
    )
    parser.add_argument(
        "--camera-info-policy", choices=["exact", "latest"], default="exact"
    )
    parser.add_argument(
        "--camera-info-transient-local",
        action="store_true",
        help="For latched CameraInfo publishers only",
    )
    parser.add_argument(
        "--max-image-age",
        type=float,
        default=0.25,
        help="Maximum acquisition age at publication, seconds",
    )
    parser.add_argument(
        "--future-tolerance",
        type=float,
        default=0.05,
        help="Allowed image clock lead, seconds",
    )
    parser.add_argument(
        "--image-timeout",
        type=float,
        default=0.5,
        help="Wall-time silence before invalid status, seconds",
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--calibration", help="Calibration JSON for --source only")
    parser.add_argument("--camera-frame", default="camera_optical_frame")
    parser.add_argument("--target-frame", help="Default: the model's object_id")
    parser.add_argument("--min-markers", type=int, default=2)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat video at recorded FPS; reset the prior each cycle",
    )
    parser.add_argument("--no-tf", action="store_true")
    args, ros_args = parser.parse_known_args()
    if args.image_topic:
        if not args.camera_info_topic or args.calibration or args.loop:
            parser.error(
                "Topic input requires --camera-info-topic and cannot use --calibration or --loop"
            )
    elif not args.calibration or args.camera_info_topic:
        parser.error(
            "--source requires --calibration and cannot use --camera-info-topic"
        )
    rclpy.init(args=ros_args)
    node = None
    try:
        node = TargetPoseNode(args)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, OSError, cv2.error) as error:
        parser.exit(1, f"{error}\n")
    finally:
        if node is not None:
            # SIGINT may already have invalidated the ROS context.
            if rclpy.ok():
                node.close()
            else:
                if node.cap is not None:
                    node.cap.release()
                node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
