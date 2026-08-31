# Integrated Windows Device Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the built Windows `scrcpy.exe` show a native device picker when multiple ADB devices are connected, then start one regular scrcpy session per selected serial.

**Architecture:** Keep the existing single-device session untouched. Add a Windows-only picker before `scrcpy()` is entered; one selection continues in-process, while multiple selections spawn child copies with explicit `--serial` arguments. Expose a reusable ADB device-list API for the picker without changing the existing single-device selector contract.

**Tech Stack:** C11, SDL3 client, Win32 common controls, Meson/Ninja, existing `sc_process_execute()` abstraction, existing ADB parser and vector utilities.

**Spec:** `docs/superpowers/specs/2026-08-31-integrated-device-picker-design.md`

## Global Constraints

- Windows native picker is the first implementation; Linux and macOS behavior remains unchanged.
- Explicit selectors (`--serial`, `--select-usb`, `--select-tcpip`, `--tcpip=<address>`) bypass the picker.
- Existing one-device behavior remains unchanged.
- Only ADB entries with state `device` can be started; other states remain visible.
- Multiple selected devices use one child process per serial and preserve all original scrcpy options.
- Do not add a new runtime dependency; use Win32 controls and existing client dependencies.
- Picker cancellation exits successfully without pushing `scrcpy-server`.

---

### Task 1: ADB Listing and Argument Tests

**Files:**
- Modify: `app/src/adb/adb.h`
- Modify: `app/src/adb/adb.c`
- Modify: `app/src/adb/adb_device.h`
- Test: `app/tests/test_adb_parser.c`
- Test: `app/tests/test_cli.c`

**Interfaces:**
- Produces `bool sc_adb_list_devices(struct sc_intr *intr, unsigned flags, struct sc_vec_adb_devices *out_vec)` for the picker.
- The returned vector owns `serial`, `state`, and optional `model` strings and is released with `sc_adb_devices_destroy()`.
- Existing `sc_adb_select_device()` remains the unique-device API used by normal sessions.

- [ ] **Step 1: Add failing parser/selection tests**

Extend the existing ADB parser test fixture with multiple entries and assert that
USB, TCP/IP, emulator, unauthorized, and offline rows retain their serial,
state, and model. Add a CLI test for the child-argument helper contract if the
helper is placed in a testable client module.

- [ ] **Step 2: Run the focused tests and verify the new assertions fail**

Run from a debug Meson build:

```text
ninja -Cx test_adb_parser test_cli
```

Expected result: the new API/helper symbols are missing or the new assertions
cannot yet be satisfied.

- [ ] **Step 3: Refactor device listing into the public ADB API**

Move the current `sc_adb_list_devices()` implementation out of `static` scope
in `app/src/adb/adb.c`, declare it in `app/src/adb/adb.h`, and keep its current
buffer/error handling. Leave selection/count/state validation in
`sc_adb_select_device()` so existing behavior and messages do not change.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run the same `ninja -Cx test_adb_parser test_cli` command and require zero
failures.

- [ ] **Step 5: Commit the API/test increment**

```text
git add app/src/adb/adb.c app/src/adb/adb.h app/src/adb/adb_device.h app/tests/test_adb_parser.c app/tests/test_cli.c
git commit -m "refactor: expose adb device listing"
```

### Task 2: Windows Device Picker Module

**Files:**
- Create: `app/src/device_picker.h`
- Create: `app/src/device_picker.c` (Windows implementation plus non-Windows stub)
- Modify: `app/meson.build`
- Test: `app/tests/test_device_picker.c`

**Interfaces:**
- Produces `enum sc_device_picker_result sc_device_picker_run(struct sc_intr *intr, struct sc_vec_adb_devices *devices, struct sc_device_picker_selection *selection)`.
- `SC_DEVICE_PICKER_CANCEL` means the user canceled; `SC_DEVICE_PICKER_START` returns one or more selected serials; `SC_DEVICE_PICKER_ERROR` reports UI/ADB failure.
- The selection object owns a vector of serial copies and exposes `sc_device_picker_selection_destroy()`.

- [ ] **Step 1: Add failing selection-filter tests**

Test that only entries with state `device` are accepted for start, that an
unauthorized/offline row remains representable, and that serials are copied
without aliasing the ADB vector.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```text
ninja -Cx test_device_picker
```

Expected result: the new picker module and selection functions do not exist.

- [ ] **Step 3: Implement the Windows-only picker**

Create a modal Win32 window using a multi-select `LISTBOX` with serial, model,
transport, and state columns rendered in a fixed-width row. Add Start selected
and Cancel buttons. The list is an ADB snapshot taken immediately before the
window opens; only ready (`device`) rows can be started.
Disable Start selected when no ready row is selected; show a message for
non-ready-only selections. On successful start, copy each selected ready
serial into the selection object. Initialize and tear down common controls and
all window/heap handles in the same function.

- [ ] **Step 4: Implement platform stubs and build gating**

