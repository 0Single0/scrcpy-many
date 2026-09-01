# Web Automation Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a portable Windows `scrcpy-automation.exe` with a React/HTML UI for selecting one device, recording and editing plans, running plans, and managing daily schedules.

**Architecture:** Keep `scrcpy.exe` as the native device picker and mirroring executable. Add a Python `pywebview` host with a constrained local bridge for bundled React assets. The bridge reuses `tools/scrcpy_automation.py` for validation, ADB execution, and Task Scheduler commands, launching the packaged `scrcpy.exe` only while recording. PyInstaller freezes the bridge and frontend as `scrcpy-automation.exe`.

**Tech Stack:** Python 3.10+, `pywebview`, PyInstaller, React, TypeScript, Vite, Vitest, existing `unittest`, ADB, Windows WebView2, `schtasks.exe`.

**Spec:** `docs/superpowers/specs/2026-09-01-web-automation-center-design.md`

## Global Constraints

- The app is Windows-only, local-only, and starts no HTTP listener.
- Every plan has one explicit serial and no execution path selects a device implicitly.
- JavaScript can call only typed bridge methods; it cannot pass shell strings or arbitrary executable paths.
- The application never records or stores credentials, clipboard data, file-drop events, or gamepad input.
- The final package retains `scrcpy.exe`, `bin/`, `lib/`, and `platform-tools/`, and requires no system Python or Node runtime.
- All UI labels are Chinese UTF-8 text and render correctly on a high-DPI Windows display.

---

### Task 1: Stabilize the Recorder-to-Runner Contract

**Files:**
- Modify: `app/src/automation_recorder.c`
- Modify: `app/src/automation_recorder.h`
- Modify: `app/src/input_manager.c`
- Modify: `app/tests/test_automation_recorder.c`
- Modify: `tests/test_scrcpy_automation.py`

**Interfaces:**
- Produces `bool sc_automation_recorder_record_key(uint32_t keycode, uint32_t elapsed_ms)`.
- Produces recorder JSON `{"action":"keyevent","code":ANDROID_KEYCODE}` only for non-repeat key-down events.

- [ ] **Step 1: Write failing C assertions for replayable key output**

```c
assert(strstr(buffer, "\"action\":\"keyevent\",\"code\":4") != NULL);
assert(strstr(buffer, "\"key_action\"") == NULL);
```

- [ ] **Step 2: Run the focused recorder test and verify it fails**

Run: `& D:\msys64\usr\bin\bash.exe -lc "export PATH=/mingw64/bin:/usr/bin:`$PATH; ninja -C /d/scrcpy-build app/test_automation_recorder.exe && /d/scrcpy-build/app/test_automation_recorder.exe"`

Expected: FAIL because the current recorder writes an SDL scancode and `key_action`.

- [ ] **Step 3: Record normalized Android keys only**

Use the existing Android key-code mapping path used by the SDK keyboard processor, then write this behavior:

```c
if (im->recorder_started && down && !repeat && keycode != AKEYCODE_UNKNOWN) {
    sc_automation_recorder_record_key(keycode, elapsed);
}
```

Remove `key_action` from the writer and update every function declaration/call site.

- [ ] **Step 4: Add a Python validation fixture**

```python
plan = validate_plan({"serial": "ABC", "steps": [{"action": "wait", "ms": 50}, {"action": "keyevent", "code": 4}]})
self.assertEqual(plan.steps[-1].params["code"], 4)
```

- [ ] **Step 5: Run C and Python tests**

Run: `& D:\msys64\usr\bin\bash.exe -lc "export PATH=/mingw64/bin:/usr/bin:`$PATH; meson test -C /d/scrcpy-build --print-errorlogs"`; then `python -m unittest tests.test_scrcpy_automation -v`.

Expected: PASS.

- [ ] **Step 6: Commit the recorder contract**

Run: `git add app/src/automation_recorder.c app/src/automation_recorder.h app/src/input_manager.c app/tests/test_automation_recorder.c tests/test_scrcpy_automation.py; git commit -m "fix(automation): emit replayable recorded key actions"`.

### Task 2: Implement the Constrained Python Bridge

**Files:**
- Create: `tools/automation_center/__init__.py`
- Create: `tools/automation_center/bridge.py`
- Create: `tools/automation_center/app.py`
- Create: `tests/test_automation_center_bridge.py`
- Modify: `tools/scrcpy_automation.py`

**Interfaces:**
- Produces `AutomationBridge(portable_root: pathlib.Path, transport: AdbTransport | None = None)`.
- Produces `list_devices()`, `list_plans()`, `load_plan()`, `save_plan()`, `run_plan_now()`, `set_schedule()`, `remove_schedule()`, and `list_runs()` returning JSON-compatible values.

