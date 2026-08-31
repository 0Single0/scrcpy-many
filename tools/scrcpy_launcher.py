#!/usr/bin/env python3
"""Small multi-device launcher for scrcpy.

The launcher deliberately starts one regular scrcpy process per selected
device. It does not duplicate or replace scrcpy's device/session logic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    transport: str
    model: str = ""
    product: str = ""


def _device_transport(serial: str, attributes: dict[str, str]) -> str:
    if "usb" in attributes:
        return "USB"
    if serial.startswith("emulator-"):
        return "Emulator"
    if ":" in serial or "adb-tls-connect" in serial:
        return "TCP/IP"
    return "USB"


def parse_adb_devices(output: str) -> list[Device]:
    """Parse the output of ``adb devices -l`` without dropping bad states."""

    devices: list[Device] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue

        fields = line.split()
        if len(fields) < 2:
            continue

        serial, state = fields[0], fields[1]
        attributes: dict[str, str] = {}
        for field in fields[2:]:
            key, separator, value = field.partition(":")
            if separator:
                attributes[key] = value

        devices.append(
            Device(
                serial=serial,
                state=state,
                transport=_device_transport(serial, attributes),
                model=attributes.get("model", "").replace("_", " "),
                product=attributes.get("product", "").replace("_", " "),
            )
        )

    return devices


def build_scrcpy_command(
    scrcpy_path: str, serial: str, extra_args: Sequence[str] = ()
) -> list[str]:
    """Build a command which always targets exactly one ADB serial."""

    return [scrcpy_path, "--serial", serial, *extra_args]


def run_adb_devices(adb_path: str) -> list[Device]:
    result = subprocess.run(
        [adb_path, "devices", "-l"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or f"adb exited with code {result.returncode}")
    return parse_adb_devices(result.stdout)


def _candidate_paths(name: str, scrcpy_path: str | None) -> Iterable[Path]:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    if scrcpy_path:
        yield Path(scrcpy_path)

    names = [name]
    if os.name == "nt" and not name.lower().endswith(".exe"):
        names.insert(0, f"{name}.exe")

    for directory in (script_dir, project_dir):
        for candidate_name in names:
            yield directory / candidate_name


def find_tool(name: str, explicit_path: str | None = None) -> str:
    for candidate in _candidate_paths(name, explicit_path):
        if candidate.is_file():
            return str(candidate.resolve())

    found = shutil.which(name)
    if found:
        return found

    hint = f" or pass --{name} PATH" if explicit_path is None else ""
    raise FileNotFoundError(f"Could not find {name}{hint}")


class LauncherApp:
    def __init__(self, root: tk.Tk, adb_path: str, scrcpy_path: str, extra_args: Sequence[str]):
        self.root = root
        self.adb_path = adb_path
        self.scrcpy_path = scrcpy_path
        self.extra_args = list(extra_args)
        self.devices: dict[str, Device] = {}
        self.processes: dict[str, subprocess.Popen[bytes]] = {}

        root.title("scrcpy many")
        root.minsize(720, 380)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = tk.StringVar(value="Ready")
        self._build_widgets()
        self.refresh()
        self.root.after(500, self._poll_processes)

    def _build_widgets(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ("serial", "state", "transport", "model", "product", "running")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "serial": "Serial",
            "state": "State",
            "transport": "Transport",
            "model": "Model",
            "product": "Product",
            "running": "scrcpy",
        }
        widths = {"serial": 190, "state": 100, "transport": 90, "model": 150, "product": 140, "running": 90}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor=tk.W)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _event: self.start_selected())

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        toolbar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Select ready", command=self.select_ready).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Clear selection", command=self.clear_selection).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Start selected", command=self.start_selected).pack(side=tk.LEFT, padx=(18, 0))
        ttk.Button(toolbar, text="Stop selected", command=self.stop_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Stop all", command=self.stop_all).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(self.root, textvariable=self.status, anchor=tk.W, padding=(12, 0, 12, 10)).pack(fill=tk.X)

    def _selected_serials(self) -> list[str]:
        return [self.tree.item(item, "values")[0] for item in self.tree.selection()]

    def refresh(self) -> None:
        selected = set(self._selected_serials()) if hasattr(self, "tree") else set()
        try:
            devices = run_adb_devices(self.adb_path)
        except (FileNotFoundError, OSError, RuntimeError) as error:
            self.status.set(str(error))
            if self.root.winfo_exists():
                messagebox.showerror("ADB error", str(error), parent=self.root)
            return

        self.devices = {device.serial: device for device in devices}
        for item in self.tree.get_children():
            self.tree.delete(item)

        for device in devices:
            running = "Running" if self._is_running(device.serial) else ""
            item = self.tree.insert(
                "",
                tk.END,
                values=(device.serial, device.state, device.transport, device.model, device.product, running),
            )
            if device.serial in selected:
                self.tree.selection_add(item)

        self._update_status(f"{len(devices)} device(s), {self._running_count()} scrcpy process(es)")

    def select_ready(self) -> None:
        self.tree.selection_remove(self.tree.selection())
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values[1] == "device":
                self.tree.selection_add(item)

    def clear_selection(self) -> None:
        self.tree.selection_remove(self.tree.selection())

    def start_selected(self) -> None:
        selected = self._selected_serials()
        if not selected:
            messagebox.showinfo("No device selected", "Select one or more devices first.", parent=self.root)
            return

        skipped: list[str] = []
        started = 0
        for serial in selected:
            device = self.devices.get(serial)
            if device is None or device.state != "device":
                skipped.append(serial)
                continue
            if self._is_running(serial):
                skipped.append(f"{serial} (already running)")
                continue

            command = build_scrcpy_command(self.scrcpy_path, serial, self.extra_args)
            try:
                process = subprocess.Popen(command, cwd=str(Path(self.scrcpy_path).parent))
            except OSError as error:
                skipped.append(f"{serial} ({error})")
                continue
            self.processes[serial] = process
            started += 1

        self.refresh()
        if skipped:
            messagebox.showwarning(
                "Some devices were skipped",
                "\n".join(skipped),
                parent=self.root,
            )
        elif started == 0:
            self._update_status("No new scrcpy process started")

    def stop_selected(self) -> None:
        for serial in self._selected_serials():
            self._stop_process(serial)
        self.refresh()

    def stop_all(self) -> None:
        for serial in list(self.processes):
            self._stop_process(serial)
        self.refresh()

    def _stop_process(self, serial: str) -> None:
        process = self.processes.get(serial)
        if process is None or process.poll() is not None:
            self.processes.pop(serial, None)
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        self.processes.pop(serial, None)

    def _is_running(self, serial: str) -> bool:
        process = self.processes.get(serial)
        return process is not None and process.poll() is None

    def _running_count(self) -> int:
        return sum(self._is_running(serial) for serial in self.processes)

    def _update_status(self, prefix: str = "") -> None:
        suffix = f" | {self._running_count()} running" if prefix else f"{self._running_count()} running"
        self.status.set(f"{prefix}{suffix}")

    def _poll_processes(self) -> None:
        for serial, process in list(self.processes.items()):
            if process.poll() is not None:
                self.processes.pop(serial, None)
        self._update_status()
        self.root.after(500, self._poll_processes)

    def close(self) -> None:
        if self._running_count() and not messagebox.askyesno(
            "Exit launcher", "Stop all scrcpy processes and exit?", parent=self.root
        ):
            return
        self.stop_all()
        self.root.destroy()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select ADB devices and launch one scrcpy process per device."
    )
    parser.add_argument("--adb", help="Path to adb (defaults to ADB, PATH, or the scrcpy directory)")
    parser.add_argument("--scrcpy", help="Path to scrcpy (defaults to the script directory or PATH)")
    parser.add_argument(
        "scrcpy_args",
        nargs=argparse.REMAINDER,
        help="Additional scrcpy options, after -- (for example -- --max-size=1024)",
    )
    args = parser.parse_args(argv)
    if args.scrcpy_args[:1] == ["--"]:
        args.scrcpy_args = args.scrcpy_args[1:]
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        scrcpy_path = find_tool("scrcpy", args.scrcpy)
        adb_explicit = args.adb or os.environ.get("ADB")
        adb_path = find_tool("adb", adb_explicit)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1

    root = tk.Tk()
    LauncherApp(root, adb_path, scrcpy_path, args.scrcpy_args)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
