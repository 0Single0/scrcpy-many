import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.scrcpy_automation import FakeAdbTransport


class AutomationBridgeStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.directory.name)
        from tools.automation_center.bridge import AutomationBridge

        self.bridge = AutomationBridge(self.root, transport=FakeAdbTransport())

    def tearDown(self):
        self.directory.cleanup()

    def test_save_plan_stores_valid_document_under_portable_plans(self):
        saved = self.bridge.save_plan({
            "name": "morning",
            "serial": "ABC",
            "steps": [{"action": "wake"}],
        })

        self.assertTrue(saved["ok"])
        plan_path = (self.root / "plans" / "morning.json").resolve()
        self.assertEqual(saved["path"], str(plan_path))
        self.assertEqual(self.bridge.list_plans(), [{
            "name": "morning",
            "path": str(plan_path),
            "serial": "ABC",
        }])

    def test_save_plan_rejects_a_path_outside_portable_plans(self):
        result = self.bridge.save_plan({
            "name": "morning",
            "serial": "ABC",
            "steps": [{"action": "wake"}],
        }, "../other.json")

        self.assertEqual(result["code"], "invalid_plan_path")
        self.assertFalse((self.root.parent / "other.json").exists())

    def test_run_dry_run_writes_and_lists_a_successful_run(self):
        saved = self.bridge.save_plan({
            "name": "morning",
            "serial": "ABC",
            "steps": [{"action": "wake"}],
        })

        result = self.bridge.run_plan_now(saved["path"], dry_run=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["success"])
        self.assertEqual(result["completed_steps"], 1)
        runs = self.bridge.list_runs("morning")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "success")
        self.assertTrue(pathlib.Path(runs[0]["run_dir"], "run.log").is_file())

    def test_load_plan_rejects_a_path_outside_portable_plans(self):
        outside = self.root.parent / "outside.json"
        outside.write_text(json.dumps({"serial": "ABC", "steps": [{"action": "wake"}]}), encoding="utf-8")

        result = self.bridge.load_plan(str(outside))

        self.assertEqual(result["code"], "invalid_plan_path")

    @mock.patch("tools.automation_center.bridge.os.startfile", create=True)
    def test_open_artifact_allows_only_files_below_run_logs(self, startfile):
        artifact = self.root / "logs" / "automation" / "morning" / "run.log"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("result=success\n", encoding="utf-8")
        plan = self.root / "plans" / "morning.json"
        plan.write_text("{}", encoding="utf-8")

        opened = self.bridge.open_artifact(str(artifact))
        rejected = self.bridge.open_artifact(str(plan))

        self.assertTrue(opened["ok"])
        startfile.assert_called_once_with(str(artifact.resolve()))
        self.assertEqual(rejected["code"], "artifact_outside_logs")

    @mock.patch("tools.automation_center.bridge.subprocess.run")
    def test_list_devices_keeps_serial_and_adb_state_visible(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0,
            "List of devices attached\nABC device product:oriole model:Pixel_6\nDEF offline\n",
            "",
        )

        devices = self.bridge.list_devices()

        self.assertEqual(
            run.call_args.kwargs["creationflags"],
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertEqual(devices, [
            {"serial": "ABC", "state": "device", "transport": "USB", "model": "Pixel 6", "product": "oriole"},
            {"serial": "DEF", "state": "offline", "transport": "USB", "model": "", "product": ""},
        ])


class AutomationBridgeSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.directory.name)
        from tools.automation_center.bridge import AutomationBridge

        self.bridge = AutomationBridge(self.root, transport=FakeAdbTransport())
        self.saved = self.bridge.save_plan({
            "name": "morning",
            "serial": "ABC",
            "schedule": {"time": "09:00", "days": ["daily"]},
            "steps": [{"action": "wake"}],
        })

    def tearDown(self):
        self.directory.cleanup()

    @mock.patch("tools.automation_center.bridge.subprocess.run")
    def test_set_schedule_uses_validated_plan_and_fixed_scheduler_arguments(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        result = self.bridge.set_schedule(self.saved["path"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["task_name"], "scrcpy-many:morning")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["schtasks.exe", "/Create", "/F", "/TN"])
        self.assertIn("/SC", command)
        self.assertEqual(command[command.index("/ST") + 1], "09:00")

    @mock.patch("tools.automation_center.bridge.subprocess.run")
    def test_remove_schedule_uses_the_namespaced_task_name(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        result = self.bridge.remove_schedule("morning")

        self.assertTrue(result["ok"])
        self.assertEqual(run.call_args.args[0], [
            "schtasks.exe", "/Delete", "/TN", "scrcpy-many:morning", "/F",
        ])


class AutomationBridgeRecordingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.directory.name)
        from tools.automation_center.bridge import AutomationBridge

        self.transport = FakeAdbTransport()
        self.bridge = AutomationBridge(self.root, transport=self.transport)

    def tearDown(self):
        self.directory.cleanup()

    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_start_recording_launches_packaged_scrcpy_for_one_ready_serial(self, popen):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process

        result = self.bridge.start_recording("ABC")

        self.assertTrue(result["ok"])
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], [str(self.root.resolve() / "bin" / "scrcpy-core.exe"), "--serial", "ABC", "--window-title"])
        self.assertEqual(command[4], "scrcpy automation - ABC")
        self.assertEqual(command[5], "--record-actions")
        self.assertTrue(command[6].endswith(".json"))
        self.assertEqual(popen.call_args.kwargs["cwd"], self.root.resolve())
        self.assertEqual(popen.call_args.kwargs["creationflags"], getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertTrue(str(popen.call_args.kwargs["env"]["PATH"]).startswith(
            str(self.root.resolve() / "lib")
        ))

    @mock.patch("tools.automation_center.bridge._request_window_close", return_value=True, create=True)
    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_stop_recording_requests_a_graceful_window_close_before_reading_plan(self, popen, close_window):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process

        started = self.bridge.start_recording("ABC")
        recording_path = pathlib.Path(started["path"])
        recording_path.write_text(json.dumps({
            "name": "recorded-actions",
            "serial": "ABC",
            "steps": [{"action": "swipe", "x1": 1, "y1": 2, "x2": 1, "y2": 20, "duration_ms": 300}],
        }), encoding="utf-8")

        result = self.bridge.stop_recording()

        self.assertTrue(result["ok"])
        close_window.assert_called_once_with("scrcpy automation - ABC")
        process.terminate.assert_not_called()

    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_stop_recording_falls_back_to_terminate_if_window_close_fails(self, popen):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process

        started = self.bridge.start_recording("ABC")
        pathlib.Path(started["path"]).write_text(json.dumps({
            "name": "recorded-actions",
            "serial": "ABC",
            "steps": [{"action": "tap", "x": 10, "y": 20}],
        }), encoding="utf-8")

        with mock.patch("tools.automation_center.bridge._request_window_close", return_value=False, create=True):
            result = self.bridge.stop_recording()

        self.assertTrue(result["ok"])
        process.terminate.assert_called_once_with()


    def test_start_recording_rejects_a_device_that_is_not_ready(self):
        transport = FakeAdbTransport([subprocess.CompletedProcess([], 0, "offline\n", "")])
        from tools.automation_center.bridge import AutomationBridge

        bridge = AutomationBridge(self.root, transport=transport)

        result = bridge.start_recording("ABC")

        self.assertEqual(result["code"], "device_not_ready")

    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_start_recording_rejects_a_second_owned_process(self, popen):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process

        self.bridge.start_recording("ABC")
        result = self.bridge.start_recording("ABC")

        self.assertEqual(result["code"], "recording_active")
        self.assertEqual(popen.call_count, 1)

    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_stop_recording_validates_and_stores_the_recorded_plan(self, popen):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process
        started = self.bridge.start_recording("ABC")
        recording_path = pathlib.Path(started["path"])
        recording_path.write_text(json.dumps({
            "name": "recorded-actions",
            "serial": "ABC",
            "steps": [{"action": "tap", "x": 10, "y": 20}],
        }), encoding="utf-8")

        result = self.bridge.stop_recording()

        self.assertTrue(result["ok"])
        self.assertTrue(pathlib.Path(result["path"]).is_file())
        self.assertEqual(self.bridge.list_plans()[0]["serial"], "ABC")
        self.assertEqual(result["document"]["schedule"], {
            "time": "21:00", "days": ["daily"],
        })
        process.terminate.assert_called_once_with()

    @mock.patch("tools.automation_center.bridge.subprocess.Popen")
    def test_stop_recording_rejects_malformed_output(self, popen):
        process = mock.Mock()
        process.poll.return_value = None
        popen.return_value = process
        started = self.bridge.start_recording("ABC")
        pathlib.Path(started["path"]).write_text("not-json", encoding="utf-8")

        result = self.bridge.stop_recording()

        self.assertEqual(result["code"], "recording_invalid")
        self.assertFalse(pathlib.Path(started["path"]).exists())


class AutomationCenterAppTests(unittest.TestCase):
    def test_script_entrypoint_resolves_project_package_before_optional_webview(self):
        script = pathlib.Path(__file__).parents[1] / "tools" / "automation_center" / "app.py"
        completed = subprocess.run(
            [sys.executable, str(script), "unexpected"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotIn("No module named 'tools'", completed.stderr)


if __name__ == "__main__":
    unittest.main()
