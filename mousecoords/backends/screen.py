"""Screen backends for live desktop capture and fixture-driven tests."""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

from PIL import Image

Region = Tuple[int, int, int, int]
RGBColor = Tuple[int, int, int]


class ScreenBackend(Protocol):
    """Protocol for screen capture backends."""

    def screenshot(self, region: Optional[Region] = None) -> Image.Image:
        """Return a screenshot as a PIL image."""

    def get_pixel_color(self, x: int, y: int) -> RGBColor:
        """Return the RGB color at the given coordinates."""


def normalize_rgb(pixel) -> RGBColor:
    """Normalize Pillow pixel values to a 3-tuple RGB color."""
    if isinstance(pixel, int):
        return (pixel, pixel, pixel)
    return tuple(pixel[:3])


class PyAutoGuiScreenBackend:
    """Live desktop capture backend backed by pyautogui."""

    @staticmethod
    def _get_pyautogui():
        import pyautogui

        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        return pyautogui

    def screenshot(self, region: Optional[Region] = None) -> Image.Image:
        return self._get_pyautogui().screenshot(region=region)

    def get_pixel_color(self, x: int, y: int) -> RGBColor:
        pixel = self.screenshot(region=(x, y, 1, 1)).getpixel((0, 0))
        return normalize_rgb(pixel)
