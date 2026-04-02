"""Tests for the vision engine (color matching, NMS, etc.)."""

import pytest

from mousecoords.vision import VisionEngine


class TestColorMatching:
    def test_exact_match(self):
        v = VisionEngine(color_tolerance=0)
        assert v.color_matches((255, 128, 0), (255, 128, 0)) is True

    def test_within_tolerance(self):
        v = VisionEngine(color_tolerance=5)
        assert v.color_matches((100, 100, 100), (103, 97, 102)) is True

    def test_outside_tolerance(self):
        v = VisionEngine(color_tolerance=3)
        assert v.color_matches((100, 100, 100), (110, 100, 100)) is False

    def test_custom_tolerance(self):
        v = VisionEngine(color_tolerance=0)
        assert v.color_matches((100, 100, 100), (105, 100, 100),
                               tolerance=10) is True

    def test_zero_tolerance(self):
        v = VisionEngine(color_tolerance=0)
        assert v.color_matches((0, 0, 0), (1, 0, 0)) is False


class TestNonMaxSuppression:
    def test_no_boxes(self):
        assert VisionEngine._non_max_suppression([], 10, 10) == []

    def test_single_box(self):
        boxes = [(100, 200, 50, 50)]
        result = VisionEngine._non_max_suppression(boxes, 50, 50)
        assert len(result) == 1

    def test_overlapping_boxes(self):
        boxes = [
            (100, 200, 50, 50),
            (105, 205, 50, 50),  # overlaps with first
            (500, 500, 50, 50),  # far away
        ]
        result = VisionEngine._non_max_suppression(boxes, 50, 50)
        assert len(result) == 2
        assert (500, 500, 50, 50) in result

    def test_non_overlapping_boxes(self):
        boxes = [
            (0, 0, 50, 50),
            (200, 200, 50, 50),
            (400, 400, 50, 50),
        ]
        result = VisionEngine._non_max_suppression(boxes, 50, 50)
        assert len(result) == 3


class TestVisionEngineFlags:
    def test_has_cv2_flag(self):
        from mousecoords.vision import HAS_CV2
        assert isinstance(HAS_CV2, bool)

    def test_has_tesseract_flag(self):
        from mousecoords.vision import HAS_TESSERACT
        assert isinstance(HAS_TESSERACT, bool)
