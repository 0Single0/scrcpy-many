"""Regression checks for the C-side action recorder coordinate boundary.

The recorder writes plans that are replayed through ``adb shell input``.  It
must therefore receive device-frame coordinates, never SDL window coordinates.
"""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_MANAGER = PROJECT_ROOT / "app" / "src" / "input_manager.c"


class RecordingInputCoordinateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = INPUT_MANAGER.read_text(encoding="utf-8")

    def test_recorder_uses_the_same_device_position_as_input_dispatch(self) -> None:
        recorder = self.source.split(
            "sc_input_manager_record_touch", maxsplit=1
        )[1].split("static void\nsc_input_manager_process_mouse_motion", maxsplit=1)[0]
        self.assertIn(
            "sc_input_manager_get_position(im, x, y)", recorder
        )
        self.assertIn(
            "position.point.x, position.point.y,\n"
            "        position.screen_size.width, position.screen_size.height",
            recorder,
        )

if __name__ == "__main__":
    unittest.main()
