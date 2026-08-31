import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "tools" / "scrcpy_launcher.py"
SPEC = importlib.util.spec_from_file_location("scrcpy_launcher", MODULE_PATH)
launcher = importlib.util.module_from_spec(SPEC)
sys.modules["scrcpy_launcher"] = launcher
SPEC.loader.exec_module(launcher)


class ParseAdbDevicesTests(unittest.TestCase):
    def test_parses_ready_devices_and_ignores_header_and_blank_lines(self):
        output = """List of devices attached
ABC123\tdevice usb:1-2 product:foo model:Pixel_7 device:panther transport_id:1
192.168.1.8:5555\tdevice product:bar model:Mi_11 device:venus transport_id:2

"""

        devices = launcher.parse_adb_devices(output)

        self.assertEqual(
            [device.serial for device in devices],
            ["ABC123", "192.168.1.8:5555"],
        )
        self.assertEqual(devices[0].transport, "USB")
        self.assertEqual(devices[0].model, "Pixel 7")
        self.assertEqual(devices[1].transport, "TCP/IP")

    def test_keeps_unauthorized_devices_visible_for_user_feedback(self):
        output = """List of devices attached
ABC123\tunauthorized usb:1-2 model:Pixel_7
"""

        devices = launcher.parse_adb_devices(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].state, "unauthorized")


class CommandTests(unittest.TestCase):
    def test_builds_one_explicit_serial_command(self):
        command = launcher.build_scrcpy_command(
            "C:/scrcpy/scrcpy.exe", "ABC123", ["--max-size=1024"]
        )

        self.assertEqual(
            command,
            ["C:/scrcpy/scrcpy.exe", "--serial", "ABC123", "--max-size=1024"],
        )


if __name__ == "__main__":
    unittest.main()
