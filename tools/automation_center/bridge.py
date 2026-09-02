"""Typed, local-only operations exposed to the automation center UI."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any

from tools.scrcpy_automation import (
    AdbTransport,
    AutomationPlan,
    PlanValidationError,
    build_schtasks_create_command,
    build_schtasks_delete_command,
    load_plan as load_automation_plan,
    run_plan,
    scheduled_task_name,
    validate_plan,
)
from tools.scrcpy_launcher import parse_adb_devices

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_WM_CLOSE = 0x0010


def _request_window_close(title: str) -> bool:
    """Ask the owned recording window to close so scrcpy can finalize JSON."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        window = ctypes.windll.user32.FindWindowW(None, title)
        return bool(window and ctypes.windll.user32.PostMessageW(
            window, _WM_CLOSE, 0, 0,
        ))
    except (AttributeError, OSError):
        return False


class AutomationBridge:
    """Own files and system calls for one portable automation-center install."""

    def __init__(self, portable_root: Path, transport: Any | None = None) -> None:
        self.portable_root = Path(portable_root).resolve()
        self.plans_dir = self.portable_root / "plans"
        self.logs_dir = self.portable_root / "logs" / "automation"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.adb_path = self.portable_root / "platform-tools" / "adb.exe"
        self.transport = transport or AdbTransport(
            self.adb_path
        )
        self._recording_process: Any | None = None
        self._recording_path: Path | None = None
        self._recording_serial: str | None = None
        self._recording_window_title: str | None = None
        self._run_thread: threading.Thread | None = None
        self._run_cancel_event: threading.Event | None = None
        self._run_status: dict[str, object] | None = None
        self._run_lock = threading.Lock()

    @staticmethod
    def _failure(code: str, message: str) -> dict[str, object]:
        return {"ok": False, "code": code, "message": message}

    @staticmethod
    def _plan_filename(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise PlanValidationError("name must be a non-empty string")
        name = name.strip()
        if Path(name).name != name or name in {".", ".."}:
            raise PlanValidationError("name must not contain a path")
        stem = name[:-5] if name.lower().endswith(".json") else name
        if not stem or not all(character.isalnum() or character in " _-" for character in stem):
            raise PlanValidationError("name contains unsupported characters")
        return f"{stem}.json"

    def _is_within(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True

    def _plan_path(self, value: str | None, name: str | None = None) -> Path:
        if value is None:
            assert name is not None
            return (self.plans_dir / self._plan_filename(name)).resolve()

        candidate = Path(value)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            if ".." in candidate.parts:
                raise ValueError("plan path must not traverse directories")
            resolved = (self.plans_dir / candidate).resolve()
        if resolved.suffix.lower() != ".json" or not self._is_within(resolved, self.plans_dir):
            raise ValueError("plan path must be a JSON file below plans")
        return resolved

    def _read_document(self, path: Path) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PlanValidationError(f"Could not read plan {path}: {exc}") from exc
        validate_plan(document)
        return document

    def list_devices(self) -> list[dict[str, str]]:
        """List all ADB-reported devices without picking a target implicitly."""
        try:
            completed = subprocess.run(
                [str(self.adb_path), "devices", "-l"],
                text=True,
                capture_output=True,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError:
            return []
        if completed.returncode:
            return []
        return [
            {
                "serial": device.serial,
                "state": device.state,
                "transport": device.transport,
                "model": device.model,
                "product": device.product,
            }
            for device in parse_adb_devices(completed.stdout)
        ]

    def list_plans(self) -> list[dict[str, str]]:
        plans: list[dict[str, str]] = []
        for path in sorted(self.plans_dir.glob("*.json"), key=lambda item: item.name.casefold()):
            try:
                plan = load_automation_plan(path)
            except PlanValidationError:
                continue
            plans.append({"name": plan.name, "path": str(path.resolve()), "serial": plan.serial})
        return plans

    def load_plan(self, path: str) -> dict[str, object]:
        try:
            document = self._read_document(self._plan_path(path))
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))
        return {"ok": True, "document": document}

    def save_plan(self, document: dict[str, Any], path: str | None = None) -> dict[str, object]:
        try:
            plan = validate_plan(document)
            target = self._plan_path(path, plan.name)
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))

        saved_document = dict(document)
        saved_document["name"] = plan.name
        saved_document["serial"] = plan.serial
        saved_document["schedule"] = plan.schedule
        temporary = target.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(saved_document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(target)
        except OSError as exc:
            return self._failure("write_error", str(exc))
        return {"ok": True, "path": str(target)}

    def delete_plan(self, path: str) -> dict[str, object]:
        """Remove one plan and its scheduled task, if Windows has one."""
        try:
            target = self._plan_path(path)
            plan = load_automation_plan(target)
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))

        task_name = scheduled_task_name(plan.name)
        try:
            query = subprocess.run(
                ["schtasks.exe", "/Query", "/TN", task_name],
                text=True,
                capture_output=True,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
            if not query.returncode:
                removed = subprocess.run(
                    build_schtasks_delete_command(task_name),
                    text=True,
                    capture_output=True,
                    check=False,
                    creationflags=_CREATE_NO_WINDOW,
                )
                if removed.returncode:
                    return self._failure(
                        "scheduler_error",
                        removed.stderr.strip() or "Could not remove scheduled task",
                    )
            target.unlink()
        except OSError as exc:
            return self._failure("delete_error", str(exc))
        return {"ok": True, "path": str(target)}

    def run_plan_now(self, path: str, dry_run: bool = False) -> dict[str, object]:
        try:
            plan_path = self._plan_path(path)
            plan = load_automation_plan(plan_path)
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = self.logs_dir / self._plan_filename(plan.name)[:-5] / timestamp
        result = run_plan(plan, self.transport, run_dir, dry_run=dry_run)
        summary = {
            "status": "success" if result.success else "failure",
            "success": result.success,
            "completed_steps": result.completed_steps,
            "error": result.error,
            "dry_run": bool(dry_run),
        }
        (run_dir / "result.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return {"ok": True, "run_dir": str(run_dir), **summary}

    def start_plan_run(self, path: str, dry_run: bool = False) -> dict[str, object]:
        """Start a plan on a worker thread so the UI can cancel it safely."""
        try:
            plan_path = self._plan_path(path)
            plan = load_automation_plan(plan_path)
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))

        with self._run_lock:
            if self._run_thread is not None and self._run_thread.is_alive():
                return self._failure("run_active", "An automation run is already active")

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            run_dir = self.logs_dir / self._plan_filename(plan.name)[:-5] / timestamp
            cancel_event = threading.Event()
            self._run_cancel_event = cancel_event
            self._run_status = {
                "running": True,
                "run_dir": str(run_dir),
                "dry_run": bool(dry_run),
            }

            def execute() -> None:
                try:
                    result = run_plan(
                        plan,
                        self.transport,
                        run_dir,
                        dry_run=dry_run,
                        cancel_event=cancel_event,
                    )
                    cancelled = result.error == "Run cancelled"
                    summary = {
                        "running": False,
                        "status": "cancelled" if cancelled else "success" if result.success else "failure",
                        "cancelled": cancelled,
                        "success": result.success,
                        "completed_steps": result.completed_steps,
                        "error": result.error,
                        "run_dir": str(run_dir),
                        "dry_run": bool(dry_run),
                    }
                except Exception as exc:
                    summary = {
                        "running": False,
                        "status": "failure",
                        "cancelled": False,
                        "success": False,
                        "completed_steps": 0,
                        "error": str(exc),
                        "run_dir": str(run_dir),
                        "dry_run": bool(dry_run),
                    }
                try:
                    run_dir.mkdir(parents=True, exist_ok=True)
                    (run_dir / "result.json").write_text(
                        json.dumps(
                            {key: value for key, value in summary.items() if key != "running"},
                            ensure_ascii=False,
                            indent=2,
                        ) + "\n",
                        encoding="utf-8",
                    )
                except OSError as exc:
                    summary["status"] = "failure"
                    summary["cancelled"] = False
                    summary["success"] = False
                    summary["error"] = str(exc)
                with self._run_lock:
                    self._run_status = summary

            self._run_thread = threading.Thread(
                target=execute,
                name="scrcpy-automation-run",
                daemon=True,
            )
            self._run_thread.start()
            return {"ok": True, "running": True, "run_dir": str(run_dir)}

    def get_plan_run_status(self) -> dict[str, object]:
        """Return the state of the most recently started asynchronous run."""
        with self._run_lock:
            if self._run_status is None:
                return self._failure("no_run", "No automation run has been started")
            status = dict(self._run_status)
            if self._run_thread is not None and self._run_thread.is_alive():
                status["running"] = True
            return {"ok": True, **status}

    def cancel_plan_run(self) -> dict[str, object]:
        """Request cancellation of the current run without killing its process."""
        with self._run_lock:
            if (
                self._run_thread is None
                or not self._run_thread.is_alive()
                or self._run_cancel_event is None
            ):
                return self._failure("no_active_run", "No automation run is active")
            self._run_cancel_event.set()
            return {"ok": True, "cancelling": True}

    def start_recording(self, serial: str) -> dict[str, object]:
        """Start one owned scrcpy recording session for a ready device."""
        if self._recording_process is not None:
            return self._failure("recording_active", "A recording session is already active")
        if not isinstance(serial, str) or not serial.strip():
            return self._failure("device_not_ready", "Choose one ready device before recording")

        serial = serial.strip()
        try:
            state = self.transport.run(serial, ["get-state"]).stdout.strip().lower()
        except Exception as exc:
            return self._failure("device_not_ready", str(exc))
        if state != "device":
            return self._failure("device_not_ready", f"Device state: {state or 'missing'}")

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        output = self.plans_dir / f".recording-{timestamp}.json"
        title = f"scrcpy automation - {serial}"
        environment = os.environ.copy()
        runtime_paths = [
            str(self.portable_root / "lib"),
            str(self.portable_root / "platform-tools"),
            environment.get("PATH", ""),
        ]
        environment["PATH"] = os.pathsep.join(path for path in runtime_paths if path)
        command = [
            str(self.portable_root / "bin" / "scrcpy-core.exe"),
            "--serial",
            serial,
            "--window-title",
            title,
            "--record-actions",
            str(output),
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=self.portable_root,
                env=environment,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            return self._failure("recording_start_failed", str(exc))

        self._recording_process = process
        self._recording_path = output
        self._recording_serial = serial
        self._recording_window_title = title
        return {"ok": True, "serial": serial, "path": str(output)}

    def stop_recording(self) -> dict[str, object]:
        """End and persist only the recording process owned by this bridge."""
        if self._recording_process is None or self._recording_path is None:
            return self._failure("recording_not_active", "No recording session is active")

        process = self._recording_process
        recording_path = self._recording_path
        window_title = self._recording_window_title
        self._recording_process = None
        self._recording_path = None
        self._recording_serial = None
        self._recording_window_title = None

        try:
            if process.poll() is None:
                if window_title and _request_window_close(window_title):
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        process.wait(timeout=5)
                else:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

            document = self._read_document(recording_path)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            document["name"] = f"recorded-{timestamp}"
            document["schedule"] = {"time": "21:00", "days": ["daily"]}
            saved = self.save_plan(document)
            if not saved.get("ok"):
                return saved
            return {"ok": True, "path": saved["path"], "document": document}
        except PlanValidationError as exc:
            return self._failure("recording_invalid", str(exc))
        except (OSError, subprocess.SubprocessError) as exc:
            return self._failure("recording_stop_failed", str(exc))
        finally:
            try:
                recording_path.unlink()
            except FileNotFoundError:
                pass

    def list_runs(self, plan_name: str) -> list[dict[str, str]]:
        try:
            plan_directory = self.logs_dir / self._plan_filename(plan_name)[:-5]
        except PlanValidationError:
            return []
        if not plan_directory.is_dir():
            return []

        runs: list[dict[str, str]] = []
        for run_dir in sorted(plan_directory.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            try:
                summary = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            runs.append({
                "run_dir": str(run_dir),
                "status": str(summary.get("status", "failure")),
                "error": str(summary.get("error") or ""),
            })
        return runs

    def open_artifact(self, path: str) -> dict[str, object]:
        try:
            artifact = Path(path).resolve(strict=True)
        except (OSError, TypeError) as exc:
            return self._failure("artifact_missing", str(exc))
        if not artifact.is_file() or not self._is_within(artifact, self.logs_dir):
            return self._failure("artifact_outside_logs", "Only files below logs may be opened")
        try:
            os.startfile(str(artifact))
        except AttributeError:
            return self._failure("artifact_open_unsupported", "Opening artifacts requires Windows")
        except OSError as exc:
            return self._failure("artifact_open_failed", str(exc))
        return {"ok": True, "path": str(artifact)}

    def set_schedule(self, path: str) -> dict[str, object]:
        try:
            plan_path = self._plan_path(path)
            plan = load_automation_plan(plan_path)
        except ValueError as exc:
            return self._failure("invalid_plan_path", str(exc))
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))

        runner_is_executable = getattr(sys, "frozen", False)
        runner = self.portable_root / "scrcpy-automation.exe"
        if not runner_is_executable:
            runner = Path(__file__).with_name("app.py")
        command = build_schtasks_create_command(
            plan_path, Path(sys.executable), runner,
            runner_is_executable=runner_is_executable,
        )
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            return self._failure("scheduler_error", str(exc))
        if completed.returncode:
            return self._failure("scheduler_error", completed.stderr.strip() or "schtasks failed")
        return {"ok": True, "task_name": scheduled_task_name(plan.name)}

    def remove_schedule(self, name: str) -> dict[str, object]:
        try:
            filename = self._plan_filename(name)
        except PlanValidationError as exc:
            return self._failure("validation_error", str(exc))
        task_name = scheduled_task_name(filename[:-5])
        command = build_schtasks_delete_command(task_name)
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            return self._failure("scheduler_error", str(exc))
        if completed.returncode:
            return self._failure("scheduler_error", completed.stderr.strip() or "schtasks failed")
        return {"ok": True, "task_name": task_name}
