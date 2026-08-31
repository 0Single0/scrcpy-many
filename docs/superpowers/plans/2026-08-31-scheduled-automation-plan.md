# Scheduled Device Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows-side runner that executes a validated Android check-in script at a scheduled time for one explicit ADB serial.

**Architecture:** Keep scheduling and automation outside the scrcpy client. A Python runner owns JSON validation, an injectable ADB transport, retries, UI hierarchy parsing, logs, and Task Scheduler command generation. A later phase can record scrcpy input events into the same JSON schema without coupling playback to the SDL client.

**Tech Stack:** Python 3.10+, `subprocess`, `json`, `xml.etree.ElementTree`, Windows `schtasks.exe`, bundled `adb.exe`, unittest, existing C11/SDL3 scrcpy client for the later recorder phase.

**Spec:** `docs/superpowers/specs/2026-08-31-scheduled-automation-design.md`

## Global Constraints

- First delivery is Windows-only and runs under the logged-in user through Task Scheduler.
- Every run targets one explicit ADB serial; never infer or switch devices during execution.
- Secure PIN, pattern, biometric, or face unlock is not bypassed or stored by the first release.
- ADB arguments are passed as subprocess argument arrays; no shell command string is built from user input.
- Supported actions are `wait`, `wake`, `dismiss_keyguard`, `launch`, `tap`, `swipe`, `text`, `keyevent`, `tap_text`, `assert_text`, and `screenshot`.
- All device interaction has bounded timeouts and retries; failures write logs and return non-zero.
- The recorder is phase 2 and must emit the same action schema as the playback runner.

---

### Task 1: Define and Validate Automation Plans

**Files:**
- Create: `tools/scrcpy_automation.py`
- Create: `tools/examples/evening-check-in.json`
- Test: `tests/test_scrcpy_automation.py`
- Modify: `tools/README.md`

**Interfaces:**
- Produces `AutomationPlan`, `Step`, and `PlanValidationError` dataclasses/classes.
- Produces `load_plan(path: pathlib.Path) -> AutomationPlan`.
- Produces `validate_plan(document: dict) -> AutomationPlan`.
- `AutomationPlan.serial` is a non-empty string; `AutomationPlan.steps` is an ordered list of `Step` objects.

- [ ] **Step 1: Write failing schema tests**

Add tests for a valid plan, missing serial, unsupported action, negative wait,
missing launch package/component, and password fields being rejected.

```python
def test_validate_plan_accepts_the_check_in_shape():
    plan = validate_plan({
        "name": "check-in",
        "serial": "ABC123",
        "schedule": {"time": "21:00", "days": ["daily"]},
        "steps": [{"action": "wake"}, {"action": "launch", "package": "com.example.app"}],
    })
    assert plan.serial == "ABC123"
    assert [step.action for step in plan.steps] == ["wake", "launch"]
```

- [ ] **Step 2: Run the schema tests and verify the expected failure**

Run: `python -m unittest tests.test_scrcpy_automation.PlanValidationTests -v`

Expected: FAIL because `tools/scrcpy_automation.py` and
`validate_plan()` do not exist yet.

- [ ] **Step 3: Implement minimal plan dataclasses and validation**

Implement an allowlist for the eleven actions. Normalize optional fields without
changing user text, require exactly one of `package` or `component` for
`launch`, require integer non-negative `ms` for `wait`, and reject keys named
`pin`, `password`, or `credential` anywhere in a step.

- [ ] **Step 4: Run the schema tests and confirm they pass**

Run: `python -m unittest tests.test_scrcpy_automation.PlanValidationTests -v`

Expected: all plan validation tests PASS.

- [ ] **Step 5: Document the JSON format**

Add a complete example with `wake`, `dismiss_keyguard`, `launch`, `tap_text`,
`assert_text`, and `screenshot` to `tools/README.md`, including the explicit
serial requirement and secure-lock limitation. Store the executable example at
`tools/examples/evening-check-in.json` with this content:

