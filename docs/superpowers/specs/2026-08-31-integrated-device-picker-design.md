# Integrated Windows Device Picker

## Goal

When the built Windows `scrcpy.exe` is launched without an explicit device
selector and multiple ADB devices are available, show a native graphical
picker. Starting one selected device keeps the existing in-process scrcpy
flow. Starting multiple selected devices launches one child `scrcpy.exe`
process per serial, each with an explicit `--serial` argument.

The existing command-line behavior remains available for scripts and for
explicit selectors (`--serial`, `--select-usb`, `--select-tcpip`, and
`--tcpip=<address>`).

## Scope

- Windows native picker integrated into the client executable.
- Enumerate and display all ADB entries, including non-ready states.
- Allow selecting one or more entries, with only `device` entries startable.
- Preserve all original scrcpy arguments when spawning child sessions.
- Reuse the existing single-device server, decoder, controller, and cleanup
  lifecycle in each child process.
- Keep Linux and macOS behavior unchanged in the first implementation.

Out of scope: a single-process multi-session refactor, window tiling, input
broadcasting, device thumbnails, or automatic reconnection.

## Architecture

### Entry flow

`main.c` parses the command line as it does today. Before calling the normal
`scrcpy()` session, a Windows-only picker decision is made:

1. If an explicit selector or `--no-device-picker` is present, call the current
   flow unchanged.
2. Otherwise enumerate ADB devices.
3. If zero or one ready device is available, preserve the current behavior.
4. If multiple devices are available, show the picker.
5. On cancel, exit successfully without starting a server.
6. On one selection, set the selected serial in the options and call
   `scrcpy()`.
7. On multiple selections, spawn child copies with `--serial=<serial>` and
   the original arguments, then exit after the children have been started.

The child sees an explicit selector and therefore never opens another picker.
The existing random SCID and tunnel-port selection remain responsible for
isolating the child sessions.

### Device enumeration

Expose a read-only ADB listing function based on the existing parser. The
listing must retain serial, state, model, and inferred transport type. The
existing `sc_adb_select_device()` remains unchanged for normal single-device
selection and its error reporting.

### Windows UI

Add a Windows-only module under `app/src/sys/win/` (or an equivalent
`device_selector_win.c/.h` boundary) using standard Win32 controls. The dialog
contains:

- a multi-select list box with serial, state, transport, and model columns;
- Start selected;
- Cancel.

The list is a fresh ADB snapshot taken before the dialog opens. A refresh
control can be added later without changing the process/session architecture.

The UI must report ADB invocation failures, leave unauthorized/offline rows
visible, disable or reject starting non-ready rows, and close all temporary
handles before returning.

### Child processes

Use the existing cross-platform process abstraction where possible, with the
Windows implementation preserving the current executable path and command
line. Each child receives the original scrcpy options plus exactly one
`--serial` option. A child-start failure is reported in the picker or console;
already-started children are not silently terminated unless the user cancels
before the picker exits.

## Compatibility and error handling

- One connected device: no picker and no behavior change.
- Multiple devices with an explicit selector: no picker and no behavior
  change.
- Multiple devices with no selector: picker appears.
- No ready devices: retain the existing ADB error path.
- ADB unavailable: show a clear error and return failure.
- Picker cancellation: return success without pushing the Android server.
- A child exits or fails after launch: its own existing scrcpy logging and exit
  code remain authoritative.

## Testing

- Unit-test the device-list conversion and selection filtering.
- Unit-test child argument construction, including preservation of options and
  insertion of one serial selector.
- Manually verify Windows cases: zero devices, one device, multiple devices,
  unauthorized device, cancel, one selection, multiple selections, and an
  explicit `--serial` invocation.
- Verify the existing client tests and a Windows release build.
