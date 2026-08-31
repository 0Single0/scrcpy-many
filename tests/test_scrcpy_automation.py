import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.scrcpy_automation import (
    AdbCommandError,
    AdbTransport,
    PlanValidationError,
    load_plan,
    validate_plan,
    wait_for_device,
)


class PlanValidationTests(unittest.TestCase):
    def test_validate_plan_accepts_the_check_in_shape(self):
        plan = validate_plan({
            "name": "check-in",
            "serial": "ABC123",
            "schedule": {"time": "21:00", "days": ["daily"]},
            "steps": [
                {"action": "wake"},
                {"action": "launch", "package": "com.example.app"},
            ],
        })

        self.assertEqual(plan.serial, "ABC123")
        self.assertEqual([step.action for step in plan.steps], ["wake", "launch"])


class TransportTests(unittest.TestCase):
    def test_transport_passes_serial_as_one_argument(self):
        transport = AdbTransport("D:/platform-tools/adb.exe")
        completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
        with mock.patch("tools.scrcpy_automation.subprocess.run", return_value=completed) as run:
            result = transport.run("192.168.1.8:5555", ["shell", "getprop"])

        self.assertIs(result, completed)
        run.assert_called_once_with(
            ["D:/platform-tools/adb.exe", "-s", "192.168.1.8:5555", "shell", "getprop"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30.0,
        )

    def test_transport_surfaces_stderr_as_an_adb_error(self):
        transport = AdbTransport("adb")
        completed = mock.Mock(returncode=1, stdout="", stderr="device offline")
        with mock.patch("tools.scrcpy_automation.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(AdbCommandError, "device offline"):
                transport.run("ABC123", ["get-state"])

    def test_wait_for_device_retries_until_ready(self):
        class FakeTransport:
            def __init__(self):
                self.states = ["offline", "device"]
                self.calls = []

            def run(self, serial, args, timeout):
                self.calls.append((serial, args, timeout))
                state = self.states.pop(0)
                return mock.Mock(returncode=0, stdout=state + "\n", stderr="")

        transport = FakeTransport()
        with mock.patch("tools.scrcpy_automation.time.sleep") as sleep:
            wait_for_device(transport, "ABC123", timeout=5, poll_interval=0.1)

        self.assertEqual(len(transport.calls), 2)
        sleep.assert_called_once_with(0.1)

    def test_wait_for_device_rejects_unauthorized_immediately(self):
        class FakeTransport:
            def run(self, serial, args, timeout):
                return mock.Mock(returncode=0, stdout="unauthorized\n", stderr="")

        with self.assertRaisesRegex(AdbCommandError, "authorize"):
            wait_for_device(FakeTransport(), "ABC123", timeout=5, poll_interval=0)

    def test_validate_plan_rejects_missing_serial(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({"name": "check-in", "steps": [{"action": "wake"}]})

    def test_validate_plan_rejects_unsupported_action(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({
                "serial": "ABC123",
                "steps": [{"action": "launch_browser"}],
            })

    def test_validate_plan_rejects_negative_wait(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({
                "serial": "ABC123",
                "steps": [{"action": "wait", "ms": -1}],
            })

    def test_validate_plan_requires_launch_target(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({
                "serial": "ABC123",
                "steps": [{"action": "launch"}],
            })

    def test_validate_plan_rejects_multiple_launch_targets(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({
                "serial": "ABC123",
                "steps": [{
                    "action": "launch",
                    "package": "com.example.app",
                    "component": "com.example.app/.MainActivity",
                }],
            })

    def test_validate_plan_rejects_credentials(self):
        with self.assertRaises(PlanValidationError):
            validate_plan({
                "serial": "ABC123",
                "steps": [{"action": "text", "password": "secret"}],
            })

    def test_load_plan_reads_json_from_disk(self):
        document = {
            "name": "check-in",
            "serial": "ABC123",
            "steps": [{"action": "wake"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "plan.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            plan = load_plan(path)

        self.assertEqual(plan.name, "check-in")
        self.assertEqual(plan.serial, "ABC123")


if __name__ == "__main__":
    unittest.main()
