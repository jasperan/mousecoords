"""Live screen region watcher with change detection.

Monitors a pixel or region and reports color changes in real-time.
Useful for detecting game state changes, UI updates, or debugging
automation profiles.
"""

from __future__ import annotations

import time
from typing import Optional, Callable

from .screen import capture_screen


class ScreenWatcher:
    """Watches a screen coordinate for color changes."""

    def __init__(self, x: int, y: int, threshold: float = 10.0,
                 poll_interval: float = 0.5):
        self.x = x
        self.y = y
        self.threshold = threshold
        self.poll_interval = poll_interval
        self._last_color: Optional[tuple] = None
        self._callbacks: list[Callable] = []
        self.running = False
        self.change_count = 0
        self.history: list[dict] = []

    def on_change(self, callback: Callable):
        """Register callback(old_color, new_color, timestamp)."""
        self._callbacks.append(callback)

    @staticmethod
    def get_pixel_color(x: int, y: int) -> tuple:
        """Get RGB color at screen coordinates."""
        img = capture_screen(region=(x, y, 1, 1))
        return img.getpixel((0, 0))[:3]

    @staticmethod
    def color_distance(c1: tuple, c2: tuple) -> float:
        """Euclidean distance between two RGB colors."""
        return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

    def check_once(self) -> Optional[tuple]:
        """Single check. Returns new color if changed beyond threshold."""
        current = self.get_pixel_color(self.x, self.y)

        if self._last_color is None:
            self._last_color = current
            return None

        dist = self.color_distance(self._last_color, current)
        if dist > self.threshold:
            old = self._last_color
            self._last_color = current
            self.change_count += 1
            self.history.append({
                "from": old, "to": current,
                "delta": round(dist, 1),
                "time": time.time(),
            })
            for cb in self._callbacks:
                cb(old, current, time.time())
            return current
        return None

    def watch(self, duration: float = 0):
        """Blocking watch loop. Ctrl+C or duration (seconds, 0=forever) to stop."""
        self.running = True
        self._last_color = self.get_pixel_color(self.x, self.y)

        print(f"Watching ({self.x}, {self.y}) | Initial RGB{self._last_color}")
        print(f"Threshold: {self.threshold} | Poll: {self.poll_interval}s")
        if duration:
            print(f"Duration: {duration}s")
        print("-" * 50)

        def _print_change(old_color, new_color, timestamp):
            dist = self.color_distance(old_color, new_color)
            ts = time.strftime("%H:%M:%S")
            print(f"  [{ts}] CHANGE #{self.change_count}: "
                  f"RGB{old_color} -> RGB{new_color} (delta={dist:.1f})")

        self.on_change(_print_change)

        start = time.time()
        try:
            while self.running:
                if duration and (time.time() - start) >= duration:
                    break
                self.check_once()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            pass

        self.running = False
        print(f"\nDone. {self.change_count} changes detected.")

    def stop(self):
        """Stop the watch loop."""
        self.running = False
