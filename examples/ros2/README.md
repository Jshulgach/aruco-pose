# Target pose and TF with ROS 2

An optional Python node for **ROS 2 Jazzy on Ubuntu 24.04**. It reads a video or
local camera through OpenCV and uses the same `Tracker` as the CLI. No ROS packages
are imported by the core `aruco_pose` library. This first example does not subscribe
to `sensor_msgs/Image`/`CameraInfo`; camera-driver integration remains roadmap work.

The node writes no files. It publishes one target's measured pose, optional dynamic
TF, and tracking diagnostics. No covariance, filtering, robot commands or world
localization are implied by these messages.

## Setup

Install [ROS 2 Jazzy for Ubuntu](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
first. Run the following in a Bash terminal, using the Ubuntu **system Python**
(the interpreter must match the installed ROS binaries):

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install python3-venv libgl1 libglib2.0-0 ros-jazzy-tf2-ros ros-jazzy-tf2-msgs ros-jazzy-geometry-msgs ros-jazzy-diagnostic-msgs
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

## Topics and frame contract

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

The pose, TF and diagnostic messages for a frame share the same ROS timestamp,
taken immediately after OpenCV returns that frame. This is an **approximate
read-completion timestamp**, not a hardware exposure time. Replay messages are
restamped into current ROS time for live visualization; original relative video
time is recorded separately in diagnostics. This example requires
`use_sim_time=false`; it does not publish `/clock` or synchronize to rosbag time.
If the ROS clock moves backward, the source stops with an error rather than
publishing transforms out of order. Use a camera-driver adapter with acquisition
timestamps for precise sensor fusion.

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
- Source/calibration/read errors: ERROR and invalid heartbeats; fix the cause and
  restart. A source that cannot be opened fails startup with an error.

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
hardware limitations. This does not consume an existing ROS camera topic.

## Tests

The ordinary suite tests the ROS-free frame/status contract. The separate Jazzy
CI job runs real ROS message and DDS tests in `ros:jazzy-ros-base-noble`, including
all 240 decoded replay frames, shared timestamps, TF direction, source EOF,
non-measured suppression, loop reset and disabling TF. To run them locally:

```bash
source /opt/ros/jazzy/setup.bash
source .venv-ros/bin/activate
python -m pip install pytest
python -m pytest examples/ros2/test_target_pose_ros.py -q
```

The [official TF broadcaster tutorial](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html)
explains `TransformStamped` and dynamic broadcasting.
