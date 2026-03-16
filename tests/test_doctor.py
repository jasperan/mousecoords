from subprocess import run
import os
import sys

from mousecoords.doctor import collect_diagnostics


EXPECTED_CHECKS = {
    "display",
    "screenshot",
    "ocr_import",
    "tkinter_import",
    "rich_import",
}


def test_collect_diagnostics_reports_expected_checks():
    diagnostics = collect_diagnostics()

    assert EXPECTED_CHECKS <= diagnostics.keys()
    for name in EXPECTED_CHECKS:
        check = diagnostics[name]
        assert isinstance(check["ok"], bool)
        assert isinstance(check["detail"], str)
        assert check["detail"]


def test_doctor_command_runs_without_display():
    env = dict(os.environ)
    env.pop("DISPLAY", None)

    result = run(
        [sys.executable, "-m", "mousecoords.cli", "doctor"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "mousecoords doctor" in result.stdout
    assert "display" in result.stdout.lower()
    assert "screenshot" in result.stdout.lower()
