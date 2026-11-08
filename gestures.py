"""Pure gesture state machine. Distance comparisons account for the camera aspect ratio."""

from dataclasses import dataclass
from math import dist, exp

type Point = tuple[float, float]
type Hand = list[tuple[float, float, float]]

from settings import Settings


@dataclass(frozen=True)
class Intent:
    label: str
    position: Point | None = None
    button: str = ""
    scroll: int = 0
    shortcut: str = ""
    volume: int = 0


class Gestures:
    def __init__(self, settings: Settings = Settings(), *, precision_origin: Point | None = None) -> None:
        self.settings = settings
        self._area = settings.cursor_area
        self._precision_origin = precision_origin
        self._precision_hand: Point | None = None
        self.paused = False
        self._pose = ""
        self._since = 0.0
        self._pinch_start: float | None = None
        self._dragging = False
        self._filtered: Point | None = None
        self._last_time = 0.0
        self._last_pointing: float | None = None
        self._window_source: tuple[str, float, Point] | None = None
        self._anchor: Point | None = None
        self._anchor_time = 0.0
        self._cooldown_until = 0.0
        self._swipe_fired = False
        self._last_seen: float | None = None
        self._right_fired = False
        self._peace_moved = False
        self._dwell_anchor: Point | None = None
        self._dwell_started = 0.0
        self._dwell_clicked = False

    def _clear_dwell(self) -> None:
        self._dwell_anchor = None
        self._dwell_clicked = False

    def _point(self, position: Point, now: float) -> Intent:
        if not self.settings.dwell_click:
            return Intent("Pointing", position)
        # Track stability independently from the displayed cursor.
        anchor = self._dwell_anchor
        reached_edge = anchor is not None and any(
            value in (0.0, 1.0) and value != previous
            for value, previous in zip(position, anchor)
        )
        if anchor is None or reached_edge or dist(position, anchor) > 0.018:
            self._dwell_anchor = position
            self._dwell_started = now
            self._dwell_clicked = False
        if self._dwell_clicked:
            return Intent("Clicked | move to rearm", position)
        remaining = self.settings.dwell_seconds - (now - self._dwell_started)
        if remaining <= 0:
            self._dwell_clicked = True
            return Intent("Dwell click", position, "click")
        return Intent(f"Hold to click | {remaining:.1f}s", position)

    def _motion(self, pose: str, center: Point, now: float, held: float) -> Intent:
        self._reset_pointer()
        self._last_pointing = None
        if self._anchor is None:
            self._anchor, self._anchor_time = center, now
        dx, dy = (center[0] - self._anchor[0], center[1] - self._anchor[1])
        if pose == "peace":
            self._peace_moved |= dist(center, self._anchor) > 0.018
            lines = max(-5, min(5, int(-dy / 0.023))) if self.settings.scroll and held >= 0.12 else 0
            if lines:
                self._anchor = (center[0], self._anchor[1] - lines * 0.023)
            if self.settings.right_click and not self._peace_moved and held >= 0.8 and not self._right_fired:
                self._right_fired = True
                return Intent("Right click", button="right")
            if self._right_fired and not lines:
                return Intent("Right clicked | lower fingers to rearm", button="up")
            if self.settings.right_click and not self._peace_moved:
                return Intent(f"Hold for right click | {max(0.0, 0.8 - held):.1f}s", button="up")
            return Intent("Scroll | move peace sign up or down" if self.settings.scroll else "Show peace sign again", button="up", scroll=lines)
        if pose == "volume":
            steps = max(-3, min(3, int(-dy / 0.027)))
            if held >= 0.16 and now >= self._cooldown_until and steps:
                self._anchor = (center[0], self._anchor[1] - steps * 0.027)
                self._cooldown_until = now + 0.22
                return Intent(f"Volume {steps * 4:+d}%", button="up", volume=steps * 4)
            return Intent("Volume | move hand up or down", button="up")
        if now - self._anchor_time > 0.55:
            self._anchor, self._anchor_time = center, now
            return Intent("Palm | swipe or close fist", button="up")
        if held >= 0.09 and now >= self._cooldown_until and not self._swipe_fired:
            shortcut = ""
            if abs(dx) > 0.14 and abs(dx) > 1.5 * abs(dy):
                shortcut = "right" if dx > 0 else "left"
            elif dy < -0.13 and -dy > 1.5 * abs(dx):
                shortcut = "up"
            if shortcut and (self.settings.mission_control if shortcut == "up" else self.settings.desktop_switch):
                self._swipe_fired = True
                self._window_source = None
                self._cooldown_until = now + 0.75
                label = "Mission Control" if shortcut == "up" else f"Desktop {shortcut}"
                return Intent(label, button="up", shortcut=shortcut)
        return Intent("Lower palm to rearm" if self._swipe_fired else "Palm | swipe or close fist", button="up")


    def _reset_pointer(self) -> None:
        self._clear_dwell()
        self._pinch_start = None
        self._dragging = False
        self._filtered = None

    def _smooth(self, point: Point, now: float) -> Point:
        # Camera margins map to the display edges. Clamp beyond the margins.
        raw_x, raw_y = point
        left, top, right, bottom = self._area
        target_x = max(0.0, min(1.0, (raw_x - left) / (right - left)))
        target_y = max(0.0, min(1.0, (raw_y - top) / (bottom - top)))
        if self._precision_origin is not None:
            if self._precision_hand is None:
                self._precision_hand = (target_x, target_y)
            origin_x, origin_y = self._precision_origin
            start_x, start_y = self._precision_hand
            target_x = max(0.0, min(1.0, origin_x + (target_x - start_x) * 0.35))
            target_y = max(0.0, min(1.0, origin_y + (target_y - start_y) * 0.35))
        x, y = target_x, target_y
        if self._filtered is not None and self.settings.smoothing_ms:
            elapsed = max(0.0, now - self._last_time)
            edge_x = min(x, 1.0 - x) < 0.12
            edge_y = min(y, 1.0 - y) < 0.12
            smoothing = self.settings.smoothing_ms / 1000
            if dist((x, y), self._filtered) > 0.025:
                smoothing *= 0.55
            alpha_x = 1 - exp(-elapsed / (smoothing * (0.4 if edge_x else 1)))
            alpha_y = 1 - exp(-elapsed / (smoothing * (0.4 if edge_y else 1)))
            x = self._filtered[0] + alpha_x * (x - self._filtered[0])
            y = self._filtered[1] + alpha_y * (y - self._filtered[1])
        # Snap the last few pixels so the Dock and screen edges are reachable.
        x = target_x if target_x in (0.0, 1.0) else x
        y = target_y if target_y in (0.0, 1.0) else y
        self._filtered = (x, y)
        self._last_time = now
        return self._filtered

    def _window_transition(self, pose: str, held: float, now: float, center: Point) -> Intent | None:
        if self.paused or self._swipe_fired:
            self._window_source = None
            return None
        if pose not in ("fist", "palm") or held < 0.15:
            return None
        source = self._window_source
        self._window_source = (pose, now, center)
        if source is None or source[0] == pose:
            return None
        if now - source[1] > 0.85 or dist(center, source[2]) > 0.14:
            return None
        if not (self.settings.fullscreen if pose == "palm" else self.settings.minimize):
            return None
        self._window_source = None
        self._reset_pointer()
        self._last_pointing = None
        self._swipe_fired = True
        self._cooldown_until = now + 0.75
        if pose == "palm":
            return Intent("Toggle fullscreen", button="up", shortcut="fullscreen")
        return Intent("Minimise window", button="up", shortcut="minimize")

    def update(self, hand: Hand | None, now: float, aspect: float) -> Intent:
        if self._last_seen is not None and now - self._last_seen > 0.25:
            self._pose = ""
            self._anchor = None
            self._last_pointing = None
            self._last_seen = None
            self._window_source = None
            self._reset_pointer()
            return Intent("Tracking interrupted", button="up")
        if hand is None:
            self._reset_pointer()
            self._pose = ""
            self._anchor = None
            self._last_seen = None
            self._window_source = None
            self._last_pointing = None
            return Intent("Paused | show palm" if self.paused else "Show one hand", button="up")

        self._last_seen = now
        points = [(x, y / aspect) for x, y, _ in hand]
        palm = max(dist(points[0], points[9]), 0.001)
        extensions = [
            (dist(points[0], points[tip]) - dist(points[0], points[tip - 2])) / palm
            for tip in (8, 12, 16, 20)
        ]
        extended = [extension > 0.23 for extension in extensions]
        index, middle, ring, pinky = extended
        pointing = index and not (middle or ring or pinky)
        other_fingers = middle or ring or pinky
        gap = dist(points[4], points[8]) / palm
        pinched = gap < (0.38 if self._pinch_start is not None else 0.30)

        center = hand[9][:2]
        source = self._window_source
        closing_palm = (
            source is not None and source[0] == "palm"
            and now - source[1] <= 0.85 and dist(center, source[2]) <= 0.14
        )
        pose = ""
        if all(extended):
            pose = "palm"
        elif (self.settings.scroll or self.settings.right_click) and index and middle and not ring and not pinky:
            pose = "peace"
        elif self.settings.volume and not index and middle and ring and pinky:
            pose = "volume"
        elif not any(extended) and self._pinch_start is None and not (
            pinched and not closing_palm and self._last_pointing is not None and now - self._last_pointing < 0.12
        ):
            pose = "fist"
        if pose != self._pose:
            self._pose, self._since = pose, now
            self._anchor = None
            self._swipe_fired = False
            self._right_fired = False
            self._peace_moved = False
        held = now - self._since
        if pose == "fist" and held >= 1:
            self.paused = True
        elif self.paused and pose == "palm" and held >= 1:
            self.paused = False
            self._swipe_fired = True
            return Intent("Resumed | lower palm to rearm", button="up")

        if self._dragging:
            self._window_source = None
        elif now >= self._cooldown_until:
            window_intent = self._window_transition(pose, held, now, center)
            if window_intent is not None:
                return window_intent
        else:
            self._window_source = None

        if self._dragging and pose == "fist" and not self.paused:
            return Intent("Dragging | raise index to move")

        if self.paused or pose == "fist":
            if self.paused:
                label = f"Paused | palm {max(0.0, 1 - held):.1f}s" if pose == "palm" else "Paused | hold open palm for 1s"
            else:
                label = f"Pausing | hold fist {max(0.0, 1 - held):.1f}s"
            self._last_pointing = None
            self._reset_pointer()
            return Intent(label, button="up")

        if self._dragging and pose == "palm":
            self._reset_pointer()
            self._last_pointing = None
            self._swipe_fired = True
            return Intent("Dropped | open palm", button="up")
        if not self._dragging and (pose == "palm" or (self._pinch_start is None and pose in ("peace", "volume"))):
            return self._motion(pose, hand[9][:2], now, held)

        if closing_palm and pinched and self._pinch_start is None:
            self._reset_pointer()
            self._last_pointing = None
            return Intent("Close fist to minimise", button="up")

        if pointing:
            self._last_pointing = now
        recently_pointing = (
            self._last_pointing is not None and now - self._last_pointing < 0.12
        )

        if not self._dragging and other_fingers and not pointing and self._pinch_start is None and not recently_pointing:
            self._reset_pointer()
            return Intent("Curl middle, ring and pinky to point", button="up")

        point = hand[8][:2]
        if (self.settings.pinch_click or self.settings.drag) and pinched and (self._pinch_start is not None or pointing or recently_pointing) and pose != "palm":
            if self._pinch_start is None:
                self._clear_dwell()
                self._pinch_start = now
            if self.settings.drag:
                return Intent("Release pinch to drop" if self._dragging else "Release pinch to grab")
            return Intent("Release pinch to click")
        if self._pinch_start is not None:
            elapsed = now - self._pinch_start
            self._pinch_start = None
            if elapsed >= 0.06:
                if self.settings.drag:
                    self._dragging = not self._dragging
                    return Intent("Grabbed | point to move" if self._dragging else "Dropped",
                                  button="down" if self._dragging else "up")
                return Intent("Click", button="click")
        if self._dragging:
            position = self._smooth(point, now) if pointing and self.settings.cursor else None
            return Intent("Dragging | pinch to drop", position)
        if pointing:
            position = self._smooth(point, now)
            if not self.settings.cursor:
                return Intent("Cursor disabled")
            return self._point(position, now)
        self._reset_pointer()
        return Intent("Point with index finger")
