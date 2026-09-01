# scrcpy many launcher

`scrcpy_launcher.py` is a small external launcher for running one regular
scrcpy process per selected ADB device. It does not modify the scrcpy protocol
or the device-side server.

## Requirements

- Python 3.10 or newer
- A Python installation with Tk support (the standard Windows installer
  includes it)
- `adb` and `scrcpy` available in `PATH`, or next to the launcher

## Run

From the repository root:

```powershell
python tools/scrcpy_launcher.py
```

Use `--adb` and `--scrcpy` when the executables are in another directory:

```powershell
python tools/scrcpy_launcher.py `
    --adb C:\Android\platform-tools\adb.exe `
    --scrcpy C:\scrcpy\scrcpy.exe
```

Arguments after `--` are passed to every launched scrcpy process:

```powershell
python tools/scrcpy_launcher.py -- --max-size=1024 --no-audio
```

Only devices whose ADB state is `device` can be started. Unauthorized and
offline devices remain visible so that their state is clear and can be fixed.

## Scheduled device automation

### Packaged graphical automation center

The portable release can include `scrcpy-automation.exe`, a local WebView
desktop application for users who do not want to edit JSON or use a terminal.
It lists ADB devices, requires an explicit ready serial, saves plans below
`plans/`, launches an owned `scrcpy.exe --record-actions` session, runs plans,
and creates or removes daily Task Scheduler jobs. Its frontend is bundled
inside the executable; it does not start an HTTP server and does not require a
system Python or Node installation.

Build that executable with:

```powershell
.\tools\build_automation_center.ps1 -OutputExe D:\scrcpy-automation.exe
```

Then add it to a normal Windows package with `-AutomationExe`, or use
`build_portable_release.ps1` to build and package in one command. Build
dependencies live in a unique system temporary directory and are deleted after
the build. The final release contains `scrcpy.exe`, `scrcpy-automation.exe`,
`bin/`, `lib/`, `platform-tools/`, `plans/`, and `logs/` only.

`scrcpy_automation.py` executes a validated JSON plan against one explicit ADB
serial. It is intended for scheduled check-in flows and does not require a
scrcpy window to be open.

Validate and preview the example plan:

```powershell
python tools/scrcpy_automation.py validate tools/examples/evening-check-in.json
python tools/scrcpy_automation.py run tools/examples/evening-check-in.json --dry-run
```

The plan can wake the display, dismiss a non-secure keyguard, launch an app,
tap or swipe coordinates, enter text, send key events, locate controls by UI
text, assert a result, and save a screenshot. The phone must already be
authorized in ADB. Secure PIN, pattern, fingerprint, and face unlock are not
stored or bypassed by this runner.

The JSON shape is:

```json
{
  "name": "evening-check-in",
  "serial": "0123456789abcdef",
  "schedule": { "time": "21:00", "days": ["daily"] },
  "steps": [
    { "action": "wake" },
    { "action": "dismiss_keyguard" },
    { "action": "launch", "package": "com.example.checkin" },
    { "action": "tap_text", "text": "打卡" },
    { "action": "assert_text", "text": "打卡成功" }
  ]
}
```

To capture a reusable action plan while operating a scrcpy window, start the
client with an output path:

```powershell
scrcpy.exe --serial 0123456789abcdef --record-actions evening-actions.json
```

The recorder is opt-in. It captures touch down/move/up sequences as `tap` or
`swipe`, keyboard events as `keyevent`, and inserts millisecond `wait` steps
between events. The file is written through a temporary path and renamed only
after a complete JSON document is closed. Clipboard, file-drop, gamepad, and
secure-unlock data are not recorded.

Use `--dry-run` to print the planned ADB actions without touching the device.
Each real run writes `run.log` and, on failure, `failure.png` to
`logs/automation/<plan-name>/<timestamp>/`.

Install the plan as a daily Windows Task Scheduler job at its configured time:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_scrcpy_automation.ps1 `
    -Plan tools/examples/evening-check-in.json
```

The wrapper resolves the Python interpreter and runner, then calls
`schtasks.exe /Create /F`. The task runs as the current user and therefore
requires that user to be logged in, the PC to be awake, and the phone to remain
ADB-authorized. Inspect or remove the task with:

```powershell
python tools/scrcpy_automation.py remove "scrcpy-many:evening-check-in"
```

Use `schedule` directly when a specific interpreter or runner is needed:

```powershell
python tools/scrcpy_automation.py schedule tools/examples/evening-check-in.json
```