```json
{
  "name": "evening-check-in",
  "serial": "0123456789abcdef",
  "schedule": { "time": "21:00", "days": ["daily"] },
  "steps": [
    { "action": "wake" },
    { "action": "dismiss_keyguard" },
    { "action": "wait", "ms": 1000 },
    { "action": "launch", "package": "com.example.checkin" },
    { "action": "wait", "ms": 2500 },
    { "action": "tap_text", "text": "打卡" },
    { "action": "assert_text", "text": "打卡成功" },
    { "action": "screenshot", "name": "success" }
  ]
}
```

- [ ] **Step 6: Commit the plan model**

```powershell
git add tools/scrcpy_automation.py tests/test_scrcpy_automation.py tools/README.md
git commit -m "feat(automation): add validated plan format"
```

### Task 2: Implement the Injectable ADB Transport

**Files:**
- Modify: `tools/scrcpy_automation.py`
- Test: `tests/test_scrcpy_automation.py`

**Interfaces:**
- Produces `class AdbTransport` with `run(serial: str, args: list[str], timeout: float) -> subprocess.CompletedProcess[str]`.
- Produces `class FakeAdbTransport` for tests with `calls: list[list[str]]` and configurable command results.
- Produces `wait_for_device(transport: AdbTransport, serial: str, timeout: float, poll_interval: float = 1.0) -> None`.

- [ ] **Step 1: Write failing transport tests**

Assert that a command is built as `[adb, "-s", serial, *args]`, serials are
passed as one argument even when they contain `:`, timeout errors are surfaced,
and `wait_for_device()` retries `get-state` until it returns `device`.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m unittest tests.test_scrcpy_automation.TransportTests -v`

Expected: FAIL because the transport classes do not yet exist.

- [ ] **Step 3: Implement command execution and bounded retry**

Use `subprocess.run(..., text=True, capture_output=True, check=False)` with a
per-command timeout. Raise `AdbCommandError` containing serial, arguments, and
stderr. `wait_for_device()` retries only `offline`, missing-device, and timeout
results until its deadline; `unauthorized` raises immediately with an
authorization hint.

- [ ] **Step 4: Run the transport tests and confirm they pass**

Run: `python -m unittest tests.test_scrcpy_automation.TransportTests -v`

Expected: all transport tests PASS.

- [ ] **Step 5: Commit the transport increment**

```powershell
git add tools/scrcpy_automation.py tests/test_scrcpy_automation.py
git commit -m "feat(automation): add safe adb transport"
```

### Task 3: Execute Actions with Logs and UI Assertions

**Files:**
- Modify: `tools/scrcpy_automation.py`
- Test: `tests/test_scrcpy_automation.py`
- Create: `tests/fixtures/uiautomator_checkin.xml`

**Interfaces:**
- Produces `run_plan(plan: AutomationPlan, transport: AdbTransport, run_dir: pathlib.Path, dry_run: bool = False) -> RunResult`.
- Produces `UiNode` and `parse_uiautomator_xml(xml_text: str) -> list[UiNode]`.
- Produces `RunResult.success: bool`, `RunResult.completed_steps: int`, and `RunResult.error: str | None`.

- [ ] **Step 1: Write failing action tests**

Use `FakeAdbTransport` to assert the exact sequence for `wake`, `launch`,
`tap`, `swipe`, `text`, and `keyevent`. Add fixture-based tests for
`tap_text` center-coordinate calculation and `assert_text` failure. Add a dry
run test proving `transport.calls` remains empty. The XML fixture must contain
one node such as:

```xml
<hierarchy rotation="0">
  <node text="打卡" resource-id="com.example.checkin:id/check_in"
        class="android.widget.Button" bounds="[400,1400][680,1520]" />
