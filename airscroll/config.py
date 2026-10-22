"""Validated local settings store; configuration values are never executed."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppConfig:
    camera_index: int = 0
    down_threshold: float = 0.08
    up_threshold: float = 0.08
    release_ratio: float = 0.35
    smoothing_alpha: float = 0.35
    scroll_sensitivity: float = 3.0
    blur_background: bool = True
    gesture_ticks: int = 3


def settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / "air-scroll-settings.json"


def load_config() -> AppConfig:
    defaults = AppConfig()
    path = settings_path()
    if not path.exists():
        return defaults
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return defaults
        return AppConfig(
            camera_index=max(0, min(9, int(raw.get("camera_index", defaults.camera_index)))),
            down_threshold=max(0.02, min(0.50, float(raw.get("down_threshold", defaults.down_threshold)))),
            up_threshold=max(0.02, min(0.50, float(raw.get("up_threshold", defaults.up_threshold)))),
            release_ratio=max(0.15, min(0.60, float(raw.get("release_ratio", defaults.release_ratio)))),
            smoothing_alpha=max(0.05, min(1.0, float(raw.get("smoothing_alpha", defaults.smoothing_alpha)))),
            scroll_sensitivity=max(1.0, min(10.0, float(raw.get("scroll_sensitivity", defaults.scroll_sensitivity)))),
            blur_background=bool(raw.get("blur_background", defaults.blur_background)),
            gesture_ticks=max(1, min(5, int(raw.get("gesture_ticks", defaults.gesture_ticks)))),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return defaults


def save_config(config: AppConfig) -> None:
    path = settings_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    temporary.replace(path)
