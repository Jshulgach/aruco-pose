# Publish aruco-pose 0.3.0

The owner performs the PyPI upload. CI tests core and ROS paths, builds the wheel
and source archive, and runs strict Twine checks. It never publishes to PyPI.
The existing project is `aruco-pose`; the import is `aruco_pose`.

## PowerShell commands

Run from the checked checkout after its release checks pass:

```powershell
cd C:\Users\jonat\Documents\GitHub\ArUco_Pose_Estimation
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install --upgrade build twine
.\.venv\Scripts\python.exe -m build --outdir dist/0.3.0
.\.venv\Scripts\python.exe -m twine check --strict dist/0.3.0/aruco_pose-0.3.0-py3-none-any.whl dist/0.3.0/aruco_pose-0.3.0.tar.gz
.\.venv\Scripts\python.exe -m twine upload --username __token__ dist/0.3.0/aruco_pose-0.3.0-py3-none-any.whl dist/0.3.0/aruco_pose-0.3.0.tar.gz
```

Enter a project-scoped PyPI API token for `aruco-pose` at Twine's password prompt.
Do not put it in the command line, repository or chat. Valid local keyring
credentials may avoid a prompt. Exact filenames exclude older `dist/` artifacts.

The module, package metadata and CLI versions must all be 0.3.0. Rebuild if code
changes after testing. PyPI files cannot be overwritten: if 0.3.0 was already
successfully uploaded, do not upload modified artifacts under the same version.

## Verify after upload

Inspect [the PyPI release](https://pypi.org/project/aruco-pose/0.3.0/) for its
README, version, license and files. Test the public wheel in a separate environment:

```powershell
python -m venv output/pypi-check
.\output\pypi-check\Scripts\python.exe -m pip install --no-cache-dir aruco-pose==0.3.0
.\output\pypi-check\Scripts\python.exe -I -m aruco_pose --version
.\output\pypi-check\Scripts\aruco-pose.exe --version
.\output\pypi-check\Scripts\aruco-cli.exe --version
.\output\pypi-check\Scripts\aruco-pose.exe kit sample --output output/pypi-sample
```

On Linux/macOS substitute `bin/python` and `bin/aruco-pose` for Windows paths.
The wheel contains the core library and CLI. ROS examples, print assets and site
source are in the GitHub checkout/source archive. ROS is installed separately;
`pip install aruco-pose` does not install ROS.

## Optional rehearsal and GitHub release

TestPyPI has separate accounts/tokens. Rehearse with
`twine upload --repository testpypi --username __token__` followed by the same two
artifact paths. This does not publish to production PyPI.

After verifying production upload, a GitHub release/tag `v0.3.0` can point at the
tested commit and use [the changelog](../CHANGELOG.md). Tags do not trigger PyPI
uploads here. Future versions update `setup.py` and `aruco_pose/__init__.py`
together, then repeat the checks on newly built artifacts.

References: [PyPA guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[PyPI tokens](https://pypi.org/help/#apitoken),
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