Declare the public header with a Windows implementation and a non-Windows stub
that returns `SC_DEVICE_PICKER_UNAVAILABLE`. Add the common implementation to
`app/meson.build`; its Win32 code is guarded by `_WIN32`.

- [ ] **Step 5: Run focused tests and a debug client build**

Run `ninja -Cx test_device_picker` and `ninja -Cx scrcpy` in a Windows debug
Meson build. Require zero test failures and a successful link against the
existing Windows libraries.

- [ ] **Step 6: Commit the picker module**

```text
git add app/src/device_picker.h app/src/device_picker.c app/meson.build
git commit -m "feat(windows): add adb device picker"
```

### Task 3: Integrated Entry Flow and Child Sessions

**Files:**
- Modify: `app/src/main.c`
- Modify: `app/src/scrcpy.c`
- Modify: `app/src/scrcpy.h`
- Modify: `app/src/cli.c`
- Modify: `app/src/options.c`
- Modify: `app/src/options.h`
- Test: `app/tests/test_cli.c`

**Interfaces:**
- Produces a Windows-only `sc_device_picker_maybe_run()` entry helper that receives parsed options and the original `argv` and returns whether normal execution should continue.
- Child command construction must append exactly one `--serial` option and its
  serial value while preserving all original arguments.
- Adds `--no-device-picker` as an automation escape hatch; explicit selectors continue to bypass the picker.

- [ ] **Step 1: Add failing CLI tests for picker gating and child arguments**

Assert that explicit `-s`, `-d`, `-e`, `--tcpip`, and `--no-device-picker`
disable picker invocation, while an empty selector set allows it. Assert that
child argv preserves an option such as `--max-size=1024` and adds one serial
selector.

- [ ] **Step 2: Run the focused CLI tests and verify failure**

Run `ninja -Cx test_cli`. Expected result: the new option/helper is absent.

- [ ] **Step 3: Add the option and preserve parsed argument state**

Add `no_device_picker` to `struct scrcpy_options`, default it to false, expose
`--no-device-picker` in `cli.c`, and ensure parsing rejects conflicting device
selectors exactly as before. Capture the original UTF-8 argv in `main.c` for
child construction.

- [ ] **Step 4: Implement the Windows preflight path**

After argument parsing and before `scrcpy()` in `main_scrcpy()`, call the
Windows picker only when no explicit selector is present and the option is not
disabled. Start ADB, list devices, and show the picker only when more than one
ready device exists. For one ready device, set `args.opts.serial` and continue
in-process. For multiple selections, spawn child copies using the existing
process abstraction with `--serial` plus the selected serial and the original
options, report
failed child starts, then return success without entering the parent session.

- [ ] **Step 5: Keep existing scrcpy() behavior unchanged for children**

Children receive explicit serials, so `app/src/server.c` selects exactly one
device and proceeds with the current push/tunnel/server lifecycle. Do not move
or duplicate decoder, controller, or screen ownership into the picker.

- [ ] **Step 6: Run CLI tests and a debug build**

Run `ninja -Cx test_cli` and `ninja -Cx scrcpy`. Require zero failures and a
successful link.

- [ ] **Step 7: Commit integrated flow**

```text
git add app/src/main.c app/src/scrcpy.c app/src/scrcpy.h app/src/cli.c app/src/options.c app/src/options.h app/tests/test_cli.c
git commit -m "feat(windows): launch selected scrcpy sessions"
```

### Task 4: Documentation and Release Verification

**Files:**
- Modify: `README.md`
- Modify: `doc/windows.md`
- Modify: `doc/shortcuts.md` only if picker keyboard behavior is documented
- Test: debug and release build outputs

**Interfaces:**
- Documents launching the built `scrcpy.exe` directly, the picker trigger,
  explicit selector behavior, and `--no-device-picker`.

- [ ] **Step 1: Update Windows usage documentation**

Document that double-clicking or launching `scrcpy.exe` with multiple ADB
devices opens the picker, and show explicit command-line examples for scripts.
State that each selected device starts an independent scrcpy window.

- [ ] **Step 2: Run all client tests**

Run:

```text
ninja -Cx test
```

Require all existing and new tests to pass.

- [ ] **Step 3: Build a Windows release artifact**

Run the repository's Windows release build, or at minimum:

```text
meson setup x --buildtype=release --strip -Db_lto=true
ninja -Cx
```

Verify that the resulting `scrcpy.exe` includes the picker code and that the
existing `scrcpy-server` artifact is produced.

- [ ] **Step 4: Manually verify the supported matrix**

With a Windows machine containing ADB, verify: zero devices, one ready device,
multiple ready devices, unauthorized/offline rows, cancel, one selection,
multiple selections, explicit `--serial`, and `--no-device-picker`. Confirm
that no server is pushed when canceling and that each selected child uses the
correct serial.

- [ ] **Step 5: Commit documentation and final verification**

```text
git add README.md doc/windows.md
git commit -m "docs: document integrated device picker"
```