</hierarchy>
```

- [ ] **Step 2: Run action tests and verify they fail**

Run: `python -m unittest tests.test_scrcpy_automation.ActionExecutionTests -v`

Expected: FAIL because `run_plan()` and XML parsing are not implemented.

- [ ] **Step 3: Implement XML parsing and action dispatch**

Parse each node's `text`, `resource-id`, `class`, and `bounds` attributes with
`xml.etree.ElementTree`. For `tap_text`, dump to a temporary device path,
read it back, find exactly one exact-text node, parse bounds `[left,top][right,bottom]`,
and tap its integer center. Implement `launch` as `am start -n component` or
`monkey -p package 1`.

- [ ] **Step 4: Add retry, timeout, and failure artifacts**

Wrap each action in two attempts for transient `AdbCommandError`. Before a
retry, wait one second. On final failure, append a timestamped line to
`run.log`, attempt `uiautomator dump` and `screenshot`, and return a non-zero
result without executing later steps. Validate tap/swipe coordinates against
the reported device size when it is available.

- [ ] **Step 5: Run action tests and confirm they pass**

Run: `python -m unittest tests.test_scrcpy_automation.ActionExecutionTests -v`

Expected: all action, retry, XML, and dry-run tests PASS.

- [ ] **Step 6: Commit the executor**

```powershell
git add tools/scrcpy_automation.py tests/test_scrcpy_automation.py tests/fixtures/uiautomator_checkin.xml
git commit -m "feat(automation): execute adb check-in actions"
```

### Task 4: Add CLI Commands and Windows Task Scheduler Integration

**Files:**
- Modify: `tools/scrcpy_automation.py`
- Modify: `tools/README.md`
- Test: `tests/test_scrcpy_automation.py`
- Create: `tools/install_scrcpy_automation.ps1`

**Interfaces:**
- CLI commands: `validate PLAN`, `run PLAN [--dry-run]`, `schedule PLAN`, and `remove NAME`.
- Produces `build_schtasks_create_command(plan_path: pathlib.Path, python_path: pathlib.Path, runner_path: pathlib.Path) -> list[str]`.
- Produces `build_schtasks_delete_command(task_name: str) -> list[str]`.

- [ ] **Step 1: Write failing CLI/scheduler tests**

Assert that `schedule` produces a command containing `/SC DAILY`, `/ST 21:00`,
and an absolute plan path; `remove` produces `/Delete`; `validate` exits zero
for the fixture and non-zero for invalid JSON; and `--dry-run` does not call
the transport.

- [ ] **Step 2: Run CLI tests and verify they fail**

Run: `python -m unittest tests.test_scrcpy_automation.CliTests -v`

Expected: FAIL because the CLI parser and scheduler command builders do not
exist.

- [ ] **Step 3: Implement CLI and scheduler commands**

Use `argparse` with subparsers. `run` creates a unique log directory and maps
the `RunResult` to exit code 0/1. `schedule` calls `schtasks.exe /Create /F`
with the plan's daily time, task name `scrcpy-many:<name>`, and an absolute
command that invokes `python -m tools.scrcpy_automation run <plan>`. `remove`
calls `/Delete /TN ... /F`.

- [ ] **Step 4: Implement the PowerShell convenience wrapper**

`tools/install_scrcpy_automation.ps1` accepts `-Plan`, `-Python`, and
`-Runner`, resolves all paths, and invokes the Python `schedule` command. It
must refuse a plan outside the current user-readable filesystem and print the
created task name.

- [ ] **Step 5: Run CLI tests and confirm they pass**

Run: `python -m unittest tests.test_scrcpy_automation.CliTests -v`

Expected: all CLI and scheduler serialization tests PASS.

- [ ] **Step 6: Commit scheduler integration**

```powershell
git add tools/scrcpy_automation.py tools/install_scrcpy_automation.ps1 tools/README.md tests/test_scrcpy_automation.py
git commit -m "feat(automation): schedule check-in plans on Windows"
```

### Task 5: End-to-End Fixtures, Documentation, and Manual Smoke Test

**Files:**
- Modify: `README.md`
- Modify: `doc/windows.md`
- Modify: `tools/README.md`
- Test: `tests/test_scrcpy_automation.py`

**Interfaces:**
- Documents the complete plan example, 21:00 installation command, log
  locations, dry-run mode, and secure-lock limitation.
- Adds a fixture transport test for a full wake/launch/tap/assert flow.

- [ ] **Step 1: Write the full-flow fixture test**

Load the JSON example, run it with a fake transport and the XML fixture, then
assert that the result is successful and the final command is the expected
`input tap` for the `打卡` node.

- [ ] **Step 2: Run the full-flow test and verify the expected failure**

Run: `python -m unittest tests.test_scrcpy_automation.FullFlowTests -v`

Expected: FAIL until the fixture plan and executor integration are complete.

- [ ] **Step 3: Add Windows usage documentation**

Document:

```powershell
python tools/scrcpy_automation.py validate plans\evening-check-in.json
python tools/scrcpy_automation.py run plans\evening-check-in.json --dry-run
powershell -ExecutionPolicy Bypass -File tools\install_scrcpy_automation.ps1 -Plan plans\evening-check-in.json
```

Explain that the phone must already be authorized, the PC must be awake or
configured to wake for the task, and secure lock screens may require manual
unlock.

- [ ] **Step 4: Run all automated checks**

Run:

```powershell
python -m unittest discover -s tests -v
$env:PATH = "D:\\msys64\\mingw64\\bin;D:\\msys64\\usr\\bin;" + $env:PATH
& D:\\msys64\\usr\\bin\\bash.exe -lc "export PATH=/mingw64/bin:/usr/bin:`$PATH; meson test -C /d/scrcpy-build --print-errorlogs"
```

Expected: all Python tests and all existing C tests pass.

- [ ] **Step 5: Perform one real-device smoke test**

Use one authorized phone without a secure lock, run `validate`, then `run`
against a harmless test app or a dry-run check-in plan. Confirm logs, exit
codes, and that a second connected phone is never touched.

- [ ] **Step 6: Commit final docs and fixtures**

```powershell
git add README.md doc/windows.md tools/README.md tests/test_scrcpy_automation.py
git commit -m "docs(automation): document scheduled device scripts"
```

### Task 6: Phase 2 Operation Recorder

**Files:**
- Modify: `app/src/input_manager.c`
- Modify: `app/src/main.c`
- Modify: `app/src/cli.c`
- Modify: `app/src/options.c`
- Modify: `app/src/options.h`
- Modify: `app/meson.build`
- Create: `app/src/automation_recorder.c`
- Create: `app/src/automation_recorder.h`
- Test: `app/tests/test_automation_recorder.c`
- Modify: `tools/scrcpy_automation.py`

**Interfaces:**
- Produces `bool sc_automation_recorder_start(const char *path, const char *serial, uint16_t width, uint16_t height)`.
- Produces `bool sc_automation_recorder_record_touch(uint8_t action, int32_t x, int32_t y, uint16_t width, uint16_t height, uint32_t elapsed_ms)`.
- Produces `bool sc_automation_recorder_record_key(uint32_t keycode, uint8_t action, uint32_t elapsed_ms)`.
- Produces `void sc_automation_recorder_stop(void)` and closes the JSON document safely.
- Python runner accepts recorder-generated `tap`, `swipe`, `text`, `keyevent`,
  and `wait` steps without schema changes.

- [ ] **Step 1: Add failing C serialization tests**

Assert that a down/move/up touch sequence becomes one `swipe` action, a click
becomes one `tap`, key events preserve action and keycode, and elapsed time is
represented by a `wait` step with millisecond rounding.

- [ ] **Step 2: Run recorder tests and verify they fail**

Run: `ninja -C D:\\scrcpy-build app/test_automation_recorder.exe`

Expected: FAIL because the recorder module and test target do not exist.

- [ ] **Step 3: Implement the recorder as an opt-in client feature**

Call the recorder from `sc_input_manager_handle_event()` only after the input
has been normalized to a touch or key action. Do not record clipboard, file-drop,
or gamepad events in the first version. Write to a temporary file and atomically
rename on stop so an interrupted recording cannot look complete.

- [ ] **Step 4: Add CLI start/stop controls and metadata**

Add `--record-actions=PATH`; record device serial, initial resolution, and
optional package metadata. Keep recording disabled by default and reject a path
that cannot be created.

- [ ] **Step 5: Run C and Python recorder tests**

Run:

```powershell
ninja -C D:\\scrcpy-build app/test_automation_recorder.exe
python -m unittest discover -s tests -v
```

Expected: all recorder and runner tests PASS.

- [ ] **Step 6: Commit phase 2 recorder**

```powershell
git add app/src/input_manager.c app/src/main.c app/src/cli.c app/src/options.c app/src/options.h app/src/automation_recorder.c app/src/automation_recorder.h app/tests/test_automation_recorder.c tools/scrcpy_automation.py
git commit -m "feat(automation): record scrcpy input actions"
```
