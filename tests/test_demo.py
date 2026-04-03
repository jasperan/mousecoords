"""Tests for the built-in demo target and smoke workflow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mousecoords.demo import create_demo_project


XVFB_RUN = shutil.which("xvfb-run")


def test_create_demo_project(tmp_path):
    profile_path = create_demo_project(tmp_path / "demo_pack", name="demo_pack")

    assert profile_path.exists()
    assert profile_path.name == "profile.yaml"
    assert (tmp_path / "demo_pack" / "assets" / "templates" / ".gitkeep").exists()
    assert (tmp_path / "demo_pack" / "assets" / "reference" / ".gitkeep").exists()


@pytest.mark.skipif(XVFB_RUN is None, reason="xvfb-run not available")
def test_demo_launch_writes_ready_and_state_files(tmp_path):
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    state_file = tmp_path / "state.json"
    ready_file = tmp_path / "ready.txt"

    result = subprocess.run(
        [
            XVFB_RUN,
            "-a",
            sys.executable,
            "-m",
            "mousecoords",
            "demo",
            "launch",
            "--state-file",
            str(state_file),
            "--ready-file",
            str(ready_file),
            "--duration",
            "0.4",
        ],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert ready_file.exists()
    payload = json.loads(state_file.read_text())
    assert payload["title"] == "mousecoords Demo Lab"
    assert payload["total_clicks"] == 0


@pytest.mark.skipif(XVFB_RUN is None, reason="xvfb-run not available")
def test_demo_smoke_succeeds_end_to_end():
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)

    result = subprocess.run(
        [
            XVFB_RUN,
            "-a",
            sys.executable,
            "-m",
            "mousecoords",
            "demo",
            "smoke",
            "--json",
        ],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["automation"]["stats"]["Total Clicks"] >= 3
    assert payload["demo_state"]["total_clicks"] >= 3


@pytest.mark.skipif(XVFB_RUN is None, reason="xvfb-run not available")
def test_demo_smoke_can_emit_debug_bundle(tmp_path):
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    bundle_dir = tmp_path / "bundles"

    smoke = subprocess.run(
        [
            XVFB_RUN,
            "-a",
            sys.executable,
            "-m",
            "mousecoords",
            "demo",
            "smoke",
            "--debug",
            "--bundle-dir",
            str(bundle_dir),
            "--json",
        ],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert smoke.returncode == 0, smoke.stderr
    payload = json.loads(smoke.stdout)
    bundle_path = payload["automation"]["bundle_path"]
    assert Path(bundle_path).exists()

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "mousecoords",
            "bundle",
            "inspect",
            bundle_path,
            "--json",
        ],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    bundle_payload = json.loads(inspect.stdout)
    assert bundle_payload["manifest"]["profile"] in {"desktop_demo", "demo_lab"}
    assert "summary.json" in bundle_payload["files"]


@pytest.mark.skipif(XVFB_RUN is None, reason="xvfb-run not available")
def test_profile_inspect_detects_demo_buttons_end_to_end(tmp_path):
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    state_file = tmp_path / "state.json"
    ready_file = tmp_path / "ready.txt"

    command = f"""
set -e
python -m mousecoords demo launch --state-file "{state_file}" --ready-file "{ready_file}" --duration 3 &
demo_pid=$!
for _ in $(seq 1 60); do
  [ -f "{ready_file}" ] && break
  sleep 0.05
done
[ -f "{ready_file}" ]
python -m mousecoords profile inspect profiles/desktop_demo --json --require-all
wait "$demo_pid" || true
"""
    result = subprocess.run(
        [XVFB_RUN, "-a", "bash", "-lc", command],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["detected_count"] == payload["button_count"] == 3
    assert {button["name"] for button in payload["buttons"]} == {"Harvest", "Boost", "Reset"}
