# Package rename: aruco-pose

The distribution is now **aruco-pose** and the Python import package is
**aruco_pose**. The GitHub repository is now `Jshulgach/aruco-pose`. This namespace
migration shipped as 0.2.0; see the [changelog](../CHANGELOG.md) for current releases.
See [publishing instructions](PUBLISHING.md) for the initial PyPI upload.

## Install this checkout

If this environment contains the old editable distribution, remove its metadata
before reinstalling (use the same environment's Python for both commands):

```powershell
python -m pip uninstall aruco-pose-estimation
python -m pip install -e ".[dev]"
```

The uninstall command is unnecessary in a fresh environment. For source development, install from the checkout. Registry installation becomes
available once the owner completes the first PyPI upload.

## Imports

```python
from aruco_pose import Tracker, TrackerConfig, Pose, PoseResult
from aruco_pose.models.aruco_pose_estimator import ArucoPoseEstimatorFromJSON
```

Replace `from src...` imports with `from aruco_pose...`. CLI implementation modules
moved from `tools.cli`/`tools.starter` to `aruco_pose.cli`/`aruco_pose.kit_cli`.
The wheel installs only `aruco_pose` and its subpackages: no generic `src` or
`tools` package is shipped. There is no `src` import shim, to avoid namespace
collisions. Examples/tests and their compatibility imports use the new package.

## CLI

These invoke the same command group:

```powershell
aruco-pose kit --help
python -m aruco_pose kit --help
aruco-cli kit --help
```

`aruco-pose` is the primary installed command; `aruco-cli` is retained as a
compatibility alias. `python -m aruco_pose.cli` also works. In a checkout,
`python tools/cli.py` remains a small repository-only compatibility wrapper.
The wrapper and other standalone visualization tools are not installed as a
second generic Python package.

The print/calibrate/track commands, model/calibration file formats, CSV schema 2,
pose API schema 1 and no-export-by-default demo behavior are unchanged.

```powershell
python examples/pose_api_demo.py --preview --seconds 20
```

Tests cover renamed metadata, both installed console scripts, module execution
outside the checkout, the repository wrapper, existing geometry/pose behavior,
and the complete camera-free workflow. Wheel validation additionally checks that
no old package namespaces are included and runs generated samples from an isolated
installation directory.
