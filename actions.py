"""Translate pointer intents to native Quartz events."""

import Quartz as q

from gestures import Intent, Point
from volume import OutputVolume


class Pointer:
    def __init__(self) -> None:
        if not q.CGPreflightPostEventAccess():
            q.CGRequestPostEventAccess()
            raise RuntimeError("Enable your launcher in Privacy & Security > Accessibility, then restart.")
        if not q.CGPreflightListenEventAccess():
            q.CGRequestListenEventAccess()
            raise RuntimeError("Enable your launcher in Privacy & Security > Input Monitoring, then restart.")
        self._bounds = q.CGDisplayBounds(q.CGMainDisplayID())
        self._down = False
        self._output = OutputVolume()

    @staticmethod
    def quit_pressed() -> bool:
        # macOS virtual key codes for Escape and the physical Q key.
        return any(q.CGEventSourceKeyState(q.kCGEventSourceStateCombinedSessionState, key)
                   for key in (53, 12))

    @staticmethod
    def _post(kind: int, point: Point, click_state: bool = False, *, right: bool = False) -> None:
        event = q.CGEventCreateMouseEvent(None, kind, point, q.kCGMouseButtonRight if right else q.kCGMouseButtonLeft)
        if event is None:
            raise RuntimeError("Quartz could not create a mouse event.")
        if click_state:
            q.CGEventSetIntegerValueField(event, q.kCGMouseEventClickState, 1)
        q.CGEventPost(q.kCGHIDEventTap, event)

    @staticmethod
    def _current() -> Point:
        location = q.CGEventGetLocation(q.CGEventCreate(None))
        return location.x, location.y

    def normalized_position(self) -> Point:
        x, y = self._current()
        bounds = self._bounds
        return ((x - bounds.origin.x) / bounds.size.width,
                (y - bounds.origin.y) / bounds.size.height)

    def release(self) -> None:
        if self._down:
            self._post(q.kCGEventLeftMouseUp, self._current(), click_state=True)
            self._down = False

    @staticmethod
    def _shortcut(direction: str) -> None:
        key = {"left": 123, "right": 124, "up": 126, "fullscreen": 3, "minimize": 46}[direction]
        flags = q.kCGEventFlagMaskControl
        if direction == "fullscreen":
            flags |= q.kCGEventFlagMaskCommand
        elif direction == "minimize":
            flags = q.kCGEventFlagMaskCommand
        down = q.CGEventCreateKeyboardEvent(None, key, True)
        up = q.CGEventCreateKeyboardEvent(None, key, False)
        if down is None or up is None:
            raise RuntimeError("Quartz could not create a keyboard event.")
        for event in (down, up):
            q.CGEventSetFlags(event, flags)
            q.CGEventPost(q.kCGHIDEventTap, event)

    def apply(self, intent: Intent) -> str | None:
        if intent.button == "right":
            self.release()
            point = self._current()
            self._post(q.kCGEventRightMouseDown, point, click_state=True, right=True)
            self._post(q.kCGEventRightMouseUp, point, click_state=True, right=True)
            return None
        if intent.button == "up":
            self.release()
            if intent.scroll:
                event = q.CGEventCreateScrollWheelEvent(
                    None, q.kCGScrollEventUnitLine, 1, intent.scroll
                )
                if event is not None:
                    q.CGEventPost(q.kCGHIDEventTap, event)
            if intent.shortcut:
                self._shortcut(intent.shortcut)
            if intent.volume and not self._output.adjust(intent.volume):
                return "Volume unavailable on current output"
            return None
        if intent.button == "down" or (intent.button == "click" and intent.position is None):
            self._post(q.kCGEventLeftMouseDown, self._current(), click_state=True)
            self._down = True
            if intent.button == "click":
                self.release()
        if intent.position is not None:
            x, y = intent.position
            bounds = self._bounds
            point = (bounds.origin.x + x * (bounds.size.width - 1),
                     bounds.origin.y + y * (bounds.size.height - 1))
            kind = q.kCGEventLeftMouseDragged if self._down else q.kCGEventMouseMoved
            self._post(kind, point, click_state=self._down)
            if intent.button == "click":
                self._post(q.kCGEventLeftMouseDown, point, click_state=True)
                self._down = True
                self._post(q.kCGEventLeftMouseUp, point, click_state=True)
                self._down = False
        return None
