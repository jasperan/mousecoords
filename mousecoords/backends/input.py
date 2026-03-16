"""Input backends for live desktop automation and future fixtures."""

from __future__ import annotations

from typing import Optional, Protocol


class InputBackend(Protocol):
    """Protocol for mouse and keyboard automation backends."""

    def move_to(self, x: int, y: int) -> None:
        ...

    def click(self, x: int, y: int, button: str = "left") -> None:
        ...

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
        ...

    def press(self, key: str) -> None:
        ...

    def key_down(self, key: str) -> None:
        ...

    def key_up(self, key: str) -> None:
        ...


class PyAutoGuiInputBackend:
    """Live input backend backed by pyautogui."""

    @staticmethod
    def _get_pyautogui():
        import pyautogui

        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        return pyautogui

    def move_to(self, x: int, y: int) -> None:
        self._get_pyautogui().moveTo(x, y, _pause=False)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._get_pyautogui().click(x, y, button=button, _pause=False)

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
        self._get_pyautogui().scroll(clicks, x=x, y=y, _pause=False)

    def press(self, key: str) -> None:
        self._get_pyautogui().press(key, _pause=False)

    def key_down(self, key: str) -> None:
        self._get_pyautogui().keyDown(key, _pause=False)

    def key_up(self, key: str) -> None:
        self._get_pyautogui().keyUp(key, _pause=False)
