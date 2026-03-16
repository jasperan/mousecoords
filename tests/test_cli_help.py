from subprocess import run
import os
import sys


def test_help_works_without_display():
    env = dict(os.environ)
    env.pop("DISPLAY", None)
    result = run(
        [sys.executable, "-m", "mousecoords.cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "studio" in result.stdout
