"""Computer vision engine: template matching, pixel detection, and OCR."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PIL import Image

from .backends.screen import PyAutoGuiScreenBackend, ScreenBackend

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
    """Cross-platform vision engine for GUI automation."""

    def __init__(
        self,
        color_tolerance: int = 3,
        screen_backend: Optional[ScreenBackend] = None,
    ):
        self.color_tolerance = color_tolerance
        self.screen_backend = screen_backend or PyAutoGuiScreenBackend()
        self._template_cache: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def _capture_pil(self, region: Optional[tuple] = None) -> Image.Image:
        return self.screen_backend.screenshot(region=region).convert("RGB")

    @staticmethod
    def _to_pil_image(image) -> Image.Image:
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        if HAS_CV2:
            return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        return Image.fromarray(image).convert("RGB")

    @staticmethod
    def _to_cv_image(image):
        if not HAS_CV2:
            return image
        if isinstance(image, Image.Image):
            return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        return image

    def screenshot(self, region: Optional[tuple] = None):
        """Capture screen (or region) as numpy BGR array, or PIL without cv2."""
        img = self._capture_pil(region)
        if HAS_CV2:
            return self._to_cv_image(img)
        return img

    # ------------------------------------------------------------------
    # Pixel color (cross-platform)
    # ------------------------------------------------------------------

    def get_pixel_color(self, x: int, y: int) -> tuple:
        """Get RGB color at screen coordinates."""
        return self.screen_backend.get_pixel_color(x, y)

    def color_matches(
        self,
        color1: tuple,
        color2: tuple,
        tolerance: Optional[int] = None,
    ) -> bool:
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
        pil_image = self._to_pil_image(image)
        if HAS_CV2:
            cv2.imwrite(str(path), self._to_cv_image(pil_image))
        else:
            pil_image.save(str(path))

    def load_template(self, path: str):
        """Load template image from disk with caching."""
        if path in self._template_cache:
            return self._template_cache[path]
        if HAS_CV2:
            tmpl = cv2.imread(path)
            if tmpl is None:
                raise FileNotFoundError(path)
        else:
            tmpl = Image.open(path).convert("RGB")
        self._template_cache[path] = tmpl
        return tmpl

    def _find_exact_matches(self, screen: Image.Image, template: Image.Image) -> list:
        screen = screen.convert("RGB")
        template = template.convert("RGB")
        screen_width, screen_height = screen.size
        template_width, template_height = template.size

        if template_width > screen_width or template_height > screen_height:
            return []

        template_bytes = template.tobytes()
        screen_pixels = screen.load()
        template_first_pixel = template.getpixel((0, 0))
        matches = []

        for y in range(screen_height - template_height + 1):
            for x in range(screen_width - template_width + 1):
                if screen_pixels[x, y] != template_first_pixel:
                    continue
                candidate = screen.crop((x, y, x + template_width, y + template_height))
                if candidate.tobytes() == template_bytes:
                    matches.append((x, y, template_width, template_height))

        return matches

    def find_on_screen(
        self,
        template,
        confidence: float = 0.8,
        region: Optional[tuple] = None,
    ) -> Optional[tuple]:
        """Find template on screen.

        Returns (x, y, w, h) of best match, or None.
        """
        if HAS_CV2:
            screen = self.screenshot(region)
            template_image = self._to_cv_image(template)
            screen_height, screen_width = screen.shape[:2]
            template_height, template_width = template_image.shape[:2]

            if template_width > screen_width or template_height > screen_height:
                return None

            result = cv2.matchTemplate(screen, template_image, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= confidence:
                x, y = max_loc
                if region:
                    x += region[0]
                    y += region[1]
                return (x, y, template_width, template_height)
            return None

        screen = self._capture_pil(region)
        template_image = self._to_pil_image(template)
        matches = self._find_exact_matches(screen, template_image)
        if not matches:
            return None

        x, y, width, height = matches[0]
        if region:
            x += region[0]
            y += region[1]
        return (x, y, width, height)

    def find_all_on_screen(
        self,
        template,
        confidence: float = 0.8,
        region: Optional[tuple] = None,
    ) -> list:
        """Find all occurrences of template on screen."""
        if HAS_CV2:
            screen = self.screenshot(region)
            template_image = self._to_cv_image(template)
            result = cv2.matchTemplate(screen, template_image, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= confidence)

            template_height, template_width = template_image.shape[:2]
            matches = []
            for pt in zip(*locations[::-1]):
                x, y = int(pt[0]), int(pt[1])
                if region:
                    x += region[0]
                    y += region[1]
                matches.append((x, y, template_width, template_height))

            return self._non_max_suppression(matches, template_width, template_height)

        screen = self._capture_pil(region)
        template_image = self._to_pil_image(template)
        matches = self._find_exact_matches(screen, template_image)
        if not region:
            return matches

        return [
            (x + region[0], y + region[1], width, height)
            for x, y, width, height in matches
        ]

    @staticmethod
    def _non_max_suppression(
        boxes: list,
        width: int,
        height: int,
        overlap_thresh: float = 0.5,
    ) -> list:
        """Remove overlapping bounding boxes."""
        if not boxes:
            return []
        filtered = [boxes[0]]
        for box in boxes[1:]:
            overlap = any(
                abs(box[0] - existing[0]) < width * overlap_thresh
                and abs(box[1] - existing[1]) < height * overlap_thresh
                for existing in filtered
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

        img = self._capture_pil(region)
        if preprocess and HAS_CV2:
            cv_image = self._to_cv_image(img)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            gray = cv2.threshold(
                gray,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )[1]
            return pytesseract.image_to_string(gray).strip()

        return pytesseract.image_to_string(img).strip()

    def read_number(self, region: tuple) -> Optional[float]:
        """Read a number from a screen region using OCR."""
        text = self.read_text(region)
        cleaned = re.sub(r"[^0-9eE.+-]", "", text)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def find_button_by_template(
        self,
        template_path: str,
        confidence: float = 0.8,
    ) -> Optional[tuple]:
        """Find button center coordinates using template matching."""
        tmpl = self.load_template(template_path)
        result = self.find_on_screen(tmpl, confidence)
        if result:
            x, y, width, height = result
            return (x + width // 2, y + height // 2)
        return None

    def find_button_by_color(
        self,
        x: int,
        y: int,
        expected_color: tuple,
        tolerance: Optional[int] = None,
    ) -> bool:
        """Check if button at coordinates has expected color."""
        actual = self.get_pixel_color(x, y)
        return self.color_matches(actual, expected_color, tolerance)
