"""Open the requested camera using a platform-appropriate backend."""

import sys

import cv2


def open_camera(index: int) -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_AVFOUNDATION
    camera = cv2.VideoCapture(index, backend)
    if not camera.isOpened() and sys.platform == "win32":
        camera.release()
        camera = cv2.VideoCapture(index, cv2.CAP_MSMF)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(
            f"Could not open camera {index}. Check Camera permission, "
            "close other camera apps, or try --camera 1."
        )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera
