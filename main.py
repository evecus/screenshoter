"""
Screenshot Tool - Main Entry Point
使用 Win32 RegisterHotKey API 注册全局热键（最可靠方式）
  Alt+Z  区域截图
  Alt+X  全屏截图 → 剪贴板 + 托盘提示
  Alt+C  当前窗口截图 → 剪贴板 + 托盘提示
"""

import sys
import threading
import winreg
import ctypes
import ctypes.wintypes
import io

from PIL import Image, ImageGrab
import win32gui
import win32con
import win32ui
import win32clipboard
import win32api

from region import RegionSelector

APP_NAME  = "ScreenshotTool"
REG_KEY   = r"Software\Microsoft\Windows\CurrentVersion\Run"

# 热键 ID（任意正整数，不与系统冲突即可）
HK_REGION     = 1   # Alt+Z
HK_FULLSCREEN = 2   # Alt+X
HK_WINDOW     = 3   # Alt+C

MOD_ALT    = 0x0001
MOD_NOREPEAT = 0x4000

user32 = ctypes.windll.user32


# ------------------------------------------------------------------ #
#  工具函数
# ------------------------------------------------------------------ #

def set_autostart(enable: bool = True):
    exe_path = sys.executable  # frozen 后 sys.executable 就是 .exe 路径
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
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()


def capture_fullscreen() -> Image.Image:
    return ImageGrab.grab(all_screens=False)


def capture_active_window() -> Image.Image:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return capture_fullscreen()

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width  = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return capture_fullscreen()

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc  = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp     = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bmp)

    ok = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

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

    if not ok:
        img = ImageGrab.grab(bbox=(left, top, right, bottom))

    return img


# ------------------------------------------------------------------ #
#  系统托盘（Shell_NotifyIcon 原生实现，支持气泡通知）
# ------------------------------------------------------------------ #

WM_TRAY   = win32con.WM_USER + 20
WM_HOTKEY = 0x0312
IDI_TRAY  = 1
NIM_ADD   = 0
NIM_MOD   = 1
NIM_DEL   = 2
NIF_MESSAGE = 0x01
NIF_ICON    = 0x02
NIF_TIP     = 0x04
NIF_INFO    = 0x10
NIIF_INFO   = 0x01
NIN_BALLOONUSERCLICK = 0x0405


