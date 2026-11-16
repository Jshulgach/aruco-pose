# Publish aruco-pose 0.2.0

Repository: https://github.com/Jshulgach/aruco-pose
Distribution: `aruco-pose`; import: `aruco_pose`; commands: `aruco-pose` and `aruco-cli`.
PyPI upload is performed manually by the owner. CI only tests, builds and validates
artifacts; it never uploads to PyPI. Do not send a token in chat or commit it.

## First upload from PowerShell

Run from your existing checkout (its local folder name need not match GitHub):

```powershell
cd C:\Users\jonat\Documents\GitHub\ArUco_Pose_Estimation
.\.venv\Scripts\python.exe -m pip install --upgrade build twine
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build --outdir dist
.\.venv\Scripts\python.exe -m twine check --strict dist/aruco_pose-0.2.0-py3-none-any.whl dist/aruco_pose-0.2.0.tar.gz
.\.venv\Scripts\python.exe -m twine upload --username __token__ dist/aruco_pose-0.2.0-py3-none-any.whl dist/aruco_pose-0.2.0.tar.gz
```

The exact file names prevent accidentally uploading older builds. The initial
wheel and source archive may already be present in `dist/` after release preparation.
If you change code/metadata after building, rebuild and recheck before uploading.

Sign in/create an account at https://pypi.org/ and complete its account requirements
(including verified email and two-factor authentication). Create an API token under
https://pypi.org/manage/account/token/ . A first upload of a new project needs a token
able to create that project; a project-scoped token cannot select a project that
hasn't been created yet. Enter the full token at Twine's password prompt, not as a
command-line argument. Account ownership comes from the token used for this upload.
After project creation, prefer a project-scoped token or Trusted Publishing.

Check https://pypi.org/project/aruco-pose/0.2.0/ after upload. In a separate clean
environment, install `aruco-pose==0.2.0` and check:

```python
from aruco_pose import Tracker
```

Also run `aruco-pose --version` and `aruco-cli --version`. The repository's README
contains the camera-free workflow; an installed package can generate those inputs
with `aruco-pose kit sample --output sample`.

PyPI release files cannot be overwritten under the same filename. If an upload
has already succeeded, do not repeatedly upload modified artifacts as 0.2.0:
choose a new version and rebuild instead. A 404 name check is not a reservation;
the first successful upload determines whether PyPI accepts the project name.

## Optional TestPyPI rehearsal

TestPyPI has separate accounts and tokens. To rehearse the same validated files,
use `twine upload --repository testpypi --username __token__` followed by the two
exact file paths above. A TestPyPI upload does not publish to production PyPI.

## GitHub release and future versions

Once upload is verified, create a GitHub release/tag `v0.2.0` pointing at the tested
commit. A GitHub release does not upload anything to PyPI in this repository.
For later versions update `setup.py` and `aruco_pose/__init__.py` together, rerun
tests, build/check new files and upload those exact filenames.

References: [PyPA packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[PyPI account tokens](https://pypi.org/help/#apitoken),
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
