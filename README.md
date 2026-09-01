# scrcpy-many

这是基于 scrcpy 4.1 的 Windows 二次开发版本，目标是让多台 Android 手机
可以更方便地被发现、选择和同时操控。

本项目不是 scrcpy 官方发行版。使用、反馈和版本信息以本仓库为准；scrcpy
本体的原始实现和许可证归上游项目所有。

## 原仓库

- 上游项目：[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)
- 本项目基于上游 `v4.1` 版本开发
- 上游许可证：Apache License 2.0

## 本项目的二开内容

### Windows 多设备选择器

启动 Windows 版 `scrcpy.exe` 时，程序会先读取 ADB 设备列表：

- 只有一台可用设备时，直接启动该设备
- 有多台可用设备时，弹出图形化选择窗口
- 支持单选或多选设备
- 多选时会为每台手机分别启动一个 scrcpy 窗口
- 可以看到序列号、型号、连接方式和 ADB 状态
- `unauthorized`、`offline` 等设备仍会显示，但不能被启动
- 双击设备行可以直接启动
- 取消选择时不会进入 scrcpy 连接流程

### 选择器 UI 重做

Windows 选择窗口使用原生 Unicode 控件重新设计：

- 使用表格列对齐设备信息，不再依赖空格拼接文本
- 增加标题、说明、选择数量和可启动数量提示
- 支持窗口缩放，列表和按钮会自适应布局
- 不可用设备使用灰色状态显示
- 支持中文型号和特殊序列号，避免 ANSI 乱码

### Windows 整理版发布目录

新增启动器和打包脚本，将运行文件分目录存放，避免所有 DLL 堆在根目录：

```text
scrcpy-release/
├─ scrcpy.exe                 # 用户启动的入口
├─ scrcpy-automation.exe      # 图形化自动化中心
├─ bin/
│  ├─ scrcpy-core.exe         # 实际 scrcpy 客户端
│  └─ scrcpy-server
├─ lib/
│  └─ *.dll                   # SDL、FFmpeg、MinGW、libusb 等运行库
└─ platform-tools/
   ├─ adb.exe
   ├─ AdbWinApi.dll
   └─ AdbWinUsbApi.dll
```

自动化中心会在根目录下另外使用两个用户数据目录：

```text
plans/                         # 保存的 JSON 自动化计划
logs/automation/               # 每次执行的日志、截图与结果
```

入口启动器会自动设置 DLL 和 ADB 搜索路径，用户只需要双击根目录的
`scrcpy.exe`。

### 命令行兼容

显式指定设备时会跳过图形选择器：

```powershell
scrcpy.exe --serial 设备序列号
scrcpy.exe --select-usb
scrcpy.exe --select-tcpip
scrcpy.exe --tcpip=192.168.1.8:5555
```

脚本或自动化场景可以使用：

```powershell
scrcpy.exe --no-device-picker
```

还可以在操控窗口时录制可回放的动作计划：

```powershell
scrcpy.exe --serial 设备序列号 --record-actions evening-actions.json
```

录制功能默认关闭，只记录触控和键盘事件，并自动插入等待时间；剪贴板、
文件拖放、手柄以及锁屏凭据不会写入计划。录制出的 JSON 可交给
`tools/scrcpy_automation.py run` 或 Windows 定时任务执行。

### 图形化自动化中心

发布目录中的 `scrcpy-automation.exe` 是本项目新增的本地 HTML/CSS
图形界面，用于创建单台设备的定时操作计划：

- 左侧显示所有 ADB 设备及状态；必须手动选择一台 `device` 状态的手机
- 可以新建、打开、编辑、保存动作步骤，并用“试运行”检查步骤顺序
- 可以启动 scrcpy 录制窗口，将点击、滑动和可回放按键保存为计划
- 可以立即执行、启用每日定时或禁用定时，并查看每次运行日志
- 页面仅能调用固定的本地 bridge 方法，不能传入任意 shell 命令或程序路径

每个计划都保存明确的设备序列号。连接或移除其它手机不会改变计划的目标。
录制和执行都要求该手机已完成 USB 调试授权。工具只能唤醒屏幕和关闭非安全
锁屏；不会保存或绕过 PIN、图案、指纹、人脸等安全解锁方式。

Linux 和 macOS 继续使用上游的标准命令行设备选择行为。

## 快速使用

1. 在手机的开发者选项中打开 USB 调试。
2. 确认电脑已经安装手机对应的 ADB 驱动。
3. 将手机通过 USB 连接，或者先通过 ADB 配置 TCP/IP 连接。
4. 双击：

   ```text
   D:\scrcpy-release-organized\scrcpy.exe
   ```

5. 连接多台手机时，在选择器中选中需要操控的设备（可使用 Ctrl/Shift 多选），
   然后点击 `Start selected`。

要创建每日自动化计划，双击同目录的 `scrcpy-automation.exe`。在界面中选择一台
状态为“可用”的设备，编辑步骤并先点击“保存计划”与“试运行”；确认无误后再使用
“立即运行”或“启用定时”。

也可以在终端中运行：

```powershell
cd D:\scrcpy-release-organized
.\scrcpy.exe
```

## 从源码构建 Windows 版本

项目使用 Meson 和 Ninja。构建完成后，可以使用打包脚本生成整理版目录：

```powershell
meson setup D:\scrcpy-build-release `
    -Dbuildtype=release `
    -Dportable=true `
    -Dprebuilt_server=D:\scrcpy-build-tools\scrcpy-server-v4.1 `
    -Dv4l2=false `
    -Dusb=true

ninja -C D:\scrcpy-build-release

.\tools\package_windows.ps1 `
    -BuildDir D:\scrcpy-build-release `
    -RuntimeDir D:\scrcpy-release `
    -OutputDir D:\scrcpy-release-organized `
    -AutomationExe D:\scrcpy-automation.exe
```

使用 `tools/build_portable_release.ps1` 可以先构建 `scrcpy-automation.exe`，再生成
一个完整的便携目录。Node、Python、PyInstaller 和中间编译文件都只放在临时目录，
最终只保留显式指定的 `-OutputDir`。

打包脚本会检查根目录没有 DLL，并确认 `bin`、`lib` 和
`platform-tools` 中的文件齐全。对应检查脚本为
`tools/test_windows_package.ps1`。

## 相关文档

- [Windows 使用说明](doc/windows.md)
- [Windows 打包脚本说明](tools/README.md)
- [定时设备自动化与 JSON 动作计划](tools/README.md#scheduled-device-automation)
- [上游 scrcpy 文档](https://github.com/Genymobile/scrcpy/tree/master/doc)

## 免责声明

本项目只是对上游 scrcpy 的二次开发和重新构建，不代表 Genymobile 官方立场。
遇到 scrcpy 核心功能问题时，请先对照上游仓库和文档确认问题是否存在于原版。

Copyright (C) 2018 Genymobile

Copyright (C) 2018-2026 Romain Vimont

二次开发部分遵循原项目 Apache License 2.0。
