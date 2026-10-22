# Air Scroll

![Air Scroll concept: webcam-controlled vertical scrolling](assets/air-scroll-concept.png)

A small Windows overlay that processes a USB camera feed locally and turns **downward index-fingertip motion** into vertical mouse-wheel scrolling.

> **Status:** experimental local desktop utility. It is not a security boundary and should be used only on a machine where you control the active window.

## Privacy and safety

- Camera frames are processed locally in memory with OpenCV and MediaPipe.
- The application does not upload frames, send telemetry, or use network APIs at runtime.
- Output is **off by default**.
- The only generated Windows input is a vertical wheel event (`MOUSEEVENTF_WHEEL` via `SendInput`). It does not move the cursor, click, type, use shortcuts, create startup entries, or change the registry.
- Press **Esc** or the overlay pause button to disable wheel output immediately.

## Overlay behavior

- The first detected index-fingertip position becomes a local movement point.
- Move the fingertip **downward in the preview** to scroll down continuously.
- Upward return is ignored, so it cannot accidentally scroll up.
- Brief hand-loss (for example while making a fist) is held briefly and safely re-anchored on reacquisition without a wheel jump.
- **Blur** affects only the displayed preview; hand tracking always uses the original frame.

## Requirements

- Windows
- Python 3.11
- A USB/web camera

## Run

1. Double-click `Start Air Scroll.bat`.
2. The first launch creates `.venv` and installs the hash-pinned dependencies from `requirements.lock`.
3. The compact overlay starts with output disabled.
4. Confirm that `INDEX FOUND` follows your index fingertip, then enable **Scroll ON** deliberately.

The main overlay starts the camera selected by the local configuration. If your camera is not the default one, use `Air Scroll Settings.bat` to select it and save settings locally. Local settings are ignored by Git. `settings.example.json` documents the default schema.

## Tests

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Public-source hygiene

This repository intentionally excludes local settings, virtual environments, caches, internal planning notes, and user-specific desktop launchers. See [PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md).

## License

MIT. See [LICENSE](LICENSE). Third-party notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