- [ ] **Step 1: Write failing tests for root-scoped plan storage**

```python
bridge = AutomationBridge(root, transport=FakeAdbTransport())
saved = bridge.save_plan({"name": "morning", "serial": "ABC", "steps": [{"action": "wake"}]})
self.assertEqual(saved["path"], str(root / "plans" / "morning.json"))
self.assertEqual(bridge.list_plans()[0]["name"], "morning")
```

- [ ] **Step 2: Run test module and verify it fails**

Run: `python -m unittest tests.test_automation_center_bridge -v`.

Expected: FAIL because `tools.automation_center.bridge` does not exist.

- [ ] **Step 3: Implement bridge operations and canonical paths**

Create `plans/` and `logs/automation/` below `portable_root`. Reject `..`, absolute save targets, invalid JSON, invalid plan data, and paths outside `plans/`. Every operation returns one of:

```python
{"ok": True, "path": "C:\\portable\\plans\\morning.json"}
{"ok": False, "code": "validation_error", "message": "steps[0].action is unsupported"}
```

- [ ] **Step 4: Implement run history and Task Scheduler methods**

Create runs below `logs/automation/<name>/<timestamp>/`. Reuse `run_plan()` and existing list-form scheduler builders. Return `success`, `completed_steps`, `error`, `run_dir`, and `task_name` fields.

- [ ] **Step 5: Run bridge and existing automation tests**

Run: `python -m unittest tests.test_automation_center_bridge tests.test_scrcpy_automation -v`.

Expected: PASS without a physical phone or a Task Scheduler mutation.

- [ ] **Step 6: Commit the local bridge**

Run: `git add tools/automation_center tests/test_automation_center_bridge.py tools/scrcpy_automation.py; git commit -m "feat(automation): add local desktop bridge"`.

### Task 3: Add Recording Process Management

**Files:**
- Modify: `tools/automation_center/bridge.py`
- Modify: `tools/automation_center/app.py`
- Modify: `tests/test_automation_center_bridge.py`

**Interfaces:**
- Produces `start_recording(serial: str) -> dict[str, str]` and `stop_recording() -> dict[str, object]`.
- Stores at most one owned `subprocess.Popen` recording process.

- [ ] **Step 1: Write failing tests for the exact recording launch command**

```python
bridge.start_recording("ABC")
popen.assert_called_once_with([str(root / "scrcpy.exe"), "--serial", "ABC", "--record-actions", mock.ANY], cwd=root)
```

- [ ] **Step 2: Run recording tests and verify they fail**

Run: `python -m unittest tests.test_automation_center_bridge.AutomationBridgeRecordingTests -v`.

Expected: FAIL with `AttributeError` for `start_recording`.

- [ ] **Step 3: Implement one owned recording lifecycle**

Start exactly `portable_root/scrcpy.exe --serial SERIAL --record-actions TEMP`. Reject non-ready serials and duplicate starts. On stop, terminate only the owned process, wait at most five seconds, validate the JSON, and atomically move it to `plans/recorded-<timestamp>.json`. On error, delete only the temporary recording and preserve the plan in the editor.

- [ ] **Step 4: Add unavailable-device, duplicate-start, malformed-output, and timeout tests**

```python
self.assertEqual(bridge.start_recording("offline")["code"], "device_not_ready")
self.assertEqual(bridge.start_recording("ABC")["code"], "recording_active")
```

- [ ] **Step 5: Run bridge tests**

Run: `python -m unittest tests.test_automation_center_bridge -v`.

Expected: PASS.

- [ ] **Step 6: Commit recording lifecycle support**

Run: `git add tools/automation_center tests/test_automation_center_bridge.py; git commit -m "feat(automation): manage scrcpy recording sessions"`.

### Task 4: Build the React HTML/CSS Editor Shell

**Files:**
- Create: `automation-ui/package.json`
- Create: `automation-ui/vite.config.ts`
- Create: `automation-ui/src/main.tsx`
- Create: `automation-ui/src/api.ts`
- Create: `automation-ui/src/App.tsx`
- Create: `automation-ui/src/styles.css`
- Create: `automation-ui/src/components/DeviceList.tsx`
- Create: `automation-ui/src/components/PlanEditor.tsx`
- Create: `automation-ui/src/components/RunPanel.tsx`
- Create: `automation-ui/src/__tests__/App.test.tsx`

**Interfaces:**
- Produces a typed `AutomationApi` matching Task 2 bridge methods.
- Produces an `App` with device selection, plan metadata, and ordered action state.

