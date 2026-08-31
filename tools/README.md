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
