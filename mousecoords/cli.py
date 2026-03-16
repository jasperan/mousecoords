"""Headless-safe CLI entry point for mousecoords."""

from __future__ import annotations

import argparse

from .automator import (
    cmd_capture,
    cmd_coords,
    cmd_ocr,
    cmd_play,
    cmd_profile,
    cmd_record,
    cmd_run,
)
from .doctor import cmd_doctor


DESCRIPTION = (
    "GUI automation toolkit with a headless-safe CLI shell, diagnostics, "
    "and future studio commands"
)


def _not_implemented(command_name: str):
    def runner(args):
        print(f"{command_name} is not implemented yet.")
        return 1

    return runner



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mousecoords", description=DESCRIPTION)
    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_doctor = sub.add_parser("doctor", help="Inspect display and optional dependencies")
    p_doctor.set_defaults(func=cmd_doctor)

    p_run = sub.add_parser("run", aliases=["automate"], help="Run game automation")
    p_run.add_argument("-p", "--profile", help="Profile name or YAML path")
    p_run.add_argument("--overlay", action="store_true", help="Show visual overlay")
    p_run.add_argument("--ocr", action="store_true", help="Enable OCR reading")
    p_run.add_argument("--simple", action="store_true", help="Plain output (no Rich)")
    p_run.set_defaults(func=cmd_run)

    p_studio = sub.add_parser("studio", help="Launch the future Studio experience")
    p_studio.set_defaults(func=_not_implemented("studio"))

    p_bundle = sub.add_parser("bundle", help="Bundle assets for future Studio workflows")
    p_bundle.set_defaults(func=_not_implemented("bundle"))

    p_coords = sub.add_parser("coords", help="Capture mouse coordinates with color readout")
    p_coords.set_defaults(func=cmd_coords)

    p_rec = sub.add_parser("record", help="Record a macro")
    p_rec.add_argument("-o", "--output", help="Output JSON path")
    p_rec.add_argument("--moves", action="store_true", help="Also record mouse movement")
    p_rec.set_defaults(func=cmd_record)

    p_play = sub.add_parser("play", help="Replay a macro")
    p_play.add_argument("input", help="Macro JSON file")
    p_play.add_argument("-s", "--speed", type=float, default=1.0, help="Speed multiplier")
    p_play.add_argument("-l", "--loop", action="store_true", help="Loop forever")
    p_play.set_defaults(func=cmd_play)

    p_cap = sub.add_parser("capture", help="Capture button template for CV matching")
    p_cap.add_argument("-n", "--name", help="Template name")
    p_cap.add_argument("-o", "--output", help="Output directory")
    p_cap.set_defaults(func=cmd_capture)

    p_prof = sub.add_parser("profile", help="Manage automation profiles")
    p_prof.add_argument("action", choices=["list", "create", "show"])
    p_prof.add_argument("-n", "--name", help="Profile name")
    p_prof.set_defaults(func=cmd_profile)

    p_ocr = sub.add_parser("ocr", help="Read text from screen region via OCR")
    p_ocr.set_defaults(func=cmd_ocr)

    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0

    result = func(args)
    if result is None:
        return 0
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
