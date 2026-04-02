"""Tests for the generic state machine."""

import time
import pytest
from unittest.mock import MagicMock

from mousecoords.state_machine import StateMachine, GamePhase, GameStats, ActionResult


class TestGameStats:
    def test_record_increments(self):
        stats = GameStats()
        stats.record("Attack")
        stats.record("Attack")
        stats.record("Heal")
        assert stats.total_count("Attack") == 2
        assert stats.cycle_count("Attack") == 2
        assert stats.total_count("Heal") == 1
        assert stats.total_clicks == 3

    def test_reset_cycle(self):
        stats = GameStats()
        stats.record("Attack")
        stats.record("Attack")
        stats.reset_cycle()
        assert stats.cycle_count("Attack") == 0
        # Totals survive cycle reset
        assert stats.total_count("Attack") == 2

    def test_to_dict(self):
        stats = GameStats()
        stats.record("Attack")
        d = stats.to_dict()
        assert "Attack" in d
        assert "Total Clicks" in d
        assert "Session" in d

    def test_session_duration(self):
        stats = GameStats()
        assert stats.session_duration >= 0


class TestStateMachine:
    def test_initial_state(self, sample_profile):
        sm = StateMachine(sample_profile)
        # "combat" is a custom phase (not in GamePhase enum), returned as string
        phase = sm.phase
        assert str(phase) == "combat"

    def test_monitored_buttons(self, sample_profile):
        sm = StateMachine(sample_profile)
        names = [b.name for b in sm.monitored_buttons]
        assert "Attack" in names
        assert "Heal" in names
        assert "Shield" in names

    def test_can_click_basic(self, sample_profile):
        sm = StateMachine(sample_profile)
        assert sm.can_click("Attack") is True
        assert sm.can_click("Heal") is True

    def test_cooldown(self, sample_profile):
        sm = StateMachine(sample_profile)
        sm.record_action("Attack")
        # Should be on cooldown now
        assert sm.is_on_cooldown("Attack") is True
        assert sm.can_click("Attack") is False

    def test_action_limits(self, sample_profile):
        sm = StateMachine(sample_profile)
        # Attack has max_actions=5 in combat state
        for _ in range(5):
            sm.cooldowns.clear()  # bypass cooldown for testing
            sm.record_action("Attack")
        sm.cooldowns.clear()
        assert sm.can_click("Attack") is False

    def test_remaining(self, sample_profile):
        sm = StateMachine(sample_profile)
        assert sm.remaining("Attack") == 5
        sm.record_action("Attack")
        assert sm.remaining("Attack") == 4
        # Heal has no limit
        assert sm.remaining("Heal") is None

    def test_state_transition(self, sample_profile):
        sm = StateMachine(sample_profile)
        # Shield triggers combat -> defend
        sm.record_action("Shield")
        phase = sm.phase
        phase_str = phase.value if isinstance(phase, GamePhase) else str(phase)
        assert phase_str == "defend"

    def test_transition_resets_cycle(self, sample_profile):
        sm = StateMachine(sample_profile)
        sm.record_action("Attack")
        assert sm.stats.cycle_count("Attack") == 1
        # Transition via Shield
        sm.cooldowns.clear()
        sm.record_action("Shield")
        # Cycle counters reset
        assert sm.stats.cycle_count("Attack") == 0

    def test_transition_callback(self, sample_profile):
        sm = StateMachine(sample_profile)
        callback = MagicMock()
        sm.on_transition(callback)
        sm.record_action("Shield")
        callback.assert_called_once()

    def test_action_callback(self, sample_profile):
        sm = StateMachine(sample_profile)
        callback = MagicMock()
        sm.on_action(callback)
        sm.record_action("Attack")
        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert isinstance(result, ActionResult)
        assert result.button_name == "Attack"
        assert result.success is True

    def test_unknown_button(self, sample_profile):
        sm = StateMachine(sample_profile)
        result = sm.record_action("NonExistent")
        assert result.success is False

    def test_pause_resume(self, sample_profile):
        sm = StateMachine(sample_profile)
        sm.pause()
        assert sm.can_click("Attack") is False
        sm.resume()
        assert sm.can_click("Attack") is True

    def test_pause_resume_specific_phase(self, sample_profile):
        sm = StateMachine(sample_profile)
        sm.pause()
        sm.resume("defend")
        phase = sm.phase
        phase_str = phase.value if isinstance(phase, GamePhase) else str(phase)
        assert phase_str == "defend"


class TestCustomPhases:
    """Test that arbitrary (non-enum) phase names work."""

    def test_custom_phase_name(self, sample_profile):
        sm = StateMachine(sample_profile)
        # Transition to 'defend' (not in GamePhase enum)
        sm.record_action("Shield")
        # Should still work even if 'defend' isn't in the enum
        phase = sm.phase
        # It might be a string or a GamePhase depending on whether it's in the enum
        assert "defend" in str(phase)

    def test_monitored_buttons_in_defend(self, sample_profile):
        sm = StateMachine(sample_profile)
        sm.record_action("Shield")  # -> defend
        names = [b.name for b in sm.monitored_buttons]
        assert "Shield" in names
        assert "Heal" in names
        assert "Attack" not in names
