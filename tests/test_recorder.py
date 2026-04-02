"""Tests for the macro recorder and playback system."""

import json
import pytest
from unittest.mock import patch, MagicMock

from mousecoords.recorder import (
    MacroRecorder, Event, EventType,
)


class TestEvent:
    def test_to_dict_roundtrip(self):
        e = Event(
            type=EventType.MOUSE_CLICK,
            timestamp=1.5,
            x=100, y=200,
            button="left",
            pressed=True,
        )
        d = e.to_dict()
        restored = Event.from_dict(d)
        assert restored.type == EventType.MOUSE_CLICK
        assert restored.x == 100
        assert restored.y == 200
        assert restored.button == "left"
        assert restored.pressed is True
        assert restored.timestamp == 1.5

    def test_to_dict_strips_none(self):
        e = Event(type=EventType.KEY_PRESS, timestamp=0.0, key="a", pressed=True)
        d = e.to_dict()
        assert "x" not in d
        assert "dy" not in d
        assert "check_color" not in d

    def test_condition_event_roundtrip(self):
        e = Event(
            type=EventType.CONDITION,
            timestamp=2.0,
            x=50, y=60,
            check_color=(255, 0, 0),
            color_tolerance=5,
        )
        d = e.to_dict()
        restored = Event.from_dict(d)
        assert restored.type == EventType.CONDITION
        assert restored.check_color == (255, 0, 0)
        assert restored.color_tolerance == 5

    def test_wait_event(self):
        e = Event(type=EventType.WAIT, timestamp=3.0)
        d = e.to_dict()
        assert d["type"] == "wait"
        restored = Event.from_dict(d)
        assert restored.type == EventType.WAIT


class TestMacroRecorderProgrammatic:
    def test_add_click(self):
        r = MacroRecorder()
        r.add_click(100, 200, delay=0.5)
        assert len(r.events) == 1
        assert r.events[0].type == EventType.MOUSE_CLICK
        assert r.events[0].x == 100
        assert r.events[0].timestamp == 0.5

    def test_add_wait(self):
        r = MacroRecorder()
        r.add_click(0, 0)
        r.add_wait(2.0)
        assert len(r.events) == 2
        assert r.events[1].type == EventType.WAIT
        # Timestamp should be previous + delay
        assert r.events[1].timestamp == 2.0

    def test_add_key(self):
        r = MacroRecorder()
        r.add_key("enter", delay=1.0)
        assert r.events[0].type == EventType.KEY_PRESS
        assert r.events[0].key == "enter"

    def test_add_condition(self):
        r = MacroRecorder()
        r.add_condition(50, 60, (255, 0, 0), tolerance=10)
        assert r.events[0].type == EventType.CONDITION
        assert r.events[0].check_color == (255, 0, 0)
        assert r.events[0].color_tolerance == 10

    def test_chained_timestamps(self):
        r = MacroRecorder()
        r.add_click(0, 0, delay=1.0)
        r.add_wait(2.0)
        r.add_click(10, 10, delay=0.5)
        # 1.0, 3.0, 3.5
        assert r.events[0].timestamp == 1.0
        assert r.events[1].timestamp == 3.0
        assert r.events[2].timestamp == 3.5


class TestMacroPersistence:
    def test_save_load(self, tmp_path):
        r = MacroRecorder()
        r.add_click(100, 200, delay=0.5)
        r.add_key("space", delay=1.0)
        r.add_condition(50, 60, (255, 0, 0))

        path = str(tmp_path / "test_macro.json")
        r.save(path)

        r2 = MacroRecorder()
        r2.load(path)
        assert len(r2.events) == 3
        assert r2.events[0].type == EventType.MOUSE_CLICK
        assert r2.events[1].type == EventType.KEY_PRESS
        assert r2.events[2].type == EventType.CONDITION
        assert r2.events[2].check_color == (255, 0, 0)

    def test_save_creates_directory(self, tmp_path):
        r = MacroRecorder()
        r.add_click(0, 0)
        path = str(tmp_path / "deep" / "macro.json")
        r.save(path)
        with open(path) as f:
            data = json.load(f)
        assert data["version"] == "2.0"
        assert data["event_count"] == 1

    def test_empty_save(self, tmp_path):
        r = MacroRecorder()
        path = str(tmp_path / "empty.json")
        r.save(path)
        with open(path) as f:
            data = json.load(f)
        assert data["event_count"] == 0
        assert data["duration"] == 0


class TestConditionPlayback:
    @patch("mousecoords.recorder.pyautogui")
    def test_condition_met_immediately(self, mock_pa):
        """Condition passes when pixel color matches."""
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (255, 0, 0, 255)
        mock_pa.screenshot.return_value = fake_img

        r = MacroRecorder()
        event = Event(
            type=EventType.CONDITION,
            timestamp=0,
            x=50, y=60,
            check_color=(255, 0, 0),
            color_tolerance=3,
        )
        # Should not raise or hang
        r._wait_for_condition(event, timeout=1.0)

    @patch("mousecoords.recorder.pyautogui")
    def test_condition_timeout(self, mock_pa):
        """Condition times out when color never matches."""
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (0, 0, 0, 255)  # wrong color
        mock_pa.screenshot.return_value = fake_img

        r = MacroRecorder()
        event = Event(
            type=EventType.CONDITION,
            timestamp=0,
            x=50, y=60,
            check_color=(255, 0, 0),
            color_tolerance=3,
        )
        # Should return after timeout without error
        import time
        start = time.time()
        r._wait_for_condition(event, timeout=0.3)
        elapsed = time.time() - start
        assert elapsed >= 0.25  # respected the timeout

    @patch("mousecoords.recorder.pyautogui")
    def test_playback_executes_condition(self, mock_pa):
        """Full playback handles CONDITION events."""
        fake_img = MagicMock()
        fake_img.getpixel.return_value = (255, 0, 0, 255)
        mock_pa.screenshot.return_value = fake_img

        r = MacroRecorder()
        r.add_condition(50, 60, (255, 0, 0))
        r.add_click(100, 200, delay=0.1)
        r.play(speed=10.0)
        mock_pa.click.assert_called_once_with(100, 200, _pause=False)
