"""OpenCV event loop and keyboard controls for the Windows preview."""

import cv2

from overlay import WINDOW


class DesktopUI:
    def __init__(self) -> None:
        self.pending = None

    def command(self) -> str | None:
        command, self.pending = self.pending, None
        return command

    def update(self, paused, detected, visible, practice, precision) -> None:
        pass

    def close(self) -> None:
        pass

    def run(self, frames) -> int:
        shortcuts = {
            27: "quit", ord("q"): "quit", ord("c"): "calibrate",
            ord("p"): "practice", ord("x"): "precision",
        }
        try:
            for _ in frames:
                key = cv2.waitKey(1) & 0xff
                self.pending = shortcuts.get(ord(chr(key).lower()) if 65 <= key <= 90 else key)
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            frames.close()
        return 0
