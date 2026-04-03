"""Tests for the shared automation runtime."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

from mousecoords.runtime import run_automation_session


def _fake_vision(*, detected: bool = True):
    vision = MagicMock()
    vision.find_button_by_color.return_value = detected
    vision.find_button_by_template.return_value = (111, 222) if detected else None
    vision.read_number.return_value = None
    return vision


def _fake_pyautogui():
    return SimpleNamespace(FAILSAFE=True, click=MagicMock())


def test_run_session_dry_run_records_actions_without_clicking(sample_profile):
    vision = _fake_vision()
    pyautogui = _fake_pyautogui()

    result = run_automation_session(
        profile=sample_profile,
        vision=vision,
        pyautogui=pyautogui,
        shutdown_event=Event(),
        mode="Automation Run",
        dry_run=True,
        once=True,
        render_output=False,
        simple=True,
    )

    pyautogui.click.assert_not_called()
    assert result.dry_run is True
    assert result.cycle_count == 1
    assert result.actions
    assert result.actions[0]["detected"] is True
    assert result.actions[0]["executed"] is False
    assert result.stats["Total Clicks"] == 0


def test_run_session_executes_click_and_updates_stats(sample_profile):
    vision = _fake_vision()
    pyautogui = _fake_pyautogui()

    result = run_automation_session(
        profile=sample_profile,
        vision=vision,
        pyautogui=pyautogui,
        shutdown_event=Event(),
        mode="Automation Run",
        dry_run=False,
        once=True,
        render_output=False,
        simple=True,
    )

    pyautogui.click.assert_called_once_with(100, 200)
    assert result.dry_run is False
    assert result.actions[0]["executed"] is True
    assert result.stats["Total Clicks"] == 1
    assert result.stats["Attack"] == 1
