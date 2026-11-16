# Local work recovery - 2026-11-16

## Result

Recovered against main at `d917cac`. The original stash remains untouched:
`3081abd0ccf3715ab225ea810257bb548000e9a8` (`stash@{0}`, recovery label dated 2026-11-16).
Changes are left uncommitted for review. No push was made.

All 30 saved paths are accounted for below. Most local work was already incorporated
into upstream: 23 files match a relocated upstream file after line-ending normalization,
4 differ only in import/bootstrap edits, and the dependency addition is already covered.
Only 2 files were missing: the overlay helper and face-map visualizer. The full video
was also already present, so no duplicate video was created. Original index/staging
state remains in the stash; recovered files follow the new package layout.

## What you were working on

The local diff extends basic single-marker tracking into tracking a marked dodecahedron:

- Geometry: two dodecahedron models, 12 pentagonal faces, marker IDs and per-face
  rotation offsets, marker corner transforms, JSON export and visual inspection.
- Pose estimation: collecting marker corners into one object frame and solving PnP;
  separate estimators for a JSON face model and an in-memory model.
- Tracking robustness: nonlinear reprojection refinement, frame-to-frame prediction,
  smoothing, optical-flow corner fallback, and exploratory patch recovery.
- Calibration and inspection: skipping capture when calibration frames already exist,
  returning detected marker poses/IDs/corners from the legacy utility, and viewing
  face normals, axes and wireframe overlays.

These are useful foundations, particularly the combined-marker PnP estimator,
reprojection refiner, JSON assets, and geometry inspection tools. The advanced
corner tracker is an experiment: much of its pose/recovery pipeline is commented out.
No claim about when these edits were made can be inferred from the stash alone.

## Repairs during recovery

- Restored missing visualizer and overlay in `tools/` and `aruco_pose/utils/`.
- Exposed the existing refiner and predictor as package modules in `aruco_pose/tracking/`;
  preserved the older advanced-example imports through small compatibility modules.
- Replaced old flat imports with package imports in recovered examples and tools.
- Pointed relocated examples at the existing root calibration files and `config/` JSON.
- Removed package initializer imports of modules/classes that do not exist upstream
  (`core.calibration`, `core.pose_estimator`, `OpticalFlowTracker`, `DenseRefiner`).
  Their advertised APIs are not implemented by this recovery; actual existing helpers
  remain available. This unblocks imports without inventing missing functionality.
- Fixed a missing `cv2` import, a one-marker indexing failure, stale plot-model names,
  overlay bounds for non-square images, and a misleading millimeters help string.

## Limits and follow-up work

1. **Physical scale corrected in follow-up.** Both model classes now scale by the
   shortest vertex separation. `edge_length=0.025` produces 25 mm pentagon sides.
   Saved face-map/tag-group geometry was corrected to 25 mm; the marked-face JSON
   retains its generator's intended 17 mm edge. Positions were scaled by the golden
   ratio; marker sizes, rotations and IDs were preserved. See `MODEL_SCALING.md`.
2. **Two pose paths differ.** `aruco_pose_pipeline.ArucoPoseEstimator` currently uses
   only marker ID 0; its combined-marker loop is commented out. The JSON/model
   estimators in `aruco_pose_estimator.py` actually combine recognized markers.
3. **Filtering is experimental.** Prediction is a simple per-frame Rodrigues-vector
   extrapolation, with no elapsed-time model or rotation-manifold handling. In the
   recovered tracking demo, predicted poses are not drawn when detection is absent.
   It is not yet a reliable occlusion-handling pipeline.
4. **Physical conventions differ.** Model sizes and per-face rotation offsets differ
   across generators and trackers. Confirm the printed object's dimensions, marker
   size, marker IDs and corner orientation before using measurements.
5. **Environment needs attention.** The repository's ignored `aruco` virtual environment
   points to a missing `C:\Python310\python.exe`; the default Python shim is also
   unconfigured. Validation used the existing neighboring Hand-Landmark-Tracker
   environment (OpenCV 4.13 with ArUco, NumPy, SciPy, Matplotlib), without changing it
   or installing dependencies. Set up a working project environment for daily use.
6. Camera calibration `.npy` files remain present and were not changed. No live camera
   session or real-world accuracy validation was performed.

