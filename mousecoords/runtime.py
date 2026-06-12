"""Reusable automation runtime for `run` and `automate` commands."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from threading import Event as ThreadEvent, Thread
from typing import Any

from .state_machine import StateMachine
from .tui import Dashboard, HAS_RICH


def _phase_name(phase: object) -> str:
    value = getattr(phase, "value", None)
    return str(value if value is not None else phase)


@dataclass
class ActionRecord:
    """Single detected or executed action during a run."""

    button_name: str
    x: int
    y: int
    detector: str
    detected: bool
    executed: bool
    timestamp: float
    phase_before: str
    phase_after: str

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "button_name": self.button_name,
            "x": self.x,
            "y": self.y,
            "detector": self.detector,
            "detected": self.detected,
            "executed": self.executed,
            "timestamp": self.timestamp,
            "phase_before": self.phase_before,
            "phase_after": self.phase_after,
        }


@dataclass
class RunResult:
    """Structured summary returned after an automation session."""

    command: str
    mode: str
    profile: str
    dry_run: bool
    once: bool
    duration_limit: float | None
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    cycle_count: int = 0
    final_phase: str = ""
    actions: list[ActionRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ocr: dict[str, float] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def iterations(self) -> int:
        """Backward-compatible alias for older debug/test code."""
        return self.cycle_count

    def finish(self, phase: object, stats: dict[str, Any], ocr: dict[str, float]):
        self.ended_at = time.time()
        self.final_phase = _phase_name(phase)
        self.stats = stats
        self.ocr = dict(ocr)

    def to_dict(self) -> dict[str, Any]:
        elapsed = round(self.ended_at - self.started_at, 3) if self.ended_at else 0.0
        return {
            "command": self.command,
            "mode": self.mode,
            "profile": self.profile,
            "dry_run": self.dry_run,
            "once": self.once,
            "duration_limit": self.duration_limit,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_seconds": elapsed,
            "cycle_count": self.cycle_count,
            "iterations": self.iterations,
            "final_phase": self.final_phase,
            "actions": [action.to_dict() for action in self.actions],
            "errors": list(self.errors),
            "ocr": dict(self.ocr),
            "stats": dict(self.stats),
        }


def run_automation_session(
    *,
    profile,
    vision,
    pyautogui,
    shutdown_event: ThreadEvent,
    mode: str,
    command: str | None = None,
    overlay_enabled: bool = False,
    ocr_enabled: bool = False,
    simple: bool = False,
    dry_run: bool = False,
    once: bool = False,
    duration: float | None = None,
    render_output: bool = True,
) -> RunResult:
    """Run the main automation loop and return a structured summary."""

    if command is None:
        command = "run" if mode == "Automation Run" else "automate"

    summary = RunResult(
        command=command,
        mode=mode,
        profile=profile.name,
        dry_run=dry_run,
        once=once,
        duration_limit=duration,
    )
    state_machine = StateMachine(profile)
    dashboard = None
    overlay = None
    ocr_data: dict[str, float] = {}

    # kind -> (dashboard method name, plain-output prefix)
    emit_kinds = {
        "action": ("log_action", "[ACTION]"),
        "error": ("log_error", "[ERROR]"),
        "warning": ("log_warning", "[WARN]"),
        "state": ("log_state", "[STATE]"),
        "info": ("log_info", ""),
    }

    def emit(message: str, *, kind: str = "info"):
        if not render_output:
            return

        method_name, prefix = emit_kinds.get(kind, emit_kinds["info"])
        if dashboard:
            getattr(dashboard, method_name)(message)
            return

        print(f"{prefix} {message}".strip())

    if render_output and HAS_RICH and not simple:
        dashboard = Dashboard(title=f"mousecoords -- {profile.game or profile.name}")
        dashboard.set_mode(mode)

    def on_transition(old, new, trigger):
        emit(f"{old} -> {new} (triggered by {trigger})", kind="state")

    state_machine.on_transition(on_transition)

    if overlay_enabled:
        try:
            from .overlay import Overlay

            overlay = Overlay()
            overlay.start()
            for button in profile.buttons:
                overlay.add_marker(button.name, button.x, button.y)
        except Exception as exc:
            emit(f"Overlay unavailable: {exc}", kind="warning")

    if ocr_enabled and profile.ocr_regions:
        def ocr_loop():
            while not shutdown_event.is_set():
                for name, region in profile.ocr_regions.items():
                    value = vision.read_number(region)
                    if value is not None:
                        ocr_data[name] = value
                shutdown_event.wait(2)

        Thread(target=ocr_loop, daemon=True).start()

    deadline = time.time() + duration if duration and duration > 0 else None

    try:
        if render_output:
            emit(f"Profile: {profile.name}")
            emit(f"Monitoring {len(profile.buttons)} buttons")
            if pyautogui.FAILSAFE:
                emit("Failsafe ON (move mouse to top-left corner to emergency stop)")
            emit("Press Ctrl+C to stop")
            if not dashboard:
                print("-" * 45)

        def update_dashboard_stats():
            if not dashboard:
                return
            stats = state_machine.stats.to_dict()
            if ocr_data:
                for key, value in ocr_data.items():
                    stats[f"OCR:{key}"] = f"{value:,.0f}"
            dashboard.update_stats(stats)
            dashboard.set_state(_phase_name(state_machine.phase).upper())

        def run_cycle():
            summary.cycle_count += 1
            buttons = state_machine.monitored_buttons

            for button in buttons:
                if shutdown_event.is_set():
                    break
                if deadline and time.time() >= deadline:
                    break

                if not state_machine.can_click(button.name):
                    if dashboard:
                        status = (
                            "cooldown"
                            if state_machine.is_on_cooldown(button.name)
                            else "disabled"
                        )
                        dashboard.set_button_status(button.name, status)
                    continue

                detected = False
                detector = "color"
                click_x, click_y = button.x, button.y

                if button.template:
                    detector = "template"
                    center = vision.find_button_by_template(button.template)
                    if center:
                        detected = True
                        click_x, click_y = center
                else:
                    detected = vision.find_button_by_color(button.x, button.y, button.color)

                if not detected:
                    if dashboard:
                        dashboard.set_button_status(button.name, "ready")
                    continue

                phase_before = _phase_name(state_machine.phase)
                if dashboard:
                    dashboard.set_button_status(button.name, "active")

                if dry_run:
                    emit(f"Would click {button.name}", kind="action")
                else:
                    pyautogui.click(click_x, click_y)
                    state_machine.record_action(button.name)
                    emit(f"Clicked {button.name}", kind="action")

                summary.actions.append(
                    ActionRecord(
                        button_name=button.name,
                        x=click_x,
                        y=click_y,
                        detector=detector,
                        detected=True,
                        executed=not dry_run,
                        timestamp=time.time(),
                        phase_before=phase_before,
                        phase_after=_phase_name(state_machine.phase),
                    )
                )

                if button.priority:
                    break

            update_dashboard_stats()

        live = dashboard.start() if dashboard else contextlib.nullcontext()
        with live:
            while not shutdown_event.is_set():
                if deadline and time.time() >= deadline:
                    break
                run_cycle()
                if once:
                    break
                time.sleep(profile.poll_interval)
        if dashboard:
            dashboard.stop()

    except KeyboardInterrupt:
        pass
    except Exception as exc:  # pragma: no cover - command-level exercise
        summary.errors.append(str(exc))
        emit(str(exc), kind="error")
    finally:
        if overlay:
            overlay.stop()

    summary.finish(state_machine.phase, state_machine.stats.to_dict(), ocr_data)
    return summary
