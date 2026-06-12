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


def get_pixel_color(x: int, y: int) -> tuple:
    """Get the RGB color at a screen coordinate. Works on any OS."""
    img = capture_screen(region=(x, y, 1, 1))
    return img.getpixel((0, 0))[:3]


def color_matches(color1: tuple, color2: tuple, tolerance: int) -> bool:
    """Check whether two RGB colors match within a per-channel tolerance."""
    return all(abs(a - b) <= tolerance for a, b in zip(color1, color2))
