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

Use `--dry-run` to print the planned ADB actions without touching the device.
Each real run writes a log and failure artifacts to its run directory. The
Windows Task Scheduler integration is added by the next implementation task.
