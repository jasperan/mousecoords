"""Shared fixtures for mousecoords tests.

All tests run headless (no display) by mocking pyautogui's X11 deps.
This conftest intercepts Xlib.display.Display AND mouseinfo before
pyautogui tries to connect, so tests work on any headless server/CI
without xvfb-run.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# ---------- Headless guard ----------
# pyautogui on Linux does two things at import time that need a display:
#   1. mouseinfo tries Xlib.display.Display(DISPLAY)
#   2. _pyautogui_x11 tries Xlib.display.Display(DISPLAY)
# We mock both so tests collect without an X server.

if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

# Mock Xlib.display.Display to avoid ConnectionRefusedError
_mock_xlib_display = MagicMock()
_mock_xlib = MagicMock()
_mock_xlib.display.Display.return_value = _mock_xlib_display
sys.modules.setdefault("Xlib", _mock_xlib)
sys.modules.setdefault("Xlib.display", _mock_xlib.display)
sys.modules.setdefault("Xlib.X", MagicMock())
sys.modules.setdefault("Xlib.ext", MagicMock())
sys.modules.setdefault("Xlib.ext.xtest", MagicMock())
sys.modules.setdefault("Xlib.XK", MagicMock())
sys.modules.setdefault("Xlib.protocol", MagicMock())
sys.modules.setdefault("Xlib.protocol.event", MagicMock())

# Mock mouseinfo (pyautogui dep that also hits X11)
sys.modules.setdefault("mouseinfo", MagicMock())

# ---------- Now safe to import ----------
import pytest
from unittest.mock import patch
from pathlib import Path

from mousecoords.config import (
    Profile, ButtonConfig, StateConfig, get_default_profile,
)


@pytest.fixture
def sample_profile():
    """A minimal two-state profile for testing."""
    return Profile(
        name="test_game",
        game="Test Game",
        resolution=(1920, 1080),
        poll_interval=0.1,
        color_tolerance=5,
        buttons=[
            ButtonConfig("Attack", 100, 200, (255, 0, 0),
                         cooldown=0.5, priority=True),
            ButtonConfig("Heal", 300, 400, (0, 255, 0), cooldown=1.0),
            ButtonConfig("Shield", 500, 600, (0, 0, 255), cooldown=2.0),
        ],
        states=[
            StateConfig(
                name="combat",
                monitor_buttons=["Attack", "Heal", "Shield"],
                transitions={"Shield": "defend"},
                max_actions={"Attack": 5},
            ),
            StateConfig(
                name="defend",
                monitor_buttons=["Shield", "Heal"],
                transitions={"Heal": "combat"},
            ),
        ],
        ocr_regions={"health": (10, 20, 100, 30)},
    )


@pytest.fixture
def default_profile():
    """The built-in Antimatter Dimensions profile."""
    return get_default_profile()


@pytest.fixture
def tmp_profile_dir(tmp_path):
    """A temporary directory for profile I/O tests."""
    return tmp_path / "profiles"


@pytest.fixture
def mock_pyautogui():
    """Mock pyautogui for headless testing."""
    with patch("pyautogui.screenshot") as mock_ss, \
         patch("pyautogui.position", return_value=(960, 540)), \
         patch("pyautogui.click"), \
         patch("pyautogui.moveTo"), \
         patch("pyautogui.scroll"), \
         patch("pyautogui.press"):
        # Return a fake 1x1 image
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (128, 64, 32, 255)
        mock_ss.return_value = fake_img
        yield mock_ss
