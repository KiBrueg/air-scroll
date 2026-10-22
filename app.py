from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import mediapipe as mp
from PIL import Image, ImageTk

from airscroll.config import AppConfig, load_config, save_config
from airscroll.engine import CalibrationSession, GestureConfig, ScrollEngine, TableDragConfig, TableDragEngine
from airscroll.visuals import blur_background_around_hand
from airscroll.winwheel import WheelSender


class AirScrollApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Air Scroll — Local Wheel Control")
        self.geometry("940x700")
        self.minsize(820, 620)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.config_data = load_config()
        self.engine = TableDragEngine(self._gesture_config())
        self.calibration: CalibrationSession | None = None
        self.sender = WheelSender()
        self.capture: cv2.VideoCapture | None = None
        self.hands = None
        self.photo = None
        self.camera_running = False
        self.control_enabled = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Camera off · output disabled")
        self.detail = tk.StringVar(value="Start the camera. Scrolling is always OFF at launch.")

        self._build_ui()
        self.bind("<Escape>", lambda _event: self.pause_control("Paused with Esc"))

    def _gesture_config(self) -> TableDragConfig:
        return TableDragConfig(
            smoothing_alpha=self.config_data.smoothing_alpha,
            movement_per_tick=0.05 / self.config_data.scroll_sensitivity,
        )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(0, weight=1)

        preview_box = ttk.LabelFrame(root, text="Local camera preview", padding=8)
        preview_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        preview_box.rowconfigure(0, weight=1)
        preview_box.columnconfigure(0, weight=1)
        self.preview = ttk.Label(preview_box, anchor="center", text="Camera preview is off")
        self.preview.grid(row=0, column=0, sticky="nsew")

        controls = ttk.LabelFrame(root, text="Safe controls", padding=12)
        controls.grid(row=0, column=1, sticky="nsew")
        controls.columnconfigure(0, weight=1)

        ttk.Label(controls, textvariable=self.status, wraplength=290, font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )
        ttk.Label(controls, textvariable=self.detail, wraplength=290).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.start_button = ttk.Button(controls, text="Start camera", command=self.start_camera)
        self.start_button.grid(row=2, column=0, sticky="ew", pady=3)
        self.stop_button = ttk.Button(controls, text="Stop camera", command=self.stop_camera, state="disabled")
        self.stop_button.grid(row=3, column=0, sticky="ew", pady=3)
        self.enable_box = ttk.Checkbutton(
            controls,
            text="Enable Air Scroll (wheel only)",
            variable=self.control_enabled,
            command=self.on_enable_change,
            state="disabled",
        )
        self.enable_box.grid(row=4, column=0, sticky="w", pady=(12, 3))
        ttk.Button(controls, text="Pause output (Esc)", command=lambda: self.pause_control("Paused manually")).grid(
            row=5, column=0, sticky="ew", pady=3
        )

        ttk.Separator(controls).grid(row=6, column=0, sticky="ew", pady=12)
        ttk.Label(controls, text="Settings are saved locally in this project folder.", wraplength=290).grid(
            row=7, column=0, sticky="ew", pady=(0, 8)
        )

        self.camera_var = tk.IntVar(value=self.config_data.camera_index)
        self.sensitivity = tk.DoubleVar(value=self.config_data.scroll_sensitivity)
        self.smoothing = tk.DoubleVar(value=self.config_data.smoothing_alpha)

        self._scale(controls, "Camera index", self.camera_var, 0, 4, 1, 8)
        self._scale(controls, "Scroll sensitivity (higher = faster)", self.sensitivity, 1.0, 10.0, 0.5, 9)
        self._scale(controls, "Smoothing", self.smoothing, 0.05, 0.95, 0.05, 10)
        ttk.Button(controls, text="Reset movement point", command=self.reset_surface_fixation).grid(row=11, column=0, sticky="ew", pady=(8, 3))
        self.calibration_label = tk.StringVar(value="Down-only mode: first fingertip point is fixed automatically; move it downward for page down.")
        ttk.Label(controls, textvariable=self.calibration_label, wraplength=290).grid(row=12, column=0, sticky="ew", pady=(4, 3))
        ttk.Button(controls, text="Save settings", command=self.save_settings).grid(row=13, column=0, sticky="ew", pady=(8, 3))

        footer = ttk.Label(
            self,
            text="Privacy: camera frames stay in memory on this PC. This program emits only vertical mouse-wheel events — never pointer moves, clicks, keys, startup entries, or network requests.",
            wraplength=900,
            justify="left",
            padding=(14, 0, 14, 12),
        )
        footer.pack(fill="x")

    def _scale(self, parent, label, variable, low, high, resolution, row):
        box = ttk.Frame(parent)
        box.grid(row=row, column=0, sticky="ew", pady=3)
        ttk.Label(box, text=label).pack(anchor="w")
        tk.Scale(box, variable=variable, from_=low, to=high, resolution=resolution, orient="horizontal", showvalue=True).pack(fill="x")

    def start_camera(self) -> None:
        if self.camera_running:
            return
        camera_index = int(self.camera_var.get())
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            self.status.set("Camera error · output disabled")
            self.detail.set(f"Could not open camera {camera_index}. Try another Camera index.")
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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
        self.engine.reset()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.enable_box.configure(state="normal")
        self.status.set("Preview active · output disabled")
        self.detail.set("The first fingertip position is fixed automatically. Move it downward for continuous page-down scrolling; upward return is ignored.")
        self.after(10, self.process_frame)

    def stop_camera(self) -> None:
        self.pause_control("Camera stopped · output disabled")
        self.camera_running = False
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if self.hands is not None:
            self.hands.close()
            self.hands = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.enable_box.configure(state="disabled")
        self.preview.configure(image="", text="Camera preview is off")
        self.photo = None

    def on_enable_change(self) -> None:
        self.engine.reset()
        if self.control_enabled.get():
            self.status.set("Air Scroll active · continuous down-only mode")
            self.detail.set("Move the fingertip downward for continuous page down. Upward return is ignored. Press Esc to pause.")
        else:
            self.status.set("Preview active · output disabled")
            self.detail.set("Camera may stay on, but no Windows input is sent.")

    def pause_control(self, reason: str) -> None:
        self.control_enabled.set(False)
        self.engine.reset()
        if self.camera_running:
            self.status.set("Preview active · output disabled")
        else:
            self.status.set("Camera off · output disabled")
        self.detail.set(reason)

    def reset_surface_fixation(self) -> None:
        self.calibration = None
        self.engine.reset()
        self.pause_control("Movement point reset; output disabled")
        self.calibration_label.set("The next detected fingertip position will become the new movement point.")
        self.detail.set("No press is required: downward movement = continuous page down; upward return is ignored.")

    def save_settings(self) -> None:
        self.config_data = AppConfig(
            camera_index=int(self.camera_var.get()),
            down_threshold=self.config_data.down_threshold,
            up_threshold=self.config_data.up_threshold,
            release_ratio=self.config_data.release_ratio,
            smoothing_alpha=float(self.smoothing.get()),
            scroll_sensitivity=float(self.sensitivity.get()),
            blur_background=self.config_data.blur_background,
            gesture_ticks=self.config_data.gesture_ticks,
        )
        save_config(self.config_data)
        self.engine = TableDragEngine(self._gesture_config())
        self.detail.set("Settings saved locally. Scroll sensitivity controls how much page travel each finger movement produces; higher is faster.")

    def _observe(self, result):
        if not result.multi_hand_landmarks:
            return False, None, None
        points = result.multi_hand_landmarks[0].landmark
        return True, points[8].x, points[8].y

    def process_frame(self) -> None:
        if not self.camera_running or self.capture is None or self.hands is None:
            return
        ok, frame = self.capture.read()
        if not ok:
            self.pause_control("Camera frame unavailable; output paused")
            self.after(200, self.process_frame)
            return
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)
        hand_present, index_x, index_y = self._observe(result)
        if hand_present:
            height, width = frame.shape[:2]
            landmarks = result.multi_hand_landmarks[0].landmark
            hand_points = [(int(point.x * width), int(point.y * height)) for point in landmarks]
            # Preview-only effect: recognition already ran on the unblurred frame.
            frame = blur_background_around_hand(frame, hand_points)

        # Surface contact is inferred locally; preview recognition never emits input by itself.
        ticks = self.engine.update(
            now_ms=int(time.monotonic() * 1000),
            hand_present=hand_present,
            index_y=index_y,
        )
        if self.control_enabled.get():
            if self.sender.escape_pressed():
                self.pause_control("Paused by global Esc")
            elif ticks:
                try:
                    self.sender.scroll(ticks)
                except OSError as exc:
                    self.pause_control(f"Wheel output error: {exc}")

        if hand_present:
            # Calibration visualization only: these landmarks never control Windows.
            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                result.multi_hand_landmarks[0],
                mp.solutions.hands.HAND_CONNECTIONS,
                mp.solutions.drawing_utils.DrawingSpec(color=(120, 120, 120), thickness=1, circle_radius=1),
                mp.solutions.drawing_utils.DrawingSpec(color=(90, 90, 90), thickness=1),
            )
            height, width = frame.shape[:2]
            point = (int(index_x * width), int(index_y * height))
            direction = self.engine.motion_label
            cv2.circle(frame, point, 17, (255, 255, 255), 5)
            cv2.circle(frame, point, 13, (0, 0, 255), 4)
            cv2.circle(frame, point, 4, (0, 0, 255), -1)
            cv2.putText(frame, "INDEX FOUND", (point[0] + 20, max(28, point[1] - 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 255), 2)
            if direction == "DRAG DOWN":
                cv2.putText(frame, direction, (12, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 255), 2)
            elif direction == "RETURN IGNORED":
                cv2.putText(frame, direction, (12, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 230, 0), 2)
            elif direction == "POINT FIXED":
                cv2.putText(frame, "POINT FIXED", (12, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 230, 0), 2)
            if not self.control_enabled.get():
                self.status.set(f"Down-only mode: {direction}")
                self.detail.set("No press is required. Move the fingertip downward for page down; upward return is ignored.")
        else:
            cv2.putText(frame, "HAND NOT DETECTED: show wrist + index", (12, frame.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 255), 2)
            if not self.control_enabled.get():
                self.status.set("No hand detected · output disabled")
                self.detail.set("Move the hand 25–40 cm from the camera; keep wrist and index fingertip inside the frame.")
        state = self.engine.motion_label if self.control_enabled.get() else "Preview"
        color = (0, 200, 0) if self.control_enabled.get() else (0, 160, 230)
        cv2.putText(frame, state, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, "Esc = pause", (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        if self.control_enabled.get():
            self.status.set(f"Air Scroll · {state}")

        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((600, 450))
        self.photo = ImageTk.PhotoImage(image=image)
        self.preview.configure(image=self.photo, text="")
        self.after(15, self.process_frame)

    def close(self) -> None:
        self.stop_camera()
        self.destroy()


if __name__ == "__main__":
    AirScrollApp().mainloop()
