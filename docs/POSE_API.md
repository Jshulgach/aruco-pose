# Shared pose API (schema version 1)

The supported CLI, `examples/pose_api_demo.py`, tag-group example and dodecahedron
tracking demo now use `aruco_pose.Tracker` and `aruco_pose.PoseResult`. Calibration and video/CSV
I/O stay in the starter workflow; pose geometry and quality decisions live in
`aruco_pose/pose.py`. The explicit-corner model used by the starter is accepted directly;
legacy marker-extrinsic files are adapted without changing their coordinate frames.

## Python usage

```python
import json
from pathlib import Path
import cv2
from aruco_pose import Tracker, TrackerConfig

model = json.loads(Path("assets/starter/board.json").read_text())
camera = json.loads(Path("assets/starter/reference_camera.json").read_text())
tracker = Tracker(
    model, camera["camera_matrix"], camera["distortion_coefficients"],
    config=TrackerConfig(min_markers=2),
    image_size=(camera["image_width"], camera["image_height"]),
    parent_frame="camera_optical", child_frame="starter_board",
)
cap = cv2.VideoCapture("assets/starter/tracking.mp4")
previous = None
index = 0
try:
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        result = tracker.process(frame, timestamp_s=index / 20., previous=previous)
        # result.pose exists only for an accepted current-frame measurement.
        if result.status == "measured":
            print(result.pose.translation_m, result.pose.quaternion_xyzw)
            previous = result
        else:
            print(result.status, result.reason)
        event = result.to_dict()          # JSON-serializable, schema_version=1
        csv_row = result.to_csv_row(index)
        index += 1
finally:
    cap.release()
```

For externally detected markers, call
`tracker.estimate(corners, ids, timestamp_s, previous=previous)` instead. Each
observation is four image points in the same order as its model corners, normally
OpenCV's detected top-left, top-right, bottom-right, bottom-left. `ids` can be flat
or Nx1. Unknown IDs remain visible in diagnostics but do not enter estimation.
Timestamp values are finite seconds supplied by the caller; the API does not
infer clock domains or hardware exposure timestamps. Use distinct camera frame
names and the same time basis when supplying a previous result.

Run the complete headless example:

```powershell
python examples/pose_api_demo.py --preview
# Optional export and time limit:
python examples/pose_api_demo.py --seconds 20 --csv output/api_example.csv
```

The demo writes no data files by default. Recorded video loops at playback speed
until Q, Escape, window close or Ctrl+C. Use `--seconds N` for a wall-clock limit
or `--once` for one pass; `--csv PATH` explicitly enables export. Replay timestamps
continue increasing, while the ambiguity prior is cleared at each restart.

This example uses the same model, result serialization and pose solver as `kit
track`. Its regression test compares statuses, support, timestamps and translations
with CLI output from the same video and estimated calibration.

## Result and transform contracts

`PoseResult` contains timestamp, object ID, parent/child frame names, status and
reason, observations, inlier/rejected marker IDs, reprojection RMSE, candidate
solutions, and how ambiguity was resolved. Each `MarkerObservation` records the
image corners, accepted corner indices (0-3) and a reason for exclusions. Invalid
nonfinite observations are recorded with empty corners, so event serialization
never emits NaNs from detector input.

| Status | Publishable `pose` | Meaning |
| --- | --- | --- |
| `measured` | Present | Current observations passed support, depth and residual checks; any competing planar branch was resolved. |
| `lost` | None | Too few usable recognized markers, including empty detections. |
| `rejected` | None | Invalid observations, no majority consensus, or failed numerical/quality checks. |
| `ambiguous` | None | Distinct current planar solutions fit similarly and no compatible recent measurement resolves them. |

No predicted result is implemented. A prior never substitutes for missing or
rejected observations. Unresolved candidates are diagnostics, not measurements.
The dataclasses are frozen and pose vectors are tuples; conversion properties
return fresh NumPy arrays. `PoseResult.to_dict()` has `schema_version=1` and
`units=meters`. No positional covariance or confidence probability is fabricated.

For `Pose(parent_frame, child_frame, translation_m, quaternion_xyzw)`:

```
p_parent = R_parent_from_child @ p_child + translation_m
```

Camera optical axes are x right, y down, z forward. Quaternions use x,y,z,w and
represent the object-to-camera rotation, not its inverse. `pose.matrix` is 4x4;
`pose.rvec`/`pose.tvec` are fresh 3x1 arrays for OpenCV. `transform_points`,
`inverse` and `compose` apply this convention. For example,
`world_from_camera.compose(camera_from_object)` gives `world_from_object`.
Composition checks that the intermediate frame names match. Quaternion sign may
change without changing the represented rotation; compare rotations, not raw signs.

## Outlier rejection

The solver proposes poses from the entire correspondence set, individual complete
markers, and corner-level RANSAC. This supports recovery from a misplaced whole
marker as well as isolated bad corners, including one bad corner on every marker.
Proposals are scored against all usable known corners. A marker must retain at
least three corners to count as support; otherwise its entire observation is
excluded. Duplicate detections of the same ID are all excluded rather than
inflating consensus.

Defaults require:

