# Public release audit

This repository was prepared as a sanitized public-source copy on 2026-10-22.

## Excluded intentionally

- Local settings (`air-scroll-settings.json`)
- Python virtual environments and bytecode (`.venv/`, `__pycache__/`, `*.pyc`)
- Internal planning material (`.hermes/`)
- Desktop launch wrappers containing absolute local paths

## Static audit summary

- No hardcoded credentials, tokens, private keys, passwords, IP addresses, email addresses, or personal local paths are included in the selected source package.
- The application has no runtime HTTP client, socket client, telemetry, analytics, or image upload code. Network access occurs only when the user installs dependencies with `pip`.
- Camera frames are processed locally in memory and are not written to disk by the application.
- Windows input is intentionally limited to vertical wheel events via `SendInput`; the code does not move the pointer, click, type, create startup entries, or edit the registry.

## Release verification required before publishing

Run `python -m unittest discover -s tests -v` and inspect `git status --ignored` before the first public push. Never add a local `air-scroll-settings.json`, `.env`, `.venv/`, or `.hermes/` directory.
