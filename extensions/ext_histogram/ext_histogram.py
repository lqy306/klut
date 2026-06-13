"""
ext_histogram.py — 实时直方图分析器
"""

import os, sys, math
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QComboBox, QApplication)

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_STRINGS = {
    "title":    {"zh": "直方图分析器", "en": "Histogram Analyzer"},
    "channel":  {"zh": "通道:", "en": "Channel:"},
    "rgb":      {"zh": "RGB 合并", "en": "RGB Combined"},
    "red":      {"zh": "红色 (R)", "en": "Red (R)"},
    "green":    {"zh": "绿色 (G)", "en": "Green (G)"},
    "blue":     {"zh": "蓝色 (B)", "en": "Blue (B)"},
    "luminance":{"zh": "亮度 (Y)", "en": "Luminance (Y)"},
    "hsv":      {"zh": "HSV 彩色", "en": "HSV Color"},
    "refresh":  {"zh": "刷新", "en": "Refresh"},
}

from lang import LANG, ext_tr as _ext_tr
def _S(key): return _ext_tr(_STRINGS, key)
def menu_id(): return "ext_histogram"
def menu_label():
    return {"zh": "直方图分析", "en": "Histogram"}.get(LANG.get(), "Histogram")
def launch(parent, images, luts, lut_paths, src_cs=0, lut_cs=0):
    HistogramDialog(parent, images).exec_()


class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hist = {"r": [0]*256, "g": [0]*256, "b": [0]*256,
                     "h": [0]*360, "s": [0]*256, "v": [0]*256}
        self.mode = "rgb"
        self.setMinimumSize(400, 240)

    def compute(self, img_path):
        if not HAS_PIL or not os.path.exists(img_path):
            return
        img = PILImage.open(img_path).convert("RGB")
        w, h = img.size
        # 缩放以加速
        if w * h > 500000:
            r = math.sqrt(500000 / (w * h))
            img = img.resize((int(w*r), int(h*r)))
        px = img.load()
        w, h = img.size
        # 重置
        for ch in [self.hist["r"], self.hist["g"], self.hist["b"], self.hist["s"], self.hist["v"]]:
            for i in range(len(ch)): ch[i] = 0
        for i in range(360): self.hist["h"][i] = 0
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                self.hist["r"][r] += 1; self.hist["g"][g] += 1; self.hist["b"][b] += 1
                mx, mn = max(r,g,b), min(r,g,b)
                v = mx
                s = ((mx-mn)*255//mx) if mx else 0
                self.hist["s"][s] += 1; self.hist["v"][v] += 1
                hue = 0
                if mx != mn:
                    if mx == r: hue = int(60 * ((g-b)/(mx-mn)))
                    elif mx == g: hue = int(60 * (2+(b-r)/(mx-mn)))
                    else: hue = int(60 * (4+(r-g)/(mx-mn)))
                if hue < 0: hue += 360
                if hue >= 360: hue = 359
                self.hist["h"][hue] += 1

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#0d0d18"))
        p.setPen(QColor("#333"))
        p.drawRect(0, 0, w-1, h-1)
        # 网格
        p.setPen(QColor("#1a1a2e"))
        for i in range(1, 5):
            y = h - i * (h-10) // 5
            p.drawLine(5, y, w-5, y)

        channels = []
        if self.mode == "rgb":
            channels = [(self.hist["r"], QColor("#ff4444")),
                        (self.hist["g"], QColor("#44ff44")),
                        (self.hist["b"], QColor("#4444ff"))]
        elif self.mode == "r":
            channels = [(self.hist["r"], QColor("#ff4444"))]
        elif self.mode == "g":
            channels = [(self.hist["g"], QColor("#44ff44"))]
        elif self.mode == "b":
            channels = [(self.hist["b"], QColor("#4444ff"))]
        elif self.mode == "y":
            # 亮度
            y_hist = [0]*256
            for i in range(256):
                y_hist[i] = self.hist["v"][i]
            channels = [(y_hist, QColor("#ffffff"))]
        elif self.mode == "hsv":
            channels = [(self.hist["h"], QColor("#ffaa33"), 360, "H"),
                        (self.hist["s"], QColor("#33ffaa"), 256, "S"),
                        (self.hist["v"], QColor("#aa33ff"), 256, "V")]

        # 找最大值
        max_val = 1
        for data, *_ in channels:
            for v in data:
                if v > max_val: max_val = v

        bar_w = max(1, (w - 12) // len(channels[0][0]) if channels else 1)
        for data, color, *extra in channels:
            bins = len(data)
            ch_max = max(data) or 1
            # 合并显示时用全局 max，单通道用各自 max
            use_max = max_val if len(channels) > 1 else ch_max
            p.setPen(QPen(color, max(1, bar_w-1)))
            for i in range(bins):
                if i % 8 != 0 and len(channels) == 1: continue  # 单通道显示全
                if i % 4 != 0: continue  # 合并时跳采
                bar_h = int((data[i] / use_max) * (h - 20))
                x = 5 + i * (w - 12) // bins
                p.drawLine(x, h - 10, x, h - 10 - bar_h)
        p.end()


class HistogramDialog(QDialog):
    def __init__(self, parent, images):
        super().__init__(parent)
        self.setWindowTitle(_S("title"))
        self.setMinimumSize(600, 500)
        self.images = images or []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(_S("channel")))
        self.ch_combo = QComboBox()
        self.ch_combo.addItems([_S("rgb"), _S("red"), _S("green"), _S("blue"),
                               _S("luminance"), _S("hsv")])
        self.ch_combo.currentIndexChanged.connect(self._update)
        top.addWidget(self.ch_combo)
        top.addStretch()
        btn = QPushButton(_S("refresh"), clicked=self._update)
        top.addWidget(btn)
        layout.addLayout(top)
        self.widget = HistogramWidget()
        layout.addWidget(self.widget, 1)
        self._update()

    def _update(self):
        idx = self.ch_combo.currentIndex()
        modes = ["rgb", "r", "g", "b", "y", "hsv"]
        self.widget.mode = modes[idx] if idx < len(modes) else "rgb"
        if self.images:
            self.widget.compute(self.images[0])
        self.widget.update()
