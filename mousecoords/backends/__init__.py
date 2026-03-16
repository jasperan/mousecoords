"""Desktop backends for screen capture, input control, and test fixtures."""

from .fixtures import FixtureScreenBackend
from .input import InputBackend, PyAutoGuiInputBackend
from .screen import PyAutoGuiScreenBackend, ScreenBackend
from .window import WindowBackend, WindowInfo

__all__ = [
    "FixtureScreenBackend",
    "InputBackend",
    "PyAutoGuiInputBackend",
    "PyAutoGuiScreenBackend",
    "ScreenBackend",
    "WindowBackend",
    "WindowInfo",
]
