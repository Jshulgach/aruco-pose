"""Installed metadata and all CLI entry points must use the renamed namespace."""

from importlib.metadata import distribution
from pathlib import Path
import os
import subprocess
import sys
import sysconfig

import pytest

import aruco_pose


def test_distribution_and_entry_points():
    package = distribution("aruco-pose")
    assert package.metadata["Name"] == "aruco-pose"
    assert package.version == aruco_pose.__version__
    entry_points = {
        e.name: e.value for e in package.entry_points if e.group == "console_scripts"
    }
    assert entry_points == {
        "aruco-pose": "aruco_pose.cli:cli",
        "aruco-cli": "aruco_pose.cli:cli",
    }


@pytest.mark.parametrize("name", ["aruco-pose", "aruco-cli"])
def test_installed_commands_work_outside_checkout(name, tmp_path):
    executable = Path(sysconfig.get_path("scripts")) / (
        name + (".exe" if os.name == "nt" else "")
    )
    result = subprocess.run(
        [str(executable), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert aruco_pose.__version__ in result.stdout


def test_module_entry_point_outside_checkout(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-m", "aruco_pose", "kit", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "calibrate" in result.stdout and "track" in result.stdout


def test_repository_cli_wrapper_still_works(tmp_path):
    wrapper = Path(__file__).resolve().parents[1] / "tools/cli.py"
    result = subprocess.run(
        [sys.executable, str(wrapper), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert aruco_pose.__version__ in result.stdout
