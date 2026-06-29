"""
系统托盘模块
右键菜单：退出
"""

import threading
from PIL import Image, ImageDraw
import pystray


def _create_icon_image() -> Image.Image:
    """生成一个简单的截图图标（绿色相机轮廓）"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 相机外框
    draw.rounded_rectangle([4, 14, 60, 54], radius=6,
                            outline="#00FF41", width=4)
    # 镜头
    draw.ellipse([18, 20, 46, 48], outline="#00FF41", width=4)
    # 快门小圆
    draw.ellipse([28, 30, 36, 38], fill="#00FF41")
    # 取景器
    draw.rectangle([44, 16, 56, 22], fill="#00FF41")

    return img


class ScreenshotTray:
    def __init__(self, on_quit=None):
        self.on_quit = on_quit
        self._icon = None

    def run(self):
        icon_img = _create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("截图工具运行中", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Alt+Z  区域截图", None, enabled=False),
            pystray.MenuItem("Alt+X  全屏截图", None, enabled=False),
            pystray.MenuItem("Alt+C  窗口截图", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._quit),
        )
        self._icon = pystray.Icon(
            "ScreenshotTool",
            icon=icon_img,
            title="截图工具\nAlt+Z/X/C",
            menu=menu
        )
        self._icon.run()

    def _quit(self, icon, item):
        icon.stop()
        if self.on_quit:
            self.on_quit()
