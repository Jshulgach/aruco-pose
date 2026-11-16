"""Replay controls and opt-in export must work independently of a camera/GUI."""

import csv
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from examples import pose_api_demo as demo


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Capture:
    def __init__(self, frames=2):
        self.frames, self.index, self.rewinds, self.released = frames, 0, 0, False

    def get(self, key):
        return 10.0

    def read(self):
        if self.index >= self.frames:
            return False, None
        self.index += 1
        return True, np.zeros((10, 10, 3), np.uint8)

    def set(self, key, value):
        assert key == cv2.CAP_PROP_POS_FRAMES and value == 0
        self.index = 0
        self.rewinds += 1
        return True

    def release(self):
        self.released = True


class Tracker:
    def __init__(self):
        self.calls = []

    def process(self, frame, timestamp, previous=None):
        self.calls.append((timestamp, previous))
        return SimpleNamespace(
            status="measured",
            to_csv_row=lambda index: {"frame": index, "time_s": timestamp},
        )


def setup_loop(monkeypatch, live=False, frames=2):
    cap, tracker, clock = Capture(frames), Tracker(), Clock()
    monkeypatch.setattr(demo, "open_capture", lambda source: (cap, live))
    monkeypatch.setattr(demo.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(demo.time, "sleep", clock.sleep)
    return cap, tracker, clock


def test_timed_replay_loops_without_creating_files_and_resets_prior(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    cap, tracker, clock = setup_loop(monkeypatch)
    count = demo.run_tracker(tracker, "sample", loop=True, seconds=0.55)
    assert count == 6 and cap.rewinds == 2 and cap.released
    assert list(tmp_path.iterdir()) == []
    np.testing.assert_allclose([t for t, _ in tracker.calls], np.arange(6) / 10)
    assert all(tracker.calls[i][1] is None for i in [0, 2, 4])
    assert clock.now == pytest.approx(0.55)


def test_explicit_csv_and_one_pass(monkeypatch, tmp_path):
    cap, tracker, _ = setup_loop(monkeypatch)
    path = tmp_path / "chosen.csv"
    assert demo.run_tracker(tracker, "sample", csv_path=path) == 2
    with path.open() as stream:
        assert len(list(csv.DictReader(stream))) == 2
    assert cap.rewinds == 0 and cap.released


def test_camera_failure_is_not_looped_and_empty_video_does_not_spin(monkeypatch):
    cap, tracker, _ = setup_loop(monkeypatch, live=True)
    assert demo.run_tracker(tracker, "0", loop=True) == 2
    assert cap.rewinds == 0
    cap, tracker, _ = setup_loop(monkeypatch, frames=0)
    with pytest.raises(ValueError, match="no readable"):
        demo.run_tracker(tracker, "empty", loop=True)
    assert cap.released


def test_ctrl_c_closes_capture(monkeypatch):
    cap, tracker, _ = setup_loop(monkeypatch)
    original = tracker.process

    def interrupt(frame, timestamp, previous=None):
        if tracker.calls:
            raise KeyboardInterrupt
        return original(frame, timestamp, previous)

    tracker.process = interrupt
    assert demo.run_tracker(tracker, "sample", loop=True) == 1
    assert cap.released


def test_window_close_stops_cleanly_even_if_backend_throws(monkeypatch):
    cap, tracker, _ = setup_loop(monkeypatch)
    tracker.camera_matrix, tracker.distortion = np.eye(3), np.zeros(5)
    monkeypatch.setattr(demo, "draw_pose_result", lambda *args: None)
    monkeypatch.setattr(cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(cv2, "waitKey", lambda *args: -1)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)

    def closed(*args):
        raise cv2.error("window no longer exists")

    monkeypatch.setattr(cv2, "getWindowProperty", closed)
    assert demo.run_tracker(tracker, "sample", loop=True, preview=True) == 1
    assert cap.released


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan")])
def test_invalid_duration_fails_before_opening_source(seconds):
    with pytest.raises(ValueError, match="finite and positive"):
        demo.run_tracker(None, "unused", seconds=seconds)


def test_command_writes_nothing_by_default(tmp_path):
    script = Path(demo.__file__).resolve()
    result = subprocess.run(
        [sys.executable, str(script), "--seconds", ".1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "no CSV requested" in result.stdout
    assert list(tmp_path.iterdir()) == []
