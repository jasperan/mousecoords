"""Computer vision engine: template matching, pixel detection, and OCR."""

from __future__ import annotations

import re
from typing import Optional
from pathlib import Path

import pyautogui

try:
    import numpy as np
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class VisionEngine:
    """Cross-platform vision engine for GUI automation.

    Uses pyautogui screenshots + OpenCV for analysis, replacing
    Windows-only win32gui/gdi32 pixel reads.
    """

    def __init__(self, color_tolerance: int = 3):
        self.color_tolerance = color_tolerance
        self._template_cache: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def screenshot(self, region: Optional[tuple] = None):
        """Capture screen (or region) as numpy BGR array (or PIL if no cv2)."""
        img = pyautogui.screenshot(region=region)
        if HAS_CV2:
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return img

    # ------------------------------------------------------------------
    # Pixel color (cross-platform)
    # ------------------------------------------------------------------

    def get_pixel_color(self, x: int, y: int) -> tuple:
        """Get RGB color at screen coordinates. Works on any OS."""
        img = pyautogui.screenshot(region=(x, y, 1, 1))
        pixel = img.getpixel((0, 0))
        return pixel[:3]

    def color_matches(self, color1: tuple, color2: tuple,
                      tolerance: Optional[int] = None) -> bool:
        """Check if two RGB colors match within tolerance."""
        tol = tolerance if tolerance is not None else self.color_tolerance
        return all(abs(a - b) <= tol for a, b in zip(color1, color2))

    # ------------------------------------------------------------------
    # Template matching
    # ------------------------------------------------------------------

    def capture_template(self, region: tuple):
        """Capture a screen region as a template image."""
        return self.screenshot(region)

    def save_template(self, image, name: str, directory: str = "templates"):
        """Save template image to disk."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        path = Path(directory) / f"{name}.png"
        if HAS_CV2:
            cv2.imwrite(str(path), image)
        else:
            from PIL import Image
            if not isinstance(image, Image.Image):
                image = Image.fromarray(image)
            image.save(str(path))

    def load_template(self, path: str):
        """Load template image from disk with caching."""
        if path in self._template_cache:
            return self._template_cache[path]
        if HAS_CV2:
            tmpl = cv2.imread(path)
        else:
            from PIL import Image
            tmpl = Image.open(path)
        self._template_cache[path] = tmpl
        return tmpl

    def find_on_screen(self, template, confidence: float = 0.8,
                       region: Optional[tuple] = None) -> Optional[tuple]:
        """Find template on screen via OpenCV matchTemplate.

        Returns (x, y, w, h) of best match, or None.
        """
        if not HAS_CV2:
            # Fallback: pyautogui.locate (slower, needs opencv-python for confidence)
            from PIL import Image
            if not isinstance(template, Image.Image):
                template = Image.fromarray(template)
            loc = pyautogui.locate(template, pyautogui.screenshot(region=region))
            return tuple(loc) if loc else None

        screen = self.screenshot(region)
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= confidence:
            h, w = template.shape[:2]
            x, y = max_loc
            if region:
                x += region[0]
                y += region[1]
            return (x, y, w, h)
        return None

    def find_all_on_screen(self, template, confidence: float = 0.8,
                           region: Optional[tuple] = None) -> list:
        """Find all occurrences of template on screen."""
        if not HAS_CV2:
            return []

        screen = self.screenshot(region)
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= confidence)

        h, w = template.shape[:2]
        matches = []
        for pt in zip(*locations[::-1]):
            x, y = int(pt[0]), int(pt[1])
            if region:
                x += region[0]
                y += region[1]
            matches.append((x, y, w, h))

        return self._non_max_suppression(matches, w, h)

    @staticmethod
    def _non_max_suppression(boxes: list, w: int, h: int,
                             overlap_thresh: float = 0.5) -> list:
        """Remove overlapping bounding boxes."""
        if not boxes:
            return []
        filtered = [boxes[0]]
        for box in boxes[1:]:
            overlap = any(
                abs(box[0] - e[0]) < w * overlap_thresh and
                abs(box[1] - e[1]) < h * overlap_thresh
                for e in filtered
            )
            if not overlap:
                filtered.append(box)
        return filtered

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    def read_text(self, region: tuple, preprocess: bool = True) -> str:
        """Read text from a screen region using Tesseract OCR."""
        if not HAS_TESSERACT:
            return ""

        img = self.screenshot(region)
        if preprocess and HAS_CV2:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Adaptive threshold for varied backgrounds
            gray = cv2.threshold(gray, 0, 255,
                                 cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            img = gray

        return pytesseract.image_to_string(img).strip()

    def read_number(self, region: tuple) -> Optional[float]:
        """Read a number from a screen region using OCR."""
        text = self.read_text(region)
        # Clean common OCR artifacts
        cleaned = re.sub(r"[^0-9eE.+-]", "", text)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def find_button_by_template(self, template_path: str,
                                confidence: float = 0.8) -> Optional[tuple]:
        """Find button center coordinates using template matching."""
        tmpl = self.load_template(template_path)
        result = self.find_on_screen(tmpl, confidence)
        if result:
            x, y, w, h = result
            return (x + w // 2, y + h // 2)
        return None

    def find_button_by_color(self, x: int, y: int, expected_color: tuple,
                             tolerance: Optional[int] = None) -> bool:
        """Check if button at coordinates has expected color."""
        actual = self.get_pixel_color(x, y)
        return self.color_matches(actual, expected_color, tolerance)
