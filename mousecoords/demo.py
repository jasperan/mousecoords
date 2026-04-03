"""Built-in demo target and scaffold helpers for end-to-end walkthroughs."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import ButtonConfig, Profile, StateConfig, save_profile
from .studio import create_studio_project

DEMO_WINDOW_TITLE = "mousecoords Demo Lab"
DEMO_WINDOW_WIDTH = 420
DEMO_WINDOW_HEIGHT = 260
DEMO_WINDOW_X = 120
DEMO_WINDOW_Y = 120


@dataclass(frozen=True)
class DemoButtonSpec:
    """Deterministic rectangle target inside the demo window."""

    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    color: tuple[int, int, int]

    @property
    def click_point(self) -> tuple[int, int]:
        return (self.x1 + 22, self.y1 + 22)


DEMO_BUTTONS: tuple[DemoButtonSpec, ...] = (
    DemoButtonSpec("Harvest", 40, 90, 140, 150, (220, 70, 70)),
    DemoButtonSpec("Boost", 160, 90, 260, 150, (70, 170, 70)),
    DemoButtonSpec("Reset", 280, 90, 380, 150, (70, 120, 220)),
)


@dataclass
class DemoState:
    """Serializable state for the walkthrough demo."""

    title: str = DEMO_WINDOW_TITLE
    started_at: float = field(default_factory=time.time)
    last_button: str | None = None
    total_clicks: int = 0
    counters: dict[str, int] = field(
        default_factory=lambda: {button.name: 0 for button in DEMO_BUTTONS}
    )

    def record_click(self, name: str):
        self.total_clicks += 1
        self.last_button = name
        self.counters[name] = self.counters.get(name, 0) + 1

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "started_at": self.started_at,
            "last_button": self.last_button,
            "total_clicks": self.total_clicks,
            "counters": dict(self.counters),
        }

    def write(self, path: str | Path | None):
        if path is None:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))


def build_demo_profile(*, name: str = "demo_lab") -> Profile:
    """Return a ready-to-run profile for the built-in demo target."""

    buttons = [
        ButtonConfig(
            name=button.name,
            x=DEMO_WINDOW_X + button.click_point[0],
            y=DEMO_WINDOW_Y + button.click_point[1],
            color=button.color,
            cooldown=0.2,
        )
        for button in DEMO_BUTTONS
    ]
    states = [
        StateConfig(
            name="default",
            monitor_buttons=[button.name for button in DEMO_BUTTONS],
            transitions={},
            max_actions={},
        )
    ]
    return Profile(
        name=name,
        game=DEMO_WINDOW_TITLE,
        resolution=(1280, 1024),
        poll_interval=0.05,
        color_tolerance=8,
        buttons=buttons,
        states=states,
        ocr_regions={},
    )


def create_demo_project(
    output_dir: str | Path,
    *,
    name: str = "demo_lab",
    force: bool = False,
) -> Path:
    """Create a scaffolded profile pack wired to the built-in demo target."""

    project = create_studio_project(output_dir, name=name, force=force)
    save_profile(build_demo_profile(name=name), str(project.profile_path))
    return project.profile_path


def launch_demo_app(
    *,
    state_file: str | Path | None = None,
    ready_file: str | Path | None = None,
    duration: float | None = None,
):
    """Launch a deterministic Tkinter target for automation walkthroughs."""

    import tkinter as tk

    state = DemoState()
    state.write(state_file)

    root = tk.Tk()
    root.title(DEMO_WINDOW_TITLE)
    root.geometry(f"{DEMO_WINDOW_WIDTH}x{DEMO_WINDOW_HEIGHT}+{DEMO_WINDOW_X}+{DEMO_WINDOW_Y}")
    root.resizable(False, False)
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    canvas = tk.Canvas(
        root,
        width=DEMO_WINDOW_WIDTH,
        height=DEMO_WINDOW_HEIGHT,
        highlightthickness=0,
        bg="#f5f5f5",
    )
    canvas.pack(fill="both", expand=True)

    canvas.create_text(
        DEMO_WINDOW_WIDTH / 2,
        28,
        text="mousecoords Demo Lab",
        fill="#202020",
        font=("TkDefaultFont", 16, "bold"),
    )
    subtitle_item = canvas.create_text(
        DEMO_WINDOW_WIDTH / 2,
        52,
        text="Click the color blocks manually or via mousecoords.",
        fill="#404040",
        font=("TkDefaultFont", 10),
    )
    footer_item = canvas.create_text(
        DEMO_WINDOW_WIDTH / 2,
        DEMO_WINDOW_HEIGHT - 18,
        text="Total clicks: 0",
        fill="#202020",
        font=("TkDefaultFont", 10),
    )

    def _refresh(name: str):
        state.record_click(name)
        canvas.itemconfigure(subtitle_item, text=f"Last click: {name}")
        canvas.itemconfigure(
            footer_item,
            text=(
                "Total clicks: "
                f"{state.total_clicks} | "
                + ", ".join(f"{key}={value}" for key, value in state.counters.items())
            ),
        )
        state.write(state_file)

    for button in DEMO_BUTTONS:
        tag = f"button:{button.name}"
        fill = "#%02x%02x%02x" % button.color
        canvas.create_rectangle(
            button.x1,
            button.y1,
            button.x2,
            button.y2,
            fill=fill,
            outline="#202020",
            width=2,
            tags=(tag,),
        )
        canvas.create_text(
            (button.x1 + button.x2) / 2,
            button.y2 + 16,
            text=button.name,
            fill="#202020",
            font=("TkDefaultFont", 11, "bold"),
        )
        canvas.tag_bind(tag, "<Button-1>", lambda _event, name=button.name: _refresh(name))

    root.update_idletasks()
    if ready_file is not None:
        ready_path = Path(ready_file)
        ready_path.parent.mkdir(parents=True, exist_ok=True)
        ready_path.write_text("ready\n")

    if duration and duration > 0:
        root.after(int(duration * 1000), root.destroy)

    def _handle_sigterm(_signum, _frame):
        root.after(0, root.destroy)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.mainloop()
    state.write(state_file)


def _wait_for_file(path: Path, timeout: float = 5.0) -> bool:
    """Wait until a file exists or the timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return False


