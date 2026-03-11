"""Transparent overlay HUD for live coordinate display and automation visualization.

Shows crosshair at mouse position, button markers, and status information
as a transparent window on top of all other windows.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import pyautogui

try:
    import tkinter as tk
    HAS_TK = True
except ImportError:
    HAS_TK = False


class Overlay:
    """Transparent screen overlay with crosshair, markers, and status bar."""

    def __init__(self, opacity: float = 0.7):
        if not HAS_TK:
            raise RuntimeError("tkinter is required for the overlay")

        self.opacity = opacity
        self.markers: dict[str, dict] = {}
        self.status_text = ""
        self.show_crosshair = True
        self.running = False
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the overlay in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the overlay."""
        self.running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def add_marker(self, label: str, x: int, y: int,
                   color: str = "#00ff00", radius: int = 10):
        """Add or update a named marker on the overlay."""
        self.markers[label] = {
            "x": x, "y": y, "color": color, "radius": radius,
        }

    def remove_marker(self, label: str):
        """Remove a named marker."""
        self.markers.pop(label, None)

    def set_status(self, text: str):
        """Set the status bar text."""
        self.status_text = text

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        """Main overlay loop (runs in its own thread)."""
        self.running = True
        self._root = tk.Tk()
        self._root.title("mousecoords overlay")

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        self._root.geometry(f"{screen_w}x{screen_h}+0+0")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        # Transparency (platform-dependent)
        try:
            self._root.attributes("-alpha", self.opacity)
        except Exception:
            pass

        # Try to make click-through on Linux
        try:
            self._root.attributes("-type", "dock")
        except Exception:
            pass

        self._root.configure(bg="black")
        try:
            self._root.wm_attributes("-transparentcolor", "black")
        except Exception:
            pass

        self._canvas = tk.Canvas(
            self._root, width=screen_w, height=screen_h,
            bg="black", highlightthickness=0,
        )
        self._canvas.pack()

        self._update()
        self._root.mainloop()

    def _update(self):
        """Redraw overlay contents (~30 fps)."""
        if not self.running or not self._canvas:
            return

        self._canvas.delete("all")

        # Crosshair at current mouse position
        if self.show_crosshair:
            try:
                mx, my = pyautogui.position()
                size = 20
                self._canvas.create_line(
                    mx - size, my, mx + size, my,
                    fill="#00ff00", width=1, tags="xhair",
                )
                self._canvas.create_line(
                    mx, my - size, mx, my + size,
                    fill="#00ff00", width=1, tags="xhair",
                )
                self._canvas.create_text(
                    mx + 25, my - 15,
                    text=f"({mx}, {my})",
                    fill="#00ff00", font=("Consolas", 10),
                    anchor="w", tags="xhair",
                )
            except Exception:
                pass

        # Button markers
        for label, m in self.markers.items():
            x, y, r = m["x"], m["y"], m["radius"]
            self._canvas.create_oval(
                x - r, y - r, x + r, y + r,
                outline=m["color"], width=2, tags="marker",
            )
            self._canvas.create_text(
                x, y - r - 12, text=label,
                fill=m["color"], font=("Consolas", 9), tags="marker",
            )

        # Status bar
        if self.status_text:
            self._canvas.create_rectangle(
                0, 0, 420, 25, fill="#1a1a2e", outline="", tags="status",
            )
            self._canvas.create_text(
                10, 12, text=self.status_text,
                fill="#00ff00", font=("Consolas", 10),
                anchor="w", tags="status",
            )

        # Schedule next frame
        if self.running:
            self._root.after(33, self._update)
