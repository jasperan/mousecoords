"""System diagnostics for mousecoords dependencies and environment."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

from .screen import capture_screen


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""
    name: str
    passed: bool
    detail: str
    required: bool = True


def _format_gui_error(exc: Exception) -> str:
    """Normalize display-related import/runtime failures into readable output."""
    message = str(exc)
    if isinstance(exc, KeyError) and exc.args == ("DISPLAY",):
        return "requires an active DISPLAY/GUI session"
    gui_markers = (
        "display",
        "x server",
        "failed to acquire x connection",
        "display environment variable is set correctly",
    )
    if any(marker in message.lower() for marker in gui_markers):
        return "requires an active DISPLAY/GUI session"
    return message


def check_display() -> CheckResult:
    if sys.platform == "win32":
        return CheckResult("display", True, "Windows (always available)")
    if sys.platform == "darwin":
        return CheckResult("display", True, "macOS (always available)")
    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    if display:
        return CheckResult("display", True, f"DISPLAY={display}")
    return CheckResult("display", False, "No DISPLAY or WAYLAND_DISPLAY set")


def check_pyautogui() -> CheckResult:
    try:
        import pyautogui
        return CheckResult("pyautogui", True, f"v{pyautogui.__version__}")
    except ImportError:
        return CheckResult("pyautogui", False, "not installed")
    except Exception as e:
        return CheckResult("pyautogui", False, _format_gui_error(e))


def check_screenshot() -> CheckResult:
    try:
        capture_screen(region=(0, 0, 1, 1))
        return CheckResult("screenshot", True, "capture working")
    except Exception as e:
        return CheckResult("screenshot", False, _format_gui_error(e))


def check_opencv() -> CheckResult:
    try:
        import cv2
        return CheckResult("opencv", True, f"v{cv2.__version__}", required=False)
    except ImportError:
        return CheckResult("opencv", False,
                           "not installed (pip install mousecoords[vision])",
                           required=False)


def check_tesseract() -> CheckResult:
    try:
        import pytesseract
        binary = shutil.which("tesseract")
        if binary:
            version = pytesseract.get_tesseract_version()
            return CheckResult("tesseract", True,
                               f"v{version} ({binary})", required=False)
        return CheckResult("tesseract", False,
                           "pytesseract installed but binary not on PATH",
                           required=False)
    except ImportError:
        return CheckResult("tesseract", False,
                           "not installed (pip install mousecoords[ocr])",
                           required=False)
    except Exception as e:
        return CheckResult("tesseract", False, str(e), required=False)


def check_pynput() -> CheckResult:
    try:
        from pynput import mouse  # noqa: F401
        return CheckResult("pynput", True, "installed", required=False)
    except ImportError as e:
        detail = _format_gui_error(e)
        if detail == "requires an active DISPLAY/GUI session":
            return CheckResult("pynput", False, detail, required=False)
        return CheckResult("pynput", False,
                           "not installed (pip install mousecoords[record])",
                           required=False)
    except Exception as e:
        return CheckResult("pynput", False, _format_gui_error(e), required=False)


def check_keyboard() -> CheckResult:
    try:
        import keyboard  # noqa: F401
        return CheckResult("keyboard", True, "installed")
    except ImportError:
        return CheckResult("keyboard", False, "not installed")


def check_keyboard_perms() -> CheckResult:
    """Check if keyboard module can actually read events (needs root on Linux)."""
    if sys.platform != "linux":
        return CheckResult("keyboard_perms", True, "non-Linux (no root needed)")
    if os.geteuid() == 0:
        return CheckResult("keyboard_perms", True, "running as root")
    return CheckResult("keyboard_perms", False,
                       "keyboard module needs root on Linux "
                       "(run with sudo or use pynput alternative)")


def check_tkinter() -> CheckResult:
    try:
        import tkinter
        return CheckResult("tkinter", True,
                           f"Tcl/Tk {tkinter.TclVersion}", required=False)
    except ImportError:
        return CheckResult("tkinter", False, "not available", required=False)


def check_rich() -> CheckResult:
    try:
        import rich  # noqa: F401
        from importlib.metadata import version
        ver = version("rich")
        return CheckResult("rich", True, f"v{ver}", required=False)
    except ImportError:
        return CheckResult("rich", False,
                           "not installed (pip install mousecoords[tui])",
                           required=False)


ALL_CHECKS = [
    check_display,
    check_pyautogui,
    check_screenshot,
    check_opencv,
    check_tesseract,
    check_pynput,
    check_keyboard,
    check_keyboard_perms,
    check_tkinter,
    check_rich,
]


def collect_diagnostics(checks=None) -> list[CheckResult]:
    """Run all diagnostic checks and return results."""
    checks = checks or ALL_CHECKS
    results = []
    for check_fn in checks:
        try:
            results.append(check_fn())
        except Exception as e:
            name = check_fn.__name__.replace("check_", "")
            results.append(CheckResult(name, False, f"unexpected error: {e}"))
    return results


def print_diagnostics(results: list[CheckResult]):
    """Print diagnostic results to stdout."""
    print("mousecoords -- System Diagnostics")
    print("=" * 55)

    for r in results:
        marker = "+" if r.passed else "-"
        tag = "PASS" if r.passed else "FAIL"
        req = "" if r.required else " (optional)"
        print(f"  [{marker}] {r.name:<18} {tag}  {r.detail}{req}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    required_fails = [r for r in results if not r.passed and r.required]

    print("=" * 55)
    print(f"  {passed}/{total} checks passed")

    if required_fails:
        print(f"\n  {len(required_fails)} required check(s) failed:")
        for r in required_fails:
            print(f"    - {r.name}: {r.detail}")

    optional_fails = [r for r in results if not r.passed and not r.required]
    if optional_fails:
        print(f"\n  Install optional extras with: pip install mousecoords[all]")
