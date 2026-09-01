"""Windows desktop host for the bundled scrcpy automation center."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

# A direct script invocation starts with tools/automation_center on sys.path;
# add the project root before importing the shared bridge modules.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.automation_center.bridge import AutomationBridge


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["run"] and len(arguments) == 2:
        from tools.scrcpy_automation import AdbTransport, load_plan, run_plan

        plan = load_plan(Path(arguments[1]))
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = portable_root() / "logs" / "automation" / plan.name / timestamp
        result = run_plan(plan, AdbTransport(portable_root() / "platform-tools" / "adb.exe"), run_dir)
        return 0 if result.success else 1
    if arguments:
        print("Usage: scrcpy-automation.exe [run PLAN]", file=sys.stderr)
        return 2
    try:
        import webview
    except ImportError as exc:
        print(f"pywebview is required: {exc}", file=sys.stderr)
        return 1

    root = portable_root()
    bridge = AutomationBridge(root)
    ui_path = root / "automation-ui" / "dist" / "index.html"
    if not ui_path.is_file():
        bundled = Path(getattr(sys, "_MEIPASS", root)) / "ui" / "index.html"
        ui_path = bundled
    if not ui_path.is_file():
        print(f"Missing automation UI: {ui_path}", file=sys.stderr)
        return 1

    webview.create_window(
        "scrcpy 自动化中心",
        ui_path.as_uri(),
        js_api=bridge,
        width=1440,
        height=900,
        min_size=(1024, 640),
        resizable=True,
    )
    webview.start(gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