- [ ] **Step 1: Add React/Vite/Vitest scripts**

```json
{"scripts":{"build":"tsc -b && vite build","test":"vitest run"},"dependencies":{"react":"19.1.1","react-dom":"19.1.1"},"devDependencies":{"@vitejs/plugin-react":"5.0.2","typescript":"5.9.2","vite":"7.1.7","vitest":"3.2.4"}}
```

- [ ] **Step 2: Write a failing device-selection test**

```tsx
render(<App api={fakeApi} />);
await user.click(screen.getByRole("button", { name: "Pixel 8" }));
expect(screen.getByLabelText("目标设备")).toHaveValue("ABC123");
```

- [ ] **Step 3: Install dependencies and verify the test fails**

Run: `npm --prefix automation-ui install; npm --prefix automation-ui test`.

Expected: FAIL because the app and API adapter are absent.

- [ ] **Step 4: Implement a high-DPI desktop layout**

Use device sidebar, plan list, and action-editor main area. Use CSS variables, no gradients, icon-only controls with accessible labels for reordering/deleting, high-contrast state tags, and Chinese labels including `设备`, `计划`, `录制操作`, `立即运行`, `试运行`, and `启用定时`.

- [ ] **Step 5: Implement action add/edit/delete/reorder controls**

Support every runner action and deterministic ordering controls:

```tsx
onMoveStep(index, -1)
onMoveStep(index, 1)
onDeleteStep(index)
```

- [ ] **Step 6: Run typecheck, tests, and production build**

Run: `npm --prefix automation-ui test; npm --prefix automation-ui run build`.

Expected: PASS and `automation-ui/dist/index.html` exists.

- [ ] **Step 7: Commit the UI shell**

Run: `git add automation-ui; git commit -m "feat(automation-ui): add React plan editor shell"`.

### Task 5: Connect UI Controls and Enforce UI Safety

**Files:**
- Modify: `automation-ui/src/api.ts`
- Modify: `automation-ui/src/App.tsx`
- Modify: `automation-ui/src/components/DeviceList.tsx`
- Modify: `automation-ui/src/components/PlanEditor.tsx`
- Modify: `automation-ui/src/components/RunPanel.tsx`
- Modify: `automation-ui/src/__tests__/App.test.tsx`
- Modify: `tools/automation_center/bridge.py`
- Modify: `tests/test_automation_center_bridge.py`

**Interfaces:**
- Consumes `window.pywebview.api` bridge methods.
- Produces save, run, record, stop, schedule, unschedule, run-history, and artifact-view controls.

- [ ] **Step 1: Write failing UI tests for dry-run and recording controls**

```tsx
await user.click(screen.getByRole("button", { name: "试运行" }));
expect(fakeApi.run_plan_now).toHaveBeenCalledWith(planPath, true);
expect(await screen.findByText("执行成功")).toBeVisible();
```

- [ ] **Step 2: Run frontend tests and verify they fail**

Run: `npm --prefix automation-ui test`.

Expected: FAIL because run and recording controls are absent.

- [ ] **Step 3: Implement pending, success, and error states**

Disable each command while its bridge call is pending. Display bridge `code` and `message` inline. Refresh saved plans after save or successful recording. The frontend never creates ADB, shell, or `schtasks` commands.

- [ ] **Step 4: Add and test an artifact-opening allowlist**

Implement `open_artifact(path: str)` in `bridge.py`. It canonicalizes the path, opens only files below `logs/`, and returns `artifact_outside_logs` for any other path. Render log/screenshot buttons only for existing returned artifacts.

- [ ] **Step 5: Run UI and bridge tests**

Run: `npm --prefix automation-ui test; python -m unittest tests.test_automation_center_bridge -v`.

Expected: PASS.

- [ ] **Step 6: Commit connected behavior**

Run: `git add automation-ui tools/automation_center tests/test_automation_center_bridge.py; git commit -m "feat(automation-ui): connect plan and recording controls"`.

### Task 6: Freeze and Package the Automation Center

**Files:**
- Create: `tools/build_automation_center.ps1`
- Create: `tools/build_portable_release.ps1`
- Create: `tools/automation_center/requirements.txt`
- Create: `tools/windows-dependencies.json`
- Modify: `tools/package_windows.ps1`
- Modify: `tools/test_windows_package.ps1`
- Modify: `tools/README.md`
- Modify: `README.md`
- Modify: `doc/windows.md`

**Interfaces:**
- Produces `scrcpy-automation.exe` from `tools/automation_center/app.py`.
- Extends `package_windows.ps1` with mandatory `-AutomationExe`.
- Produces one final portable directory while all Meson, server, ADB, Python, and Node build files live below a unique directory under `$env:TEMP` and are removed in a `finally` block.

