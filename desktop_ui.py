"""Native macOS menu, settings dialog and running application list."""

from dataclasses import asdict
import os
from threading import Event, Thread
from time import monotonic

import AppKit as A
from Foundation import NSActivityLatencyCritical, NSActivityUserInitiated, NSObject, NSProcessInfo
from PyObjCTools.AppHelper import callAfter

from settings import Settings, validate_settings


class MenuTarget(NSObject):
    def select_(self, sender):
        self.pending = str(sender.representedObject())


class DesktopUI:
    def __init__(self) -> None:
        self.target = MenuTarget.alloc().init()
        self.target.pending = None
        self.item = A.NSStatusBar.systemStatusBar().statusItemWithLength_(A.NSVariableStatusItemLength)
        self.menu = A.NSMenu.alloc().init()
        self.items = {}
        for command, title in (
            ("pause", "Pause tracking"), ("timed", "Pause temporarily"),
            ("preview", "Hide preview"), ("practice", "Practice mode"),
            ("calibrate", "Calibrate reach (30 seconds)"), ("precision", "Precision mode"),
            ("switch", "Switch apps"), ("settings", "Gesture settings…"), ("quit", "Quit HandDesk"),
        ):
            item = self.menu.addItemWithTitle_action_keyEquivalent_(title, "select:", "")
            item.setTarget_(self.target)
            item.setRepresentedObject_(command)
            self.items[command] = item
        self.item.setMenu_(self.menu)
        self._state = None
        self.update(False, False, True, False, False)

    def update(self, paused: bool, detected: bool, visible: bool, practice: bool, precision: bool) -> None:
        state = (paused, detected, visible, practice, precision)
        if state == self._state:
            return
        self._state = state
        status = "Paused" if paused else "Hand" if detected else "Ready"
        title = f"HandDesk · {status}"
        button = self.item.button()
        if button.title() != title:
            button.setTitle_(title)
        pause_title = "Resume tracking" if paused else "Pause tracking"
        if self.items["pause"].title() != pause_title:
            self.items["pause"].setTitle_(pause_title)
        self.items["preview"].setTitle_("Hide preview" if visible else "Show preview")
        self.items["practice"].setState_(int(practice))
        self.items["precision"].setState_(int(precision))

    def command(self) -> str | None:
        command = self.target.pending
        self.target.pending = None
        return command

    def run(self, frames) -> int:
        app = A.NSApplication.sharedApplication()
        outcome = []
        stopping = Event()
        frame_done = Event()

        def tick():
            if stopping.is_set():
                return
            try:
                next(frames)
            except BaseException as error:
                outcome.append(error)
                stopping.set()
                app.stop_(None)
                # Wake AppKit so its run loop can observe stop_.
                event = A.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                    A.NSEventTypeApplicationDefined, (0, 0), 0, 0, 0, None, 0, 0, 0
                )
                app.postEvent_atStart_(event, True)
            finally:
                frame_done.set()

        def schedule():
            while not stopping.is_set():
                started = monotonic()
                frame_done.clear()
                callAfter(tick)
                frame_done.wait()
                stopping.wait(max(0.0, 1 / 60 - (monotonic() - started)))

        def key_down(event):
            chars = event.charactersIgnoringModifiers()
            if chars in ("c", "C"):
                self.target.pending = "calibrate"
                return None
            if chars in ("q", "Q", "\x1b"):
                self.target.pending = "quit"
                return None
            return event

        monitor = A.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(A.NSEventMaskKeyDown, key_down)
        process = NSProcessInfo.processInfo()
        activity = process.beginActivityWithOptions_reason_(
            NSActivityUserInitiated | NSActivityLatencyCritical, "HandDesk live hand tracking"
        )
        scheduler = Thread(target=schedule, name="HandDesk frame scheduler", daemon=True)
        scheduler.start()
        try:
            app.run()
        finally:
            stopping.set()
            frame_done.set()
            scheduler.join()
            process.endActivity_(activity)
            if monitor is not None:
                A.NSEvent.removeMonitor_(monitor)
            frames.close()
        if outcome and not isinstance(outcome[0], StopIteration):
            raise outcome[0]
        return 0

    def close(self) -> None:
        A.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)


def running_apps() -> list:
    return [
        app for app in A.NSWorkspace.sharedWorkspace().runningApplications()
        if app.activationPolicy() == A.NSApplicationActivationPolicyRegular
        and app.processIdentifier() != os.getpid() and app.localizedName()
    ]


def edit_settings(settings: Settings) -> Settings | None:
    numbers = ("sensitivity", "smoothing_ms", "dwell_seconds", "tracking_pause_seconds")
    flags = tuple(key for key, value in asdict(settings).items() if type(value) is bool)
    rows = (*numbers, *flags)
    view = A.NSView.alloc().initWithFrame_(((0, 0), (330, len(rows) * 25)))
    fields = {}
    for row, key in enumerate(rows):
        y = (len(rows) - row - 1) * 25
        title = key.replace("_", " ").capitalize()
        if key in numbers:
            label = A.NSTextField.labelWithString_(title)
            label.setFrame_(((0, y), (210, 22)))
            view.addSubview_(label)
            field = A.NSTextField.alloc().initWithFrame_(((220, y), (100, 22)))
            field.setStringValue_(str(getattr(settings, key)))
        else:
            field = A.NSButton.checkboxWithTitle_target_action_(title, None, None)
            field.setFrame_(((0, y), (320, 22)))
            field.setState_(int(getattr(settings, key)))
        view.addSubview_(field)
        fields[key] = field
    alert = A.NSAlert.alloc().init()
    alert.setMessageText_("HandDesk gesture settings")
    alert.setAccessoryView_(view)
    alert.addButtonWithTitle_("Save")
    alert.addButtonWithTitle_("Cancel")
    if alert.runModal() != A.NSAlertFirstButtonReturn:
        return None
    values = asdict(settings)
    for key, field in fields.items():
        if key in numbers:
            try:
                values[key] = int(field.stringValue()) if key == "tracking_pause_seconds" else float(field.stringValue())
            except ValueError as error:
                raise ValueError(f"{key} must be numeric.") from error
        else:
            values[key] = bool(field.state())
    return validate_settings(values)