def run_demo_smoke(
    *,
    profile: str | None = None,
    bundle_dir: str | None = None,
    debug: bool = False,
    startup_timeout: float = 5.0,
) -> dict:
    """Launch the demo target and exercise the real CLI against it."""

    with tempfile.TemporaryDirectory(prefix="mousecoords-demo-") as tmpdir:
        workspace = Path(tmpdir)
        state_file = workspace / "state.json"
        ready_file = workspace / "ready.txt"
        profile_target: str
        if profile:
            profile_target = profile
        else:
            profile_target = str(workspace / "demo-pack")
            create_demo_project(profile_target, name="demo_lab")

        launch_cmd = [
            sys.executable,
            "-m",
            "mousecoords",
            "demo",
            "launch",
            "--state-file",
            str(state_file),
            "--ready-file",
            str(ready_file),
            "--duration",
            "8",
        ]
        env = os.environ.copy()
        app = subprocess.Popen(
            launch_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            if not _wait_for_file(ready_file, timeout=startup_timeout):
                stdout, stderr = app.communicate(timeout=2)
                return {
                    "success": False,
                    "profile": profile,
                    "error": "Demo app did not become ready.",
                    "launch_stdout": stdout,
                    "launch_stderr": stderr,
                }

            time.sleep(0.25)
            run_cmd = [
                sys.executable,
                "-m",
                "mousecoords",
                "run",
                "-p",
                profile_target,
                "--once",
                "--json",
            ]
            if debug:
                run_cmd.append("--debug")
            if bundle_dir:
                run_cmd.extend(["--bundle-dir", bundle_dir])

            run_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            try:
                automation = json.loads(run_result.stdout)
            except json.JSONDecodeError as exc:
                return {
                    "success": False,
                    "profile": profile_target,
                    "error": f"Could not parse automation output: {exc}",
                    "run_stdout": run_result.stdout,
                    "run_stderr": run_result.stderr,
                    "run_returncode": run_result.returncode,
                }

            time.sleep(0.25)
            if app.poll() is None:
                app.send_signal(signal.SIGTERM)
            try:
                launch_stdout, launch_stderr = app.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                app.kill()
                launch_stdout, launch_stderr = app.communicate(timeout=3)

            demo_state = json.loads(state_file.read_text()) if state_file.exists() else {}
            success = (
                run_result.returncode == 0
                and automation.get("stats", {}).get("Total Clicks", 0) >= len(DEMO_BUTTONS)
                and demo_state.get("total_clicks", 0) >= len(DEMO_BUTTONS)
            )
            return {
                "success": success,
                "profile": profile_target,
                "automation": automation,
                "demo_state": demo_state,
                "run_returncode": run_result.returncode,
                "run_stderr": run_result.stderr,
                "launch_stdout": launch_stdout,
                "launch_stderr": launch_stderr,
            }
        finally:
            if app.poll() is None:
                app.kill()
                app.communicate(timeout=3)