## Validation

- 3 recovery regression tests pass: synthetic multi-marker PnP plus refinement,
  predictor/reset behavior, overlay bounds on a wide image.
- Package/model/tracking imports succeed; calibration, basic pose and dodecahedron
  pose command `--help` checks succeed.
- Five geometry/face-map plotting scripts run using Matplotlib's headless Agg backend.
- Existing installation verification: 6/7 pass. The logging test fails on Windows
  because it deletes its temporary log while the file handler still holds it open.
  This is outside the recovery changes.
- Stash retained; no unresolved Git merge entries; diff whitespace check passes.

## Complete inventory

| Saved path | Current path | Disposition |
| --- | --- | --- |
| `calibrate.py` | `examples/01_basic/camera_calibration.py` | Already included; only import/bootstrap changes |
| `config.yaml` | `config.yaml` | Identical upstream |
| `dodecahedron_model.py` | `aruco_pose/models/dodecahedron_model.py` | Identical upstream, including staged/unstaged geometry work |
| `dodecahedron_pose.py` | `examples/04_custom_models/dodecahedron_pose.py` | Already included; repaired remaining old imports |
| `pose.py` | `examples/02_single_marker/simple_pose_estimation.py` | Already included; only import/bootstrap changes |
| `requirements.txt` | `requirements.txt` | Local packaging addition already covered by packaging>=20.0 |
| `utils.py` | `aruco_pose/utils/legacy_utils.py` | Identical upstream |
| `aruco_group.json` | `config/aruco_group.json` | Identical upstream |
| `aruco_main_tracker.py` | `examples/02_single_marker/marker_tracking.py` | Already included; repaired imports/data paths and single-detection indexing |
| `aruco_pose_pipeline.py` | `aruco_pose/models/aruco_pose_pipeline.py` | Identical upstream |
| `assets/WIN_20250404_11_11_34_Pro.mp4` | `assets/WIN_20250404_11_11_34_Pro.mp4` | Identical upstream |
| `assets/desktop.ini` | `assets/desktop.ini` | Identical upstream |
| `dodecahedron_face_map.json` | `config/dodecahedron_face_map.json` | Identical upstream |
| `dodecahedron_with_markers.json` | `config/dodecahedron_with_markers.json` | Identical upstream |
| `generate_model.py` | `tools/visualize_dodecahedron_model.py` | Already included; repaired model import |
| `generate_model_to_json.py` | `examples/04_custom_models/generate_model_to_json.py` | Already included; repaired import/output path |
| `gpt_aruco_pose_estimator.py` | `aruco_pose/models/aruco_pose_estimator.py` | Identical upstream |
| `gpt_draw_overlay.py` | `aruco_pose/utils/dodecahedron_overlay.py` | Restored missing file; corrected width/height bounds |
| `gpt_generate_model.py` | `tools/visualize_face_map.py` | Restored missing file; repaired data path; plotting under main guard |
| `gpt_main_tracker.py` | `examples/04_custom_models/dodecahedron_tracking_demo.py` | Already included; repaired imports/data paths |
| `gpt_pose_refiner.py` | `aruco_pose/tracking/pose_refiner.py` | Already upstream in examples; restored as reusable package module |
| `gpt_predictive_filter.py` | `aruco_pose/tracking/predictive_filter.py` | Already upstream in examples; restored as reusable package module |
| `index.html` | `assets/index.html` | Identical upstream |
| `test.py` | `examples/05_advanced/corner_tracking_demo.py` | Already included; only import/bootstrap changes |
| `test/dode_model_test.py` | `tests/test_dodecahedron_model.py` | Already included; repaired removed model name and faces attribute |
| `test/plot_test2.py` | `tests/test_visualization.py` | Already included; repaired model import |
| `utilities/dense_refinement.py` | `aruco_pose/tracking/dense_refinement.py` | Already included; added missing cv2 import |
| `utilities/optical_flow.py` | `aruco_pose/tracking/optical_flow.py` | Identical upstream |
| `visualize_aruco_extrinsics.py` | `tools/visualize_aruco_extrinsics.py` | Already included; repaired JSON path |
| `viz2.py` | `tools/visualize_dodecahedron_3d.py` | Already included; repaired model import |
