# Roadmap after the starter kit

The first deliverable is a reproducible print -> calibrate -> rigid-board tracking
-> CSV workflow. The next milestones below build on it in dependency order. These
are proposed development tasks, not claims that the capabilities already exist.

Public distribution: `aruco-pose`; Python package: `aruco_pose`; command:
`aruco-pose` (`aruco-cli` compatibility alias). See [migration notes](PACKAGE_MIGRATION.md).

## 0. Starter kit (implemented)

- Physical-size SVG marker board and checkerboard, model generated alongside print.
- Video/live-camera calibration, headless video replay, multi-marker object pose,
  CSV with explicit missing/rejected observations and reproducible summary metadata.
- Synthetic calibration/tracking videos with known camera and motion, full/partial
  occlusion, and CLI regression checks against ground truth.
- Fresh-environment installation and clear coordinate/unit documentation.

Remaining release checks: physically print and measure the sheets, run a real
webcam session on several cameras, and verify Linux/macOS installation and capture.
Synthetic tests do not satisfy those checks.

## 1. Stable pose API and measurement quality (API and robust fitting implemented)

Implemented in this follow-up: `Tracker`, `TrackerConfig`, `Pose`, `PoseResult`,
shared CLI/example serialization, corner/marker outlier rejection, planar IPPE
candidate comparison and explicit recent-measurement ambiguity selection.
See [Pose API](POSE_API.md) for thresholds, contracts and tested limitations.
CSV/summary schema 2 retains old columns and appends quality diagnostics.

Still pending in this milestone: rotation-aware temporal filtering, calibrated
uncertainty if supported by evidence, hardware timestamps/backends, CI coverage,
and migration/deprecation of remaining experimental scripts and old CLI commands.

**Deliver:** a documented Python `Tracker` API and `PoseResult`, shared by CLI,
examples and future adapters. Include source/exposure timestamp where available,
parent/child frames, object ID, meter translation, quaternion, marker observations,
quality metrics, and explicit measured/predicted/lost status. Preserve the starter's
CSV semantics and version the schema.

Add robust corner/marker outlier rejection, planar PnP ambiguity handling, and
rotation-aware temporal filtering. Estimate uncertainty only with documented
assumptions; do not relabel reprojection error as positional accuracy or publish
invented covariance. Add hardware timestamps only for backends that expose them.

**Done when:** public API examples run in CI; transform inversion/composition and
quaternion conventions are tested; wrong IDs, noisy corners, outliers, occlusion
and ambiguous planar views have regression cases. No rejected observation becomes
an unlabeled predicted measurement. Deprecate or repair the older CLI commands.

## 2. Shared marker-layout format and target tools

**Deliver:** one versioned rigid-target schema with dictionary, units, named frames,
ordered 3D marker corners, physical dimensions and marker orientation. Provide
importers for existing dodecahedron/tag-group JSON without discarding face offsets.
Use the same validated geometry for tracking, visualization and export.

Support single markers, planar grids, cubes and dodecahedra. Add dimensioned nets,
assembly orientation guides and a model inspector. Add ChArUco target generation
and calibration alongside the starter checkerboard. Optional AprilTag-family
support needs explicit corner-order and detector validation before advertising it.

**Done when:** every supplied target round-trips through the schema; printable
models agree with 3D dimensions; all legacy assets import with matching transforms;
users can define a new rigid arrangement without modifying tracker code.

## 3. ROS 2 adapter and manipulation example

**Replay/local-camera and raw ROS camera-topic input implemented:**
[ROS 2 Jazzy pose + TF example](../examples/ros2/README.md) publishes measured
`PoseStamped`, optional dynamic TF and per-frame tracking diagnostics through the
shared Tracker. It includes the dodecahedron replay, an RViz view, explicit optical
frames, read-completion timestamps for OpenCV input, EOF invalid heartbeats, and
real ROS/DDS CI. Raw `Image`/`CameraInfo` input preserves acquisition timestamps,
validates matching optical frames and calibration geometry, bounds pending input,
and reports stale/invalid/missing data. Exact and latest calibration pairing,
sensor-data QoS, and externally supplied simulated time are supported. Core
Python stays ROS-free. Explicit rectified input now uses P/R and restores the
original optical-frame pose. Raw fisheye/ROI/binning input and the separately
packaged adapter/manipulation integration below remain future work.

**Depends on:** stable pose API and frame conventions.

**Deliver:** a separate optional ROS 2 package subscribing to `Image` and
`CameraInfo`, publishing `PoseStamped`, quality/status information and optional TF.
Use image acquisition timestamps, explicit optical frames, bounded processing
queues and transforms supplied for camera-to-robot mounting. Covariance messages
come only when uncertainty estimation is supported. Core Python stays ROS-free.

Include a launch file, RViz configuration, recorded replay, and an example that
transforms an object's named grasp frame into robot base coordinates. A marker
pose alone is not an authorized motion command.

**Done when:** replay reproduces reference poses; TF direction, frame IDs, units,
time synchronization and stale-data handling are tested; installation is documented
for one explicitly selected supported ROS 2 distribution.

## 4. Docking and known-marker localization

**Depends on:** ROS 2 adapter and quality/timing handling.

**Deliver:** a Nav2 docking example that supplies a detected dock pose, plus an
example computing camera/robot pose from a surveyed fixed-marker map. Define the
marker-to-dock and camera-to-base transforms explicitly. Fuse landmark observations
with odometry through a documented integration rather than implying a tag detector
provides continuous navigation.

**Done when:** simulated/replayed approaches demonstrate detection loss recovery,
stale-pose rejection and correct transforms; a physical robot experiment reports
repeatability and failure conditions. Keep navigation/control outside the core
vision library. Nav2's external-detection interface is documented at
https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/.

## 5. Public benchmark and release process

Start collecting data during milestones 1-4 rather than waiting for the end.

**Deliver:** recordings with independently measured reference positions/rotations,
camera calibration, lighting/distance/view-angle annotations and hardware details.
Report translation/rotation error, stationary jitter, detection rate, recovery time,
latency and throughput separately. Compare single-marker, flat-board and polyhedron
tracking under the same conditions. Publish code, data licenses and failure clips.

**Done when:** results can be regenerated with one command; performance claims
identify camera, resolution, distance, target dimensions and reference uncertainty;
CI checks Windows/Linux and a supported dependency matrix. Add wheel-install smoke
tests, packaging/version consistency, and release notes. Never infer real-world
accuracy from the synthetic starter video alone.

## Recommended next task

Complete one measured real-camera board session and add its replay dataset. Use
that evidence to evaluate the shared API thresholds and design rotation-aware
filtering and uncertainty tests. The API and synthetic outlier/ambiguity tests
are now implemented; the ROS replay example is available. Physical validation
should precede accuracy claims and ROS control integration. Next ROS work includes
cropped/binned camera geometry and camera mounting transforms.
