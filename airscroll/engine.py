"""Gesture engines for local, wheel-only index-fingertip control."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass
class GestureConfig:
    down_threshold: float = 0.08
    up_threshold: float = 0.08
    release_ratio: float = 0.35
    smoothing_alpha: float = 0.35
    gesture_ticks: int = 3


class ScrollEngine:
    """Legacy discrete stroke recognizer retained for calibration compatibility."""

    def __init__(self, config: GestureConfig | None = None) -> None:
        self.config = config or GestureConfig()
        self.reset()

    def reset(self) -> None:
        self._filtered_y: float | None = None
        self._baseline: float | None = None
        self._locked_direction: str | None = None
        self._locked_amplitude = 0.0
        self.motion_label = "NO HAND"

    def _filter(self, index_y: float) -> float:
        if self._filtered_y is None:
            self._filtered_y = index_y
            return index_y
        alpha = max(0.05, min(1.0, self.config.smoothing_alpha))
        self._filtered_y = alpha * index_y + (1.0 - alpha) * self._filtered_y
        return self._filtered_y

    def update(self, *, now_ms: int, hand_present: bool, index_y: float | None = None) -> int:
        del now_ms
        if not hand_present or index_y is None:
            self.reset()
            return 0
        y = self._filter(index_y)
        if self._baseline is None:
            self._baseline = y
            self.motion_label = "READY"
            return 0
        if self._locked_direction is not None:
            returned = y <= self._baseline + self._locked_amplitude * self.config.release_ratio if self._locked_direction == "DOWN" else y >= self._baseline - self._locked_amplitude * self.config.release_ratio
            if returned:
                self._baseline = y
                self._locked_direction = None
                self._locked_amplitude = 0.0
                self.motion_label = "READY"
            else:
                self.motion_label = "RETURN IGNORED"
            return 0
        down, up = y - self._baseline, self._baseline - y
        if down >= self.config.down_threshold:
            self._locked_direction, self._locked_amplitude, self.motion_label = "DOWN", down, "DOWN"
            return -max(1, int(self.config.gesture_ticks))
        if up >= self.config.up_threshold:
            self._locked_direction, self._locked_amplitude, self.motion_label = "UP", up, "UP"
            return max(1, int(self.config.gesture_ticks))
        self.motion_label = "READY"
        return 0


@dataclass
class TableDragConfig:
    """Thresholds for a camera placed at table level, facing across the surface."""

    contact_min_y: float = 0.70
    contact_hold_ms: int = 120
    contact_jitter: float = 0.012
    movement_per_tick: float = 0.020
    smoothing_alpha: float = 0.35
    hand_loss_grace_ms: int = 700
    max_ticks_per_frame: int = 3


class TableDragEngine:
    """Continuous page-down scrolling from index-fingertip downward movement.

    The first tracked fingertip coordinate becomes the reference point. Moving
    down in the camera image emits continuous page-down ticks. Upward return is
    explicitly ignored so it cannot create unintended page-up scrolling.
    """

    def __init__(self, config: TableDragConfig | None = None) -> None:
        self.config = config or TableDragConfig()
        self.reset()

    def reset(self) -> None:
        self._filtered_y: float | None = None
        self._candidate_y: float | None = None
        self._candidate_since: int | None = None
        self._surface_fixed = False
        self._last_y: float | None = None
        self._hand_missing_since: int | None = None
        self._residual = 0.0
        self.motion_label = "NO HAND"

    def _filter(self, index_y: float) -> float:
        if self._filtered_y is None:
            self._filtered_y = index_y
            return index_y
        alpha = max(0.05, min(1.0, self.config.smoothing_alpha))
        self._filtered_y = alpha * index_y + (1.0 - alpha) * self._filtered_y
        return self._filtered_y

    def update(self, *, now_ms: int, hand_present: bool, index_y: float | None = None) -> int:
        if not hand_present or index_y is None:
            if self._surface_fixed:
                if self._hand_missing_since is None:
                    self._hand_missing_since = now_ms
                if now_ms - self._hand_missing_since < max(0, self.config.hand_loss_grace_ms):
                    self.motion_label = "HAND HOLD"
                    return 0
            self.reset()
            return 0

        y = self._filter(index_y)
        if self._hand_missing_since is not None:
            # A fist or brief occlusion can hide landmark 8. Re-anchor y on
            # reacquisition so its changed pose cannot cause a scroll jump,
            # while retaining the user's existing movement point.
            self._hand_missing_since = None
            if self._surface_fixed:
                self._last_y = y
                self._residual = 0.0
                self.motion_label = "POINT FIXED"
                return 0

        if not self._surface_fixed:
            self._surface_fixed = True
            self._last_y = y
            self._residual = 0.0
            self.motion_label = "POINT FIXED"
            return 0

        assert self._last_y is not None
        vertical_motion = y - self._last_y
        self._last_y = y
        if vertical_motion <= self.config.contact_jitter:
            if vertical_motion < -self.config.contact_jitter:
                self._residual = 0.0
                self.motion_label = "RETURN IGNORED"
            else:
                self.motion_label = "POINT FIXED"
            return 0

        self._residual += vertical_motion
        step = max(0.003, self.config.movement_per_tick)
        ticks = int(self._residual / step)
        if ticks <= 0:
            self.motion_label = "DRAG DOWN"
            return 0
        cap = max(1, int(self.config.max_ticks_per_frame))
        ticks = min(cap, ticks)
        self._residual -= ticks * step
        self.motion_label = "DRAG DOWN"
        # Windows wheel convention: negative scrolls page down.
        return -ticks


class CalibrationSession:
    """Collect repeated one-direction strokes while ignoring their return phase."""

    def __init__(self, *, direction: str, target_samples: int = 10, minimum_amplitude: float = 0.03) -> None:
        if direction not in {"UP", "DOWN"}:
            raise ValueError("direction must be UP or DOWN")
        self.direction = direction
        self.target_samples = max(1, int(target_samples))
        self.minimum_amplitude = max(0.005, float(minimum_amplitude))
        self.samples: list[float] = []
        self._baseline: float | None = None
        self._locked_amplitude = 0.0
        self._waiting_for_return = False

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def complete(self) -> bool:
        return self.count >= self.target_samples

    @property
    def threshold(self) -> float:
        return max(self.minimum_amplitude, float(median(self.samples)) * 0.5) if self.samples else self.minimum_amplitude

    @property
    def status_label(self) -> str:
        return f"CALIBRATE {self.direction} {self.count}/{self.target_samples}"

    def update(self, *, hand_present: bool, index_y: float | None) -> bool:
        if not hand_present or index_y is None:
            self._baseline = None
            self._waiting_for_return = False
            return False
        if self.complete:
            return True
        if self._baseline is None:
            self._baseline = index_y
            return False
        signed = index_y - self._baseline if self.direction == "DOWN" else self._baseline - index_y
        if self._waiting_for_return:
            if abs(index_y - self._baseline) <= self._locked_amplitude * 0.35:
                self._baseline = index_y
                self._waiting_for_return = False
            return False
        if signed >= self.minimum_amplitude:
            self.samples.append(abs(signed))
            self._locked_amplitude = abs(signed)
            self._waiting_for_return = True
            return self.complete
        return False
