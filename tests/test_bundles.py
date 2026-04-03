"""Tests for debug bundle utilities."""

from __future__ import annotations

import json
from zipfile import ZipFile
from unittest.mock import MagicMock, patch

from mousecoords.bundles import (
    capture_bundle_screenshot,
    collect_runtime_bundle_inputs,
    create_bundle,
    inspect_bundle,
)


def test_create_bundle_contains_expected_files(tmp_path):
    screenshot = tmp_path / "screen.png"
    screenshot.write_bytes(b"png")
    profile = tmp_path / "profile.yaml"
    profile.write_text("name: demo\n")
    attachment = tmp_path / "notes.txt"
    attachment.write_text("hello\n")

    bundle = create_bundle(
        tmp_path / "run.zip",
        {"profile": "demo", "dry_run": True},
        json_payloads={"summary.json": {"iterations": 1}},
        text_payloads={"notes/info.txt": "bundle notes"},
        attachments=[("attachments/notes.txt", attachment)],
        profile_path=profile,
        doctor_results=[{"name": "display", "passed": True}],
        stats={"Total Clicks": 0},
        actions=[{"button_name": "Start", "executed": False}],
        screenshots=[screenshot],
    )

    assert bundle.exists()
    with ZipFile(bundle) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "profile.yaml" in names
        assert "doctor.json" in names
        assert "stats.json" in names
        assert "actions.json" in names
        assert "summary.json" in names
        assert "notes/info.txt" in names
        assert "attachments/notes.txt" in names
        assert "screenshots/screen.png" in names


def test_inspect_bundle_reads_manifest_and_files(tmp_path):
    bundle = create_bundle(tmp_path / "run.zip", {"profile": "demo"})
    info = inspect_bundle(bundle)
    assert info["manifest"]["profile"] == "demo"
    assert "manifest.json" in info["files"]


def test_capture_bundle_screenshot_writes_file(tmp_path):
    fake_image = MagicMock()
    with patch("mousecoords.bundles.capture_screen", return_value=fake_image):
        output = capture_bundle_screenshot(tmp_path, "snapshot.png")
    assert output == tmp_path / "snapshot.png"
    fake_image.save.assert_called_once_with(tmp_path / "snapshot.png")


def test_collect_runtime_bundle_inputs_uses_summary_shape(sample_profile):
    result = MagicMock()
    result.command = "run"
    result.dry_run = True
    result.final_phase = "farming"
    result.iterations = 2
    result.errors = ["boom"]
    result.stats = {"Total Clicks": 0}
    result.actions = [{"button_name": "Attack", "simulated": True}]
    result.to_dict.return_value = {"command": "run", "iterations": 2}

    with patch("mousecoords.bundles.collect_diagnostics", return_value=[]):
        with patch("mousecoords.bundles.capture_bundle_screenshot", return_value=None):
            inputs = collect_runtime_bundle_inputs(profile=sample_profile, result=result)

    assert inputs["manifest"]["command"] == "run"
    assert inputs["manifest"]["iterations"] == 2
    assert inputs["manifest"]["error_count"] == 1
    assert inputs["actions"] == [{"button_name": "Attack", "simulated": True}]
    assert inputs["json_payloads"]["summary.json"]["iterations"] == 2
