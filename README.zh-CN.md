# scrcpy-many 中文说明

[English README](README.md)

这是基于 [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) 的 Windows 二次开发版本。保留 scrcpy 原有的设备控制能力，并增加多设备启动器、整理版便携目录、动作录制和图形化自动化中心。

## 整体改动

- 启动 `scrcpy.exe` 时自动读取 ADB 设备；多台设备可在图形界面中单选或多选，分别打开 scrcpy 窗口。
- 显示设备序列号、型号、连接方式和 ADB 状态；`unauthorized`、`offline` 等不可用设备会保留显示但不能启动。
- Windows 发布目录按 `bin`、`lib`、`platform-tools` 分类存放运行文件和 DLL，根目录不再堆放大量 DLL。
- 支持 `--serial`、`--select-usb`、`--select-tcpip`、`--tcpip=...` 和 `--no-device-picker` 等命令行用法。
- 支持使用 `--record-actions` 录制单台手机的点击、滑动、按键和动作间隔，坐标按设备空间保存；不会记录 PIN、图案、生物识别等安全凭据。
- 新增 `scrcpy-automation.exe` 图形化自动化中心，可创建、编辑、删除、拖拽排序和保存 JSON 计划。
- 支持唤醒屏幕、等待、打开应用、点击坐标和滑动等常用动作，也能导入录制出的计划。
- 支持试运行、立即执行、Windows 每日定时、最近运行记录和日志打开。
- 执行在后台线程运行，运行中可点击“终止执行”；终止会打断等待并阻止后续动作继续发送。
- 自动化中心支持中文/English 切换；启动时会自动重试计划库加载，避免 pywebview 桥接尚未就绪导致计划暂时不显示。

## 目录结构

```text
scrcpy-many-portable/
├─ scrcpy.exe
├─ scrcpy-automation.exe
├─ bin/
├─ lib/
├─ platform-tools/
├─ plans/
└─ logs/automation/
```

## 使用方式

1. 在手机上打开 USB 调试并授权电脑。
2. 双击便携目录中的 `scrcpy.exe`，选择要操控的设备。
3. 双击 `scrcpy-automation.exe`，选择设备并创建自动化计划。
4. 保存计划后先使用“试运行”，确认无误后再立即执行或启用每日定时。

## 构建和上游地址

核心项目使用 Meson 和 Ninja；Windows 打包脚本位于 `tools/`。自动化中心可使用 `tools/build_automation_center.ps1` 构建，便携目录可使用 `tools/test_windows_package.ps1` 检查。

上游仓库：[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)

上游许可证：[Apache License 2.0](LICENSE)
