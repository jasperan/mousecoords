"""Finite state machine for structured game automation.

Replaces the flat polling loop with named states, each defining which
buttons to monitor, per-cycle action limits, and transition triggers.
"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable

from .config import Profile, ButtonConfig, StateConfig


class GamePhase(str, Enum):
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
    """Tracks cumulative and per-cycle statistics."""
    dimension_boosts: int = 0
    antimatter_galaxies: int = 0
    big_crunches: int = 0
    max_ticks: int = 0
    infinities: int = 0
    eternities: int = 0

    # Per-cycle counters (reset on Big Crunch)
    cycle_boosts: int = 0
    cycle_galaxies: int = 0

    # Limits (loaded from profile)
    max_boosts_per_cycle: int = 22
    max_galaxies_per_cycle: int = 1

    # Session
    start_time: float = field(default_factory=time.time)
    total_clicks: int = 0

    def reset_cycle(self):
        """Reset per-cycle counters (called on Big Crunch)."""
        self.cycle_boosts = 0
        self.cycle_galaxies = 0

    @property
    def boosts_remaining(self) -> int:
        return max(0, self.max_boosts_per_cycle - self.cycle_boosts)

    @property
    def galaxies_remaining(self) -> int:
        return max(0, self.max_galaxies_per_cycle - self.cycle_galaxies)

    @property
    def session_duration(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        mins, secs = divmod(int(self.session_duration), 60)
        hrs, mins = divmod(mins, 60)
        duration = f"{hrs}h{mins:02d}m{secs:02d}s" if hrs else f"{mins}m{secs:02d}s"
        return {
            "Dimension Boosts": self.dimension_boosts,
            "Boosts This Cycle": f"{self.cycle_boosts}/{self.max_boosts_per_cycle}",
            "Antimatter Galaxies": self.antimatter_galaxies,
            "Galaxies This Cycle": f"{self.cycle_galaxies}/{self.max_galaxies_per_cycle}",
            "Big Crunches": self.big_crunches,
            "Max Ticks": self.max_ticks,
            "Total Clicks": self.total_clicks,
            "Session": duration,
        }


class StateMachine:
    """Finite state machine driving Antimatter Dimensions automation."""

    def __init__(self, profile: Profile):
        self.profile = profile
        self.stats = GameStats()
        self.phase = GamePhase.FARMING
        self.cooldowns: dict[str, float] = {}

        self._on_transition: list[Callable] = []
        self._on_action: list[Callable] = []

        # Build lookup tables
        self._buttons = {b.name: b for b in profile.buttons}
        self._states = {s.name: s for s in profile.states}

        # Apply limits from the initial state config
        self._apply_limits()

    def _apply_limits(self):
        """Load action limits from the current state config."""
        state = self.current_state_config
        if not state:
            return
        if "Dimension Boost" in state.max_actions:
            self.stats.max_boosts_per_cycle = state.max_actions["Dimension Boost"]
        if "Antimatter Galaxies" in state.max_actions:
            self.stats.max_galaxies_per_cycle = state.max_actions["Antimatter Galaxies"]

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
        return self._states.get(self.phase.value)

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
        """Whether the button is clickable right now."""
        if self.phase == GamePhase.PAUSED:
            return False
        if self.is_on_cooldown(button_name):
            return False
        if button_name == "Dimension Boost" and self.stats.boosts_remaining <= 0:
            return False
        if button_name == "Antimatter Galaxies" and self.stats.galaxies_remaining <= 0:
            return False
        return True

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
        self.stats.total_clicks += 1

        # Update counters
        if button_name == "Dimension Boost":
            self.stats.dimension_boosts += 1
            self.stats.cycle_boosts += 1
        elif button_name == "Antimatter Galaxies":
            self.stats.antimatter_galaxies += 1
            self.stats.cycle_galaxies += 1
        elif button_name == "Big Crunch":
            self.stats.big_crunches += 1
            self.stats.reset_cycle()
        elif button_name == "Max Ticks":
            self.stats.max_ticks += 1

        result = ActionResult(button_name, True, time.time())

        # Check state transitions
        state = self.current_state_config
        if state and button_name in state.transitions:
            new_phase = GamePhase(state.transitions[button_name])
            old_phase = self.phase
            self.phase = new_phase
            for cb in self._on_transition:
                cb(old_phase, new_phase, button_name)

        for cb in self._on_action:
            cb(result)

        return result

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def pause(self):
        self.phase = GamePhase.PAUSED

    def resume(self, phase: Optional[GamePhase] = None):
        self.phase = phase or GamePhase.FARMING
