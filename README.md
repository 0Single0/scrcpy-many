# scrcpy-many

English documentation for the Windows-focused scrcpy-many fork.

[中文说明](README.zh-CN.md)

This repository is a custom Windows build based on [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy). It keeps scrcpy's core device-control behavior and adds a graphical multi-device launcher, an organized portable layout, and a local automation center for repeatable Android workflows.

This is not an official Genymobile release. The upstream project, its source code, and its Apache License 2.0 remain the authority for the original scrcpy components.

## What Was Added

### Multi-device launcher

- Starts `scrcpy.exe` with a graphical device picker when multiple ADB devices are available.
- Starts the only ready device directly when there is no ambiguity.
- Supports selecting multiple ready devices and opens one scrcpy window per selected serial.
- Shows serial, model, transport, and ADB state in a Unicode-safe Windows UI.
- Keeps `unauthorized`, `offline`, and other unavailable devices visible while preventing them from being launched.
- Supports double-click launch and command-line bypasses such as `--serial`, `--select-usb`, `--select-tcpip`, `--tcpip=...`, and `--no-device-picker`.

### Organized portable package

The Windows packaging scripts keep the root directory clean instead of placing every DLL beside the launcher:

```text
scrcpy-many-portable/
├─ scrcpy.exe                 # device picker / launcher
├─ scrcpy-automation.exe      # graphical automation center
├─ bin/
│  ├─ scrcpy-core.exe         # bundled scrcpy client
│  └─ scrcpy-server
├─ lib/                       # SDL, FFmpeg, MinGW, libusb, and other DLLs
├─ platform-tools/            # adb.exe and Android platform DLLs
├─ plans/                     # saved JSON plans
└─ logs/automation/           # run logs, results, and failure artifacts
```

The launchers set their local DLL and ADB search paths automatically. Build and packaging intermediates stay in temporary directories; the final output is a single explicitly selected portable folder.

### Action recording

Run scrcpy with `--record-actions <file>` to capture replayable touch and keyboard actions for one explicit device:

```powershell
scrcpy.exe --serial DEVICE_SERIAL --record-actions evening-actions.json
```

The recorder coalesces noisy pointer events, records meaningful waits between actions, and stores coordinates in device space. Credentials and unsafe data such as PINs, patterns, biometrics, clipboard contents, file drops, and gamepad input are not recorded.

### Graphical automation center

`scrcpy-automation.exe` is a local HTML/CSS/React interface hosted by pywebview. It provides:

- A device list with automatic refresh and explicit target selection.
- Plan creation, editing, deletion, drag-and-drop ordering, and JSON persistence.
- A focused action menu for wake, wait, launch, tap, and swipe workflows.
- Import of recorded plans without requiring a separate conversion step.
- Dry-run simulation that validates the order without touching a phone.
- Immediate execution and Windows daily scheduling through `schtasks`.
- A cancellable background run with a visible stop button; cancellation interrupts waits and prevents later actions from being sent.
- Recent-run history and one-click access to execution logs.
- Chinese/English UI switching.

Each plan stores one explicit ADB serial. Connecting or disconnecting other phones does not silently retarget an existing plan. Secure lock-screen credentials still must be completed on the phone; the automation layer only wakes the display and dismisses non-secure keyguards.

## Quick Start (Windows)

1. Enable USB debugging and authorize the computer on each Android device.
2. Put the phone's ADB driver on Windows and connect devices by USB or configured ADB TCP/IP.
3. Launch `scrcpy.exe` from the portable directory. Select one or more ready devices when the picker appears.
4. Launch `scrcpy-automation.exe` to create or run scheduled plans.

For a first automation run, select a ready device, save the plan, use **Simulate**, then choose **Run now** or enable the daily schedule. The plan library is loaded automatically when the bridge becomes ready.

## Build

The core project uses Meson and Ninja. The Windows packaging helpers are in `tools/`:

```powershell
meson setup D:\scrcpy-many-build `
    -Dbuildtype=release `
    -Dportable=true `
    -Dprebuilt_server=D:\scrcpy-build-tools\scrcpy-server-v4.1 `
    -Dv4l2=false `
    -Dusb=true

ninja -C D:\scrcpy-many-build

.\tools\package_windows.ps1 `
    -BuildDir D:\scrcpy-many-build `
    -RuntimeDir D:\scrcpy-runtime `
    -OutputDir D:\scrcpy-many-portable
```

Use `tools/build_automation_center.ps1` to build the single-file automation executable. Use `tools/test_windows_package.ps1 -PackageRoot <path>` to verify the portable layout.

The automation UI can be developed independently:

```powershell
cd automation-ui
npm ci
npm test
npm run build
```

## Project Status

The fork is maintained as a practical Windows customization of scrcpy. Changes to the upstream scrcpy core are kept separate from the launcher, recorder, automation bridge, and React UI so the custom features can evolve without changing the upstream command-line model.

## License and Attribution

- Upstream project: [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)
- Upstream license: [Apache License 2.0](LICENSE)
- Upstream documentation: [scrcpy docs](https://github.com/Genymobile/scrcpy/tree/master/doc)

The custom launcher and automation-center code in this repository is distributed under the same Apache License 2.0 terms unless a component states otherwise.
