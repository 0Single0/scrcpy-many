# On Windows

## Install

### From the official release

Download the [latest release]:

 - [`scrcpy-win64-v4.1.zip`][direct-win64] (64-bit)  
   <sub>SHA-256: `5b12172b3264b2889f4583ee64752ce832e29bc8b1089dca81093459697165db`</sub>
 - [`scrcpy-win32-v4.1.zip`][direct-win32] (32-bit)  
   <sub>SHA-256: `fa57b36622a53b6aec74c5e5b5c08236165efa445c4f186d48f176ebf9c24eec`</sub>

[latest release]: https://github.com/Genymobile/scrcpy/releases/latest
[direct-win64]: https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip
[direct-win32]: https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win32-v4.1.zip

and extract it.

The custom Windows build in this repository can also be packaged with the
directory layout below (the `tools/package_windows.ps1` script does this):

```text
scrcpy-release/
  scrcpy.exe                 # launcher to run
  scrcpy-automation.exe      # graphical local automation center
  bin/scrcpy-core.exe        # client executable
  bin/scrcpy-server
  lib/*.dll                  # runtime libraries
  platform-tools/adb.exe
  plans/                     # user-created plans
  logs/                      # automation run history
```

The launcher adds `lib` and `platform-tools` to the child process search path,
so the DLLs and ADB files do not need to remain in the top-level directory.

`scrcpy.exe` remains the multi-device picker and mirroring entry point.
`scrcpy-automation.exe` is the separate, portable HTML/CSS desktop interface
for a single explicitly selected device: create/edit a plan, record actions,
run it, and create or remove its daily schedule. It bundles its own Python
runtime and WebView host, so the end user does not need Python or Node.

## Scheduled device automation

The repository includes a Windows-side Python runner for repeatable Android
flows such as an evening check-in. It always targets the explicit `serial` in
the JSON plan; connecting another phone does not change the target.

Preview and validate the supplied example before touching a device:

```powershell
python tools/scrcpy_automation.py validate tools/examples/evening-check-in.json
python tools/scrcpy_automation.py run tools/examples/evening-check-in.json --dry-run
```

Create the daily 21:00 task:

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_scrcpy_automation.ps1 `
    -Plan tools/examples/evening-check-in.json
```

The phone must already be authorized (`adb devices` shows `device`). The
runner can wake the display and dismiss a non-secure keyguard, but it does not
store or bypass PIN, pattern, fingerprint, or face unlock. The task runs under
the logged-in Windows user. Run logs and failure screenshots are written under
`logs/automation/<plan-name>/<timestamp>/`.

## Graphical automation center

Open `scrcpy-automation.exe` from the packaged directory. Select one ready
ADB device in the Devices column, create or open a plan, then save it before
using the run or scheduler controls. “Try run” validates the plan flow without
sending ADB actions; “Run now” sends actions to the plan's explicit serial.

“Record actions” opens one scrcpy session owned by the automation center. On
stop, its touch, swipe, and supported Android key actions are validated before
they are saved below `plans/`. The center cannot choose a target automatically,
store credentials, execute arbitrary commands, or bypass secure device locks.
Run logs and available failure screenshots stay under `logs/automation/` and
can be opened from the history panel.


### From a package manager

From [WinGet] (ADB and other dependencies will be installed alongside scrcpy):

```bash
winget install --exact Genymobile.scrcpy
```

From [Chocolatey]:

```bash
choco install scrcpy
choco install adb    # if you don't have it yet
```

From [Scoop]:

```bash
scoop install scrcpy
scoop install adb    # if you don't have it yet
```

[WinGet]: https://github.com/microsoft/winget-cli
[Chocolatey]: https://chocolatey.org/
[Scoop]: https://scoop.sh

_See [build.md](build.md) to build and install the app manually._


## Run

_Make sure that your device meets the [prerequisites](/README.md#prerequisites)._

Scrcpy is a command line application: it is mainly intended to be executed from
a terminal with command line arguments.

The built `scrcpy.exe` also provides a Windows device picker. If multiple ADB
devices are ready and no selector is provided, double-clicking `scrcpy.exe` (or
running it without arguments) opens a native window listing the serial, model,
transport, and state of each device. Select one or more ready devices and
choose `Start selected`; each selection starts an independent scrcpy window.
Cancel closes the picker without starting a device session.

The picker is bypassed when using an explicit selector (`--serial`,
`--select-usb`, `--select-tcpip`, or `--tcpip=<address>`). To force the normal
command-line flow in scripts, use `--no-device-picker`.

To open a terminal at the expected location, double-click on
`open_a_terminal_here.bat` in your scrcpy directory, then type your command. For
example, without arguments:

```bash
scrcpy
```

or with arguments (here to disable audio and record to `file.mkv`):

```bash
scrcpy --no-audio --record=file.mkv
```

Documentation for command line arguments is available:
 - `scrcpy --help`
 - on [github](/README.md)

If you plan to always use the same arguments, create a file `myscrcpy.bat`
(enable [show file extensions] to avoid confusion) containing your command, For
example:

```bash
scrcpy --prefer-text --turn-screen-off --stay-awake
```

Add `--pause-on-exit=if-error` if you want the console to remain open when
scrcpy fails:

```bash
scrcpy --prefer-text --turn-screen-off --stay-awake --pause-on-exit=if-error
```

[show file extensions]: https://www.howtogeek.com/205086/beginner-how-to-make-windows-show-file-extensions/

Then just double-click on that file to run it.

To start scrcpy without opening a terminal, double-click `scrcpy-noconsole.vbs`
(note that errors won't be shown). To pass arguments, edit (a copy of)
`scrcpy-noconsole.vbs` and add the desired arguments.
