"""Tests for screenshot fallbacks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mousecoords.screen import capture_screen


def test_capture_screen_prefers_imagegrab():
    fake_image = MagicMock()
    with patch("PIL.ImageGrab.grab", return_value=fake_image) as mock_grab:
        result = capture_screen(region=(1, 2, 3, 4))
    assert result is fake_image
    mock_grab.assert_called_once_with(bbox=(1, 2, 4, 6))


def test_capture_screen_falls_back_to_pyautogui():
    fake_image = MagicMock()
    with patch("PIL.ImageGrab.grab", side_effect=RuntimeError("missing backend")):
        with patch("pyautogui.screenshot", return_value=fake_image) as mock_shot:
            result = capture_screen(region=(10, 20, 30, 40))
    assert result is fake_image
    mock_shot.assert_called_once_with(region=(10, 20, 30, 40))
