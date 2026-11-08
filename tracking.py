"""Convert local frames to plain lists of normalized (x, y, z) landmarks."""

from pathlib import Path
from time import monotonic_ns

import cv2
import mediapipe as mp
from numpy.typing import NDArray
from numpy import uint8

type Point = tuple[float, float, float]
type Hand = list[Point]
type Frame = NDArray[uint8]


class HandTracker:
    def __init__(self, model: Path) -> None:
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
        )
        self._detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._last_ms = -1

    def detect(self, frame: Frame) -> list[Hand]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires a strictly increasing timestamp in milliseconds.
        self._last_ms = max(monotonic_ns() // 1_000_000, self._last_ms + 1)
        result = self._detector.detect_for_video(image, self._last_ms)
        return [
            [(point.x, point.y, point.z) for point in hand]
            for hand in result.hand_landmarks
        ]

    def close(self) -> None:
        self._detector.close()
