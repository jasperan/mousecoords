"""Tests for the screen watcher module."""

import pytest
from unittest.mock import patch, MagicMock, call

from mousecoords.watcher import ScreenWatcher


class TestColorDistance:
    def test_identical_colors(self):
        assert ScreenWatcher.color_distance((0, 0, 0), (0, 0, 0)) == 0.0

    def test_known_distance(self):
        # sqrt(3^2 + 4^2 + 0^2) = 5.0
        assert ScreenWatcher.color_distance((0, 0, 0), (3, 4, 0)) == 5.0

    def test_symmetric(self):
        d1 = ScreenWatcher.color_distance((100, 50, 25), (200, 60, 30))
        d2 = ScreenWatcher.color_distance((200, 60, 30), (100, 50, 25))
        assert d1 == d2

    def test_max_distance(self):
        d = ScreenWatcher.color_distance((0, 0, 0), (255, 255, 255))
        assert d == pytest.approx(441.67, rel=0.01)


class TestWatcherInit:
    def test_defaults(self):
        w = ScreenWatcher(100, 200)
        assert w.x == 100
        assert w.y == 200
        assert w.threshold == 10.0
        assert w.poll_interval == 0.5
        assert w.change_count == 0
        assert w.running is False

    def test_custom_params(self):
        w = ScreenWatcher(50, 60, threshold=20.0, poll_interval=0.1)
        assert w.threshold == 20.0
        assert w.poll_interval == 0.1


class TestCheckOnce:
    @patch("mousecoords.watcher.pyautogui")
    def test_first_call_returns_none(self, mock_pa):
        """First check establishes baseline, returns None."""
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (100, 100, 100, 255)
        mock_pa.screenshot.return_value = fake_img

        w = ScreenWatcher(0, 0)
        result = w.check_once()
        assert result is None
        assert w._last_color == (100, 100, 100)

    @patch("mousecoords.watcher.pyautogui")
    def test_no_change(self, mock_pa):
        """No change when color stays the same."""
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (100, 100, 100, 255)
        mock_pa.screenshot.return_value = fake_img

        w = ScreenWatcher(0, 0, threshold=10.0)
        w.check_once()  # baseline
        result = w.check_once()
        assert result is None
        assert w.change_count == 0

    @patch("mousecoords.watcher.pyautogui")
    def test_detects_change(self, mock_pa):
        """Detects when color changes beyond threshold."""
        fake_img = MagicMock()
        mock_pa.screenshot.return_value = fake_img

        w = ScreenWatcher(0, 0, threshold=10.0)

        # First call: baseline
        fake_img.getpixel.return_value = (100, 100, 100, 255)
        w.check_once()

        # Second call: big change
        fake_img.getpixel.return_value = (200, 200, 200, 255)
        result = w.check_once()
        assert result == (200, 200, 200)
        assert w.change_count == 1

    @patch("mousecoords.watcher.pyautogui")
    def test_callback_fired(self, mock_pa):
        """Callback is called on change detection."""
        fake_img = MagicMock()
        mock_pa.screenshot.return_value = fake_img
        callback = MagicMock()

        w = ScreenWatcher(0, 0, threshold=5.0)
        w.on_change(callback)

        fake_img.getpixel.return_value = (0, 0, 0, 255)
        w.check_once()

        fake_img.getpixel.return_value = (255, 255, 255, 255)
        w.check_once()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == (0, 0, 0)       # old color
        assert args[1] == (255, 255, 255)  # new color

    @patch("mousecoords.watcher.pyautogui")
    def test_history_recorded(self, mock_pa):
        """Changes are recorded in history."""
        fake_img = MagicMock()
        mock_pa.screenshot.return_value = fake_img

        w = ScreenWatcher(0, 0, threshold=5.0)

        fake_img.getpixel.return_value = (0, 0, 0, 255)
        w.check_once()

        fake_img.getpixel.return_value = (255, 0, 0, 255)
        w.check_once()

        assert len(w.history) == 1
        assert w.history[0]["from"] == (0, 0, 0)
        assert w.history[0]["to"] == (255, 0, 0)
