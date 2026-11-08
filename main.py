"""Run the camera and hand skeleton preview."""

from __future__ import annotations

import argparse
import sys
from contextlib import ExitStack
from collections.abc import Iterator
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

import cv2
import numpy as np

from camera import open_camera
from gestures import Gestures
from settings import DEFAULT_CONFIG, Settings, load_settings, save_settings, validate_settings
from overlay import WINDOW, TrackingMenu, show
from tracking import HandTracker
if sys.platform == "win32":
    from windows_ui import DesktopUI
else:
    from desktop_ui import DesktopUI, edit_settings, running_apps
from workflows import AppSwitcher, Calibration

if TYPE_CHECKING:
    from actions import Pointer

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"


def preview(camera: cv2.VideoCapture, tracker: HandTracker, pointer: Pointer | None, settings: Settings, config: Path, ui: DesktopUI, *, calibrate: bool = False) -> Iterator[None]:
    gestures = Gestures(settings)
    menu = TrackingMenu(settings.tracking_pause_seconds)
    cv2.setMouseCallback(WINDOW, menu.mouse)
    practice = pointer is None
    precision = False
    visible = True
    calibration = Calibration(monotonic() + 30) if calibrate else None
    switcher = None
    notice = ""
    notice_until = 0.0
    interval_start = monotonic()
    good_frames = 0
    fps = None
    failure_start = None
    next_report = 0.0
    camera_time = tracking_time = preview_time = 0.0
    frame_work = 0.0
    next_key_check = 0.0
    while True:
        frame_start = monotonic()
        now = frame_start
        if pointer is not None and calibration is None and now >= next_key_check:
            next_key_check = now + 0.10
            if pointer.quit_pressed():
                return
        command = ui.command()
        if command is not None:
            # Native menus can pause frame delivery while they are open.
            interval_start, good_frames, fps = now, 0, None
            camera_time = tracking_time = preview_time = frame_work = 0.0
        if command == "quit":
            return 0
        changed = menu.update(now)
        if command == "pause":
            menu.paused, menu.deadline = not menu.paused, None
            changed = True
        elif command == "timed":
            menu.paused, menu.deadline = True, now + menu.delay
            changed = True
        elif command == "preview":
            visible = not visible
            if visible:
                cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
                cv2.setMouseCallback(WINDOW, menu.mouse)
            else:
                cv2.destroyWindow(WINDOW)
        elif command == "practice" and pointer is not None:
            practice = not practice
            changed = True
        elif command == "precision" and pointer is not None:
            precision = not precision
            changed = True
        elif command in ("calibrate", "switch"):
            calibration = Calibration(now + 30) if command == "calibrate" and calibration is None else None
            apps = running_apps() if command == "switch" and switcher is None else []
            if command == "switch" and switcher is None and not apps:
                notice, notice_until = "No apps available", now + 3
            switcher = AppSwitcher(apps) if apps else None
            if not visible:
                visible = True
                cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
                cv2.setMouseCallback(WINDOW, menu.mouse)
            menu.paused, menu.deadline = False, None
            changed = True
        elif command == "settings":
            if pointer is not None:
                pointer.release()
            try:
                edited = edit_settings(settings)
                if edited is not None:
                    save_settings(config, edited)
                    settings = edited
                    menu.delay = settings.tracking_pause_seconds
                    notice = "Settings saved"
            except (ValueError, OSError) as error:
                notice = str(error)
            interval_start = monotonic()
            notice_until = interval_start + 4
            changed = True
        if changed:
            origin = pointer.normalized_position() if precision and pointer is not None and switcher is None else None
            gestures = Gestures(settings, precision_origin=origin)
            if pointer is not None:
                pointer.release()
            if menu.paused or command == "settings":
                calibration = switcher = None
        started = monotonic()
        ok, frame = camera.read()
        camera_time += monotonic() - started
        if ok and frame is not None and frame.size:
            frame = cv2.flip(frame, 1)
            started = monotonic()
            hands = [] if menu.paused else tracker.detect(frame)
            tracking_time += monotonic() - started
            status = "Hand detected" if hands else "Show one hand to the camera"
            good_frames += 1
            failure_start = None
        else:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            hands = []
            status = "Camera frame unavailable. Retrying..."
            if failure_start is None:
                failure_start = monotonic()

        now = monotonic()
        if menu.paused and failure_start is None:
            remaining = max(0, int(menu.deadline - now + 0.999)) if menu.deadline is not None else None
            status = "Tracking disabled" if remaining is None else f"Tracking resumes in {remaining}s"
        hand = hands[0] if hands else None
        if not menu.paused and failure_start is None:
            height, width = frame.shape[:2]
            if calibration is not None:
                sample = gestures.update(hand, now, width / height)
                status = calibration.update(hand if sample.position is not None else None, now)
                if now >= calibration.deadline:
                    try:
                        edited = validate_settings({**vars(settings), "calibrated_area": calibration.area(), "sensitivity": 1.0})
                        save_settings(config, edited)
                        settings = edited
                        status = "Calibration saved"
                    except (ValueError, OSError) as error:
                        status = str(error)
                    notice, notice_until = status, now + 4
                    calibration = None
                    origin = pointer.normalized_position() if precision and pointer is not None else None
                    gestures = Gestures(settings, precision_origin=origin)
            else:
                intent = gestures.update(hand, now, width / height)
                if switcher is not None:
                    app = switcher.update(intent.position, now)
                    status = "Point across app row | hold for 1s"
                    if app is not None:
                        if practice:
                            status = f"Practice: switch to {app.localizedName()}"
                        else:
                            status = f"Switch to {app.localizedName()}" if app.activateWithOptions_(0) else "Could not activate app"
                        notice, notice_until = status, now + 3
                        switcher = None
                        origin = pointer.normalized_position() if precision and pointer is not None else None
                        gestures = Gestures(settings, precision_origin=origin)
                else:
                    action_status = pointer.apply(intent) if pointer is not None and not practice else None
                    status = action_status or intent.label
                    if practice:
                        if intent.button in ("click", "down", "right") or intent.shortcut:
                            notice, notice_until = f"Practice: {intent.label}", now + 2
                        status = f"Practice: {status}"
                    elif precision:
                        status = f"Precision: {status}"
            if now < notice_until and calibration is None and switcher is None:
                status = notice
        elif failure_start is not None and pointer is not None:
            pointer.release()
            gestures.update(None, now, 1)
        ui.update(menu.paused or gestures.paused, bool(hands), visible, practice, precision)
        guide = settings.cursor_area if settings.cursor and not menu.paused and calibration is None else None
        if visible:
            started = monotonic()
            show(frame, hands, fps, status, menu=menu, guide=guide, switcher=switcher)
            preview_time += monotonic() - started
        if failure_start is not None and now - failure_start >= 3:
            raise RuntimeError("Camera stopped returning frames. Reopen the app and check Camera permission.")
        now = monotonic()
        frame_work += now - frame_start
        elapsed = now - interval_start
        if elapsed >= 1:
            fps = good_frames / elapsed
            if fps < 10 and now >= next_report:
                print(f"HandDesk {fps:.1f} FPS | camera {camera_time / elapsed:.0%} | "
                      f"tracking {tracking_time / elapsed:.0%} | drawing {preview_time / elapsed:.0%} | "
                      f"other work {max(0, frame_work - camera_time - tracking_time - preview_time) / elapsed:.0%} | "
                      f"between frames {max(0, elapsed - frame_work) / elapsed:.0%}",
                      flush=True)
                next_report = now + 3
            interval_start = now
            good_frames = 0
            camera_time = tracking_time = preview_time = frame_work = 0.0

        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, help="Override the configured camera index")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Local .task model path")
    parser.add_argument("--preview-only", action="store_true", help="Disable desktop control")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to the JSON settings file")
    parser.add_argument("--calibrate", action="store_true", help="Start reach calibration immediately")
    args = parser.parse_args()
    if args.camera is not None and args.camera < 0:
        parser.error("--camera must be zero or greater")

    try:
        settings = load_settings(args.config)
        if not args.model.is_file():
            raise RuntimeError(f"Model missing at {args.model}. Download the .task file first.")
        with ExitStack() as cleanup:
            pointer = None
            if not args.preview_only:
                try:
                    if sys.platform == "win32":
                        from windows_actions import Pointer
                    else:
                        from actions import Pointer
                except ImportError as error:
                    raise RuntimeError("Install pyobjc-framework-Quartz, or use --preview-only.") from error
                pointer = Pointer()
                cleanup.callback(pointer.release)
            tracker = HandTracker(args.model)
            cleanup.callback(tracker.close)
            camera = open_camera(settings.camera if args.camera is None else args.camera)
            cleanup.callback(camera.release)
            cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
            cleanup.callback(cv2.destroyAllWindows)
            ui = DesktopUI()
            cleanup.callback(ui.close)
            return ui.run(preview(camera, tracker, pointer, settings, args.config, ui, calibrate=args.calibrate))
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, ValueError, OSError, cv2.error) as error:
        parser.exit(1, f"HandDesk: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
