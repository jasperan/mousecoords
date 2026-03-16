"""Window lookup stubs for future window-scoped automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

Bounds = Tuple[int, int, int, int]


@dataclass
class WindowInfo:
    """Minimal window descriptor used by the future runtime."""

    title: str
    bounds: Optional[Bounds] = None


class WindowBackend:
    """Stub window backend with title matching and bounds helpers."""

    def list_windows(self) -> List[WindowInfo]:
        return []

    def find_by_title(self, title: str, title_match: str = "exact") -> Optional[WindowInfo]:
        for window in self.list_windows():
            if title_match == "contains" and title in window.title:
                return window
            if title_match == "exact" and window.title == title:
                return window
        return None

    @staticmethod
    def get_bounds(window: Optional[WindowInfo]) -> Optional[Bounds]:
        if window is None:
            return None
        return window.bounds
