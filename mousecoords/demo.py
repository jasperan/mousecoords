"""Deterministic demo target used for onboarding and end-to-end validation."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import ButtonConfig, Profile, StateConfig, save_profile
from .studio import create_studio_project

DEMO_PROFILE_NAME = "desktop_demo"
DEMO_WINDOW_TITLE = "mousecoords Demo Lab"
DEMO_WINDOW_WIDTH = 420
DEMO_WINDOW_HEIGHT = 260
DEMO_WINDOW_X = 120
DEMO_WINDOW_Y = 120
DEMO_BUTTONS = (
    {"name": "Harvest", "x1": 40, "y1": 90, "x2": 140, "y2": 150, "color": (220, 70, 70)},
    {"name": "Boost", "x1": 160, "y1": 90, "x2": 260, "y2": 150, "color": (70, 170, 70)},
    {"name": "Reset", "x1": 280, "y1": 90, "x2": 380, "y2": 150, "color": (70, 120, 220)},
)


def get_demo_profile_dir() -> Path:
    """Return the bundled demo profile-pack directory."""
    return Path(__file__).resolve().parent.parent / "profiles" / DEMO_PROFILE_NAME


def get_demo_profile_path() -> Path:
    """Return the canonical profile file for the bundled demo scenario."""
    return get_demo_profile_dir() / "profile.yaml"


def build_demo_profile(*, name: str = DEMO_PROFILE_NAME) -> Profile:
    """Return a ready-to-run profile for the built-in demo target."""
    buttons = [
        ButtonConfig(
            name=button["name"],
            x=DEMO_WINDOW_X + ((button["x1"] + button["x2"]) // 2),
            y=DEMO_WINDOW_Y + ((button["y1"] + button["y2"]) // 2),
            color=button["color"],
            cooldown=0.2,
        )
        for button in DEMO_BUTTONS
    ]
    states = [
        StateConfig(
            name="default",
            monitor_buttons=[button["name"] for button in DEMO_BUTTONS],
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


def read_demo_state(path: str | Path | None) -> dict[str, Any]:
    """Read a previously-written demo state file."""
    if path is None:
        return {}
    state_path = Path(path)
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text())


def write_demo_state(path: str | Path | None, payload: dict[str, Any]):
    """Persist demo state as JSON when a path is configured."""
    if path is None:
        return
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def create_demo_project(
    output_dir: str | Path,
    *,
    name: str = DEMO_PROFILE_NAME,
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
    """Launch the deterministic demo target and block until it closes."""
    import tkinter as tk

    root = tk.Tk()
    root.title(DEMO_WINDOW_TITLE)
    root.geometry(f"{DEMO_WINDOW_WIDTH}x{DEMO_WINDOW_HEIGHT}+{DEMO_WINDOW_X}+{DEMO_WINDOW_Y}")
    root.resizable(False, False)
    root.configure(bg="#f5f5f5")
    root.attributes("-topmost", True)
    root.overrideredirect(True)

    state: dict[str, Any] = {
        "title": DEMO_WINDOW_TITLE,
        "started_at": time.time(),
        "total_clicks": 0,
        "last_button": None,
        "counters": {button["name"]: 0 for button in DEMO_BUTTONS},
        "closed": False,
    }

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
        text=DEMO_WINDOW_TITLE,
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

    def flush_state(*, ready: bool = False, closed: bool = False):
        root.update_idletasks()
        state["ready"] = ready or state.get("ready", False)
        state["closed"] = closed
        state["updated_at"] = time.time()
        write_demo_state(state_file, state)
        if ready_file is not None and state["ready"]:
            ready_path = Path(ready_file)
            ready_path.parent.mkdir(parents=True, exist_ok=True)
            ready_path.write_text("ready\n")

    def on_click(name: str):
        state["total_clicks"] += 1
        state["last_button"] = name
        state["counters"][name] += 1
        canvas.itemconfigure(subtitle_item, text=f"Last click: {name}")
        canvas.itemconfigure(
            footer_item,
            text=(
                "Total clicks: "
                f"{state['total_clicks']} | "
                + ", ".join(f"{key}={value}" for key, value in state["counters"].items())
            ),
        )
        flush_state()

    for button in DEMO_BUTTONS:
        tag = f"button:{button['name']}"
        fill = "#%02x%02x%02x" % button["color"]
        canvas.create_rectangle(
            button["x1"],
            button["y1"],
            button["x2"],
            button["y2"],
            fill=fill,
            outline="#202020",
            width=2,
            tags=(tag,),
        )
        canvas.create_text(
            (button["x1"] + button["x2"]) / 2,
            button["y2"] + 16,
            text=button["name"],
            fill="#202020",
            font=("TkDefaultFont", 11, "bold"),
        )
        canvas.tag_bind(tag, "<Button-1>", lambda _event, name=button["name"]: on_click(name))

    def close_app():
        if state.get("closed"):
            return
        flush_state(closed=True)
        root.destroy()

    def on_signal(_signum, _frame):
        root.after(0, close_app)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    root.after(200, lambda: flush_state(ready=True))
    if duration is not None and duration > 0:
        root.after(int(duration * 1000), close_app)

    root.bind("<Escape>", lambda _event: close_app())
    root.protocol("WM_DELETE_WINDOW", close_app)
    try:
        root.mainloop()
    finally:
        if not state.get("closed"):
            state["closed"] = True
            state["updated_at"] = time.time()
            write_demo_state(state_file, state)


def run_demo_app(**kwargs):
    """Backward-compatible alias for older callers."""
    launch_demo_app(**kwargs)


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
) -> dict[str, Any]:
    """Launch the demo target and exercise the real CLI against it."""

    with tempfile.TemporaryDirectory(prefix="mousecoords-demo-") as tmpdir:
        workspace = Path(tmpdir)
        state_file = workspace / "state.json"
        ready_file = workspace / "ready.txt"
        profile_target = profile or str(workspace / "demo-pack")

        if profile is None:
            create_demo_project(profile_target, name="demo_lab")

        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path.cwd()))
        app = subprocess.Popen(
            [
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
            ],
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
                    "profile": profile_target,
                    "error": "Demo app did not become ready.",
                    "launch_stdout": stdout,
                    "launch_stderr": stderr,
                }

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

            if app.poll() is None:
                app.send_signal(signal.SIGTERM)
            try:
                launch_stdout, launch_stderr = app.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                app.kill()
                launch_stdout, launch_stderr = app.communicate(timeout=3)

            demo_state = read_demo_state(state_file)
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
