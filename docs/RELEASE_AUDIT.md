# Public-release audit - 2026-11-16

## Verdict

The supported starter/API path is a tested alpha candidate. Do not describe the
entire legacy collection as production-ready or publish a stable PyPI release yet.
At audit time the existing GitHub repository was already public and the new
features were local. The subsequent release-preparation change renames the
repository to `Jshulgach/aruco-pose` and adds CI. Package uploads remain manual;
see [publishing instructions](PUBLISHING.md).

## Naming follow-up (completed)

The chosen distribution is now `aruco-pose`; the import namespace is `aruco_pose`.
The generic namespace finding below is resolved. Both `aruco-pose` and the legacy
`aruco-cli` command are supplied by the same module. The repository has also been renamed to `Jshulgach/aruco-pose`;
no registry publication was performed by the assistant. See [package migration](PACKAGE_MIGRATION.md).
The preliminary shortlist below records the audit's earlier naming discussion.

## Verified

- **81 tests pass without warnings**, including formerly false-passing installation
  checks, all pose/geometry regressions, demo controls and legacy fixes.
- Built a wheel, installed it into a separate target directory, changed working
  directory and used isolated Python. Verified project modules loaded from that
  installed wheel, not the editable checkout. Generated samples, calibrated their
  camera and tracked/exported 120 frames: 110 measured, 10 lost.
- Undefined-name checks across `src`, `tools` and `examples` pass. Installed
  dependency consistency (`pip check`) passes.
- A credential-pattern scan over 17 local Git revisions (including stash history)
  found zero matches for the checked private-key/AWS/GitHub/OpenAI token patterns.
  This is a limited pattern scan, not proof of no secrets or a full security audit.
- Existing Apache-2.0 LICENSE retained. Metadata, README and synthetic sample
  provenance now agree with it; no relicensing was performed.

## Findings corrected

| Finding | Repair |
| --- | --- |
| Package metadata and sample docs incorrectly claimed MIT despite the Apache LICENSE. | Corrected labels and restored the original inspiration acknowledgement. |
| Python module reported 2.0.0 while package/CLI reported 0.2.0. | Aligned module version to 0.2.0. A new release version should be chosen before tagging. |
| Seven installation tests returned booleans, so failed checks could pass pytest. | Pytest wrappers now assert results; returning non-None is treated as an error. |
| Windows logging verification deleted an open log file; reconfiguration also discarded handlers without closing them. | Close/remove handlers properly; test cleanup releases handles. |
| Visualization test created a plot at collection time. | Moved plotting behind its explicit main entry point. |
| Legacy helpers referenced undefined marker maps and transformation functions. | Routed compatibility paths through the shared pose API and added known-pose regressions. |
| Legacy calibration used a removed root utils import and incomplete settings. | Fixed package import and complete config conversion; headless capture now starts. |
| Missing-image calibration error referenced an undefined variable. | Error now reports the configured directory. |
| Standalone marker PNG generation used a removed OpenCV API. | Updated generation and tested actual marker detection from its output. |
| Legacy tracking source option inferred integer-only input. | Accepts camera indexes or video paths as documented. |
| Build backend wasn't declared and package discovery was too broad. | Added pyproject build requirements and limited discovery to maintained package namespaces. |
| Historical docs advertised unverified performance and obsolete commands. | Clearly labeled them historical; current README/API guide define supported behavior. |
| Gitignore suppressed all YAML/text files, hiding potential source/config additions. | Removed those broad rules; retained calibration/output ignores and added local log/env/desktop metadata rules. |

## Demo behavior requested alongside the audit

`examples/pose_api_demo.py` now writes no data file unless `--csv PATH` is supplied.
It loops recorded video at playback speed until stopped; `--seconds N` applies a
positive finite wall-clock limit, and `--once` stops at the first EOF. Q, Escape,
window close and Ctrl+C clean up capture/writer resources. Video timestamps/frame
indices increase across repeats; the pose prior is cleared on each restart. Empty
videos and failed live cameras never spin in a restart loop.

```powershell
python examples/pose_api_demo.py --preview
python examples/pose_api_demo.py --preview --seconds 20
python examples/pose_api_demo.py --preview --seconds 20 --csv output/poses.csv
```

## Remaining release decisions and checks

1. **Media/privacy review.** The pre-existing 25 MB raw MP4 contains a visible face
   and workplace background in sampled frames. Review the entire clip and the old
   GIF before redistributing them in a renamed/repackaged release. They are already
   in the public repository and were not removed or altered. The new synthetic
   samples contain no recorded people/workplace footage.
2. **Public namespace migration: resolved in the naming follow-up.** The wheel now
   installs only `aruco_pose`. The previous generic `src` and `tools` package exports
   have been removed; the old CLI spelling remains an alias.
3. **Limit the release promise.** Starter/API paths are supported; monolithic legacy
   experiments and every older CLI mode have not received equivalent runtime/GUI
   validation. Their docs are labeled accordingly. No real-world speed, subpixel,
   navigation safety or positional accuracy guarantee is justified by synthetic data.
4. **Physical and platform validation.** Print and measure targets; run calibrated
   cameras; exercise GUI closing on actual Windows/Linux/macOS backends. Automated
   tests cover behavior with simulated controls and headless videos. Add CI across
   supported Python/OpenCV/platform combinations before a stable release.
5. **Prepare release scope.** Review the substantial uncommitted recovery/starter/API
   changes; keep local recovery notes out of public release docs if unwanted; remove
   tracked desktop.ini if desired; select release version and changelog. Stash retained.
6. **Dependency/security scope.** Dependency consistency was checked, but no external
   vulnerability-database, full dependency-license or exhaustive source security scan
   was performed. No findings-free certification is implied.

## Preliminary naming check

Checked on 2026-11-16. GitHub names are scoped by owner; a similarly named repo
elsewhere does not alone prevent an owner-scoped repository name. Python import
names and PyPI distribution names are separate choices.

| Name | Observed result | Assessment |
| --- | --- | --- |
| ArUco_Pose_Estimation / aruco-pose-estimation | Your existing GitHub repo is public; the exact PyPI JSON endpoint returned 404. Many related projects use similar descriptive wording. | Can keep the repo name; weak differentiation and the generic Python namespace should still change. |
| FiducialKit / fiducialkit | PyPI JSON endpoint returned 404; no exact indexed GitHub hit found in the preliminary search. | Best provisional shortlist choice for print/calibration/rigid-target workflows. |
| MarkerForge / markerforge | PyPI JSON endpoint returned 404; broader web uses exist. | More suggestive of marker generation than pose tracking; secondary choice. |
| PoseKit / posekit | Existing `anibali/posekit` repository and other uses found, even though the PyPI JSON lookup returned 404. | Avoid to reduce confusion. |

404 means no currently returned public project at that endpoint, not guaranteed
registrability: names may be reserved or otherwise unavailable. GitHub API search
could not be verified from this environment due certificate validation, so web
index searches are preliminary. No name/domain/trademark clearance or reservation
was performed. Recheck the chosen name directly before renaming/publishing.

Sources: [existing repository](https://github.com/Jshulgach/aruco-pose),
[existing PoseKit](https://github.com/anibali/posekit), and direct HTTPS requests to
`https://pypi.org/pypi/{name}/json` for the listed normalized distribution names.
