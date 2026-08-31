# Scheduled Device Automation Design

## Goal

Provide a Windows-side automation runner that wakes a selected Android device,
opens an app, and executes a deterministic check-in script at a scheduled time,
while keeping scrcpy available for inspection and manual troubleshooting.

## Scope

The first delivery is an external, headless Python runner invoked by Windows
Task Scheduler. It communicates through the repository's bundled `adb.exe` and
always addresses a device by an explicit serial. Scripts are JSON documents with
validated actions, bounded waits, retries, and optional UI text assertions.

Supported actions in the first delivery:

- `wait`: delay for a bounded number of milliseconds
- `wake`: send `KEYCODE_WAKEUP`
- `dismiss_keyguard`: request dismissal of a non-secure keyguard
- `launch`: start an app package or explicit component
- `tap`: tap absolute device coordinates
- `swipe`: swipe between absolute coordinates for a duration
- `text`: input text through ADB with safe argument passing
- `keyevent`: send a named or numeric Android key event
- `tap_text`: locate a visible UI node by exact text and tap its center
- `assert_text`: fail unless a visible UI node contains exact text
- `screenshot`: pull a failure/debug screenshot to the run directory

The runner must never silently bypass a secure PIN, pattern, fingerprint, or
face unlock. `wake` and `dismiss_keyguard` are supported; a secure lock reports
an actionable failure and stops the plan unless the user has configured a
device-specific unlock provider in a later release.

## Script Format

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

Coordinates are intentionally absolute in the first release. The runner logs
the device resolution and warns when a coordinate falls outside it. Text-based
actions use `uiautomator dump` plus XML parsing and are preferred for controls
that have stable labels. A later recorder can add normalized coordinates and
resource-id selectors without changing the executor interface.

## Execution Semantics

1. Validate the complete plan before touching the device.
2. Run `adb -s SERIAL get-state` and retry until the configured timeout.
3. Execute steps in order; each step has a timeout and at most two retries for
   transient ADB failures.
4. On failure, write a timestamped log, dump the current UI hierarchy when
   possible, and attempt a screenshot.
5. Exit non-zero for scheduler reporting; exit zero only after all steps pass.
6. Never launch scrcpy as a prerequisite. The user may launch scrcpy manually
   with the same serial to observe a run.

## Scheduling

`tools/scrcpy_automation.py schedule` creates or updates a Windows Task
Scheduler task using `schtasks.exe`. The task runs under the current user and
uses an absolute Python path, script path, plan path, and log directory. The
default first release assumes the user is logged in, because USB ADB drivers and
some OEM devices are not available to a non-interactive service session.

The command supports `install`, `run`, `validate`, and `remove` operations. A
separate `--dry-run` mode prints every ADB command without executing it.

## Security and Reliability

- Serial, package, component, and action arguments are passed as subprocess
  argument arrays; no user value is concatenated into a shell command.
- PINs and passwords are not stored in JSON and are rejected by schema
  validation in the first release.
- Device authorization must already be accepted (`adb devices` state
  `device`). `unauthorized` and `offline` states produce a clear failure.
- Every run gets a unique directory under `logs/`; old runs are retained until
  an explicit cleanup command is added.
- The runner handles ADB disconnects with bounded retry and never loops forever.

## Phase 2: Operation Recording

After the playback engine is stable, add an optional recorder to the scrcpy
client. The recorder observes the existing events in
`app/src/input_manager.c`, converts mouse/touch/key events to the JSON action
schema, and writes elapsed delays between actions. Recording is explicitly
separate from scheduling so a malformed recording cannot affect the runner's
device safety rules.

Phase 2 adds:

- start/stop recording controls in the Windows picker or a command-line flag
- JSON export with device resolution and app package metadata
- review/edit of recorded steps before scheduling
- normalized coordinates and resource-id/text selectors where available

## Acceptance Criteria

- A validated plan runs against one explicit serial and never selects another
  device, even when multiple phones are connected.
- `wake`, `launch`, `tap`, `swipe`, `text`, and `keyevent` execute in order.
- `tap_text` and `assert_text` work from a real `uiautomator dump` fixture.
- A disconnected, unauthorized, or secure-locked device fails with a useful
  message and a non-zero exit code.
- `--dry-run` produces no ADB side effects.
- A daily 21:00 Task Scheduler entry can be installed, inspected, and removed.
- All parser, command, retry, and scheduler serialization tests pass without a
  connected device; one manual smoke test covers a real phone.
