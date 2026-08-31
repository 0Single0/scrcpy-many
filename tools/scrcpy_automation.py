"""Validate and execute scheduled ADB automation plans for scrcpy-many."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import subprocess
import time
from typing import Any


SUPPORTED_ACTIONS = frozenset({
    "wait",
    "wake",
    "dismiss_keyguard",
    "launch",
    "tap",
    "swipe",
    "text",
    "keyevent",
    "tap_text",
    "assert_text",
    "screenshot",
})

_CREDENTIAL_KEYS = frozenset({"pin", "password", "credential"})
_TIME_PATTERN = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


class PlanValidationError(ValueError):
    """Raised when an automation plan does not match the supported schema."""


@dataclasses.dataclass(frozen=True)
class Step:
    action: str
    params: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class AutomationPlan:
    name: str
    serial: str
    schedule: dict[str, Any]
    steps: list[Step]


class AdbCommandError(RuntimeError):
    """Raised when ADB cannot execute a command successfully."""

    def __init__(
        self,
        serial: str,
        args: list[str],
        stderr: str,
        returncode: int | None = None,
    ) -> None:
        details = stderr.strip() or "ADB command failed"
        command = " ".join(args)
        suffix = f" (exit {returncode})" if returncode is not None else ""
        super().__init__(f"ADB error for {serial}: {command}: {details}{suffix}")
        self.serial = serial
        self.command_args = args
        self.stderr = stderr
        self.returncode = returncode


class AdbTransport:
    """Run ADB commands for one explicit serial without a shell."""

    def __init__(self, adb_path: str | pathlib.Path = "adb", default_timeout: float = 30.0) -> None:
        self.adb_path = str(adb_path)
        self.default_timeout = default_timeout

    def run(
        self,
        serial: str,
        args: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [self.adb_path, "-s", serial, *[str(arg) for arg in args]]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.default_timeout if timeout is None else timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbCommandError(serial, command[3:], f"command timed out: {exc}") from exc
        if result.returncode != 0:
            raise AdbCommandError(serial, command[3:], result.stderr, result.returncode)
        return result


class FakeAdbTransport:
    """Deterministic transport useful for unit and fixture tests."""

    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[tuple[str, list[str], float | None]] = []

    def run(
        self,
        serial: str,
        args: list[str],
        timeout: float | None = None,
    ) -> Any:
        self.calls.append((serial, list(args), timeout))
        if not self.responses:
            return subprocess.CompletedProcess([], 0, "", "")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            return response(serial, args, timeout)
        return response


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanValidationError(message)


def _reject_credentials(value: Any, location: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _CREDENTIAL_KEYS:
                raise PlanValidationError(
                    f"Credentials are not allowed in {location}.{key}"
                )
            _reject_credentials(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_credentials(child, f"{location}[{index}]")


def _validate_schedule(schedule: Any) -> dict[str, Any]:
    if schedule is None:
        return {"time": "21:00", "days": ["daily"]}
    _require(isinstance(schedule, dict), "schedule must be an object")
    time = schedule.get("time", "21:00")
    days = schedule.get("days", ["daily"])
    _require(isinstance(time, str) and _TIME_PATTERN.fullmatch(time),
             "schedule.time must use HH:MM format")
    _require(isinstance(days, list) and days and all(
        isinstance(day, str) and day for day in days
    ), "schedule.days must be a non-empty list of strings")
    return {"time": time, "days": list(days)}


def _validate_step(document: Any, index: int) -> Step:
    location = f"steps[{index}]"
    _require(isinstance(document, dict), f"{location} must be an object")
    _reject_credentials(document, location)
    action = document.get("action")
    _require(isinstance(action, str) and action in SUPPORTED_ACTIONS,
             f"{location}.action is unsupported")
    params = {key: value for key, value in document.items() if key != "action"}

    if action == "wait":
        ms = params.get("ms")
        _require(isinstance(ms, int) and not isinstance(ms, bool) and ms >= 0,
                 f"{location}.ms must be a non-negative integer")
    elif action == "launch":
        has_package = isinstance(params.get("package"), str) and bool(params["package"])
        has_component = isinstance(params.get("component"), str) and bool(params["component"])
        _require(has_package ^ has_component,
                 f"{location} requires exactly one non-empty package or component")
    elif action in {"tap_text", "assert_text"}:
        _require(isinstance(params.get("text"), str) and bool(params["text"]),
                 f"{location}.text must be a non-empty string")
    elif action == "screenshot":
        name = params.get("name", "screenshot")
        _require(isinstance(name, str) and bool(name),
                 f"{location}.name must be a non-empty string")
        params["name"] = name

    return Step(action=action, params=params)


def validate_plan(document: dict[str, Any]) -> AutomationPlan:
    """Validate a decoded JSON object and return an immutable plan model."""
    _require(isinstance(document, dict), "plan must be an object")
    _reject_credentials(document, "plan")

    name = document.get("name", "scrcpy-automation")
    serial = document.get("serial")
    raw_steps = document.get("steps")
    _require(isinstance(name, str) and bool(name.strip()),
             "name must be a non-empty string")
    _require(isinstance(serial, str) and bool(serial.strip()),
             "serial must be a non-empty string")
    _require(isinstance(raw_steps, list) and raw_steps,
             "steps must be a non-empty list")

    steps = [_validate_step(step, index) for index, step in enumerate(raw_steps)]
    return AutomationPlan(
        name=name,
        serial=serial,
        schedule=_validate_schedule(document.get("schedule")),
        steps=steps,
    )


def load_plan(path: pathlib.Path) -> AutomationPlan:
    """Load and validate one UTF-8 JSON automation plan from disk."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanValidationError(f"Could not read plan {path}: {exc}") from exc
    return validate_plan(document)


def wait_for_device(
    transport: AdbTransport,
    serial: str,
    timeout: float,
    poll_interval: float = 1.0,
) -> None:
    """Wait until ADB reports the explicit serial as ready."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            result = transport.run(serial, ["get-state"], timeout=min(remaining, 10.0))
        except AdbCommandError as exc:
            details = str(exc).lower()
            if "unauthorized" in details:
                raise AdbCommandError(
                    serial,
                    ["get-state"],
                    "Device is unauthorized; accept the USB debugging prompt",
                    exc.returncode,
                ) from exc
            if time.monotonic() >= deadline:
                raise
        else:
            state = result.stdout.strip().lower()
            if state == "device":
                return
            if state == "unauthorized":
                raise AdbCommandError(
                    serial,
                    ["get-state"],
                    "Device is unauthorized; accept the USB debugging prompt",
                    result.returncode,
                )
            if time.monotonic() >= deadline:
                raise AdbCommandError(serial, ["get-state"], f"Device state: {state or 'missing'}")

        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
