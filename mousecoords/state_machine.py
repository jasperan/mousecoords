"""Finite state machine for structured game automation.

Replaces the flat polling loop with named states, each defining which
buttons to monitor, per-cycle action limits, and transition triggers.

The state machine is fully profile-driven: phases, transitions, and
action limits all come from the YAML profile. No game-specific logic
is hardcoded here.
"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable

from .config import Profile, ButtonConfig, StateConfig


class GamePhase(str, Enum):
    """Well-known phases (for backward compat). Profiles can use any name."""
    FARMING = "farming"
    CRUNCHING = "crunching"
    INFINITY = "infinity"
    ETERNITY = "eternity"
    PAUSED = "paused"


@dataclass
class ActionResult:
    """Result of clicking a button."""
    button_name: str
    success: bool
    timestamp: float = 0.0


@dataclass
class GameStats:
    """Tracks cumulative and per-cycle statistics.

    Uses generic counters keyed by button name. Legacy named fields are
    kept for backward compatibility with existing profiles/dashboards.
    """
    # Generic counters (button_name -> lifetime count)
    action_totals: dict = field(default_factory=dict)
    # Per-cycle counters (reset on state transition)
    cycle_counts: dict = field(default_factory=dict)

    # Session
    start_time: float = field(default_factory=time.time)
    total_clicks: int = 0
    transitions: int = 0

    def record(self, button_name: str):
        """Increment counters for a button click."""
        self.total_clicks += 1
        self.action_totals[button_name] = self.action_totals.get(button_name, 0) + 1
        self.cycle_counts[button_name] = self.cycle_counts.get(button_name, 0) + 1

    def reset_cycle(self):
        """Reset per-cycle counters (called on state transitions)."""
        self.cycle_counts.clear()

    def cycle_count(self, button_name: str) -> int:
        return self.cycle_counts.get(button_name, 0)

    def total_count(self, button_name: str) -> int:
        return self.action_totals.get(button_name, 0)

    @property
    def session_duration(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        mins, secs = divmod(int(self.session_duration), 60)
        hrs, mins = divmod(mins, 60)
        duration = f"{hrs}h{mins:02d}m{secs:02d}s" if hrs else f"{mins}m{secs:02d}s"

        d = {}
        for name, total in self.action_totals.items():
            d[name] = total
            cycle = self.cycle_counts.get(name, 0)
            if cycle:
                d[f"{name} (cycle)"] = cycle

        d["Total Clicks"] = self.total_clicks
        d["Transitions"] = self.transitions
        d["Session"] = duration
        return d


class StateMachine:
    """Profile-driven finite state machine for automation.

    Phases, transitions, and action limits are all defined in the YAML
    profile. The machine itself has no game-specific knowledge.
    """

    def __init__(self, profile: Profile):
        self.profile = profile
        self.stats = GameStats()
        self.cooldowns: dict[str, float] = {}

        self._on_transition: list[Callable] = []
        self._on_action: list[Callable] = []

        # Build lookup tables
        self._buttons = {b.name: b for b in profile.buttons}
        self._states = {s.name: s for s in profile.states}

        # Start in first defined state, or "farming" as fallback
        initial = profile.states[0].name if profile.states else "farming"
        self._phase: str = initial

    # ------------------------------------------------------------------
    # Phase property (backward compat: returns GamePhase when possible)
    # ------------------------------------------------------------------

    @property
    def phase(self):
        try:
            return GamePhase(self._phase)
        except ValueError:
            return self._phase

    @phase.setter
    def phase(self, value):
        if isinstance(value, GamePhase):
            self._phase = value.value
        else:
            self._phase = str(value)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_transition(self, callback: Callable):
        """Register a state-transition callback(old_phase, new_phase, trigger)."""
        self._on_transition.append(callback)

    def on_action(self, callback: Callable):
        """Register an action callback(ActionResult)."""
        self._on_action.append(callback)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    @property
    def current_state_config(self) -> Optional[StateConfig]:
        return self._states.get(self._phase)

    @property
    def monitored_buttons(self) -> list:
        """Buttons to monitor in the current state."""
        state = self.current_state_config
        if not state:
            return list(self._buttons.values())
        return [
            self._buttons[name]
            for name in state.monitor_buttons
            if name in self._buttons
        ]

    def is_on_cooldown(self, button_name: str) -> bool:
        if button_name not in self.cooldowns:
            return False
        return time.time() < self.cooldowns[button_name]

    def can_click(self, button_name: str) -> bool:
        """Whether the button is clickable right now (generic limit check)."""
        if self._phase == "paused":
            return False
        if self.is_on_cooldown(button_name):
            return False

        # Check per-cycle action limits from the current state config
        state = self.current_state_config
        if state and button_name in state.max_actions:
            limit = state.max_actions[button_name]
            if self.stats.cycle_count(button_name) >= limit:
                return False

        return True

    def remaining(self, button_name: str) -> Optional[int]:
        """How many more clicks are allowed this cycle, or None if unlimited."""
        state = self.current_state_config
        if not state or button_name not in state.max_actions:
            return None
        limit = state.max_actions[button_name]
        return max(0, limit - self.stats.cycle_count(button_name))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def record_action(self, button_name: str) -> ActionResult:
        """Record a button click and update stats / state transitions."""
        button = self._buttons.get(button_name)
        if not button:
            return ActionResult(button_name, False)

        # Set cooldown
        self.cooldowns[button_name] = time.time() + button.cooldown

        # Update generic counters
        self.stats.record(button_name)

        result = ActionResult(button_name, True, time.time())

        # Check state transitions
        state = self.current_state_config
        if state and button_name in state.transitions:
            new_phase_name = state.transitions[button_name]
            old_phase = self.phase
            self._phase = new_phase_name
            self.stats.transitions += 1
            self.stats.reset_cycle()
            for cb in self._on_transition:
                cb(old_phase, self.phase, button_name)

        for cb in self._on_action:
            cb(result)

        return result

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def pause(self):
        self._phase = "paused"

    def resume(self, phase: Optional[str] = None):
        if phase is None:
            initial = (self.profile.states[0].name
                       if self.profile.states else "farming")
            self._phase = initial
        elif isinstance(phase, GamePhase):
            self._phase = phase.value
        else:
            self._phase = str(phase)
