"""
区域截图模块
- 全屏半透明黑色蒙版
- 拖选绿色边框 + 左上角实时尺寸
- 松开后底部工具栏：✓ 复制 / ↓ 保存 / ✕ 取消
"""

import tkinter as tk
from tkinter import filedialog
import threading
import datetime
import io

from PIL import Image, ImageGrab
import win32clipboard
import win32con


def _copy_image_to_clipboard(img: Image.Image):
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()


class RegionSelector:
    def __init__(self, on_done=None):
        self._on_done = on_done

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        root = tk.Tk()
        _Overlay(root, on_done=self._on_done)
        root.mainloop()


class _Overlay:
    BORDER   = "#00FF41"
    BW       = 2
    TB_H     = 50
    BTN_W    = 46
    BTN_H    = 36
    BTN_GAP  = 6

    def __init__(self, root: tk.Tk, on_done=None):
        self.root    = root
        self.on_done = on_done

        # 截图要在蒙版出现之前
        self.bg = ImageGrab.grab(all_screens=False)
        self.sw, self.sh = self.bg.size

        self.x0 = self.y0 = self.x1 = self.y1 = 0
        self.dragging      = False
        self.toolbar_shown = False
        self.sel           = None

        self._setup_window()
        self._bind()

    def _setup_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-fullscreen", True)
        r.attributes("-alpha", 0.45)
        r.attributes("-topmost", True)
        r.configure(bg="black")
        r.config(cursor="crosshair")

        self.cv = tk.Canvas(r, bg="black", highlightthickness=0,
                            width=self.sw, height=self.sh)
        self.cv.pack(fill=tk.BOTH, expand=True)

        self.rect_id = self.cv.create_rectangle(0,0,0,0,
            outline=self.BORDER, width=self.BW, state=tk.HIDDEN)
        self.info_id = self.cv.create_text(0,0, text="", anchor=tk.SW,
            fill="#ffffff", font=("Consolas", 11, "bold"), state=tk.HIDDEN)

    def _bind(self):
        c = self.cv
        c.bind("<ButtonPress-1>",   self._press)
        c.bind("<B1-Motion>",       self._drag)
        c.bind("<ButtonRelease-1>", self._release)
        self.root.bind("<Escape>",  lambda e: self._close())

    def _press(self, e):
        if self.toolbar_shown:
            return
        self.x0, self.y0 = e.x, e.y
        self.dragging = True
        self.cv.itemconfig(self.rect_id, state=tk.NORMAL)
        self.cv.itemconfig(self.info_id, state=tk.NORMAL)

    def _drag(self, e):
        if not self.dragging:
            return
        self.x1, self.y1 = e.x, e.y
        x0 = min(self.x0, self.x1); y0 = min(self.y0, self.y1)
        x1 = max(self.x0, self.x1); y1 = max(self.y0, self.y1)
        self.cv.coords(self.rect_id, x0, y0, x1, y1)
        lx = x0
        ly = max(y0 - 5, 14)
        self.cv.coords(self.info_id, lx, ly)
        self.cv.itemconfig(self.info_id, text=f"{x1-x0} × {y1-y0}")

    def _release(self, e):
        if not self.dragging:
            return
        self.dragging = False
        self.x1, self.y1 = e.x, e.y
        x0 = min(self.x0, self.x1); y0 = min(self.y0, self.y1)
        x1 = max(self.x0, self.x1); y1 = max(self.y0, self.y1)
        if x1 - x0 < 5 or y1 - y0 < 5:
            self._close()
            return
        self.sel = (x0, y0, x1, y1)
        self._show_toolbar(x0, y0, x1, y1)

    # -------- 工具栏 --------

    def _show_toolbar(self, x0, y0, x1, y1):
        self.toolbar_shown = True
        tw = self.BTN_W * 3 + self.BTN_GAP * 4
        tx = x0 + (x1 - x0 - tw) // 2
        ty = y1 + 8
        if ty + self.TB_H > self.sh:
            ty = y0 - self.TB_H - 8
        tx = max(2, min(tx, self.sw - tw - 2))

        # 背景
        self.cv.create_rectangle(tx - 2, ty - 2, tx + tw + 2, ty + self.TB_H + 2,
                                  fill="#1e1e1e", outline="#555", width=1)

        bx = tx + self.BTN_GAP
        by = ty + (self.TB_H - self.BTN_H) // 2

        self._btn(bx,                          by, "✓", "#27ae60", self._do_copy)
        self._btn(bx + self.BTN_W + self.BTN_GAP, by, "↓", "#2980b9", self._do_save)
        self._btn(bx + (self.BTN_W + self.BTN_GAP)*2, by, "✕", "#c0392b", self._close)

    def _btn(self, x, y, symbol, color, cmd):
        w, h = self.BTN_W, self.BTN_H
        r_id = self.cv.create_rectangle(x, y, x+w, y+h,
                                         fill=color, outline="", width=0)
        t_id = self.cv.create_text(x + w//2, y + h//2, text=symbol,
                                    fill="white", font=("Segoe UI", 15, "bold"))
        light = self._lighten(color)

        def click(e): cmd()
        def enter(e): self.cv.itemconfig(r_id, fill=light)
        def leave(e): self.cv.itemconfig(r_id, fill=color)

        for item in (r_id, t_id):
            self.cv.tag_bind(item, "<ButtonPress-1>", click)
            self.cv.tag_bind(item, "<Enter>", enter)
            self.cv.tag_bind(item, "<Leave>", leave)

    @staticmethod
    def _lighten(h):
        r, g, b = int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)
        return f"#{min(255,r+40):02x}{min(255,g+40):02x}{min(255,b+40):02x}"

    # -------- 动作 --------

    def _crop(self):
        return self.bg.crop(self.sel)

    def _do_copy(self):
        img = self._crop()
        _copy_image_to_clipboard(img)
        self._close()

    def _do_save(self):
        img = self._crop()
        self._close()   # 先关蒙版

        def _dialog():
            tmp = tk.Tk()
            tmp.withdraw()
            name = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
            path = filedialog.asksaveasfilename(
                initialfile=name,
                defaultextension=".png",
                filetypes=[("PNG 图片","*.png"),("JPEG 图片","*.jpg"),("所有文件","*.*")],
                title="保存截图"
            )
            tmp.destroy()
            if path:
                img.save(path)

        threading.Thread(target=_dialog, daemon=True).start()

    def _close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        if self.on_done:
            self.on_done()
