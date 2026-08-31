"""Validate and execute scheduled ADB automation plans for scrcpy-many."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
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
