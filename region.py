"""
区域截图模块
- 全屏半透明黑色蒙版
- 鼠标拖选绿色边框 + 左上角尺寸提示
- 松开后底部工具栏：✓（复制）/ ↓（保存）/ ✕（取消）
"""

import tkinter as tk
from tkinter import filedialog
import threading
from PIL import Image, ImageGrab, ImageTk
import win32clipboard
import win32con
import io
import os
import datetime


def copy_image_to_clipboard(img: Image.Image):
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()


class RegionSelector:
    def __init__(self):
        self.active = False
        self._thread = None

    def start(self):
        self.active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        root = tk.Tk()
        _RegionOverlay(root, on_done=self._done)
        root.mainloop()

    def _done(self):
        self.active = False


class _RegionOverlay:
    # UI 常量
    OVERLAY_ALPHA   = 0.45      # 蒙版透明度
    BORDER_COLOR    = "#00FF41" # 绿色边框
    BORDER_WIDTH    = 2
    TOOLBAR_H       = 48        # 工具栏高度
    TOOLBAR_W       = 144       # 工具栏宽度（3个按钮）
    BTN_SIZE        = 40        # 按钮尺寸
    BTN_GAP         = 8
    LABEL_BG        = "#1a1a1a"
    LABEL_FG        = "#ffffff"
    FONT_SIZE_INFO  = 11

    def __init__(self, root: tk.Tk, on_done=None):
        self.root = root
        self.on_done = on_done

        # 先截全屏（蒙版之前）
        self.screenshot = ImageGrab.grab()
        self.sw = self.screenshot.width
        self.sh = self.screenshot.height

        # 拖选状态
        self.x0 = self.y0 = 0
        self.x1 = self.y1 = 0
        self.dragging = False
        self.toolbar_shown = False

        self._build_overlay()
        self._bind_events()

    # ------------------------------------------------------------------ #
    #  构建全屏蒙版窗口
    # ------------------------------------------------------------------ #
    def _build_overlay(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-fullscreen", True)
        r.attributes("-alpha", self.OVERLAY_ALPHA)
        r.attributes("-topmost", True)
        r.configure(bg="black")
        r.config(cursor="crosshair")

        # Canvas 覆盖全屏
        self.canvas = tk.Canvas(r, bg="black", highlightthickness=0,
                                width=self.sw, height=self.sh)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 选框矩形（初始隐藏）
        self.rect_id = self.canvas.create_rectangle(
            0, 0, 0, 0,
            outline=self.BORDER_COLOR,
            width=self.BORDER_WIDTH,
            state=tk.HIDDEN
        )
        # 尺寸标签
        self.info_id = self.canvas.create_text(
            0, 0, text="", anchor=tk.SW,
            fill=self.LABEL_FG,
            font=("Consolas", self.FONT_SIZE_INFO, "bold"),
            state=tk.HIDDEN
        )

    # ------------------------------------------------------------------ #
    #  事件绑定
    # ------------------------------------------------------------------ #
    def _bind_events(self):
        c = self.canvas
        c.bind("<ButtonPress-1>",   self._on_press)
        c.bind("<B1-Motion>",       self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>",  lambda e: self._cancel())

    # ------------------------------------------------------------------ #
    #  鼠标事件
    # ------------------------------------------------------------------ #
    def _on_press(self, event):
        if self.toolbar_shown:
            return
        self.x0, self.y0 = event.x, event.y
        self.dragging = True
        self.canvas.itemconfig(self.rect_id, state=tk.NORMAL)
        self.canvas.itemconfig(self.info_id, state=tk.NORMAL)

    def _on_drag(self, event):
        if not self.dragging:
            return
        self.x1, self.y1 = event.x, event.y
        x0, y0 = min(self.x0, self.x1), min(self.y0, self.y1)
        x1, y1 = max(self.x0, self.x1), max(self.y0, self.y1)
        w, h = x1 - x0, y1 - y0

        self.canvas.coords(self.rect_id, x0, y0, x1, y1)

        # 尺寸标签跟随左上角
        lx = x0
        ly = max(y0 - 4, 14)
        self.canvas.coords(self.info_id, lx, ly)
        self.canvas.itemconfig(self.info_id, text=f"{w} × {h}")

    def _on_release(self, event):
        if not self.dragging:
            return
        self.dragging = False
        self.x1, self.y1 = event.x, event.y

        x0, y0 = min(self.x0, self.x1), min(self.y0, self.y1)
        x1, y1 = max(self.x0, self.x1), max(self.y0, self.y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            self._cancel()
            return

        self.sel = (x0, y0, x1, y1)
        self._show_toolbar(x0, y0, x1, y1)

    # ------------------------------------------------------------------ #
    #  工具栏
    # ------------------------------------------------------------------ #
    def _show_toolbar(self, x0, y0, x1, y1):
        self.toolbar_shown = True

        # 工具栏 x 居中于选框，y 在选框下方 8px
        tw = self.TOOLBAR_W
        th = self.TOOLBAR_H
        tx = x0 + (x1 - x0 - tw) // 2
        ty = y1 + 8

        # 防止超出屏幕底部
        if ty + th > self.sh:
            ty = y0 - th - 8

        tx = max(0, min(tx, self.sw - tw))

        # 工具栏背景
        self.tb_bg = self.canvas.create_rectangle(
            tx, ty, tx + tw, ty + th,
            fill="#202020", outline="#444444", width=1
        )

        bx = tx + self.BTN_GAP
        by_center = ty + th // 2

        # ✓ 复制按钮
        self._make_btn(bx, by_center, "✓", "#27ae60", self._action_copy)
        bx += self.BTN_SIZE + self.BTN_GAP

        # ↓ 保存按钮
        self._make_btn(bx, by_center, "↓", "#2980b9", self._action_save)
        bx += self.BTN_SIZE + self.BTN_GAP

        # ✕ 取消按钮
        self._make_btn(bx, by_center, "✕", "#c0392b", self._cancel)

    def _make_btn(self, cx, cy, symbol, color, command):
        s = self.BTN_SIZE
        x0, y0 = cx, cy - s // 2
        x1, y1 = cx + s, cy + s // 2

        btn_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            fill=color, outline="", width=0
        )
        txt_id = self.canvas.create_text(
            (x0 + x1) // 2, (y0 + y1) // 2,
            text=symbol, fill="white",
            font=("Segoe UI", 16, "bold")
        )

        def on_click(e):
            command()

        def on_enter(e):
            self.canvas.itemconfig(btn_id, fill=self._lighten(color))

        def on_leave(e):
            self.canvas.itemconfig(btn_id, fill=color)

        for item in (btn_id, txt_id):
            self.canvas.tag_bind(item, "<ButtonPress-1>", on_click)
            self.canvas.tag_bind(item, "<Enter>", on_enter)
            self.canvas.tag_bind(item, "<Leave>", on_leave)

    @staticmethod
    def _lighten(hex_color: str) -> str:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ------------------------------------------------------------------ #
    #  动作
    # ------------------------------------------------------------------ #
    def _crop(self) -> Image.Image:
        x0, y0, x1, y1 = self.sel
        return self.screenshot.crop((x0, y0, x1, y1))

    def _action_copy(self):
        img = self._crop()
        copy_image_to_clipboard(img)
        self._close()

    def _action_save(self):
        img = self._crop()
        # 先关闭蒙版，再弹文件对话框（否则对话框被蒙版盖住）
        self._close()

        def _save_dialog():
            default_name = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
            path = filedialog.asksaveasfilename(
                initialfile=default_name,
                defaultextension=".png",
                filetypes=[("PNG 图片", "*.png"), ("JPEG 图片", "*.jpg"), ("所有文件", "*.*")],
                title="保存截图"
            )
            if path:
                img.save(path)

        # 单独的 Tk 根用于文件对话框
        dialog_root = tk.Tk()
        dialog_root.withdraw()
        _save_dialog()
        dialog_root.destroy()

    def _cancel(self):
        self._close()

    def _close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        if self.on_done:
            self.on_done()
