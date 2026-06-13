"""
ext_compare.py — 网格对比: 同一图片上并排显示多个 LUT 效果
"""

import os, sys, math
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QSlider, QCheckBox, QFileDialog, QMessageBox,
    QApplication, QScrollArea, QGridLayout, QComboBox, QGroupBox)

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from engine.lut3d import LUT3D

_STRINGS = {
    "title":        {"zh": "LUT 网格对比", "en": "LUT Grid Compare"},
    "open_img":     {"zh": "📂 打开图片", "en": "📂 Open Image"},
    "select_luts":  {"zh": "📁 选择 LUT 文件...", "en": "📁 Select LUT Files..."},
    "grid_cols":    {"zh": "列数:", "en": "Columns:"},
    "refresh":      {"zh": "刷新", "en": "Refresh"},
    "original":     {"zh": "原始", "en": "Original"},
    "no_img":       {"zh": "请先打开一张图片", "en": "Open an image first"},
    "no_luts":      {"zh": "请选择至少一个 LUT", "en": "Select at least one LUT"},
}

from lang import LANG, ext_tr as _ext_tr
def _S(key): return _ext_tr(_STRINGS, key)
def menu_id(): return "ext_compare"
def menu_label():
    return {"zh": "LUT 网格对比", "en": "LUT Grid"}.get(LANG.get(), "LUT Grid")
def launch(parent, images, luts, lut_paths, src_cs=0, lut_cs=0):
    CompareDialog(parent, images, luts, lut_paths).exec_()


class CompareDialog(QDialog):
    def __init__(self, parent, images, luts, lut_paths):
        super().__init__(parent)
        self.setWindowTitle(_S("title"))
        self.setMinimumSize(900, 600)
        self.source_path = images[0] if images else ""
        self.lut_paths = list(lut_paths or [])
        self.lut_names = list(luts or [])
        self.cols = 3
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        btn = QPushButton(_S("open_img"), clicked=self._open_img)
        btn.setStyleSheet("border-color:#f90;color:#f90")
        top.addWidget(btn)
        btn2 = QPushButton(_S("select_luts"), clicked=self._pick_luts)
        top.addWidget(btn2)
        top.addWidget(QLabel(_S("grid_cols")))
        self.col_spin = QSlider(Qt.Horizontal)
        self.col_spin.setRange(2, 6); self.col_spin.setValue(3)
        self.col_spin.valueChanged.connect(self._rebuild)
        top.addWidget(self.col_spin)
        top.addStretch()
        layout.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(4)
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll, 1)
        self._rebuild()

    def _open_img(self):
        p,_ = QFileDialog.getOpenFileName(self,"Open Image","","Images (*.png *.jpg *.jpeg);;All (*)")
        if p: self.source_path = p; self._rebuild()

    def _pick_luts(self):
        paths,_ = QFileDialog.getOpenFileNames(self,"Select LUTs","","LUT (*.cube);;All (*)")
        if not paths: return
        for p in paths:
            if p not in self.lut_paths:
                self.lut_paths.append(p)
                self.lut_names.append(os.path.splitext(os.path.basename(p))[0])
        self._rebuild()

    def _rebuild(self):
        import os, time
        while self.grid.count():
            w = self.grid.itemAt(0).widget()
            if w: w.deleteLater()
        if not HAS_PIL or not self.source_path:
            self.grid.addWidget(QLabel(_S("no_img")), 0, 0)
            return
        cols = self.col_spin.value()
        try:
            src = PILImage.open(self.source_path).convert("RGB")
        except:
            self.grid.addWidget(QLabel("Cannot open image"), 0, 0)
            return
        # Original
        self._add_thumb(src, _S("original"), 0, 0, cols)
        # LUTs
        row, col = 0, 1
        total = len(self.lut_paths)
        if total == 0:
            self.grid.addWidget(QLabel(_S("no_luts")), 0, 1)
            return
        # 缩放源图到网格尺寸以加速
        cell_w = min(300, (self.width() - 20) // cols)
        r = cell_w / src.width
        if r < 1.0:
            src_small = src.resize((int(src.width*r), int(src.height*r)), PILImage.LANCZOS)
        else:
            src_small = src.copy()
        for i, (lp, ln) in enumerate(zip(self.lut_paths, self.lut_names)):
            if col >= cols: col = 0; row += 1
            try:
                lut = LUT3D()
                lut.load(lp)
                result = lut.apply_image(src_small)
                self._add_thumb(result, ln, row, col, cols)
            except Exception as e:
                self.grid.addWidget(QLabel(f"{ln}: {str(e)[:30]}"), row, col)
            QApplication.processEvents()
            col += 1

    def _add_thumb(self, pil_img, name, row, col, total_cols):
        import time
        cell_w = min(300, (self.width() - 20) // total_cols)
        r = cell_w / pil_img.width
        if r < 1.0:
            thumb = pil_img.resize((int(pil_img.width*r), int(pil_img.height*r)), PILImage.LANCZOS)
        else:
            thumb = pil_img.copy()
        # 内存中处理, 避免文件竞争
        from io import BytesIO
        buf = BytesIO()
        thumb.save(buf, "PNG")
        qi = QImage.fromData(buf.getvalue())
        buf.close()
        if qi.isNull(): return
        pix = QPixmap.fromImage(qi)
        w = QWidget(); wl = QVBoxLayout(w); wl.setContentsMargins(2,2,2,2)
        lbl = QLabel()
        lbl.setPixmap(pix)
        lbl.setAlignment(Qt.AlignCenter)
        wl.addWidget(lbl)
        nl = QLabel(name)
        nl.setAlignment(Qt.AlignCenter)
        nl.setStyleSheet("color:#f90;font-weight:bold;font-size:11px")
        wl.addWidget(nl)
        self.grid.addWidget(w, row, col)
