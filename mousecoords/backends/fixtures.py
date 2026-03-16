"""Fixture-backed screen capture helpers for tests."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PIL import Image

from .screen import Region, normalize_rgb


class FixtureScreenBackend:
    """Read screenshots from a static image instead of the live desktop."""

    def __init__(self, image: Union[str, Path, Image.Image]):
        if isinstance(image, Image.Image):
            self._image = image.convert("RGB")
        else:
            self._image = Image.open(image).convert("RGB")

    def screenshot(self, region: Optional[Region] = None) -> Image.Image:
        image = self._image
        if region is not None:
            x, y, width, height = region
            image = image.crop((x, y, x + width, y + height))
        return image.copy()

    def get_pixel_color(self, x: int, y: int):
        return normalize_rgb(self._image.getpixel((x, y)))
