"""Load and validate HandDesk's local JSON settings."""

from dataclasses import asdict, dataclass
import json
import os
from tempfile import NamedTemporaryFile
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().with_name("settings.json")


@dataclass(frozen=True)
class Settings:
    camera: int = 0
    tracking_pause_seconds: int = 30
    sensitivity: float = 1.0
    smoothing_ms: float = 30
    dwell_seconds: float = 1.5
    cursor: bool = True
    dwell_click: bool = True
    pinch_click: bool = True
    drag: bool = True
    right_click: bool = True
    scroll: bool = True
    desktop_switch: bool = True
    mission_control: bool = True
    fullscreen: bool = True
    minimize: bool = True
    volume: bool = True
    calibrated_area: list[float] | None = None

    @property
    def cursor_area(self) -> tuple[float, float, float, float]:
        left, top, right, bottom = self.calibrated_area or (0.24, 0.23, 0.76, 0.72)
        x, y = (left + right) / 2, (top + bottom) / 2
        half_width = (right - left) / (2 * self.sensitivity)
        half_height = (bottom - top) / (2 * self.sensitivity)
        return (max(0, x - half_width), max(0, y - half_height),
                min(1, x + half_width), min(1, y + half_height))


def load_settings(path: Path) -> Settings:
    with path.open(encoding="utf-8") as file:
        return validate_settings(json.load(file))


def validate_settings(values: object) -> Settings:
    if not isinstance(values, dict):
        raise ValueError("Settings must be a JSON object.")
    defaults = asdict(Settings())
    ranges = {"sensitivity": (0.65, 2.0), "smoothing_ms": (0, 200), "dwell_seconds": (0.3, 10)}
    for key, value in values.items():
        if key not in defaults:
            raise ValueError(f"Unknown setting: {key}")
        if key in ranges:
            low, high = ranges[key]
            if type(value) not in (int, float) or not low <= value <= high:
                raise ValueError(f"{key} must be a number from {low} to {high}.")
        elif key == "calibrated_area":
            if value is None:
                continue
            if not isinstance(value, list) or len(value) != 4 or any(
                type(v) not in (int, float) or not 0 <= v <= 1 for v in value
            ) or value[2] - value[0] < 0.1 or value[3] - value[1] < 0.1:
                raise ValueError("Calibration needs a reachable rectangle inside the camera view.")
        elif key == "tracking_pause_seconds":
            if type(value) is not int or not 1 <= value <= 3600:
                raise ValueError("tracking_pause_seconds must be an integer from 1 to 3600.")
        elif key == "camera":
            if type(value) is not int or value < 0:
                raise ValueError("camera must be a non-negative integer.")
        elif type(value) is not bool:
            raise ValueError(f"{key} must be true or false.")
    return Settings(**values)


def save_settings(path: Path, settings: Settings) -> None:
    temporary = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(asdict(settings), file, indent=2)
            file.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
