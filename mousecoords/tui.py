"""Rich terminal UI dashboard for mousecoords automation.

Provides a live-updating terminal display with stats table, event log,
button status indicators, and keyboard shortcut footer.
"""

from __future__ import annotations

from datetime import datetime
from collections import deque
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class LogEntry:
    __slots__ = ("message", "level", "color", "timestamp")

    def __init__(self, message: str, level: str = "INFO", color: str = "white"):
        self.message = message
        self.level = level
        self.color = color
        self.timestamp = datetime.now()


class Dashboard:
    """Rich-based live terminal dashboard."""

    def __init__(self, title: str = "mousecoords", max_log: int = 20):
        if not HAS_RICH:
            raise RuntimeError("Rich is required for TUI. Install: pip install rich")

        self.title = title
        self.console = Console()
        self.stats: dict = {}
        self.state = "IDLE"
        self.mode = ""
        self.log_entries: deque = deque(maxlen=max_log)
        self._live: Optional[Live] = None
        self._running = False
        self._buttons_status: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Live:
        """Create and return a Rich Live context manager."""
        self._running = True
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            screen=False,
        )
        return self._live

    def stop(self):
        self._running = False

    def refresh(self):
        """Push an update to the live display."""
        if self._live:
            self._live.update(self._render())

    # ------------------------------------------------------------------
    # Data setters
    # ------------------------------------------------------------------

    def update_stats(self, stats: dict):
        self.stats = stats
        self.refresh()

    def set_state(self, state: str):
        self.state = state
        self.refresh()

    def set_mode(self, mode: str):
        self.mode = mode

    def set_button_status(self, name: str, status: str):
        """Set button status: 'ready', 'cooldown', 'disabled', 'active'."""
        self._buttons_status[name] = status

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, message: str, level: str = "INFO", color: str = "white"):
        self.log_entries.append(LogEntry(message, level, color))
        self.refresh()

    def log_info(self, msg: str):
        self.log(msg, "INFO", "cyan")

    def log_action(self, msg: str):
        self.log(msg, "CLICK", "green")

    def log_warning(self, msg: str):
        self.log(msg, "WARN", "yellow")

    def log_error(self, msg: str):
        self.log(msg, "ERROR", "red")

    def log_state(self, msg: str):
        self.log(msg, "STATE", "magenta")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> Panel:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="log", ratio=2),
        )

        # --- Header ---
        header = Text()
        header.append(f" {self.title} ", style="bold white on blue")
        header.append("  Mode: ", style="dim")
        header.append(self.mode or "N/A", style="bold cyan")
        header.append("  State: ", style="dim")
        state_style = {
            "FARMING": "bold green",
            "CRUNCHING": "bold yellow",
            "PAUSED": "bold red",
            "IDLE": "dim",
        }.get(self.state.upper(), "bold white")
        header.append(self.state, style=state_style)
        layout["header"].update(Panel(header, box=box.SIMPLE))

        # --- Stats table ---
        tbl = Table(
            title="Statistics", box=box.ROUNDED,
            title_style="bold cyan", border_style="cyan", expand=True,
        )
        tbl.add_column("Metric", style="bold")
        tbl.add_column("Value", justify="right")
        for key, val in self.stats.items():
            tbl.add_row(key, str(val))

        # Button status section
        if self._buttons_status:
            tbl.add_section()
            tbl.add_row("[bold]Buttons[/bold]", "", style="dim")
            status_icons = {
                "ready": "[green]● READY[/green]",
                "cooldown": "[yellow]○ COOLDOWN[/yellow]",
                "disabled": "[red]✕ DISABLED[/red]",
                "active": "[cyan]▶ ACTIVE[/cyan]",
            }
            for btn, status in self._buttons_status.items():
                tbl.add_row(f"  {btn}", status_icons.get(status, status))

        layout["stats"].update(Panel(tbl, border_style="cyan"))

        # --- Event log ---
        log_text = Text()
        for entry in self.log_entries:
            ts = entry.timestamp.strftime("%H:%M:%S")
            log_text.append(f"[{ts}] ", style="dim")
            log_text.append(f"[{entry.level}] ", style=f"bold {entry.color}")
            log_text.append(f"{entry.message}\n", style=entry.color)
        layout["log"].update(Panel(
            log_text, title="[bold green]Event Log[/bold green]",
            border_style="green", box=box.ROUNDED,
        ))

        # --- Footer ---
        footer = Text()
        footer.append(" Ctrl+C", style="bold yellow")
        footer.append(" stop  ", style="dim")
        layout["footer"].update(Panel(footer, box=box.SIMPLE))

        return Panel(
            layout,
            title="[bold blue]mousecoords v2.0[/bold blue]",
            border_style="blue", box=box.DOUBLE,
        )

    # ------------------------------------------------------------------
    # Fallback for environments without Rich
    # ------------------------------------------------------------------

    @staticmethod
    def print_fallback(stats: dict, log_msg: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        parts = " | ".join(f"{k}: {v}" for k, v in stats.items())
        suffix = f"  {log_msg}" if log_msg else ""
        print(f"[{ts}] {parts}{suffix}")
