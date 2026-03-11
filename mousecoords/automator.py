"""Main automation orchestrator and CLI entry point.

Ties together config, vision, state machine, TUI, overlay, recorder,
and OCR into a unified command-line interface.

Usage:
    mousecoords coords          # grab mouse coordinates
    mousecoords automate        # run game automation
    mousecoords record          # record a macro
    mousecoords play FILE       # play back a macro
    mousecoords capture         # capture a button template
    mousecoords profile list    # manage profiles
    mousecoords ocr             # read text from screen region
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from threading import Thread

import pyautogui

from .config import (
    load_profile, save_profile, get_default_profile,
    list_profiles, get_profiles_dir,
)
from .vision import VisionEngine
from .state_machine import StateMachine, GamePhase
from .tui import Dashboard, HAS_RICH
from .recorder import MacroRecorder

# Disable pyautogui safety features for automation
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


# ======================================================================
# Commands
# ======================================================================

def cmd_coords(args):
    """Enhanced coordinate grabber with color readout."""
    import keyboard

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


def cmd_automate(args):
    """Run game automation with vision, state machine, and TUI."""
    # Load profile
    if args.profile:
        profile_path = args.profile
        if not Path(profile_path).exists():
            profile_path = str(get_profiles_dir() / f"{args.profile}.yaml")
        profile = load_profile(profile_path)
    else:
        profile = get_default_profile()

    vision = VisionEngine(color_tolerance=profile.color_tolerance)
    sm = StateMachine(profile)

    # --- Dashboard setup ---
    dashboard = None
    if HAS_RICH and not args.simple:
        dashboard = Dashboard(
            title=f"mousecoords -- {profile.game or profile.name}",
        )
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

    # --- Overlay (optional) ---
    overlay = None
    if args.overlay:
        try:
            from .overlay import Overlay
            overlay = Overlay()
            overlay.start()
            for btn in profile.buttons:
                overlay.add_marker(btn.name, btn.x, btn.y)
        except Exception as e:
            msg = f"Overlay unavailable: {e}"
            if dashboard:
                dashboard.log_warning(msg)
            else:
                print(f"[WARN] {msg}")

    # --- OCR thread (optional) ---
    ocr_data: dict = {}
    if args.ocr and profile.ocr_regions:
        def ocr_loop():
            while True:
                for name, region in profile.ocr_regions.items():
                    val = vision.read_number(region)
                    if val is not None:
                        ocr_data[name] = val
                time.sleep(2)  # OCR is expensive, poll slowly

        Thread(target=ocr_loop, daemon=True).start()

    # --- Main automation loop ---
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

                    # Detect button: template matching or color check
                    detected = False
                    click_x, click_y = btn.x, btn.y

                    if btn.template:
                        center = vision.find_button_by_template(btn.template)
                        if center:
                            detected = True
                            click_x, click_y = center
                    else:
                        detected = vision.find_button_by_color(
                            btn.x, btn.y, btn.color,
                        )

                    if detected:
                        if dashboard:
                            dashboard.set_button_status(btn.name, "active")
                        pyautogui.click(click_x, click_y)
                        sm.record_action(btn.name)

                        # Priority: after clicking galaxies, skip rest
                        if btn.name == "Antimatter Galaxies":
                            break
                    else:
                        if dashboard:
                            dashboard.set_button_status(btn.name, "ready")

                # Merge OCR data into stats display
                stats = sm.stats.to_dict()
                if ocr_data:
                    for k, v in ocr_data.items():
                        stats[f"OCR:{k}"] = f"{v:,.0f}"

                if dashboard:
                    dashboard.update_stats(stats)
                    dashboard.set_state(sm.phase.value.upper())

                time.sleep(profile.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                if dashboard:
                    dashboard.log_error(str(e))
                else:
                    print(f"[ERROR] {e}")
                time.sleep(1)

    # --- Run ---
    if dashboard:
        live = dashboard.start()
        dashboard.log_info(f"Profile: {profile.name}")
        dashboard.log_info(f"Monitoring {len(profile.buttons)} buttons")
        dashboard.log_info(f"Resolution: {profile.resolution[0]}x{profile.resolution[1]}")
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

    # Final stats
    print("\nFinal Statistics:")
    for k, v in sm.stats.to_dict().items():
        print(f"  {k}: {v}")


def cmd_record(args):
    """Record a macro."""
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


def cmd_play(args):
    """Play back a recorded macro."""
    recorder = MacroRecorder()
    recorder.load(args.input)

    print(f"mousecoords v2.0 -- Macro Playback")
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
    import keyboard

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
        name = args.name or "antimatter_dimensions"
        path = str(get_profiles_dir() / f"{name}.yaml")
        if Path(path).exists():
            print(Path(path).read_text())
        else:
            print(f"Profile '{name}' not found. Run 'profile list' to see available profiles.")


def cmd_ocr(args):
    """Read text from a screen region using OCR."""
    import keyboard

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
    p_prof.add_argument("action", choices=["list", "create", "show"])
    p_prof.add_argument("-n", "--name", help="Profile name")

    # ocr
    sub.add_parser("ocr", help="Read text from screen region via OCR")

    args = parser.parse_args()

    commands = {
        "coords": cmd_coords,
        "automate": cmd_automate,
        "record": cmd_record,
        "play": cmd_play,
        "capture": cmd_capture,
        "profile": cmd_profile,
        "ocr": cmd_ocr,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
