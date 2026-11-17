# Public release review - 0.3.0

Review date: 2026-11-17. Distribution: `aruco-pose`; import: `aruco_pose`.
Repository: [Jshulgach/aruco-pose](https://github.com/Jshulgach/aruco-pose).

## Scope and publication

This is a beta toolkit for print/calibrate/track/CSV, rigid-target pose estimation
and optional ROS 2 examples. It includes synthetic replays and printable target
geometry. It is not a physically validated navigation, robot-control or metrology
system. Older experiments are labeled separately from supported starter/API paths.

0.3.0 is prepared for owner-run publication, subject to the final checks below.
CI never uploads to PyPI. Use [the publishing guide](PUBLISHING.md) after checks
pass. The prior audit's local recovery/naming discussion is preserved in Git
history; its alpha verdict and old test counts are not this release's verdict.

## Verification record

Local release checks completed:

- 141 core tests pass, including rectified geometry and decoded-marker regressions.
- Wheel/source build and strict Twine validation pass. Dependency consistency
  (`pip check`) passes. Both artifacts report 0.3.0 and Apache-2.0 metadata.
- An isolated wheel install outside the checkout generates sample inputs,
  calibrates and tracks 120 frames: 110 measured, 10 lost.
- Source-archive inspection finds the changelog, review, ROS scripts/RViz view,
  print PDF and site sources. Legacy footage, GIFs and personal calibration/output
  files are excluded. The wheel exports only the core namespace and metadata.
- Desktop/mobile browser checks cover layout, ROS command copying and both
  synthetic video decoders. The exact packaged README renders with valid UTF-8.
- Limited credential-pattern scan of 129 source/text files finds no matches.
- Independent geometry and public-release review finds no blocking issue in
  rectified transforms, candidates, prior frames, stereo offsets, archive contents,
  public claims or publishing commands. The post-upload module check uses isolated
  Python so it cannot import the checkout instead of the installed wheel.

CI additionally exercises Windows/Linux core tests and real Jazzy message/DDS
tests: raw/rectified/replay input, acquisition stamps, frame direction, nonidentity
R, P distinct from K, stereo offsets, invalid input and clean shutdown. The final
commit's green results remain required before upload.

See [CI](https://github.com/Jshulgach/aruco-pose/actions/workflows/ci.yml) for the
final commit's results. Distribution builds require core and ROS jobs to pass.
[Changelog](../CHANGELOG.md) records compatibility; core API/CSV schemas are unchanged.

## Geometry and time

Raw topics use K/D. Explicit rectified input uses P's left 3x3 and zero distortion,
then restores both pose rotation and translation to original optical axes with
R.T. Candidates are converted too; internal priors stay rectified and reset when
R changes. Stereo P offsets are not camera mounting transforms. Invalid matrices
and unsupported ROI/binning produce invalid status instead of geometry guesses.

ROS topics preserve image acquisition stamps. OpenCV has approximate host
read-completion stamps. Neither proves hardware timestamp accuracy. Consumers
must check status and freshness: buffered TF is not a current measurement.

## Packaging and public surface

- The wheel exports `aruco_pose` and the `aruco-pose`/`aruco-cli` commands, without
  generic `src`/`tools` packages or ROS dependencies.
- Apache-2.0 license and original-project acknowledgement remain. Kit ZIPs include
  the license. Release archives include maintained guides/examples and synthetic
  assets; personal calibration/output files are excluded.
- Showcase footage is synthetic. Legacy camera footage/GIF already in Git history
  is not used on the site or included in release artifacts. This release does
  not remove or certify the privacy of that pre-existing history.
- Public pages distinguish source-release features from the currently published
  PyPI version. ROS examples require the checkout and a separate ROS installation.

## Remaining validation limits

Physical print measurements, assembly tolerance, calibrated hardware capture,
RViz GUI interaction, hardware synchronization and every OS/Python/OpenCV pairing
have not received equivalent physical testing. Synthetic/headless results do not
establish real-world accuracy. Requirements allow Python 3.9+; core CI exercises
3.11 and Jazzy integration exercises system Python 3.12.

Credential-pattern checks and archive inspection are limited safeguards, not a
security certification or exhaustive dependency/license/vulnerability audit.
Resolve blocking review/test findings before upload. The owner's PyPI upload
and post-publication verification remain the final manual steps.
