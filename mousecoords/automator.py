"""Command implementations for mousecoords.

This module deliberately keeps desktop-only imports inside command
functions so the package can be imported in headless environments.
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread


def _get_pyautogui():
    import pyautogui

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    return pyautogui


# ======================================================================
# Commands
# ======================================================================


def cmd_coords(args):
    """Enhanced coordinate grabber with color readout."""
    import keyboard

    from .vision import VisionEngine

    pyautogui = _get_pyautogui()
    vision = VisionEngine()
    print("mousecoords v2.0 -- Coordinate Grabber")
    print("Press SPACE to capture coordinates, Q to quit")
    print("-" * 45)

    while True:
        event = keyboard.read_event(suppress=False)
        if event.event_type != "down":
            continue
        if event.name == "q":
            break
        if event.name == "space":
            x, y = pyautogui.position()
            color = vision.get_pixel_color(x, y)
            print(f"  ({x:>5}, {y:>5})  RGB{color}")

    print("Done.")
    return 0



def cmd_run(args):
    """Run game automation with vision, state machine, and TUI."""
    from .config import get_default_profile, get_profiles_dir, load_profile
    from .state_machine import StateMachine
    from .tui import Dashboard, HAS_RICH
    from .vision import VisionEngine

    pyautogui = _get_pyautogui()

    if args.profile:
        profile_path = args.profile
        if not Path(profile_path).exists():
            profile_path = str(get_profiles_dir() / f"{args.profile}.yaml")
        profile = load_profile(profile_path)
    else:
        profile = get_default_profile()

    vision = VisionEngine(color_tolerance=profile.color_tolerance)
    sm = StateMachine(profile)

    dashboard = None
    if HAS_RICH and not args.simple:
        dashboard = Dashboard(title=f"mousecoords -- {profile.game or profile.name}")
        dashboard.set_mode("Game Automation")

    def on_transition(old, new, trigger):
        msg = f"{old.value} -> {new.value} (triggered by {trigger})"
        if dashboard:
            dashboard.log_state(msg)
        else:
            print(f"[STATE] {msg}")

    def on_action(result):
        if dashboard:
            dashboard.log_action(f"Clicked {result.button_name}")
        else:
            print(f"[CLICK] {result.button_name}")

    sm.on_transition(on_transition)
    sm.on_action(on_action)

    overlay = None
    if args.overlay:
        try:
            from .overlay import Overlay

            overlay = Overlay()
            overlay.start()
            for btn in profile.buttons:
                overlay.add_marker(btn.name, btn.x, btn.y)
        except Exception as exc:
            msg = f"Overlay unavailable: {exc}"
            if dashboard:
                dashboard.log_warning(msg)
            else:
                print(f"[WARN] {msg}")

    ocr_data: dict = {}
    if args.ocr and profile.ocr_regions:

        def ocr_loop():
            while True:
                for name, region in profile.ocr_regions.items():
                    val = vision.read_number(region)
                    if val is not None:
                        ocr_data[name] = val
                time.sleep(2)

        Thread(target=ocr_loop, daemon=True).start()

    def automation_loop():
        while True:
            try:
                buttons = sm.monitored_buttons

                for btn in buttons:
                    if not sm.can_click(btn.name):
                        if dashboard:
                            status = "cooldown" if sm.is_on_cooldown(btn.name) else "disabled"
                            dashboard.set_button_status(btn.name, status)
                        continue

                    detected = False
                    click_x, click_y = btn.x, btn.y

                    if btn.template:
                        center = vision.find_button_by_template(btn.template)
                        if center:
                            detected = True
                            click_x, click_y = center
                    else:
                        detected = vision.find_button_by_color(btn.x, btn.y, btn.color)

                    if detected:
                        if dashboard:
                            dashboard.set_button_status(btn.name, "active")
                        pyautogui.click(click_x, click_y)
                        sm.record_action(btn.name)

                        if btn.name == "Antimatter Galaxies":
                            break
                    else:
                        if dashboard:
                            dashboard.set_button_status(btn.name, "ready")

                stats = sm.stats.to_dict()
                if ocr_data:
                    for key, value in ocr_data.items():
                        stats[f"OCR:{key}"] = f"{value:,.0f}"

                if dashboard:
                    dashboard.update_stats(stats)
                    dashboard.set_state(sm.phase.value.upper())

                time.sleep(profile.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                if dashboard:
                    dashboard.log_error(str(exc))
                else:
                    print(f"[ERROR] {exc}")
                time.sleep(1)

    if dashboard:
        live = dashboard.start()
        dashboard.log_info(f"Profile: {profile.name}")
        dashboard.log_info(f"Monitoring {len(profile.buttons)} buttons")
        dashboard.log_info(
            f"Resolution: {profile.resolution[0]}x{profile.resolution[1]}"
        )
        if ocr_data or profile.ocr_regions:
            dashboard.log_info(f"OCR regions: {len(profile.ocr_regions)}")
        dashboard.log_info("Press Ctrl+C to stop")
        dashboard.set_state(sm.phase.value.upper())

        with live:
            automation_loop()
        dashboard.stop()
    else:
        print(f"Profile: {profile.name}")
        print(f"Monitoring {len(profile.buttons)} buttons")
        print("Press Ctrl+C to stop")
        print("-" * 45)
        automation_loop()

    if overlay:
        overlay.stop()

    print("\nFinal Statistics:")
    for key, value in sm.stats.to_dict().items():
        print(f"  {key}: {value}")

    return 0


cmd_automate = cmd_run



def cmd_record(args):
    """Record a macro."""
    from .recorder import MacroRecorder

    recorder = MacroRecorder(record_moves=args.moves)

    print("mousecoords v2.0 -- Macro Recorder")
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

    return 0



def cmd_play(args):
    """Play back a recorded macro."""
    from .recorder import MacroRecorder

    recorder = MacroRecorder()
    recorder.load(args.input)

    print("mousecoords v2.0 -- Macro Playback")
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
    return 0



def cmd_capture(args):
    """Capture a button template for CV-based detection."""
    import keyboard

    from .vision import VisionEngine

    pyautogui = _get_pyautogui()
    vision = VisionEngine()

    print("mousecoords v2.0 -- Template Capture")
    print("Position mouse at TOP-LEFT of button, press SPACE")
    keyboard.wait("space")
    x1, y1 = pyautogui.position()
    print(f"  Top-left: ({x1}, {y1})")

    print("Position mouse at BOTTOM-RIGHT, press SPACE")
    keyboard.wait("space")
    x2, y2 = pyautogui.position()
    print(f"  Bottom-right: ({x2}, {y2})")

    region = (x1, y1, x2 - x1, y2 - y1)
    template = vision.capture_template(region)

    name = args.name or f"button_{x1}_{y1}"
    output_dir = args.output or "templates"
    vision.save_template(template, name, output_dir)
    print(f"  Saved: {output_dir}/{name}.png ({region[2]}x{region[3]}px)")
    print(f"\nTo use in a profile, set template: \"{output_dir}/{name}.png\"")
    return 0



def cmd_profile(args):
    """Manage automation profiles."""
    from .config import get_default_profile, get_profiles_dir, list_profiles, save_profile

    if args.action == "list":
        profiles = list_profiles()
        if profiles:
            print("Available profiles:")
            for profile in profiles:
                print(f"  - {profile}")
        else:
            print("No profiles found. Use 'profile create' to generate the default.")
        return 0

    if args.action == "create":
        profile = get_default_profile()
        if args.name:
            profile.name = args.name
        path = str(get_profiles_dir() / f"{profile.name}.yaml")
        save_profile(profile, path)
        print(f"Created: {path}")
        print("Edit the YAML to customize buttons, colors, limits, and OCR regions.")
        return 0

    name = args.name or "antimatter_dimensions"
    path = str(get_profiles_dir() / f"{name}.yaml")
    if Path(path).exists():
        print(Path(path).read_text())
    else:
        print(f"Profile '{name}' not found. Run 'profile list' to see available profiles.")
    return 0



def cmd_ocr(args):
    """Read text from a screen region using OCR."""
    import keyboard

    from .vision import VisionEngine

    pyautogui = _get_pyautogui()
    vision = VisionEngine()

    print("mousecoords v2.0 -- OCR Reader")
    print("Position at TOP-LEFT of text region, press SPACE")
    keyboard.wait("space")
    x1, y1 = pyautogui.position()
    print(f"  Top-left: ({x1}, {y1})")

    print("Position at BOTTOM-RIGHT, press SPACE")
    keyboard.wait("space")
    x2, y2 = pyautogui.position()
    print(f"  Bottom-right: ({x2}, {y2})")

    region = (x1, y1, x2 - x1, y2 - y1)

    text = vision.read_text(region)
    print(f"\nOCR Result:\n  {text}")

    number = vision.read_number(region)
    if number is not None:
        print(f"  Parsed number: {number:,.2f}")

    return 0


# ======================================================================
# Compatibility entry point
# ======================================================================


def main(argv: list[str] | None = None) -> int:
    from .cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
