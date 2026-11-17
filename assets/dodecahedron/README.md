# Dodecahedron print and replay kit

One layout for a printable target and a camera-free replay. The ideal target has
25 mm edges, twelve 15 mm ArUco markers (black square including its border), and
uses `DICT_5X5_100`. IDs are 0, 1, 3-12; ID 2 is intentionally unused.
This is a prototype papercraft kit: the replay is synthetic, and physical tracking
accuracy has not been validated. Assembly, paper thickness and printing can all
move the real marker corners away from the ideal JSON coordinates.

Download and extract the **dodecahedron-kit.zip** from
https://jshulgach.github.io/aruco-pose/#dodecahedron . It contains a `dodecahedron/`
folder. Open a terminal **inside that folder** for every command below.
Repository users can instead open `assets/dodecahedron/`.

## 1. Try it without a camera

Use Python 3.9+ in a fresh virtual environment. Install the published package:

```powershell
python -m pip install aruco-pose
python -m aruco_pose kit track --source tracking.mp4 --model model.json --calibration replay_camera.json --csv output/replay.csv --output-video output/replay-overlay.mp4
```

Add `--preview` to see tracking while it runs (graphical desktop required; press
Q to stop). Without it, the command is headless and finishes at the end of the
ten-second video. CSV and an annotated video are written because the command
explicitly requests them. Omit `--output-video` to skip the annotated file.

`tracking.mp4` contains **raw rendered pixels**, with no axes, marker outlines or
pose labels baked in. The tracker detects those pixels afresh. The camera JSON
is the renderer's known 960 x 720 camera, not a calibration for a real camera.
Expected: 240 frames at 24 fps, all measured, at least two inlier markers per frame.
`ground_truth.csv` gives object-to-camera translations in meters and rotations as
rotation vectors in radians for comparison. `replay_validation.json` records the
decoded-video check; small errors here do not predict physical accuracy.

CSV columns include time, status, translation, quaternion (x/y/z/w), inlier marker
IDs and reprojection error. A missing/rejected/ambiguous pose has blank pose
columns. The companion `.summary.json` records the model, camera and settings.

## 2. Print and assemble the target

1. Print `faces.pdf` on A4 at **actual size / 100%**, single-sided. Disable
   fit-to-page, scaling and mirroring. `faces.svg` is the identical vector source
   if you prefer an SVG print workflow. Do not print both and combine them.
2. Measure the reference line: it must be **50 mm**. Also check a pentagon edge
   is **25 mm** and a black marker square is **15 mm**. Fix printer settings if
   any dimension is wrong; do not compensate by changing camera calibration.
3. Use matte, stiff paper or light card. Lightly pencil each face ID on its back
   before cutting (the printed ID heading is outside the cut piece).
   Score only the dashed tab folds, then
   cut along the solid perimeter of each of the twelve pieces. Cut on the line;
   do not trim the pentagons smaller. Keep each marker attached to its pentagon.
4. Every edge code E01-E30 appears exactly twice. Join matching codes edge to
   edge with the **markers facing outward**, folding glue tabs inward and
   attaching them to the unprinted back of the matching face. Each pair has
   exactly one tab. Keep the printed marker orientation fixed on its face.
5. Start with face ID 0 and its five neighboring pieces, then close the shell
   by matching the remaining edge codes. Leave a final face open until the
   inside tabs are glued. Allow the glue to set before tracking.
6. Keep faces flat, edges aligned, and the white area around each marker clean.
   Do not cover markers or their white border with glossy tape. Check the final
   shell has twelve faces and no unmatched edges. Do not move, rotate, resize
   or swap individual markers after assembly.

The printed edge labels establish the model's adjacency and orientation; merely
putting the same IDs on an arbitrary dodecahedron is insufficient. `assembly.json`
lists each face's edge codes, neighboring IDs, tab ownership, and local print
coordinates in millimeters. `model.json` holds the corresponding four 3D corners
per marker in meters, in detected top-left/right/bottom-right/left order.
The object origin is the solid's center; its fixed axes are defined by those
coordinates. The returned transform maps **object points into camera coordinates**
(camera +x right, +y down, +z forward), not into a robot or world frame.

This layout is independent of the older `config/dodecahedron_*.json` physical
targets. Use **this kit's `model.json`** with this print. For a different size or
marker layout, generate/measure a corresponding model instead of mixing files.

## 3. Calibrate your camera, then track the assembled target

Print `checkerboard.svg` at actual size on a flat rigid backing: 9 x 6 **inner
corners**, 20 mm squares. Measure a square. Keep the same camera, resolution,
focus and zoom for calibration and tracking. The CLI uses the camera's default
capture resolution; changing it afterward requires a matching calibration.

```powershell
python -m aruco_pose kit calibrate --source 0 --preview --cols 9 --rows 6 --square-size 0.02 --output output/my-camera.json
python -m aruco_pose kit track --source 0 --model model.json --calibration output/my-camera.json --csv output/camera.csv --preview
```

During calibration press SPACE for each checkerboard view. Capture varied tilts,
distances and positions, including image edges; the default limit is 40 views and
at least eight valid views are required. Press Q when finished. Inspect the
reported RMS; capture better views if it exceeds 1 pixel. A low RMS alone is not
a guarantee of physical pose accuracy.

During tracking press Q or Ctrl+C to stop. Try camera index 1 if 0 is the wrong
device. Use bright diffuse lighting and bring the target close enough for sharp
marker squares while keeping it in focus. Turn it slowly so at least two markers
are visible and readable. Face transitions change the inlier IDs while the
object coordinate frame stays fixed. The default requires two markers; do not
lower that threshold simply to hide loss or ambiguity.

**Never use `replay_camera.json` for a physical camera.** If the program reports a
resolution mismatch, use the same camera settings as calibration or recalibrate;
do not resize images to silence the check. If axes jump or scale looks wrong,
check print measurements, face assembly, marker orientation, focus and calibration.
If nothing is detected, check lighting, focus, dictionary and marker pixel size.
If the app reports lost/rejected/ambiguous, it has no accepted measurement for
that frame; downstream software must handle that status.

## Contents and regeneration

- `faces.pdf`, `faces.svg`: A4 vector print sheet, including glue tabs and scale bar.
- `model.json`, `assembly.json`: matching ideal geometry and assembly information.
- `checkerboard.svg`: physical camera calibration target.
- `tracking.mp4`, `replay_camera.json`, `ground_truth.csv`: synthetic replay inputs.
- `replay_validation.json`: result of tracking the decoded replay with this model.
- `README.md`: these instructions. Package and generated assets: Apache-2.0.

Maintainers can regenerate from a repository checkout with its development
environment. Media/PDF tools are optional developer dependencies:

```powershell
python -m pip install -e ".[dev]"
python -m pip install imageio-ffmpeg reportlab
python -m scripts.build_dodecahedron_kit
python scripts/render_kit_pdf.py assets/dodecahedron/faces.svg assets/dodecahedron/faces.pdf
python scripts/generate_dodecahedron_demo.py
python scripts/build_project_page.py
```

Regenerating the demo also writes the kit's raw replay and ground truth. The
tests run the documented CLI on the **decoded** video and compare its exported
poses to ground truth, plus verify print geometry, marker bits and edge pairing.