class ScreenshotApp:
    def __init__(self):
        self._hwnd        = None
        self._hicon       = None
        self._selector_active = False
        self._lock        = threading.Lock()

    # -------- 热键动作 --------

    def on_region(self):
        with self._lock:
            if self._selector_active:
                return
            self._selector_active = True
        sel = RegionSelector(on_done=self._region_done)
        sel.start()

    def _region_done(self):
        with self._lock:
            self._selector_active = False

    def on_fullscreen(self):
        try:
            img = capture_fullscreen()
            copy_image_to_clipboard(img)
            w, h = img.size
            self._notify("全屏截图已复制", f"{w} × {h} · 已复制到剪贴板")
        except Exception as e:
            self._notify("截图失败", str(e))

    def on_window(self):
        try:
            img = capture_active_window()
            copy_image_to_clipboard(img)
            w, h = img.size
            self._notify("窗口截图已复制", f"{w} × {h} · 已复制到剪贴板")
        except Exception as e:
            self._notify("截图失败", str(e))

    # -------- 托盘气泡通知 --------

    def _notify(self, title: str, msg: str, timeout_ms: int = 2000):
        if not self._hwnd:
            return
        nid = self._make_nid()
        nid.uFlags     = NIF_INFO | NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.szInfo     = msg
        nid.szInfoTitle = title
        nid.uTimeout   = timeout_ms
        nid.dwInfoFlags = NIIF_INFO
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_MOD, ctypes.byref(nid))

    # -------- Win32 窗口消息循环 --------

    def run(self):
        set_autostart(True)
        self._create_window()
        self._add_tray_icon()
        self._register_hotkeys()
        print("[main] 截图工具已启动  Alt+Z/X/C")
        self._message_loop()

    def _create_window(self):
        """创建隐藏消息窗口，用于接收热键 / 托盘消息"""
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "ScreenshotToolMsgWnd"
        wc.lpfnWndProc   = self._wnd_proc
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass
        self._hwnd = win32gui.CreateWindow(
            wc.lpszClassName, "", 0,
            0, 0, 0, 0,
            0, 0, 0, None
        )

    def _add_tray_icon(self):
        # 用系统内置信息图标（IDI_INFORMATION = 32516）
        hicon = win32gui.LoadIcon(0, win32con.IDI_INFORMATION)
        self._hicon = hicon

        nid = self._make_nid()
        nid.uFlags   = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.hIcon    = hicon
        nid.szTip    = "截图工具\nAlt+Z 区域  Alt+X 全屏  Alt+C 窗口"
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _make_nid(self):
        """构造 NOTIFYICONDATA 结构"""
        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize",       ctypes.wintypes.DWORD),
                ("hWnd",         ctypes.wintypes.HWND),
                ("uID",          ctypes.wintypes.UINT),
                ("uFlags",       ctypes.wintypes.UINT),
                ("uCallbackMessage", ctypes.wintypes.UINT),
                ("hIcon",        ctypes.wintypes.HICON),
                ("szTip",        ctypes.c_wchar * 128),
                ("dwState",      ctypes.wintypes.DWORD),
                ("dwStateMask",  ctypes.wintypes.DWORD),
                ("szInfo",       ctypes.c_wchar * 256),
                ("uTimeout",     ctypes.wintypes.UINT),
                ("szInfoTitle",  ctypes.c_wchar * 64),
                ("dwInfoFlags",  ctypes.wintypes.DWORD),
            ]

        nid = NOTIFYICONDATA()
        nid.cbSize          = ctypes.sizeof(nid)
        nid.hWnd            = self._hwnd
        nid.uID             = IDI_TRAY
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon           = self._hicon or 0
        nid.szTip           = "截图工具"
        return nid

    def _register_hotkeys(self):
        flag = MOD_ALT | MOD_NOREPEAT
        # 0x5A = Z, 0x58 = X, 0x43 = C
        for hk_id, vk in [(HK_REGION, 0x5A), (HK_FULLSCREEN, 0x58), (HK_WINDOW, 0x43)]:
            ok = user32.RegisterHotKey(self._hwnd, hk_id, flag, vk)
            if not ok:
                print(f"[hotkey] 注册失败 id={hk_id}，错误码={ctypes.GetLastError()}")

    def _unregister_hotkeys(self):
        for hk_id in (HK_REGION, HK_FULLSCREEN, HK_WINDOW):
            user32.UnregisterHotKey(self._hwnd, hk_id)

    def _message_loop(self):
        msg = ctypes.wintypes.MSG()
        while True:
            ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_HOTKEY:
            if   wparam == HK_REGION:
                threading.Thread(target=self.on_region,     daemon=True).start()
            elif wparam == HK_FULLSCREEN:
                threading.Thread(target=self.on_fullscreen, daemon=True).start()
            elif wparam == HK_WINDOW:
                threading.Thread(target=self.on_window,     daemon=True).start()

        elif msg == WM_TRAY:
            # 右键菜单
            if lparam in (win32con.WM_RBUTTONUP, win32con.WM_LBUTTONUP):
                self._show_context_menu()

        elif msg == win32con.WM_DESTROY:
            self._cleanup()
            win32gui.PostQuitMessage(0)

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _show_context_menu(self):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED,
                            0, "截图工具  v1.0")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED,
                            0, "Alt+Z  区域截图")
        win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED,
                            0, "Alt+X  全屏截图")
        win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED,
                            0, "Alt+C  窗口截图")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 9, "退出")

        x, y = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        cmd = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
            x, y, 0, self._hwnd, None
        )
        win32gui.DestroyMenu(menu)
        if cmd == 9:
            win32gui.PostMessage(self._hwnd, win32con.WM_DESTROY, 0, 0)

    def _cleanup(self):
        self._unregister_hotkeys()
        nid = self._make_nid()
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_DEL, ctypes.byref(nid))


if __name__ == "__main__":
    app = ScreenshotApp()
    app.run()