- [ ] **Step 1: Add failing package assertions**

```powershell
$required += @('scrcpy-automation.exe', 'plans', 'logs')
```

- [ ] **Step 2: Run the package test against the current portable release**

Run: `& .\tools\test_windows_package.ps1 -PackageRoot D:\scrcpy-many-portable`.

Expected: FAIL with `Missing packaged path: scrcpy-automation.exe`.

- [ ] **Step 3: Implement deterministic web/executable builds**

`build_automation_center.ps1` runs `npm ci`, builds React assets, creates a temporary virtual environment, installs pinned `pywebview` and `pyinstaller` from `requirements.txt`, and calls PyInstaller with `automation-ui/dist` as bundled data. It writes only the requested `-OutputExe`.

- [ ] **Step 4: Add a temporary-workspace portable-release wrapper**

`build_portable_release.ps1` creates `$env:TEMP\\scrcpy-many-<GUID>`. It downloads the versioned server and platform-tools sources specified in `windows-dependencies.json`, configures Meson below that temporary directory, stages DLLs from the configured MSYS2 runtime, calls `build_automation_center.ps1`, then calls `package_windows.ps1`. It deletes the temporary directory from `finally`, whether the build succeeds or fails. Its only persistent output is the explicit `-OutputDir`.

- [ ] **Step 5: Extend the package without flattening runtime files**

Copy `scrcpy-automation.exe` to package root, create empty `plans/` and `logs/`, and retain `bin/`, `lib/`, and `platform-tools/`. Do not copy Python, Node, `node_modules`, tests, source, or build directories.

- [ ] **Step 6: Build and smoke-test a fresh portable folder**

Run: `& .\tools\build_portable_release.ps1 -OutputDir D:\scrcpy-many-portable-next`; then `& .\tools\test_windows_package.ps1 -PackageRoot D:\scrcpy-many-portable-next`; then `& D:\scrcpy-many-portable-next\scrcpy.exe --help`.

Expected: PASS; `scrcpy.exe --help` works; `scrcpy-automation.exe` starts without a system Python installation.

- [ ] **Step 7: Commit packaging and docs**

Run: `git add tools/build_automation_center.ps1 tools/build_portable_release.ps1 tools/automation_center/requirements.txt tools/windows-dependencies.json tools/package_windows.ps1 tools/test_windows_package.ps1 tools/README.md README.md doc/windows.md; git commit -m "build(automation): package web automation center"`.

### Task 7: Full Validation and Release Handoff

**Files:**
- Modify: `README.md`
- Modify: `doc/windows.md`
- Modify: `tests/test_automation_center_bridge.py`

**Interfaces:**
- Documents both portable entry points and the non-secure-lock limitation.
- Produces a release folder free of development artifacts.

- [ ] **Step 1: Add a full bridge fixture test**

```python
saved = bridge.save_plan(document)
result = bridge.run_plan_now(saved["path"], dry_run=True)
self.assertTrue(result["success"])
self.assertEqual(bridge.list_runs("morning")[0]["status"], "success")
```

- [ ] **Step 2: Run the full bridge test**

Run: `python -m unittest tests.test_automation_center_bridge -v`.

Expected: PASS.

- [ ] **Step 3: Document safe normal use**

Document `scrcpy.exe` for mirroring and `scrcpy-automation.exe` for automation. State that ADB authorization is required and secure PIN, pattern, fingerprint, and face unlock are not bypassed.

- [ ] **Step 4: Run all automated checks**

Run: `python -m unittest discover -s tests -v`; then `npm --prefix automation-ui test`; then `npm --prefix automation-ui run build`; then `& D:\msys64\usr\bin\bash.exe -lc "export PATH=/mingw64/bin:/usr/bin:`$PATH; meson test -C /d/scrcpy-build --print-errorlogs"`; then `& .\tools\test_windows_package.ps1 -PackageRoot D:\scrcpy-many-portable-next`.

Expected: all Python, frontend, C, and package checks PASS.

- [ ] **Step 5: Perform a one-device manual smoke test**

Open `scrcpy-automation.exe`, refresh an already-authorized phone, create a one-step `wake` plan, save it, run dry-run, enable then disable a schedule, record one tap, and verify the generated plan loads. Do not test a secure lock screen or submit a real attendance action.

- [ ] **Step 6: Commit release validation**

Run: `git add README.md doc/windows.md tests/test_automation_center_bridge.py; git commit -m "docs(automation): document web automation center release"`.
