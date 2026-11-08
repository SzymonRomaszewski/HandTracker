"""Render the mirrored preview and handle focused-window quit keys."""

import cv2

from tracking import Frame, Hand
from workflows import AppSwitcher

WINDOW = "HandDesk"
CHAINS = (
    (0, 1, 2, 3, 4),
    (0, 5, 6, 7, 8),
    (5, 9, 10, 11, 12),
    (9, 13, 14, 15, 16),
    (13, 17, 18, 19, 20),
    (17, 0),
)


class TrackingMenu:
    LEFT, RIGHT = 370, 565
    TOP, ROW = 35, 32

    def __init__(self, delay: int) -> None:
        self.delay = delay
        self.paused = False
        self.deadline: float | None = None
        self.open = False
        self.choice: int | None = None

    def mouse(self, event: int, x: int, y: int, flags: int, data: object) -> None:
        if event != cv2.EVENT_LBUTTONUP:
            return
        row = (y - self.TOP) // self.ROW
        inside = self.LEFT <= x <= self.RIGHT
        if inside and row == 0:
            self.open = not self.open
        elif self.open:
            if inside and row in (1, 2):
                self.choice = row - 1
            self.open = False

    def update(self, now: float) -> bool:
        previous = self.paused
        if self.choice == 0:
            self.paused = not self.paused
            self.deadline = None
        elif self.choice == 1:
            self.paused = True
            self.deadline = now + self.delay
        self.choice = None
        if self.deadline is not None and now >= self.deadline:
            self.paused = False
            self.deadline = None
            self.open = False
        return previous != self.paused

    def draw(self, frame: Frame) -> None:
        label = "Enable tracking" if self.paused else "Disable tracking"
        first = "Enable now" if self.paused else "Pause until enabled"
        second = f"Enable in {self.delay}s" if self.paused else f"Pause for {self.delay}s"
        labels = (label, first, second) if self.open else (label,)
        for row, text in enumerate(labels):
            top = self.TOP + row * self.ROW
            start, end = (self.LEFT, top), (self.RIGHT, top + self.ROW - 2)
            fill = (70, 78, 100) if row == 0 else (48, 48, 48)
            cv2.rectangle(frame, start, end, fill, -1)
            cv2.rectangle(frame, start, end, (120, 130, 155), 1)
            cv2.putText(frame, text, (self.LEFT + 10, top + 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.52, (245, 245, 245), 1, cv2.LINE_AA)


def show(frame: Frame, hands: list[Hand], fps: float | None, status: str, *, menu: TrackingMenu | None = None, guide: tuple[float, float, float, float] | None = None, switcher: AppSwitcher | None = None) -> None:
    height, width = frame.shape[:2]
    if guide is not None:
        left, top, right, bottom = guide
        cv2.rectangle(
            frame, (round(left * width), round(top * height)),
            (round(right * width), round(bottom * height)), (140, 160, 165), 1, cv2.LINE_AA,
        )
    for hand in hands:
        pixels = [(round(x * (width - 1)), round(y * (height - 1))) for x, y, _ in hand]
        for chain in CHAINS:
            for start, end in zip(chain, chain[1:]):
                cv2.line(frame, pixels[start], pixels[end], (240, 210, 70), 2, cv2.LINE_AA)
        for point in pixels:
            cv2.circle(frame, point, 4, (255, 255, 255), -1, cv2.LINE_AA)

    rate = "Measuring FPS" if fps is None else f"{fps:.1f} FPS"
    slow = fps is not None and fps < 20
    if slow:
        rate += " | LOW (below 20)"
    cv2.rectangle(frame, (0, 0), (width, 76), (24, 24, 24), -1)
    for y, label, color in (
        (27, status, (255, 255, 255)),
        (56, f"{rate}   |   Esc / Q to quit", (80, 195, 255) if slow else (220, 220, 220)),
    ):
        cv2.putText(frame, label, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.56, color, 1, cv2.LINE_AA)

    if switcher is not None:
        switcher.draw(frame)
    if menu is not None:
        menu.draw(frame)
    cv2.imshow(WINDOW, frame)
