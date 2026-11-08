"""Windows desktop actions for the shared gesture engine."""

import ctypes as C
from ctypes import wintypes as W

from gestures import Intent, Point


class MouseInput(C.Structure):
    _fields_ = [
        ("dx", W.LONG), ("dy", W.LONG), ("data", W.DWORD),
        ("flags", W.DWORD), ("time", W.DWORD), ("extra", C.c_size_t),
    ]


class KeyInput(C.Structure):
    _fields_ = [
        ("key", W.WORD), ("scan", W.WORD), ("flags", W.DWORD),
        ("time", W.DWORD), ("extra", C.c_size_t),
    ]


class InputData(C.Union):
    _fields_ = [("mouse", MouseInput), ("key", KeyInput)]


class Input(C.Structure):
    _fields_ = [("kind", W.DWORD), ("data", InputData)]


def mouse(flags: int, data: int = 0) -> Input:
    return Input(0, InputData(mouse=MouseInput(0, 0, data & 0xffffffff, flags, 0, 0)))


def key(code: int, release: bool = False) -> Input:
    extended = code in (0x25, 0x27, 0x5B, 0xAE, 0xAF)
    return Input(1, InputData(key=KeyInput(code, 0, int(extended) | (2 if release else 0), 0, 0)))


class Pointer:
    def __init__(self) -> None:
        self.user = C.WinDLL("user32", use_last_error=True)
        self.user.SendInput.argtypes = [W.UINT, C.POINTER(Input), C.c_int]
        self.user.SendInput.restype = W.UINT
        self.user.GetForegroundWindow.restype = W.HWND
        self.user.ShowWindowAsync.argtypes = [W.HWND, C.c_int]
        self.user.SetCursorPos.argtypes = [C.c_int, C.c_int]
        self.user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
        self._down = False

    def _send(self, *events: Input) -> None:
        buffer = (Input * len(events))(*events)
        if self.user.SendInput(len(events), buffer, C.sizeof(Input)) != len(events):
            raise OSError("Windows rejected input. Try a normal, non-administrator app.")

    def _keys(self, *codes: int) -> None:
        self._send(*(key(code) for code in codes), *(key(code, True) for code in reversed(codes)))

    def quit_pressed(self) -> bool:
        # The preview handles keyboard shortcuts without intercepting other apps.
        return False

    def normalized_position(self) -> Point:
        point = W.POINT()
        self.user.GetCursorPos(C.byref(point))
        return tuple(max(0, min(1, value / max(1, self.user.GetSystemMetrics(axis) - 1)))
                     for axis, value in enumerate((point.x, point.y)))

    def release(self) -> None:
        if self._down:
            self._send(mouse(0x0004))
            self._down = False

    def _shortcut(self, name: str) -> None:
        if name == "minimize":
            window = self.user.GetForegroundWindow()
            if window:
                self.user.ShowWindowAsync(window, 6)
            return
        keys = {
            "left": (0x5B, 0x11, 0x25), "right": (0x5B, 0x11, 0x27),
            "up": (0x5B, 0x09), "fullscreen": (0x7A,),
        }
        self._keys(*keys[name])

    def apply(self, intent: Intent) -> str | None:
        if intent.position is not None:
            x, y = intent.position
            width, height = (self.user.GetSystemMetrics(axis) for axis in (0, 1))
            self.user.SetCursorPos(round(x * (width - 1)), round(y * (height - 1)))
        if intent.button == "up":
            self.release()
        elif intent.button == "down":
            self._send(mouse(0x0002))
            self._down = True
        elif intent.button == "click":
            self._send(mouse(0x0002), mouse(0x0004))
        elif intent.button == "right":
            self._send(mouse(0x0008), mouse(0x0010))
        if intent.scroll:
            self._send(mouse(0x0800, intent.scroll * 120))
        if intent.shortcut:
            self._shortcut(intent.shortcut)
        if intent.volume:
            code = 0xAF if intent.volume > 0 else 0xAE
            for _ in range(max(1, abs(intent.volume) // 2)):
                self._keys(code)
        return None
