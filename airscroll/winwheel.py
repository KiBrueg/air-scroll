"""Windows input boundary: emits vertical wheel events only, never clicks or moves."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", INPUT_UNION)]


class WheelSender:
    """Minimal Windows SendInput wrapper restricted to MOUSEEVENTF_WHEEL."""

    MOUSE_INPUT = 0
    MOUSEEVENTF_WHEEL = 0x0800
    WHEEL_DELTA = 120
    VK_ESCAPE = 0x1B

    def __init__(self) -> None:
        self._enabled = sys.platform == "win32"
        self._user32 = ctypes.WinDLL("user32", use_last_error=True) if self._enabled else None

    def escape_pressed(self) -> bool:
        """Global emergency pause detector; it does not emit any keyboard input."""
        return bool(self._enabled and (self._user32.GetAsyncKeyState(self.VK_ESCAPE) & 0x8000))

    def scroll(self, ticks: int) -> None:
        if not self._enabled or not ticks:
            return
        direction = self.WHEEL_DELTA if ticks > 0 else -self.WHEEL_DELTA
        for _ in range(min(abs(int(ticks)), 3)):
            event = INPUT(
                type=self.MOUSE_INPUT,
                mi=MOUSEINPUT(0, 0, ctypes.c_ulong(direction).value, self.MOUSEEVENTF_WHEEL, 0, None),
            )
            sent = self._user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
            if sent != 1:
                raise ctypes.WinError(ctypes.get_last_error())
