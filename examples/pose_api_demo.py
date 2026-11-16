"""Direct Python API example, using the same Tracker/PoseResult as `kit track`."""

import argparse
import csv
from contextlib import ExitStack
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2

from aruco_pose import Tracker
from aruco_pose.pose import draw_pose_result
from aruco_pose.starter import CSV_FIELDS, load_calibration, load_model, open_capture


def run_tracker(
    tracker,
    source,
    csv_path=None,
    preview=False,
    extra_draw=None,
    *,
    loop=False,
    seconds=None,
):
    """Run until EOF, a wall-clock limit, Q/Esc/window close, or Ctrl+C.

    Recorded sources repeat when loop=True, at their recorded frame rate. Clear
    the prior on each repeat; timestamps/frame numbers continue increasing.
    CSV output is strictly opt-in. Live camera failures never trigger a replay.
    """
    if seconds is not None and (not math.isfinite(seconds) or seconds <= 0):
        raise ValueError("seconds must be finite and positive")
    cap, live = open_capture(source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps <= 0:
        cap.release()
        raise ValueError("Video needs a valid frame rate")
    previous = None
    index = 0
    cycle_frames = 0
    start = time.monotonic()
    deadline = start + seconds if seconds is not None else math.inf
    try:
        with ExitStack() as stack:
            writer = None
            if csv_path is not None:
                csv_path = Path(csv_path)
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                stream = stack.enter_context(
                    csv_path.open("w", newline="", encoding="utf-8")
                )
                writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
                writer.writeheader()
            while time.monotonic() < deadline:
                ok, frame = cap.read()
                if not ok:
                    if loop and not live and cycle_frames:
                        if not cap.set(cv2.CAP_PROP_POS_FRAMES, 0):
                            cap.release()
                            cap, _ = open_capture(source)
                        cycle_frames = 0
                        previous = None
                        continue
                    break
                timestamp = time.monotonic() - start if live else index / fps
                result = tracker.process(frame, timestamp, previous=previous)
                if writer is not None:
                    writer.writerow(result.to_csv_row(index))
                if result.status == "measured":
                    previous = result
                if preview:
                    draw_pose_result(
                        frame, result, tracker.camera_matrix, tracker.distortion
                    )
                    if extra_draw is not None and result.pose is not None:
                        extra_draw(frame, result.pose)
                    cv2.imshow("Pose API example", frame)
                index += 1
                cycle_frames += 1
                # Interactive/timed replay runs at playback speed rather than
                # consuming CPU as fast as possible. Poll controls while waiting.
                target = (
                    min(start + index / fps, deadline)
                    if not live and (preview or loop or seconds is not None)
                    else time.monotonic()
                )
                stop = False
                while True:
                    if preview:
                        key = cv2.waitKey(1) & 0xFF
                        try:
                            visible = cv2.getWindowProperty(
                                "Pose API example", cv2.WND_PROP_VISIBLE
                            )
                        except cv2.error:
                            visible = 0
                        if key in (ord("q"), 27) or visible < 1:
                            stop = True
                            break
                    remaining = target - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(remaining, 0.02))
                if stop:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()
    if not index:
        raise ValueError("Source contains no readable frames")
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT / "assets/starter/tracking.mp4"))
    parser.add_argument(
        "--model", type=Path, default=ROOT / "assets/starter/board.json"
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=ROOT / "assets/starter/reference_camera.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional CSV destination; no data file is written by default",
    )
    parser.add_argument("--preview", action="store_true")
    parser.add_argument(
        "--seconds",
        type=float,
        help="Stop after this many wall-clock seconds (default: unlimited)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Stop at recorded-video EOF instead of looping",
    )
    args = parser.parse_args()
    if args.seconds is not None and (
        not math.isfinite(args.seconds) or args.seconds <= 0
    ):
        parser.error("--seconds must be finite and positive")
    calibration, matrix, distortion = load_calibration(args.calibration)
    tracker = Tracker(
        load_model(args.model),
        matrix,
        distortion,
        image_size=(calibration["image_width"], calibration["image_height"]),
    )
    count = run_tracker(
        tracker,
        args.source,
        args.csv,
        args.preview,
        loop=not args.once,
        seconds=args.seconds,
    )
    if args.csv is not None:
        print(f"Wrote {count} PoseResult rows to {args.csv}")
    else:
        print(f"Processed {count} frames; no CSV requested.")


if __name__ == "__main__":
    main()
