# Changelog

## 0.3.0 - 2026-11-17

### Targets and examples

- Printable 25 mm-edge dodecahedron kit: A4 vector PDF/SVG, paired edge labels,
  glue tabs, matching model JSON, assembly guide and a raw camera-free replay.
- Project page with annotated board/dodecahedron demos, downloadable kits and
  runnable commands. All showcase footage is synthetic.
- Optional ROS 2 Jazzy example publishing measured PoseStamped, dynamic TF and
  per-frame diagnostics from video, a local camera or ROS Image/CameraInfo topics.
- Exact/latest calibration pairing, bounded pending input, sensor-topic QoS,
  acquisition timestamps, stale/future/duplicate rejection and timeout recovery.
- Explicit rectified-image input: P intrinsics, zero distortion, validated R,
  and pose conversion back to the original camera optical frame. Stereo reference
  projection offsets do not shift camera-local pose. Priors stay in their correct
  internal frame; R changes invalidate them.
- Real ROS/DDS CI checks alongside Windows/Linux core tests. Distribution builds
  require both core and ROS checks to pass.

### Compatibility and limits

- Core imports (`aruco_pose`), CLI names (`aruco-pose`, `aruco-cli`) and existing
  raw/replay defaults are unchanged. The package version advances from 0.2.0.
- ROS remains an optional source-checkout example, not a dependency of the core
  wheel. CSV/summary and pose API schemas are unchanged.
- ROS Image input supports mono8/BGR/RGB/BGRA/RGBA. Cropped/ROI/binned geometry,
  raw fisheye/Bayer/16-bit images and compressed transport remain unsupported.
  Already rectified pinhole pixels can come from an upstream fisheye rectifier
  when valid CameraInfo K/P/R is supplied.
- Synthetic results do not validate physical pose accuracy, target assembly,
  hardware timestamps, navigation or robot control. Older experiments remain
  labeled separately from the supported starter/API paths.

## 0.2.0

- Published `aruco-pose` distribution and `aruco_pose` import namespace.
- Print/calibrate/track/CSV starter kit and shared robust pose API.
- Corrected dodecahedron edge scaling, outlier rejection and planar ambiguity
  handling. Camera-free examples and opt-in CSV output.
