# Project showcase

Live URL: https://jshulgach.github.io/aruco-pose/

The project page is a buildless static site deployed by `.github/workflows/pages.yml`.
It uses GitHub Pages, with no analytics, external fonts, accounts or backend.
Its install link points to the published `aruco-pose` distribution on PyPI.

## Edit and preview

- Content: `site/index.html`
- Layout/responsive styles: `site/styles.css`
- Clipboard/reduced-motion behavior: `site/app.js`
- Public synthetic video and poster: `site/assets/`
- Assembly and local resource validation: `scripts/build_project_page.py`

```powershell
python scripts/build_project_page.py
python -m http.server 8766 --bind 127.0.0.1 --directory output/project-page
```

Open http://127.0.0.1:8766/ . Rebuild after editing; reload the browser afterward.
All local asset paths are relative so the site works under GitHub's `/aruco-pose/`
project URL. The marker SVGs retain their physical millimeter dimensions.

The builder creates a sample ZIP from `assets/starter/` and copies only explicit
static assets. It does not expose the repository, local CSVs/calibration, or older
personal camera recordings. The annotated hero video comes from the synthetic
starter replay, transcoded to H.264/yuv420p with fast-start MP4 metadata for browser
compatibility. Its six-second clip includes complete and partial occlusion.

The second demo shows a rotating synthetic dodecahedron with true 25 mm edges and
15 mm markers. Each frame is rendered with back-face culling and perspective
marker textures, then passed through `Tracker.process` without a pose prior.
The axes and visible wireframe use the measured pose; ground truth is used only
to check the result. This generated marker layout is separate from the physical
target configurations. It does not change the saved physical JSON models.

The dodecahedron is also the lead README/site demonstration. The README embeds
`site/assets/dodecahedron-tracking.gif` through the public Pages asset URL; it is
a 640 x 480, 12 FPS, ten-second looping conversion of the annotated synthetic MP4.
The website uses the H.264 video in its hero so playback controls and reduced-motion
preferences remain available. The generator recreates the GIF alongside the MP4
and poster. This new synthetic GIF is unrelated to the older personal camera GIF.
Describe multi-face geometric support and the fixed target origin; physical
jitter reduction has not been benchmarked, and no temporal smoothing is shown.

The downloadable dodecahedron kit is assembled from the explicit file list in
`scripts/build_project_page.py`, under a `dodecahedron/` ZIP folder. Its source is
`assets/dodecahedron/`: vector PDF/SVG faces with paired edge labels and tabs,
matching marker corners, raw synthetic replay, known replay camera, ground truth
and instructions. The kit works with the published 0.2.0 CLI; it needs no new
package release. A separate PDF preview and guide link are on the page. See
`docs/DODECAHEDRON_KIT.md` for assembly, camera/replay commands and regeneration.

To regenerate the ten-second H.264 clip, poster and verification report:

```powershell
python -m pip install imageio-ffmpeg
python -m scripts.build_dodecahedron_kit
python scripts/generate_dodecahedron_demo.py
python scripts/build_project_page.py
```

Run this in the development environment (`pip install -e .[dev]`).
`imageio-ffmpeg` is an optional media-generation tool, not a runtime dependency.
The report is `site/assets/dodecahedron-demo.json`; its errors measure recovery
from ideal synthetic images, not accuracy with a physical camera or target.
To regenerate the print PDF too, install `reportlab` and follow the kit guide.

## Deploy

Push changes to `site/`, the starter assets, the builder or Pages workflow on `main`.
GitHub Actions builds and validates resources, uploads the dedicated output folder,
and deploys with the `github-pages` environment. The workflow can also be run
manually from Actions. It has no PyPI publishing step.

## Verification

Tests validate local links, target downloads, both sample ZIPs and separate build
output. Browser QA covers desktop/mobile layout, video decoding/playback, section
navigation and both copy buttons. Reduced-motion preferences suppress autoplay;
video controls remain available. Static content and download links work without JS.

Keep accuracy claims tied to measured evidence. The replay is synthetic; ROS 2,
docking and navigation adapters remain roadmap work rather than present features.
