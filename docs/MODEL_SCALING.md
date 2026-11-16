# Dodecahedron dimensions

All lengths are in meters. Both `CleanDodecahedronModel(edge_length=0.025)` and
`DodecahedronWithMarkers(edge_length=0.025)` now produce 30 edges of 25 mm each.
The example model module imports the canonical implementation in `aruco_pose/models/`.
Nonpositive and nonfinite edge lengths raise `ValueError`.

The old implementation normalized against the first pair of vertices, which was
a diagonal rather than an edge. Actual edges were the requested length divided
by the golden ratio (approximately 1.618034).

## Saved model correction

| File in `config/` | Previous actual edge | Corrected edge |
| --- | --- | --- |
| `dodecahedron_face_map.json` | 15.45085 mm | 25 mm |
| `aruco_group.json` | Same face centers as the old 25 mm face map | 25 mm |
| `dodecahedron_with_markers.json` | 10.50658 mm | 17 mm |

The marked-face file retains the generator's existing 17 mm setting; it has not
been converted into a 25 mm model. Geometry vertices, centers and the translation
components of extrinsics were multiplied by the golden ratio. Marker IDs,
rotation vectors, face ordering and printed-marker sizes are unchanged. The
tag-group translations were verified against the old face-map centers before
correction and against the corrected centers afterward.

The two object-shaped JSON files now include `edge_length` and `units` metadata.
The face-map file retains its existing list format. The tracking demo reads the
marked-face model's edge length for its wireframe overlay rather than assuming
25 mm. The previous JSON versions remain available in Git and the recovery stash.

## Generate a different size

From the repository root, with the project dependencies available:

```powershell
python examples/04_custom_models/generate_model_to_json.py --edge-length 0.025 --output config/dodecahedron_25mm.json
```

The default is still 17 mm and the default output is
`config/dodecahedron_with_markers.json`. Importing the generator no longer writes
a file. Its per-face orientation corrections are retained.

Marker size is the printed square's side length, a separate physical quantity
from the pentagon edge. Do not rescale it merely because the solid was corrected.
Use a model matching the measured physical object; corrected geometry changes
pose measurements from the previously underscaled model. Camera intrinsic and
distortion files were not changed. No live-camera accuracy claim is made.

## Verification

24 tests pass across `test_dodecahedron_scaling.py` and
`test_recovered_tracking.py`. Checks cover every edge at several requested sizes,
invalid sizes, saved geometry/translation consistency, the example compatibility
module, JSON export at 25 mm, and synthetic multi-marker pose/refinement behavior.
The saved 17 mm model also matches a fresh export, including rotations.
