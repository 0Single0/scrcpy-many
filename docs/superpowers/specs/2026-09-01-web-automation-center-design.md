# Web Automation Center Design

## Goal

Deliver a Windows desktop automation center with a modern HTML/CSS interface. It selects one explicit Android ADB device per plan, records scrcpy actions, edits JSON plans, runs them immediately, and manages daily schedules without requiring the end user to use a terminal or install Python.

## Product Boundary

The existing `scrcpy.exe` remains the fast multi-device picker and mirroring entry point. A new `scrcpy-automation.exe` is placed beside it in the portable folder. It launches a normal scrcpy session only for recording, and it owns plan editing, execution, scheduling, run history, and failure-artifact views.

The first release is Windows-only and offline. `pywebview` hosts locally bundled React assets through WebView2. A Python bridge exposes only a small allowlisted API to the page; JavaScript cannot execute arbitrary commands. PyInstaller produces the executable, so no system Python is required.

## User Flows

1. The user opens `scrcpy-automation.exe` from the portable folder.
2. The app uses `platform-tools\\adb.exe` and lists every ADB device. A plan can be saved only with one ready serial.
3. The user creates or opens a plan, changes its name, serial, daily time, and ordered actions, then saves it under `plans/`.
4. Record starts packaged `scrcpy.exe --serial SERIAL --record-actions TEMP`. Stop ends only that session, validates the result, then loads it into the editor.
5. Run now calls the existing validated runner and returns status, log path, and failure screenshot path.
6. Enable schedule and Disable schedule use the existing `schtasks.exe` command builders and report the exact task name.

## UI Scope

The first release contains a device sidebar, plan list, plan metadata form, ordered action editor, recording controls, run result panel, and run-history drawer. It uses React, CSS variables, local icons, Chinese text, keyboard focus states, and high-DPI Windows sizing. It has no remote service, account, plugin system, flow canvas, control-tree selector, loops, conditions, or credential storage.

## Plan and Recording Contract

Plans continue using `tools/scrcpy_automation.py`, and every plan contains one non-empty `serial`. The UI never infers a target from the first connected device. Recorded touch sequences become `tap` or `swipe` with measured `wait` steps. Only supported, non-repeated Android key-down events become `keyevent` actions; SDL scancodes and a `key_action` property are never written. Clipboard, file-drop, gamepad input, PINs, passwords, and biometric data are not recorded.

## Backend Bridge

The Python bridge returns JSON-compatible dictionaries only:

```python
list_devices() -> list[dict[str, str]]
list_plans() -> list[dict[str, str]]
load_plan(path: str) -> dict[str, object]
save_plan(document: dict[str, object], path: str | None) -> dict[str, object]
start_recording(serial: str) -> dict[str, str]
stop_recording() -> dict[str, object]
run_plan_now(path: str, dry_run: bool) -> dict[str, object]
set_schedule(path: str) -> dict[str, str]
remove_schedule(name: str) -> dict[str, str]
list_runs(plan_name: str) -> list[dict[str, str]]
```

It canonicalizes paths below the portable root `plans/` and `logs/` folders. Plans can be imported only after validation. Save and save-as always write to `plans/`. Errors use `{ "ok": false, "code": "...", "message": "..." }`.

## Packaging and Failure Handling

The release package retains `scrcpy.exe`, `bin/`, `lib/`, and `platform-tools/`, and adds `scrcpy-automation.exe`, `plans/`, and `logs/`. Frontend assets and the Python bridge live inside the PyInstaller executable; the release contains no Python, Node, `node_modules`, source, test executables, or build directories. ADB authorization/offline state remains visible. Invalid plans are never saved. Failed real runs retain `run.log` and `failure.png` when available. Failed recordings delete only temporary output and preserve the previous editor plan.

## Acceptance Criteria

- The portable directory runs `scrcpy-automation.exe` without system Python.
- Users can create, edit, save, dry-run, run, schedule, and unschedule a plan for one selected serial without a terminal.
- Recorded taps, swipes, and supported keys validate and replay through the existing Python runner without a schema conversion step.
- Bridge Python tests, React tests, C recorder tests, and package checks pass.
