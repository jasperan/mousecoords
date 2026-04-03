"""Main automation orchestrator and CLI entry point.

Ties together config, vision, state machine, TUI, overlay, recorder,
OCR, diagnostics, and screen watcher into a unified command-line interface.

Usage:
    mousecoords coords          # grab mouse coordinates
    mousecoords automate        # run game automation
    mousecoords record          # record a macro
    mousecoords play FILE       # play back a macro
    mousecoords capture         # capture a button template
    mousecoords profile list    # manage profiles
    mousecoords ocr             # read text from screen region
    mousecoords doctor          # check system dependencies
    mousecoords watch           # monitor a pixel for color changes
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from importlib import import_module
from pathlib import Path
from queue import Queue
from threading import Thread, Event as ThreadEvent

from .config import (
    load_profile, save_profile, get_default_profile,
    list_profiles, get_profiles_dir, is_default_profile_name,
    profile_to_data, resolve_profile_target, validate_profile,
)
from .runtime import run_automation_session
from .studio import create_studio_project

# Global shutdown event for clean Ctrl+C handling
_shutdown = ThreadEvent()


def _format_gui_error(exc: Exception) -> str:
    """Normalize common display/runtime errors into readable output."""
    if isinstance(exc, KeyError) and exc.args == ("DISPLAY",):
        return "requires an active DISPLAY/GUI session"
    return str(exc) or exc.__class__.__name__


def _load_pyautogui(command_name: str):
    """Import pyautogui only when a command actually needs GUI access."""
    try:
        pyautogui = import_module("pyautogui")
    except Exception as exc:
        detail = _format_gui_error(exc)
        print(f"`mousecoords {command_name}` requires an active graphical session.")
        print(f"Reason: {detail}")
        print("Run `mousecoords doctor` for diagnostics. On headless Linux, try `xvfb-run -a ...`.")
        raise SystemExit(1)
    # Re-enable pyautogui failsafe (move mouse to corner to emergency-stop).
    # Users can disable with --no-failsafe if they know what they're doing.
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0
    return pyautogui


def _install_signal_handlers():
    """Install SIGINT/SIGTERM handlers that set the shutdown event."""
    def _handler(signum, frame):
        _shutdown.set()
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def _keyboard_module_usable() -> bool:
    """The keyboard module needs root on Linux, but is fine elsewhere."""
    return sys.platform != "linux" or os.geteuid() == 0


def _normalize_key_name(key) -> str | None:
    """Normalize keyboard or pynput key objects into lowercase names."""
    if isinstance(key, str):
        return key.lower()

    name = getattr(key, "name", None)
    if name:
        return str(name).lower()

    char = getattr(key, "char", None)
    if char:
        return str(char).lower()

    vk = getattr(key, "vk", None)
    if vk == 32:
        return "space"

    return None


def _read_keypress(valid_keys: set[str]) -> str:
    """Wait for one of the requested keys using keyboard or pynput."""
    valid = {key.lower() for key in valid_keys}

    if _keyboard_module_usable():
        try:
            import keyboard
            while True:
                event = keyboard.read_event(suppress=False)
                if event.event_type != "down":
                    continue
                name = _normalize_key_name(event.name)
                if name in valid:
                    return name
        except Exception:
            pass

    try:
        from pynput import keyboard as pyn_keyboard
    except ImportError as exc:
        options = ", ".join(sorted(valid))
        raise RuntimeError(
            f"Keyboard input requires root on Linux or the optional pynput dependency. "
            f"Install mousecoords[record] or run with sudo. Waiting for: {options}."
        ) from exc

    pressed: Queue[str] = Queue()

    def _on_press(key):
        name = _normalize_key_name(key)
        if name in valid:
            pressed.put(name)
            return False
        return None

    with pyn_keyboard.Listener(on_press=_on_press) as listener:
        name = pressed.get()
        listener.stop()
        return name


def _wait_for_key(key_name: str):
    """Wait until a specific key is pressed."""
    return _read_keypress({key_name})


# ======================================================================
# Commands
# ======================================================================

def cmd_coords(args):
    """Enhanced coordinate grabber with color readout."""
    pyautogui = _load_pyautogui("coords")
    from .vision import VisionEngine

    vision = VisionEngine()
    print("mousecoords -- Coordinate Grabber")
    print("Press SPACE to capture coordinates, Q to quit")
    print("-" * 45)

    while True:
        key = _read_keypress({"space", "q"})
        if key == "q":
            break
        if key == "space":
            x, y = pyautogui.position()
            color = vision.get_pixel_color(x, y)
            print(f"  ({x:>5}, {y:>5})  RGB{color}")

    print("Done.")


def _resolve_profile(profile_arg: str | None):
    """Resolve CLI profile input into a Profile instance."""
    profile, path, source = resolve_profile_target(profile_arg)
    return profile, str(path) if path is not None else source


def _print_json(payload: dict):
    print(json.dumps(payload, indent=2, sort_keys=False))


def _maybe_create_bundle(args, profile, result):
    if not getattr(args, "debug", False) and not getattr(args, "bundle_dir", None):
        return None

    from .bundles import collect_runtime_bundle_inputs, create_debug_bundle

    bundle_dir = Path(args.bundle_dir or "bundles")
    inputs = collect_runtime_bundle_inputs(profile=profile, result=result)
    return create_debug_bundle(bundle_dir=bundle_dir, inputs=inputs)


def _run_command(args, *, command_name: str, mode_label: str):
    """Shared execution path for `run` and legacy `automate`."""
    try:
        profile, _ = _resolve_profile(args.profile)
    except FileNotFoundError as exc:
        print(str(exc))
        raise SystemExit(1)

    pyautogui = _load_pyautogui(command_name)
    if args.no_failsafe:
        pyautogui.FAILSAFE = False

    from .vision import VisionEngine

    vision = VisionEngine(color_tolerance=profile.color_tolerance)
    _shutdown.clear()
    _install_signal_handlers()

    result = run_automation_session(
        profile=profile,
        vision=vision,
        pyautogui=pyautogui,
        shutdown_event=_shutdown,
        mode=mode_label,
        overlay_enabled=args.overlay,
        ocr_enabled=args.ocr,
        simple=args.simple,
        dry_run=getattr(args, "dry_run", False),
        once=getattr(args, "once", False),
        duration=getattr(args, "duration", None),
        render_output=not getattr(args, "json", False),
    )
    bundle_path = _maybe_create_bundle(args, profile, result)
    payload = result.to_dict()
    if bundle_path is not None:
        payload["bundle_path"] = str(bundle_path)

    if getattr(args, "json", False):
        _print_json(payload)
        return payload

    print("\nFinal Statistics:")
    for key, value in result.stats.items():
        print(f"  {key}: {value}")
    if bundle_path is not None:
        print(f"\nDebug bundle: {bundle_path}")
    return payload


def cmd_automate(args):
    """Run game automation with vision, state machine, and TUI."""
    _run_command(args, command_name="automate", mode_label="Game Automation")


def cmd_run(args):
    """Run automation with safer execution controls."""
    _run_command(args, command_name="run", mode_label="Automation Run")


def cmd_bundle(args):
    """Inspect exported debug bundles."""
    from zipfile import BadZipFile
    from .bundles import inspect_bundle

    try:
        info = inspect_bundle(args.bundle)
    except FileNotFoundError:
        print(f"Bundle not found: {args.bundle}")
        raise SystemExit(1)
    except (BadZipFile, KeyError, ValueError) as exc:
        print(f"Could not inspect bundle '{args.bundle}': {exc}")
        raise SystemExit(1)

    if args.json:
        _print_json(info)
        return

    print(f"Bundle: {args.bundle}")
    print("Manifest:")
    for key, value in info["manifest"].items():
        print(f"{key}: {value}")
    if info["files"]:
        print("Files:")
        for name in info["files"]:
            print(f"  - {name}")


def cmd_profile_validate(args):
    """Validate a profile and report actionable issues."""
    target = args.name or args.target or args.path or get_default_profile().name
    try:
        profile, resolved_path = _resolve_profile(target)
    except (FileNotFoundError, OSError, ValueError, TypeError) as exc:
        payload = {
            "profile_name": target,
            "source": str(target),
            "ok": False,
            "issues": [
                {
                    "level": "error",
                    "code": "profile_load_failed",
                    "message": str(exc),
                }
            ],
        }
        if args.json:
            _print_json(payload)
        else:
            print(f"Profile '{target}' could not be loaded:")
            print(f"  - [error] profile_load_failed: {exc}")
        raise SystemExit(1)

    validation = validate_profile(profile, profile_path=resolved_path)
    payload = validation.to_dict()
    if args.json:
        _print_json(payload)
        if not validation.ok:
            raise SystemExit(1)
        return

    if validation.ok:
        print(f"Profile '{profile.name}' is valid.")
        return
    print(f"Profile '{profile.name}' has {len(validation.issues)} issue(s):")
    for issue in validation.issues:
        print(f"  - [{issue.level}] {issue.code}: {issue.message}")
    raise SystemExit(1)


def cmd_automate_legacy(args):
    """Compatibility wrapper retained for existing users."""
    cmd_automate(args)


def cmd_record(args):
    """Record a macro."""
    _load_pyautogui("record")

    from .recorder import MacroRecorder

    recorder = MacroRecorder(record_moves=args.moves)

    print("mousecoords -- Macro Recorder")
    print("Recording starts NOW. Press ESC to stop.")
    print("-" * 45)

    recorder.start_recording()

    try:
        while recorder.recording:
            time.sleep(0.1)
    except KeyboardInterrupt:
        recorder.stop_recording()

    events = recorder.events
    print(f"\nRecorded {len(events)} events")

    if events:
        output = args.output or "recordings/macro.json"
        recorder.save(output)
        print(f"Saved to {output}")
    else:
        print("No events recorded.")


def cmd_play(args):
    """Play back a recorded macro."""
    _load_pyautogui("play")

    from .recorder import MacroRecorder

    recorder = MacroRecorder()
    recorder.load(args.input)

    print(f"mousecoords -- Macro Playback")
    print(f"  File:   {args.input}")
    print(f"  Events: {len(recorder.events)}")
    print(f"  Speed:  {args.speed}x")
    print(f"  Loop:   {args.loop}")
    print("-" * 45)
    print("Starting in 3 seconds...")
    time.sleep(3)

    try:
        recorder.play(speed=args.speed, loop=args.loop)
    except KeyboardInterrupt:
        pass

    print("Playback complete.")


def cmd_capture(args):
    """Capture a button template for CV-based detection."""
    pyautogui = _load_pyautogui("capture")
    from .vision import VisionEngine

    vision = VisionEngine()

    print("mousecoords -- Template Capture")
    print("Position mouse at TOP-LEFT of button, press SPACE")
    _wait_for_key("space")
    x1, y1 = pyautogui.position()
    print(f"  Top-left: ({x1}, {y1})")

    print("Position mouse at BOTTOM-RIGHT, press SPACE")
    _wait_for_key("space")
    x2, y2 = pyautogui.position()
    print(f"  Bottom-right: ({x2}, {y2})")

    region = (x1, y1, x2 - x1, y2 - y1)
    template = vision.capture_template(region)

    name = args.name or f"button_{x1}_{y1}"
    output_dir = args.output or "templates"
    vision.save_template(template, name, output_dir)
    print(f"  Saved: {output_dir}/{name}.png ({region[2]}x{region[3]}px)")
    print(f"\nTo use in a profile, set template: \"{output_dir}/{name}.png\"")


def cmd_profile(args):
    """Manage automation profiles."""
    if args.action == "list":
        profiles = list_profiles()
        if profiles:
            print("Available profiles:")
            for p in profiles:
                print(f"  - {p}")
        else:
            print("No profiles found. Use 'profile create' to generate the default.")

    elif args.action == "create":
        profile = get_default_profile()
        if args.name:
            profile.name = args.name
        path = str(get_profiles_dir() / f"{profile.name}.yaml")
        save_profile(profile, path)
        print(f"Created: {path}")
        print("Edit the YAML to customize buttons, colors, limits, and OCR regions.")

    elif args.action == "show":
        name = args.name or args.target or get_default_profile().name
        try:
            _, resolved_path, _ = resolve_profile_target(name)
        except FileNotFoundError:
            resolved_path = None

        if resolved_path is not None:
            print(Path(resolved_path).read_text())
        elif is_default_profile_name(name):
            import yaml

            profile = get_default_profile()
            data = profile_to_data(profile)
            print(yaml.dump(data, default_flow_style=False, sort_keys=False))
        else:
            print(f"Profile '{name}' not found. Run 'profile list' to see available profiles.")


def cmd_studio_new(args):
    """Create a minimal profile-pack scaffold."""
    try:
        project = create_studio_project(
            args.output,
            name=args.name,
            from_profile=args.from_profile,
            force=args.force,
        )
    except FileExistsError as exc:
        print(str(exc))
        raise SystemExit(1)
    except FileNotFoundError as exc:
        print(str(exc))
        raise SystemExit(1)

    print(f"Created studio scaffold: {project.output_dir}")
    print(f"  Profile: {project.profile_path}")
    print(f"  Source:  {project.source}")
    print("  Assets:  assets/templates/, assets/reference/")


def cmd_studio(args):
    """Dispatch studio subcommands."""
    if args.studio_action == "new":
        cmd_studio_new(args)
        return
    print("Use `mousecoords studio new --output <dir>` to create a profile pack scaffold.")
    raise SystemExit(1)


def cmd_ocr(args):
    """Read text from a screen region using OCR."""
    pyautogui = _load_pyautogui("ocr")
    from .vision import VisionEngine

    vision = VisionEngine()

    print("mousecoords -- OCR Reader")
    print("Position at TOP-LEFT of text region, press SPACE")
    _wait_for_key("space")
    x1, y1 = pyautogui.position()
    print(f"  Top-left: ({x1}, {y1})")

    print("Position at BOTTOM-RIGHT, press SPACE")
    _wait_for_key("space")
    x2, y2 = pyautogui.position()
    print(f"  Bottom-right: ({x2}, {y2})")

    region = (x1, y1, x2 - x1, y2 - y1)

    text = vision.read_text(region)
    print(f"\nOCR Result:\n  {text}")

    number = vision.read_number(region)
    if number is not None:
        print(f"  Parsed number: {number:,.2f}")


def cmd_doctor(args):
    """Run system diagnostics."""
    from .doctor import collect_diagnostics, print_diagnostics
    results = collect_diagnostics()
    print_diagnostics(results)


def cmd_watch(args):
    """Monitor a screen pixel for color changes."""
    if args.pick:
        pyautogui = _load_pyautogui("watch")
        print("mousecoords -- Screen Watcher")
        print("Position mouse at the pixel to watch, press SPACE")
        _wait_for_key("space")
        x, y = pyautogui.position()
    else:
        x, y = args.x, args.y

    if x is None or y is None:
        print("Specify coordinates: mousecoords watch -x 100 -y 200")
        print("Or use --pick to select with your mouse.")
        sys.exit(1)

    _load_pyautogui("watch")
    from .watcher import ScreenWatcher
    watcher = ScreenWatcher(
        x=x, y=y,
        threshold=args.threshold,
        poll_interval=args.interval,
    )
    watcher.watch(duration=args.duration)


# ======================================================================
# CLI
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="mousecoords",
        description="GUI automation toolkit: computer vision, macro recording, game automation",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # coords
    sub.add_parser("coords", help="Capture mouse coordinates with color readout")

    # automate
    p_auto = sub.add_parser("automate", help="Run game automation")
    p_auto.add_argument("-p", "--profile", help="Profile name or YAML path")
    p_auto.add_argument("--overlay", action="store_true", help="Show visual overlay")
    p_auto.add_argument("--ocr", action="store_true", help="Enable OCR reading")
    p_auto.add_argument("--simple", action="store_true", help="Plain output (no Rich)")
    p_auto.add_argument("--dry-run", action="store_true", help="Detect actions without clicking")
    p_auto.add_argument("--once", action="store_true", help="Run a single automation cycle")
    p_auto.add_argument("--duration", type=float, default=None, help="Stop after N seconds")
    p_auto.add_argument("--json", action="store_true", help="Print structured JSON summary")
    p_auto.add_argument("--debug", action="store_true", help="Export a debug bundle after the run")
    p_auto.add_argument("--bundle-dir", help="Directory for exported debug bundles")
    p_auto.add_argument("--no-failsafe", action="store_true",
                        help="Disable pyautogui corner failsafe")

    # run
    p_run = sub.add_parser("run", help="Run automation with safer execution controls")
    p_run.add_argument("-p", "--profile", help="Profile name or YAML path")
    p_run.add_argument("--overlay", action="store_true", help="Show visual overlay")
    p_run.add_argument("--ocr", action="store_true", help="Enable OCR reading")
    p_run.add_argument("--simple", action="store_true", help="Plain output (no Rich)")
    p_run.add_argument("--dry-run", action="store_true", help="Detect actions without clicking")
    p_run.add_argument("--once", action="store_true", help="Run a single automation cycle")
    p_run.add_argument("--duration", type=float, default=None, help="Stop after N seconds")
    p_run.add_argument("--json", action="store_true", help="Print structured JSON summary")
    p_run.add_argument("--debug", action="store_true", help="Export a debug bundle after the run")
    p_run.add_argument("--bundle-dir", help="Directory for exported debug bundles")
    p_run.add_argument("--no-failsafe", action="store_true",
                       help="Disable pyautogui corner failsafe")

    # record
    p_rec = sub.add_parser("record", help="Record a macro")
    p_rec.add_argument("-o", "--output", help="Output JSON path")
    p_rec.add_argument("--moves", action="store_true", help="Also record mouse movement")

    # play
    p_play = sub.add_parser("play", help="Replay a macro")
    p_play.add_argument("input", help="Macro JSON file")
    p_play.add_argument("-s", "--speed", type=float, default=1.0, help="Speed multiplier")
    p_play.add_argument("-l", "--loop", action="store_true", help="Loop forever")

    # capture
    p_cap = sub.add_parser("capture", help="Capture button template for CV matching")
    p_cap.add_argument("-n", "--name", help="Template name")
    p_cap.add_argument("-o", "--output", help="Output directory")

    # profile
    p_prof = sub.add_parser("profile", help="Manage automation profiles")
    p_prof.add_argument("action", choices=["list", "create", "show", "validate"])
    p_prof.add_argument("target", nargs="?", help="Profile name or YAML path")
    p_prof.add_argument("-n", "--name", help="Profile name")
    p_prof.add_argument("--path", help="Explicit profile path to validate")
    p_prof.add_argument("--json", action="store_true", help="Print structured JSON validation output")

    # ocr
    sub.add_parser("ocr", help="Read text from screen region via OCR")

    # doctor
    sub.add_parser("doctor", help="Check system dependencies and environment")

    # bundle
    p_bundle = sub.add_parser("bundle", help="Inspect exported debug bundles")
    p_bundle_sub = p_bundle.add_subparsers(dest="bundle_action")
    p_bundle_inspect = p_bundle_sub.add_parser("inspect", help="Print manifest details from a bundle")
    p_bundle_inspect.add_argument("bundle", help="Path to bundle zip")
    p_bundle_inspect.add_argument("--json", action="store_true", help="Print JSON output")

    # studio
    p_studio = sub.add_parser("studio", help="Create and manage profile-pack scaffolds")
    p_studio_sub = p_studio.add_subparsers(dest="studio_action")
    p_studio_new = p_studio_sub.add_parser("new", help="Create a new profile-pack scaffold")
    p_studio_new.add_argument("--output", required=True, help="Directory for the new profile pack")
    p_studio_new.add_argument("--name", help="Profile name to write into profile.yaml")
    p_studio_new.add_argument("--from-profile", help="Existing profile name or path to copy from")
    p_studio_new.add_argument("--force", action="store_true", help="Overwrite an existing non-empty output directory")

    # watch
    p_watch = sub.add_parser("watch", help="Monitor a pixel for color changes")
    p_watch.add_argument("-x", type=int, default=None, help="X coordinate")
    p_watch.add_argument("-y", type=int, default=None, help="Y coordinate")
    p_watch.add_argument("--pick", action="store_true",
                         help="Pick coordinates with mouse (press SPACE)")
    p_watch.add_argument("-t", "--threshold", type=float, default=10.0,
                         help="Color change threshold (default: 10.0)")
    p_watch.add_argument("-i", "--interval", type=float, default=0.5,
                         help="Poll interval in seconds (default: 0.5)")
    p_watch.add_argument("-d", "--duration", type=float, default=0,
                         help="Watch duration in seconds (0=forever)")

    args = parser.parse_args()

    commands = {
        "coords": cmd_coords,
        "automate": cmd_automate_legacy,
        "run": cmd_run,
        "record": cmd_record,
        "play": cmd_play,
        "capture": cmd_capture,
        "profile": cmd_profile,
        "ocr": cmd_ocr,
        "doctor": cmd_doctor,
        "watch": cmd_watch,
        "bundle": cmd_bundle,
        "studio": cmd_studio,
    }

    if args.command == "bundle" and args.bundle_action != "inspect":
        p_bundle.print_help()
        return
    if args.command == "studio" and args.studio_action != "new":
        p_studio.print_help()
        return

    if args.command in commands:
        if args.command == "profile" and args.action == "validate":
            cmd_profile_validate(args)
        else:
            commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