- At least two accepted markers (`min_markers`).
- A majority of usable known corners: at least 60% (`min_inlier_fraction=.6`;
  configurable values must exceed 50%).
- Each accepted corner within 3 pixels (`outlier_threshold_px`).
- Accepted-point reprojection RMSE at most 3 pixels
  (`max_reprojection_rmse_px`).
- Finite solutions and positive camera depth for every accepted point.

Only the consensus is refitted. Corners may be removed during reclassification;
removed observations cannot re-enter that fit. Final refinement uses only those
inliers and is checked again. A frame with no majority is rejected even if one
small subset can be fit very well. A physically incorrect model/calibration or a
coherent majority of wrong detections can still produce a plausible pose: these
checks are not a guarantee of correctness.

RMSE means sqrt(mean(squared 2D corner distance)), in pixels, over the accepted
corners only. It is not translation error, uncertainty, or independent evidence
of physical accuracy. Inspect excluded observations too.

## Planar ambiguity

When the accepted object points are planar, the solver transforms them to a local
plane basis and requests both IPPE solutions, then transforms each back into the
original object frame. This works for offset/tilted planes and single faces of a
polyhedron, not only z=0 boards. Nonplanar sets use SQPnP. The approach follows the
[OpenCV PnP methods](https://docs.opencv.org/4.13.0/d5/d1f/calib3d_solvePnP.html).

Finite positive-depth candidates are evaluated on the same accepted observations.
Distinct alternatives within `ambiguity_gap_px=.05` RMSE of the best candidate
and within the maximum quality error cause `ambiguous`. Coincident solutions
(rotation separation <= .001 rad AND translation separation <= 1 micrometer) are
one effective pose, including the exact frontal case. Candidate errors are before
nonlinear refinement, so refinement cannot merge the branches before comparison.

An explicit `previous` result may select among these close candidates only if it:

- Is measured, from the same object and parent/child frames.
- Has an earlier timestamp no more than .25 seconds old (`prior_max_age_s`).
- Clearly favors a branch: score separation at least .1 (`prior_score_margin`).
- Is within .5 radians and .1 meters of that branch (`prior_max_rotation_rad`,
  `prior_max_translation_m`).

The score is rotation distance in radians plus translation distance divided by
the model's spatial extent. These are tunable continuity heuristics, not a motion
model or probability. `ambiguity_resolved_by` is `recent_measurement` or
`reprojection` for accepted poses. Refinement cannot silently cross to the competing
branch; it keeps the selected current-frame hypothesis if that happens. Equidistant,
stale, future, differently framed or overly distant priors leave the result ambiguous.

The tracker has no hidden temporal state. Set `previous=None` after a scene reset,
object relocation or calibration change. Callers must not feed it an invented or
predicted value labeled as a measurement. The starter CLI passes its last measured
result explicitly; loss never advances that measurement's timestamp.

## CLI and CSV compatibility

The existing starter commands still work. Additional options:

```powershell
python -m aruco_pose kit track --source assets/starter/tracking.mp4 --model assets/starter/board.json --calibration output/sample_calibration.json --csv output/poses.csv --outlier-threshold 3 --ambiguity-gap 0.05
```

The CSV/summary schema is now **version 2**, preserving the original column names
and order and appending diagnostics. `marker_ids`/`marker_count` now describe
accepted inlier marker support; `observed_marker_ids` includes all detector IDs.
The other new columns are `reason`, `rejected_marker_ids`, `inlier_corner_count`,
`candidate_count`, `ambiguity_resolved_by`, `parent_frame` and `child_frame`.
Lost, rejected **and ambiguous** rows have blank position/quaternion fields.
Inlier IDs on an ambiguous/rejected row indicate diagnostic consensus, not an
accepted measurement. Summary metadata reports each status separately and includes
the complete tracker configuration. Read columns by name, not fixed total count.

Legacy `estimate_pose` methods keep the tuple API; the new `estimate_result` and
`process` methods return the shared result. Tag-group estimation now considers all
recognized visible tags, rather than only ID 0. Legacy marker corner conventions
and rotations are preserved by the adapters. New and updated examples are:

- `examples/pose_api_demo.py` (camera-free starter board).
- `examples/02_single_marker/marker_tracking.py` (tag-group JSON).
- `examples/04_custom_models/dodecahedron_tracking_demo.py` (face JSON).

The older monolithic `dodecahedron_pose.py` and basic/advanced research scripts
still contain experimental algorithms; they have not all been converted to the
shared result contract. The redundant multi-marker and GPT estimator modules now
re-export the shared adapters. Rotation-aware filtering, calibrated uncertainty,
ROS and hardware timestamps remain separate roadmap work.

## Tests

```powershell
python -m pytest tests/test_pose_api.py tests/test_starter_workflow.py tests/test_recovered_tracking.py tests/test_dodecahedron_scaling.py -q
```

Tests use known synthetic poses, not expected values copied from the solver.
They cover units and frame composition/inversion, JSON/CSV serialization,
corner/marker outliers, split consensus, invalid and duplicate observations,
frontal/tilted/arbitrary planes, both ambiguous branches, prior age/frame/motion
gates, branch-preserving refinement, nonplanar legacy models and camera-free
CLI/example parity. Real camera validation remains a release check.
