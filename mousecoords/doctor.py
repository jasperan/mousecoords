"""Diagnostics for mousecoords environments."""

from __future__ import annotations

import importlib
import os
import platform
import sys
from typing import Callable


CheckResult = dict[str, str | bool]
DiagnosticMap = dict[str, CheckResult]


def _ok(detail: str) -> CheckResult:
    return {"ok": True, "detail": detail}


def _fail(detail: str) -> CheckResult:
    return {"ok": False, "detail": detail}


def _check_display() -> CheckResult:
    if sys.platform.startswith("linux"):
        if os.environ.get("DISPLAY"):
            return _ok(f"DISPLAY={os.environ['DISPLAY']}")
        if os.environ.get("WAYLAND_DISPLAY"):
            return _ok(f"WAYLAND_DISPLAY={os.environ['WAYLAND_DISPLAY']}")
        return _fail("DISPLAY and WAYLAND_DISPLAY are unset")

    return _ok(f"{platform.system()} does not rely on DISPLAY")


def _check_import(module_name: str) -> CheckResult:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - environment dependent
        return _fail(f"{type(exc).__name__}: {exc}")

    return _ok(f"{module_name} import succeeded")


def _check_screenshot() -> CheckResult:
    try:
        pyautogui = importlib.import_module("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        pyautogui.screenshot(region=(0, 0, 1, 1))
    except Exception as exc:  # pragma: no cover - environment dependent
        return _fail(f"{type(exc).__name__}: {exc}")

    return _ok("pyautogui screenshot succeeded")


CHECKS: tuple[tuple[str, Callable[[], CheckResult]], ...] = (
    ("display", _check_display),
    ("screenshot", _check_screenshot),
    ("ocr_import", lambda: _check_import("pytesseract")),
    ("tkinter_import", lambda: _check_import("tkinter")),
    ("rich_import", lambda: _check_import("rich")),
)


def collect_diagnostics() -> DiagnosticMap:
    return {name: checker() for name, checker in CHECKS}


def format_diagnostics(diagnostics: DiagnosticMap) -> str:
    lines = ["mousecoords doctor", "=================="]
    for name, result in diagnostics.items():
        status = "OK" if result["ok"] else "FAIL"
        lines.append(f"{name:<14} {status:<4} {result['detail']}")
    return "\n".join(lines)


def cmd_doctor(args=None) -> int:
    print(format_diagnostics(collect_diagnostics()))
    return 0


def main(argv=None) -> int:
    return cmd_doctor()


if __name__ == "__main__":
    raise SystemExit(main())
