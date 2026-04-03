"""Screenshot helpers with a Pillow fallback for headless/Xvfb sessions."""

from __future__ import annotations

from typing import Optional

try:
    from PIL import ImageGrab
    HAS_IMAGEGRAB = True
except ImportError:
    HAS_IMAGEGRAB = False
    ImageGrab = None


def capture_screen(region: Optional[tuple] = None):
    """Capture the screen using Pillow ImageGrab, then pyautogui as fallback."""
    if HAS_IMAGEGRAB:
        bbox = None
        if region is not None:
            x, y, width, height = region
            bbox = (x, y, x + width, y + height)
        try:
            return ImageGrab.grab(bbox=bbox)
        except Exception:
            pass

    import pyautogui
    return pyautogui.screenshot(region=region)


def capture_screenshot(region: Optional[tuple] = None):
    """Backward-compatible alias for older in-progress refactors."""
    return capture_screen(region=region)
