import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.scrcpy_automation import (
    AdbCommandError,
    AdbTransport,
    AutomationPlan,
    FakeAdbTransport,
    PlanValidationError,
    RunResult,
    load_plan,
    parse_uiautomator_xml,
    build_schtasks_create_command,
    build_schtasks_delete_command,
    main,
    run_plan,
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


class ActionExecutionTests(unittest.TestCase):
    def make_plan(self, steps):
        return validate_plan({
            "name": "test",
            "serial": "ABC123",
            "steps": steps,
        })

    def test_executes_basic_actions_in_order(self):
        plan = self.make_plan([
            {"action": "wake"},
            {"action": "dismiss_keyguard"},
            {"action": "launch", "package": "com.example.app"},
            {"action": "tap", "x": 100, "y": 200},
            {"action": "swipe", "x1": 100, "y1": 200, "x2": 100, "y2": 500, "duration_ms": 300},
            {"action": "text", "value": "hello"},
            {"action": "keyevent", "code": "BACK"},
        ])
        transport = FakeAdbTransport()
        with tempfile.TemporaryDirectory() as directory:
            result = run_plan(plan, transport, pathlib.Path(directory))

        self.assertTrue(result.success)
        self.assertEqual(
            [call[1] for call in transport.calls],
            [
                ["get-state"],
                ["shell", "input", "keyevent", "KEYCODE_WAKEUP"],
                ["shell", "wm", "dismiss-keyguard"],
                ["shell", "monkey", "-p", "com.example.app", "1"],
                ["shell", "input", "tap", "100", "200"],
                ["shell", "input", "swipe", "100", "200", "100", "500", "300"],
                ["shell", "input", "text", "hello"],
                ["shell", "input", "keyevent", "BACK"],
            ],
        )

    def test_tap_text_uses_the_center_of_the_matching_node(self):
        xml = (pathlib.Path(__file__).parent / "fixtures" / "uiautomator_checkin.xml").read_text(encoding="utf-8")
        transport = FakeAdbTransport([
            None,
            None,
            None,
            None,
        ])
        transport.responses = [
            mock.Mock(returncode=0, stdout="device\n", stderr=""),
            mock.Mock(returncode=0, stdout="UI hierchary dumped to: /sdcard/window.xml\n", stderr=""),
            mock.Mock(returncode=0, stdout=xml, stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        plan = self.make_plan([{"action": "tap_text", "text": "打卡"}])

        with tempfile.TemporaryDirectory() as directory:
            result = run_plan(plan, transport, pathlib.Path(directory))

        self.assertTrue(result.success)
        self.assertEqual(transport.calls[-1][1], ["shell", "input", "tap", "540", "1460"])

    def test_assert_text_failure_stops_later_actions(self):
        transport = FakeAdbTransport([
            mock.Mock(returncode=0, stdout="device\n", stderr=""),
            mock.Mock(returncode=0, stdout="dumped\n", stderr=""),
            mock.Mock(returncode=0, stdout="<hierarchy />", stderr=""),
        ])
        plan = self.make_plan([
            {"action": "assert_text", "text": "打卡成功"},
            {"action": "tap", "x": 1, "y": 1},
        ])

        with tempfile.TemporaryDirectory() as directory:
            result = run_plan(plan, transport, pathlib.Path(directory))
            log_exists = pathlib.Path(directory, "run.log").exists()

        self.assertFalse(result.success)
        self.assertEqual(result.completed_steps, 0)
        self.assertNotIn(["shell", "input", "tap", "1", "1"], [call[1] for call in transport.calls])
        self.assertTrue(log_exists)

    def test_adb_action_retries_once_after_transient_failure(self):
        transient = AdbCommandError("ABC123", ["shell", "input", "tap", "1", "2"], "offline", 1)
        transport = FakeAdbTransport([
            mock.Mock(returncode=0, stdout="device\n", stderr=""),
            transient,
            mock.Mock(returncode=0, stdout="", stderr=""),
        ])
        plan = self.make_plan([{"action": "tap", "x": 1, "y": 2}])
        with tempfile.TemporaryDirectory() as directory, mock.patch("tools.scrcpy_automation.time.sleep") as sleep:
            result = run_plan(plan, transport, pathlib.Path(directory))

        self.assertTrue(result.success)
        self.assertEqual([call[1] for call in transport.calls].count(["shell", "input", "tap", "1", "2"]), 2)
        sleep.assert_called_once_with(1.0)

    def test_screenshot_writes_binary_file(self):
        transport = FakeAdbTransport([
            mock.Mock(returncode=0, stdout="device\n", stderr=""),
            mock.Mock(returncode=0, stdout=b"PNG\x00bytes", stderr=b""),
        ])
        plan = self.make_plan([{"action": "screenshot", "name": "state"}])
        with tempfile.TemporaryDirectory() as directory:
            result = run_plan(plan, transport, pathlib.Path(directory))
            screenshot = pathlib.Path(directory, "state.png")
            screenshot_bytes = screenshot.read_bytes()

        self.assertTrue(result.success)
        self.assertEqual(screenshot_bytes, b"PNG\x00bytes")

    def test_dry_run_does_not_call_adb(self):
        transport = FakeAdbTransport()
        plan = self.make_plan([{"action": "wake"}, {"action": "tap", "x": 1, "y": 2}])

        with tempfile.TemporaryDirectory() as directory:
            result = run_plan(plan, transport, pathlib.Path(directory), dry_run=True)

        self.assertTrue(result.success)
        self.assertEqual(result.completed_steps, 2)
        self.assertEqual(transport.calls, [])

    def test_parse_uiautomator_xml_extracts_bounds(self):
        nodes = parse_uiautomator_xml(
            '<hierarchy><node text="打卡" bounds="[400,1400][680,1520]" /></hierarchy>'
        )
        self.assertEqual(nodes[0].text, "打卡")
        self.assertEqual(nodes[0].bounds, (400, 1400, 680, 1520))


class CliTests(unittest.TestCase):
    def test_scheduler_command_contains_daily_time_and_absolute_plan(self):
        plan_path = pathlib.Path("tools/examples/evening-check-in.json")
        command = build_schtasks_create_command(
            plan_path, pathlib.Path("C:/Python/python.exe"), pathlib.Path("tools/scrcpy_automation.py")
        )
        self.assertIn("/SC", command)
        self.assertEqual(command[command.index("/SC") + 1], "DAILY")
        self.assertEqual(command[command.index("/ST") + 1], "21:00")
        self.assertIn(str(plan_path.resolve()), command[-1])

    def test_remove_command_uses_delete_and_force(self):
        self.assertEqual(
            build_schtasks_delete_command("scrcpy-many:evening-check-in"),
            ["schtasks.exe", "/Delete", "/TN", "scrcpy-many:evening-check-in", "/F"],
        )

    def test_validate_cli_returns_zero_for_example(self):
        self.assertEqual(main(["validate", "tools/examples/evening-check-in.json"]), 0)

    def test_run_dry_run_returns_zero_without_adb(self):
        with mock.patch("tools.scrcpy_automation.AdbTransport") as transport:
            result = main(["run", "tools/examples/evening-check-in.json", "--dry-run"])
        self.assertEqual(result, 0)
        transport.assert_called_once()


class FullFlowTests(unittest.TestCase):
    def test_example_plan_runs_wake_launch_tap_assert_flow(self):
        xml = (pathlib.Path(__file__).parent / "fixtures" / "uiautomator_checkin.xml").read_text(encoding="utf-8")
        responses = [
            mock.Mock(returncode=0, stdout="device\n", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout=xml, stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout=xml.replace("打卡", "打卡成功"), stderr=""),
            mock.Mock(returncode=0, stdout=b"PNG", stderr=b""),
        ]
        transport = FakeAdbTransport(responses)
        plan = load_plan(pathlib.Path("tools/examples/evening-check-in.json"))

        with tempfile.TemporaryDirectory() as directory, mock.patch("tools.scrcpy_automation.time.sleep"):
            result = run_plan(plan, transport, pathlib.Path(directory))

        self.assertTrue(result.success, result.error)
        self.assertIn(["shell", "input", "tap", "540", "1460"], [call[1] for call in transport.calls])

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
