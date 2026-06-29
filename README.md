# ScreenshotTool 截图工具

Windows 全局快捷键截图工具，系统托盘驻留，开机自启。

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt+Z` | **区域截图**：全屏蒙版，拖选区域，底部工具栏选择操作 |
| `Alt+X` | **全屏截图**：直接复制到剪贴板 |
| `Alt+C` | **窗口截图**：截取当前焦点窗口，复制到剪贴板 |

区域截图工具栏：
- **✓**（绿）复制到剪贴板
- **↓**（蓝）弹出文件管理器保存为 PNG/JPG
- **✕**（红）取消

## 使用方式

### 直接下载（推荐）

前往 [Releases](../../releases) 页面下载最新的 `ScreenshotTool.exe`，双击运行即可。

> 首次运行会弹出 UAC 权限请求（全局快捷键监听需要管理员权限），点击「是」即可。

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 自行编译

```bash
pip install pyinstaller
pyinstaller ScreenshotTool.spec
# 输出：dist/ScreenshotTool.exe
```

## 特性

- **开机自启**：首次启动自动写入注册表 `HKCU\...\Run`
- **系统托盘**：右键图标可退出程序
- **无黑窗口**：后台静默运行
- **区域截图**：蒙版半透明，选框显示实时尺寸（如 `421 × 390`）
- **窗口截图**：使用 `PrintWindow` API，支持部分遮挡的窗口

## 系统要求

- Windows 10 / 11
- 无需安装 Python（.exe 已打包全部依赖）
