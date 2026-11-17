# Target pose and TF with ROS 2

An optional Python node for **ROS 2 Jazzy on Ubuntu 24.04**. It reads a video or
local camera through OpenCV, or raw ROS `sensor_msgs/Image` and `CameraInfo` topics,
and uses the same `Tracker` as the CLI. No ROS packages are imported by the core
`aruco_pose` library. File replay remains available without a ROS camera driver.

The example saves no CSV or video. It publishes one target's measured pose, optional dynamic
TF, and tracking diagnostics. No covariance, filtering, robot commands or world
localization are implied by these messages.

## Setup

Install [ROS 2 Jazzy for Ubuntu](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
first. Run the following in a Bash terminal, using the Ubuntu **system Python**
(the interpreter must match the installed ROS binaries):

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install python3-venv libgl1 libglib2.0-0 ros-jazzy-tf2-ros ros-jazzy-tf2-msgs ros-jazzy-geometry-msgs ros-jazzy-diagnostic-msgs ros-jazzy-sensor-msgs
git clone https://github.com/Jshulgach/aruco-pose.git
cd aruco-pose
python3 -m venv --system-site-packages .venv-ros
source .venv-ros/bin/activate
python -m pip install -e .
```

The `--system-site-packages` environment sees the apt-installed ROS Python modules;
the project and its dependencies stay in the environment. Do not reuse the
Windows virtual environment, a Conda interpreter, or a differently versioned Python.
If system packages already provide another `cv2` wheel, use a clean ROS environment
so only the project's `opencv-contrib-python` wheel supplies OpenCV.
See the official [ROS Python package guidance](https://docs.ros.org/en/jazzy/How-To-Guides/Using-Python-Packages.html).
There is no colcon build or custom message generation for this example.

## Try the replay pack

From the repository root, run the included dodecahedron replay:

```bash
python examples/ros2/target_pose_node.py \
  --source assets/dodecahedron/tracking.mp4 \
  --model assets/dodecahedron/model.json \
  --calibration assets/dodecahedron/replay_camera.json \
  --loop
```

Alternatively [download and extract the kit](https://jshulgach.github.io/aruco-pose/downloads/dodecahedron-kit.zip)
and replace these three paths with the files in its `dodecahedron/` folder.
Use the raw `tracking.mp4`, not the annotated website video. The example works
with the published `aruco-pose` package too; the example scripts come from this
checkout. No camera is required. The replay is entirely synthetic, with 25 mm
target edges and 15 mm marker squares; it is not an accuracy benchmark.

The recording is paced at its 24 FPS. Each replay cycle has 240 measured frames;
`--loop` repeats until Ctrl+C and clears the prior between cycles. If processing
takes longer than a frame interval, playback slows; frames are processed in
order without an accumulating input queue. Omit `--loop` for one pass: at EOF
the node stops pose/TF publication and continues invalid status heartbeats at
1 Hz until Ctrl+C. No CSV or video is saved by this node.

In **another terminal**, source `/opt/ros/jazzy/setup.bash`, then inspect:

```bash
ros2 topic echo /aruco_target_tracker/pose --once
ros2 topic echo /aruco_target_tracker/status --once
ros2 run tf2_ros tf2_echo camera_optical_frame dodecahedron_25mm
```

The expected translation is roughly 0.25 m in front of the camera, while the
orientation rotates. Status reports `measured`, readable inlier IDs, and
`measurement_valid=true`. `source_time_s` runs 0 through 239/24 in each cycle;
`frame_index` continues increasing across cycles. All terminals must share the
same ROS domain and discovery/network settings.

## Use a ROS camera topic

Start your camera driver with its real calibration. Inspect its topics, frames
and timestamps before launching the tracker:

```bash
ros2 topic info /camera/image_raw --verbose
ros2 topic echo /camera/camera_info --once --qos-reliability best_effort
```

From the repository root, using the ROS/venv setup above:

```bash
python examples/ros2/target_pose_node.py \
  --image-topic /camera/image_raw \
  --camera-info-topic /camera/camera_info \
  --camera-frame camera_color_optical_frame \
  --model assets/dodecahedron/model.json
```

Replace the topic names and `camera_color_optical_frame` with your driver's
actual names. **Both Image and CameraInfo headers must have that same optical
frame ID.** `--camera-frame` is an exact expected frame name, not an override or a
coordinate conversion. The default is `camera_optical_frame`, as in file replay.
No JSON calibration is used in this mode: do not supply `--calibration`, `--source`
or `--loop` with `--image-topic`.

### Calibration pairing

The default `--camera-info-policy exact` requires **identical Image and CameraInfo
acquisition timestamps**. An image may arrive before its CameraInfo; only the
latest image waits, with at most eight CameraInfo messages cached. Until a match
arrives, diagnostics report `waiting_calibration` and no pose/TF. A later match
can produce a measured result with that same acquisition timestamp, provided
the image is still fresh. Thus a pending frame can have an invalid status followed
by a measured status at the same stamp. Newer images replace pending older ones.

For drivers publishing calibration periodically or once, explicitly choose:

```bash
python examples/ros2/target_pose_node.py \
  --image-topic /camera/image_raw --camera-info-topic /camera/camera_info \
  --camera-frame camera_color_optical_frame --model assets/dodecahedron/model.json \
  --camera-info-policy latest
```

`latest` uses the newest received calibration stamp **no later than the image**;
a zero CameraInfo stamp is allowed as static calibration only in this policy.
The cache has no independent calibration-age limit: the driver must publish
updates when intrinsics change. Changed K/D or resolution resets the pose prior
and rebuilds the tracker. Future calibration is never applied to an earlier
image. For a publish-once **transient-local** CameraInfo publisher, additionally
use `--camera-info-transient-local` to receive retained calibration on joining.
Do not use that flag with a volatile publisher; their durability is incompatible.

Image subscription QoS is **best effort, volatile, keep-last 1**; CameraInfo is
**best effort, keep-last 8**, volatile by default. These subscribers accept
best-effort or reliable publishers. Slow processing drops queued images instead
of building an unbounded backlog. Unlike file replay, this mode does not promise
to process every published image. Pose/status output QoS remains reliable depth 1.

### Supported pixels and calibration

Use **uncompressed, raw, unrectified** Image messages with `mono8`, `bgr8`, `rgb8`,
`bgra8` or `rgba8` encoding. Row padding (`step`) is respected; RGB/RGBA are converted
to BGR. Single-byte channels are independent of byte order. There is no cv_bridge
dependency. Bayer, 16-bit, floating-point and CompressedImage inputs need upstream
conversion to a supported unrectified Image stream.

Calibration uses **K and D**, as defined by the official
[CameraInfo message](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/CameraInfo.msg).
Supported distortion models are calibrated `plumb_bob` (5 coefficients) and
`rational_polynomial` (8). A zero focal length, nonfinite calibration, unsupported
distortion model, frame mismatch or resolution mismatch produces invalid diagnostics
and no pose/TF. Input size must match CameraInfo width/height exactly.

This version rejects active cropping/ROI and binning greater than 1. It accepts
zero/default or full-image ROI with `do_rectify=false`, and binning 0/1. It does
not adjust intrinsics, resize pixels, use P, or rectify images implicitly. Do not
point it at `image_rect` with the raw K/D; rectified and fisheye input require a
separate explicit geometry path. If a driver has already adjusted its intrinsics
for a smaller full image, publish matching dimensions/K with no active ROI/binning.

### Acquisition time, clocks and timeout

For topic input, pose, TF and per-image status preserve **Image.header.stamp
exactly**, including nanoseconds; reception time never replaces a valid acquisition
stamp. The tracker uses acquisition time for prior age as well. See the official
[Image timestamp/frame contract](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/Image.msg).

The default `--max-image-age 0.25` rejects images older than 0.25 s at processing
and checks again before publishing. `--future-tolerance 0.05` allows up to 0.05 s
of camera clock lead. Zero, duplicate, backward and more distant future timestamps
are rejected. The image stamps and node's ROS clock must use the same time domain;
fix clock synchronization rather than treating receipt time as acquisition time.
Age limits can be adjusted explicitly for a measured pipeline's latency.

After `--image-timeout 0.5` seconds with no Image callbacks, a steady-clock watchdog
clears the prior and emits `timeout`, invalid status at up to 1 Hz. Before any
image it reports `waiting_image`. An unmatched pending image also expires at
the maximum image age. Watchdog statuses use **current ROS status time**, not a
new acquisition stamp, and have `measurement_valid=false`; `stamp_basis` identifies
that distinction. Invalid timestamps also receive status-time diagnostics. Valid
image-specific rejections/calibration waits retain the image stamp. Invalid input
does not stop the topic node: subsequent valid images/calibration can recover.

Unlike OpenCV input, topic mode supports `use_sim_time=true` when an external
`/clock` is available, for example with a recorded camera bag:

```bash
ros2 bag play /path/to/camera_bag --clock
# In another sourced terminal:
python examples/ros2/target_pose_node.py \
  --image-topic /camera/image_raw --camera-info-topic /camera/camera_info \
  --camera-frame camera_color_optical_frame --model assets/dodecahedron/model.json \
  --ros-args -p use_sim_time:=true
```

The bag must contain matching calibrated CameraInfo. Wait for nonzero `/clock`
before expecting poses. Pause/silence causes invalid wall-time watchdog status.
Backward acquisition times (including bag looping/seeking backward) are rejected;
restart the tracker after a clock reset. The node never broadcasts out-of-order TF
as if it were a new forward-time measurement. It does not publish `/clock` itself.

## Output topics and frame contract

| Topic | Type | Contract |
| --- | --- | --- |
| `/aruco_target_tracker/pose` | `geometry_msgs/msg/PoseStamped` | Only accepted measurements; `header.frame_id=camera_optical_frame` |
| `/tf` | `tf2_msgs/msg/TFMessage` | Optional dynamic `camera_optical_frame` parent to `dodecahedron_25mm` child, only on measurement |
| `/aruco_target_tracker/status` | `diagnostic_msgs/msg/DiagnosticArray` | Every processed frame; terminal invalid heartbeats at 1 Hz |

Default node name is `aruco_target_tracker`; pose/status use private `~/pose` and
`~/status` names. Pose and status QoS are **reliable, volatile, keep-last 1**. The
TF broadcaster uses the same depth-1 QoS. Nothing is latched as a current pose.
ROS remapping works, for example `--ros-args -r __ns:=/demo` changes the private
topics to `/demo/aruco_target_tracker/...`. `--no-tf` disables the broadcaster.

The numeric transform is exactly:

```text
p_camera = R_target_to_camera @ p_target + t_target_to_camera
parent: camera_optical_frame    child: dodecahedron_25mm
```

- Translation is in **meters**, orientation is a unit quaternion **x, y, z, w**.
- Camera optical axes are **+x right, +y down, +z forward**, following
  [REP-103](https://www.ros.org/reps/rep-0103.html). They are different from a
  conventional robot body frame's axes.
- Target origin is the dodecahedron center. Its fixed axes come from `model.json`;
  visible face changes do not change the target frame.
- `--camera-frame` and `--target-frame` name these same physical frames. Renaming
  a frame does **not** rotate or translate the pose. Do not set the camera frame
  to `base_link`, `map`, or `odom` to pretend a mounting transform was applied.
- TF stores the target's pose in the camera frame; the numbers are not inverted.
  Supply the independently known camera-to-robot mounting transform in your own
  TF tree. Ensure each child has one parent and one active TF authority. Use
  distinct target frame names when running more than one tracker.

In **OpenCV input mode**, pose, TF and diagnostics for a frame share a ROS timestamp,
taken immediately after OpenCV returns that frame. This is an **approximate
read-completion timestamp**, not a hardware exposure time. Replay messages are
restamped into current ROS time for live visualization; original relative video
time is recorded separately in diagnostics. OpenCV input requires
`use_sim_time=false`; it does not publish `/clock` or synchronize to rosbag time.
If the ROS clock moves backward, the source stops with an error rather than
publishing transforms out of order. Topic input instead preserves acquisition
timestamps as described above; camera drivers remain responsible for timestamp quality.

## Tracking status and stale data

Each diagnostic array contains one `aruco_pose/target` status. Key/value entries
include `tracking_status`, `measurement_valid`, `source_state`, `reason`, frame
names, object ID, `frame_index`, `source_time_s`, timestamp basis, inlier/observed/
rejected marker IDs, reprojection RMSE, candidate count and ambiguity resolution.
RMSE is an image residual in pixels, not positional uncertainty or confidence.

- `measured`: DiagnosticStatus OK; a pose and, unless disabled, TF are published.
- `lost`, `rejected`, `ambiguous`: WARN; status only, no pose or TF. An old pose
  is never republished as a new measurement.
- `source_state=eof` or `stopped`: WARN, `measurement_valid=false`, no current pose.
- Topic waits, stale frames and input timeout: WARN and invalid status only.
- Bad topic calibration/encoding/frames/timestamps: ERROR and no pose/TF for that
  input; valid subsequent messages can recover. Diagnostics expose the reason.
- OpenCV source/read errors: ERROR and invalid heartbeats; fix the cause and restart.
  A file/camera that cannot be opened fails startup with an error.

**Consumers must check both status and timestamp age.** TF buffers and RViz can
retain a historical transform after tracking stops; absence of new TF does not
delete it. `tf2_echo` showing a transform is not proof of current visibility.
Use a bounded freshness threshold appropriate for the application (for example,
0.25 s at 24 FPS), reject invalid status, and treat a stopped status stream as
unavailable. Status and pose are separate topics: match their timestamps, not
arrival order. A blocked camera read or a killed/disconnected process cannot send
a final status, so downstream watchdogs are required. No motion controller is
included in this example.

## RViz

On a graphical Ubuntu session, optionally install RViz and open the supplied view:

```bash
sudo apt install ros-jazzy-rviz2
rviz2 -d examples/ros2/target_pose.rviz
```

The fixed frame is `camera_optical_frame`. The Pose display shows axes from
`/aruco_target_tracker/pose`; TF shows the camera and target frames. The display
uses the un-namespaced defaults; update its topic/fixed frame if you remap them.
Keep the replay running with `--loop`. RViz can display old poses after loss;
use the status topic and freshness checks above for application decisions.

## Use a physical kit

Follow the [kit assembly and calibration guide](../../docs/DODECAHEDRON_KIT.md).
Keep the camera's capture resolution/focus/zoom identical to calibration, then run:

```bash
python examples/ros2/target_pose_node.py \
  --source 0 --model assets/dodecahedron/model.json \
  --calibration /absolute/path/to/my-camera.json
```

Use your real calibration, never `replay_camera.json`. Default capture resolution
comes from OpenCV; a calibration/image-size mismatch stops the source and reports
an error. Camera timestamp quality and assembled-target accuracy remain unvalidated
hardware limitations. For an existing ROS camera driver use topic mode above.

## Tests

The ordinary suite tests the ROS-free frame/status contract. The separate Jazzy
CI job runs real ROS message and DDS tests in `ros:jazzy-ros-base-noble`, including
all 240 decoded replay frames, shared timestamps, TF direction, source EOF,
non-measured suppression, loop reset, disabling TF, CLI remapping and clean Ctrl+C
shutdown. Camera tests cover acquisition stamps, exact/late/static calibration,
QoS, RGB/gray/padded decoding, changed resolution/calibration, unsupported inputs,
stale/future/duplicate timestamps, timeout/recovery and simulated time.
To run them locally:

```bash
source /opt/ros/jazzy/setup.bash
source .venv-ros/bin/activate
python -m pip install pytest
python -m pytest examples/ros2 -q
```

The [official TF broadcaster tutorial](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html)
explains `TransformStamped` and dynamic broadcasting.
