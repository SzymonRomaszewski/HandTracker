"""Interactive calibration and hands-free app selection."""

from dataclasses import dataclass, field
from math import ceil

import cv2

from tracking import Frame, Hand


@dataclass
class Calibration:
    deadline: float
    samples: list[tuple[float, float]] = field(default_factory=list)

    def update(self, hand: Hand | None, now: float) -> str:
        if hand is not None:
            self.samples.append(hand[8][:2])
        return f"Calibrate: point around your reach | {max(0, ceil(self.deadline - now))}s"

    def area(self) -> list[float]:
        if len(self.samples) < 20:
            raise ValueError("Calibration needs more tracked frames. Try again.")
        x, y = (sorted(axis) for axis in zip(*self.samples))
        low, high = len(x) // 50, len(x) - 1 - len(x) // 50
        return [max(0, x[low]), max(0, y[low]), min(1, x[high]), min(1, y[high])]


class AppSwitcher:
    def __init__(self, apps: list) -> None:
        self.apps = apps
        self.selected: int | None = None
        self.since = 0.0
        self.page = 0

    def update(self, point: tuple[float, float] | None, now: float):
        start = self.page * 6
        entries = self.apps[start:start + 6]
        count = len(entries) + int(len(self.apps) > 6)
        index = min(count - 1, int(point[0] * count)) if point is not None and count else None
        if index != self.selected:
            self.selected, self.since = index, now
        if index is None or now - self.since < 1:
            return None
        self.since = now
        if index == len(entries):
            self.page = (self.page + 1) % ((len(self.apps) + 5) // 6)
            self.selected = None
            return None
        return entries[index]

    def draw(self, frame: Frame) -> None:
        width = frame.shape[1]
        entries = [str(app.localizedName()) for app in self.apps[self.page * 6:self.page * 6 + 6]]
        if len(self.apps) > 6:
            entries.append("Next page")
        for index, label in enumerate(entries):
            left, right = index * width // len(entries), (index + 1) * width // len(entries)
            color = (90, 108, 150) if index == self.selected else (50, 50, 55)
            cv2.rectangle(frame, (left + 2, 86), (right - 2, 143), color, -1)
            cv2.putText(frame, label[:max(4, (right - left) // 7)], (left + 6, 119),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
