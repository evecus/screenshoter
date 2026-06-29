"""
Screenshot Tool - Main Entry Point
快捷键：
  Alt+Z  区域截图（蒙版拖选 → 工具栏选择）
  Alt+X  全屏截图（直接复制到剪贴板）
  Alt+C  当前窗口截图（直接复制到剪贴板）
"""

import sys
import threading
import winreg
import os

import keyboard
from PIL import Image, ImageGrab
import win32gui
import win32con
import win32ui
import win32clipboard

from tray import ScreenshotTray
from region import RegionSelector


APP_NAME = "ScreenshotTool"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_autostart(enable: bool = True):
    """写/删注册表实现开机自启"""
    exe_path = sys.executable if not getattr(sys, "frozen", False) else sys.executable
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[autostart] 注册表操作失败: {e}")


def copy_image_to_clipboard(img: Image.Image):
    """将 PIL Image 复制到 Windows 剪贴板"""
    import io
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # 去掉 BMP 文件头
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()


def capture_fullscreen() -> Image.Image:
    """全屏截图"""
    return ImageGrab.grab()


def capture_active_window() -> Image.Image:
    """截取键盘焦点窗口"""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return capture_fullscreen()

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    # 使用 PrintWindow 截取（支持部分被遮挡的窗口）
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bmp)

    result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    bmp_info = bmp.GetInfo()
    bmp_bits = bmp.GetBitmapBits(True)

    img = Image.frombuffer(
        "RGB",
        (bmp_info["bmWidth"], bmp_info["bmHeight"]),
        bmp_bits, "raw", "BGRX", 0, 1
    )

    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    win32ui.DeleteObject(bmp.GetHandle())

    if result != 1:
        # PrintWindow 失败，退回到 BitBlt 方案
        img = ImageGrab.grab(bbox=(left, top, right, bottom))

    return img


class ScreenshotApp:
    def __init__(self):
        self.selector = None
        self._lock = threading.Lock()

    def on_region(self):
        """Alt+Z：区域截图"""
        with self._lock:
            if self.selector and self.selector.active:
                return
            self.selector = RegionSelector()
            self.selector.start()

    def on_fullscreen(self):
        """Alt+X：全屏截图 → 剪贴板"""
        try:
            img = capture_fullscreen()
            copy_image_to_clipboard(img)
            print("[fullscreen] 已复制到剪贴板")
        except Exception as e:
            print(f"[fullscreen] 失败: {e}")

    def on_window(self):
        """Alt+C：当前窗口截图 → 剪贴板"""
        try:
            img = capture_active_window()
            copy_image_to_clipboard(img)
            print("[window] 已复制到剪贴板")
        except Exception as e:
            print(f"[window] 失败: {e}")

    def run(self):
        set_autostart(True)

        # 注册全局快捷键（suppress=True 阻止原始按键透传）
        keyboard.add_hotkey("alt+z", self.on_region, suppress=True)
        keyboard.add_hotkey("alt+x", self.on_fullscreen, suppress=True)
        keyboard.add_hotkey("alt+c", self.on_window, suppress=True)

        print("[main] 截图工具已启动")
        print("  Alt+Z  区域截图")
        print("  Alt+X  全屏截图")
        print("  Alt+C  窗口截图")

        # 启动系统托盘（阻塞主线程）
        tray = ScreenshotTray(on_quit=self.quit)
        tray.run()

    def quit(self):
        keyboard.unhook_all_hotkeys()
        sys.exit(0)


if __name__ == "__main__":
    app = ScreenshotApp()
    app.run()
