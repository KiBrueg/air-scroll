"""Compact, always-on-top local Air Scroll overlay."""
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import replace
from tkinter import ttk

import cv2
import mediapipe as mp
from PIL import Image, ImageTk

from airscroll.config import load_config, save_config
from airscroll.engine import TableDragConfig, TableDragEngine
from airscroll.visuals import blur_background_around_hand
from airscroll.winwheel import WheelSender


class AirScrollOverlay(tk.Tk):
    """Small preview/control overlay. Output remains off until explicitly enabled."""

    PREVIEW_WIDTH = 274
    PREVIEW_HEIGHT = 206

    def __init__(self) -> None:
        super().__init__()
        self.title("Air Scroll Overlay")
        self.geometry("290x272")
        self.minsize(290, 272)
        self.maxsize(290, 272)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.config_data = load_config()
        self.engine = TableDragEngine(
            TableDragConfig(smoothing_alpha=self.config_data.smoothing_alpha, movement_per_tick=0.05 / self.config_data.scroll_sensitivity)
        )
        self.sender = WheelSender()
        self.capture: cv2.VideoCapture | None = None
        self.hands = None
        self.photo = None
        self.camera_running = False
        self.control_enabled = tk.BooleanVar(value=False)
        self.blur_enabled = tk.BooleanVar(value=self.config_data.blur_background)
        self.status = tk.StringVar(value="Starting local camera preview · output disabled")

        self._build_ui()
        self.bind("<Escape>", lambda _event: self.pause_output("Paused with Esc"))
        self.after(120, self.start_camera)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        self.preview = ttk.Label(root, text="Opening camera…", anchor="center", relief="solid")
        self.preview.pack(fill="both", expand=True)

        ttk.Label(root, textvariable=self.status, anchor="center", wraplength=270, font=("Segoe UI", 8)).pack(fill="x", pady=(4, 3))
        controls = ttk.Frame(root)
        controls.pack(fill="x")
        self.enable_box = ttk.Checkbutton(
            controls,
            text="Scroll ON",
            variable=self.control_enabled,
            command=self.on_enable_change,
            state="disabled",
        )
        self.enable_box.pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Blur",
            variable=self.blur_enabled,
            command=self.on_blur_change,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="||", width=3, command=lambda: self.pause_output("Paused")).pack(side="right")
        ttk.Button(controls, text="×", width=3, command=self.close).pack(side="right", padx=(0, 4))

    def start_camera(self) -> None:
        if self.camera_running:
            return
        capture = cv2.VideoCapture(self.config_data.camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            self.status.set(f"Camera {self.config_data.camera_index} unavailable · output disabled")
            return
        # Best effort only: USB cameras/backends that expose autofocus keep the
        # hand sharp while it moves between an open hand and a fist.
        capture.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        self.capture = capture
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=1,
            min_detection_confidence=0.45,
            min_tracking_confidence=0.45,
        )
        self.camera_running = True
        self.enable_box.configure(state="normal")
        self.status.set("Preview active · output disabled")
        self.after(10, self.process_frame)

    def on_enable_change(self) -> None:
        self.engine.reset()
        if self.control_enabled.get():
            self.status.set("ACTIVE · move index fingertip down to scroll")
        else:
            self.status.set("Preview active · output disabled")

    def on_blur_change(self) -> None:
        enabled = bool(self.blur_enabled.get())
        self.config_data = replace(self.config_data, blur_background=enabled)
        save_config(self.config_data)
        self.status.set("Blur ON · preview background softened" if enabled else "Blur OFF · original preview")

    def pause_output(self, reason: str) -> None:
        self.control_enabled.set(False)
        self.engine.reset()
        self.status.set(f"{reason} · output disabled")

    @staticmethod
    def _observe(result):
        if not result.multi_hand_landmarks:
            return False, None, None
        points = result.multi_hand_landmarks[0].landmark
        return True, points[8].x, points[8].y

    def process_frame(self) -> None:
        if not self.camera_running or self.capture is None or self.hands is None:
            return
        ok, frame = self.capture.read()
        if not ok:
            self.pause_output("Camera frame unavailable")
            self.after(200, self.process_frame)
            return
        frame = cv2.flip(frame, 1)
        result = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        hand_present, index_x, index_y = self._observe(result)
        if hand_present:
            height, width = frame.shape[:2]
            landmarks = result.multi_hand_landmarks[0].landmark
            hand_points = [(int(point.x * width), int(point.y * height)) for point in landmarks]
            if self.blur_enabled.get():
                frame = blur_background_around_hand(frame, hand_points)

        ticks = self.engine.update(
            now_ms=int(time.monotonic() * 1000),
            hand_present=hand_present,
            index_y=index_y,
        )
        if self.control_enabled.get():
            if self.sender.escape_pressed():
                self.pause_output("Paused by global Esc")
            elif ticks:
                try:
                    self.sender.scroll(ticks)
                except OSError as exc:
                    self.pause_output(f"Wheel output error: {exc}")

        if hand_present:
            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                result.multi_hand_landmarks[0],
                mp.solutions.hands.HAND_CONNECTIONS,
                mp.solutions.drawing_utils.DrawingSpec(color=(120, 120, 120), thickness=1, circle_radius=1),
                mp.solutions.drawing_utils.DrawingSpec(color=(90, 90, 90), thickness=1),
            )
            height, width = frame.shape[:2]
            point = (int(index_x * width), int(index_y * height))
            cv2.circle(frame, point, 17, (255, 255, 255), 5)
            cv2.circle(frame, point, 13, (0, 0, 255), 4)
            cv2.circle(frame, point, 4, (0, 0, 255), -1)
            cv2.putText(frame, "INDEX FOUND", (point[0] + 20, max(28, point[1] - 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 255), 2)
            state = self.engine.motion_label
            if state == "DRAG DOWN":
                cv2.putText(frame, state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 180, 255), 2)
            elif state == "RETURN IGNORED":
                cv2.putText(frame, state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 230, 0), 2)
            elif state == "POINT FIXED":
                cv2.putText(frame, state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 230, 0), 2)
            if not self.control_enabled.get():
                self.status.set(f"INDEX FOUND · {state} · output disabled")
        else:
            lost_state = self.engine.motion_label
            message = "HAND HOLD · KEEPING POINT" if lost_state == "HAND HOLD" else "HAND NOT DETECTED"
            color = (0, 190, 255) if lost_state == "HAND HOLD" else (0, 0, 255)
            cv2.putText(frame, message, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2)
            if not self.control_enabled.get():
                self.status.set(f"{message} · output disabled")

        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))
        self.photo = ImageTk.PhotoImage(image=image)
        self.preview.configure(image=self.photo, text="")
        self.after(15, self.process_frame)

    def close(self) -> None:
        self.pause_output("Closed")
        self.camera_running = False
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.hands is not None:
            self.hands.close()
            self.hands = None
        self.destroy()


if __name__ == "__main__":
    AirScrollOverlay().mainloop()
