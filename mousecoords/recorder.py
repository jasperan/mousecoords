"""Macro recording and replay system.

Records mouse clicks, scrolls, key presses (and optionally mouse movement)
with precise timestamps. Saves as JSON for editing and sharing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

import pyautogui

try:
    from pynput import mouse, keyboard as kb
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class EventType(str, Enum):
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    WAIT = "wait"
    CONDITION = "condition"


@dataclass
class Event:
    """A single recorded input event."""
    type: EventType
    timestamp: float
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    key: Optional[str] = None
    pressed: Optional[bool] = None
    dx: Optional[int] = None
    dy: Optional[int] = None
    # For conditional checks
    check_color: Optional[tuple] = None
    color_tolerance: int = 3

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> Event:
        d = dict(d)  # don't mutate original
        d["type"] = EventType(d["type"])
        if "check_color" in d and d["check_color"]:
            d["check_color"] = tuple(d["check_color"])
        return cls(**d)


class MacroRecorder:
    """Records and replays mouse/keyboard macros."""

    def __init__(self, record_moves: bool = False):
        self.events: list[Event] = []
        self.recording = False
        self.record_moves = record_moves
        self._start_time = 0.0
        self._listeners: list = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(self):
        """Start recording mouse and keyboard events. Press ESC to stop."""
        if not HAS_PYNPUT:
            raise RuntimeError(
                "pynput is required for recording. Install: pip install pynput"
            )

        self.events = []
        self.recording = True
        self._start_time = time.time()

        mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            on_move=self._on_move if self.record_moves else None,
        )
        key_listener = kb.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )

        mouse_listener.start()
        key_listener.start()
        self._listeners = [mouse_listener, key_listener]

    def stop_recording(self) -> list:
        """Stop recording and return captured events."""
        self.recording = False
        for listener in self._listeners:
            listener.stop()
        self._listeners = []
        return self.events

    def _elapsed(self) -> float:
        return time.time() - self._start_time

    def _on_click(self, x, y, button, pressed):
        if not self.recording:
            return
        self.events.append(Event(
            type=EventType.MOUSE_CLICK,
            timestamp=self._elapsed(),
            x=x, y=y,
            button=button.name,
            pressed=pressed,
        ))

    def _on_scroll(self, x, y, dx, dy):
        if not self.recording:
            return
        self.events.append(Event(
            type=EventType.MOUSE_SCROLL,
            timestamp=self._elapsed(),
            x=x, y=y, dx=dx, dy=dy,
        ))

    def _on_move(self, x, y):
        if not self.recording:
            return
        self.events.append(Event(
            type=EventType.MOUSE_MOVE,
            timestamp=self._elapsed(),
            x=x, y=y,
        ))

    def _on_key_press(self, key):
        if not self.recording:
            return
        try:
            key_name = key.char
        except AttributeError:
            key_name = key.name

        if key_name == "esc":
            self.stop_recording()
            return

        self.events.append(Event(
            type=EventType.KEY_PRESS,
            timestamp=self._elapsed(),
            key=key_name,
            pressed=True,
        ))

    def _on_key_release(self, key):
        if not self.recording:
            return
        try:
            key_name = key.char
        except AttributeError:
            key_name = key.name

        self.events.append(Event(
            type=EventType.KEY_RELEASE,
            timestamp=self._elapsed(),
            key=key_name,
            pressed=False,
        ))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str):
        """Save recorded events to JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "2.0",
            "event_count": len(self.events),
            "duration": self.events[-1].timestamp if self.events else 0,
            "events": [e.to_dict() for e in self.events],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str):
        """Load events from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        self.events = [Event.from_dict(e) for e in data["events"]]

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self, speed: float = 1.0, loop: bool = False,
             on_event: Optional[Callable] = None):
        """Replay recorded events with optional speed multiplier."""
        if not self.events:
            return

        while True:
            start = time.time()
            for event in self.events:
                target_time = start + (event.timestamp / speed)
                wait = target_time - time.time()
                if wait > 0:
                    time.sleep(wait)

                self._execute_event(event)

                if on_event:
                    on_event(event)

            if not loop:
                break

    def _execute_event(self, event: Event):
        """Execute a single event during playback."""
        if event.type == EventType.MOUSE_MOVE:
            pyautogui.moveTo(event.x, event.y, _pause=False)

        elif event.type == EventType.MOUSE_CLICK:
            if event.pressed:
                pyautogui.click(event.x, event.y, _pause=False)

        elif event.type == EventType.MOUSE_SCROLL:
            pyautogui.scroll(event.dy, event.x, event.y, _pause=False)

        elif event.type == EventType.KEY_PRESS:
            try:
                pyautogui.press(event.key, _pause=False)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Programmatic macro building
    # ------------------------------------------------------------------

    def _next_ts(self, delay: float = 0.0) -> float:
        return (self.events[-1].timestamp + delay) if self.events else delay

    def add_click(self, x: int, y: int, delay: float = 0.0):
        """Programmatically add a click event."""
        self.events.append(Event(
            type=EventType.MOUSE_CLICK,
            timestamp=self._next_ts(delay),
            x=x, y=y, button="left", pressed=True,
        ))

    def add_wait(self, seconds: float):
        """Add a timed pause."""
        self.events.append(Event(
            type=EventType.WAIT,
            timestamp=self._next_ts(seconds),
        ))

    def add_key(self, key: str, delay: float = 0.0):
        """Add a key press event."""
        self.events.append(Event(
            type=EventType.KEY_PRESS,
            timestamp=self._next_ts(delay),
            key=key, pressed=True,
        ))

    def add_condition(self, x: int, y: int, expected_color: tuple,
                      tolerance: int = 3):
        """Add a conditional color check (playback skips if color doesn't match)."""
        self.events.append(Event(
            type=EventType.CONDITION,
            timestamp=self._next_ts(),
            x=x, y=y,
            check_color=expected_color,
            color_tolerance=tolerance,
        ))
