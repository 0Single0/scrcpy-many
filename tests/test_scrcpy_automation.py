import json
import pathlib
import tempfile
import unittest

from tools.scrcpy_automation import (
    PlanValidationError,
    load_plan,
    validate_plan,
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
