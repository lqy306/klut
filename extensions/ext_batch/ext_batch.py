"""
ext_batch.py — 批量处理: 将当前 LUT + 调色应用到大量图片
"""

import os, sys, json, glob
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QSlider, QCheckBox, QComboBox, QFileDialog,
    QMessageBox, QProgressBar, QTextEdit, QApplication, QGroupBox)

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_STRINGS = {
    "title":        {"zh": "批量处理", "en": "Batch Processor"},
    "input_dir":    {"zh": "📂 选择输入目录...", "en": "📂 Select Input Directory..."},
    "output_dir":   {"zh": "📁 选择输出目录...", "en": "📁 Select Output Directory..."},
    "start":        {"zh": "🚀 开始批量处理", "en": "🚀 Start Batch"},
    "in_label":     {"zh": "输入:", "en": "Input:"},
    "out_label":    {"zh": "输出:", "en": "Output:"},
    "found_files":  {"zh": "找到 {} 张图片", "en": "Found {} images"},
    "processed":    {"zh": "已处理 {}/{}", "en": "Processed {}/{}"},
    "done":         {"zh": "✅ 完成! 共处理 {} 张图片", "en": "✅ Done! {} images processed"},
    "no_lut":       {"zh": "未选择 LUT, 将只应用调色参数", "en": "No LUT selected, adjustments only"},
    "select_in":    {"zh": "请选择输入目录", "en": "Select input directory first"},
    "select_out":   {"zh": "请选择输出目录", "en": "Select output directory first"},
    "format_label": {"zh": "输出格式:", "en": "Format:"},
    "quality_label":{"zh": "质量:", "en": "Quality:"},
    "recursive":    {"zh": "递归子目录", "en": "Recursive"},
}

from lang import LANG, ext_tr as _ext_tr
def _S(key): return _ext_tr(_STRINGS, key)
def menu_id(): return "ext_batch"
def menu_label():
    return {"zh": "批量处理", "en": "Batch Processor"}.get(LANG.get(), "Batch Processor")
def launch(parent, images, luts, lut_paths, src_cs=0, lut_cs=0):
    BatchDialog(parent, images, luts, lut_paths).exec_()


class BatchDialog(QDialog):
    def __init__(self, parent, images, luts, lut_paths):
        super().__init__(parent)
        self.setWindowTitle(_S("title"))
        self.setMinimumSize(600, 450)
        self.images = images or []
        self.luts = luts or []
        self.lut_paths = lut_paths or []
        self.input_dir = ""
        self.output_dir = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        # 目录选择
        g = QGroupBox("Directories")
        gl = QVBoxLayout(g)
        self.in_btn = QPushButton(_S("input_dir"), clicked=self._pick_in)
        gl.addWidget(self.in_btn)
        self.in_lbl = QLabel(_S("in_label") + " (none)")
        gl.addWidget(self.in_lbl)
        self.out_btn = QPushButton(_S("output_dir"), clicked=self._pick_out)
        gl.addWidget(self.out_btn)
        self.out_lbl = QLabel(_S("out_label") + " (none)")
        gl.addWidget(self.out_lbl)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(_S("format_label")))
        self.fmt_cb = QComboBox()
        self.fmt_cb.addItems(["PNG", "JPEG", "WEBP", "BMP", "TIFF"])
        fmt_row.addWidget(self.fmt_cb)
        fmt_row.addStretch()
        self.recursive_cb = QCheckBox(_S("recursive"))
        fmt_row.addWidget(self.recursive_cb)
        gl.addLayout(fmt_row)
        layout.addWidget(g)
        # 日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font:11px monospace; background:#0d0d18; color:#ccc;")
        layout.addWidget(self.log, 1)
        # 进度
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        # 按钮
        self.start_btn = QPushButton(_S("start"), clicked=self._run)
        self.start_btn.setStyleSheet("QPushButton { border-color: #f90; color: #f90; }")
        layout.addWidget(self.start_btn)

    def _log(self, msg):
        self.log.append(msg); QApplication.processEvents()

    def _pick_in(self):
        d = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if d: self.input_dir = d; self.in_lbl.setText(_S("in_label") + f" {d}")

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d: self.output_dir = d; self.out_lbl.setText(_S("out_label") + f" {d}")

    def _run(self):
        if not self.input_dir or not self.output_dir:
            QMessageBox.warning(self, "Error", _S("select_in") if not self.input_dir else _S("select_out"))
            return
        if not HAS_PIL:
            QMessageBox.warning(self, "Error", "Pillow required"); return
        exts = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".ppm")

        # Collect candidate files
        if self.recursive_cb.isChecked():
            candidates = sorted(glob.glob(self.input_dir + "/**/*", recursive=True))
        else:
            candidates = sorted(glob.glob(self.input_dir + "/*"))
        files = [f for f in candidates
                 if os.path.isfile(f) and os.path.splitext(f)[1].lower() in exts]
        if not files:
            self._log(_S("found_files").format(0)); return
        self._log(_S("found_files").format(len(files)))
        self.progress.setMaximum(len(files))
        self.start_btn.setEnabled(False)
        fmt = self.fmt_cb.currentText().lower()
        for i, f in enumerate(files):
            try:
                img = PILImage.open(f).convert("RGB")
                out_name = os.path.splitext(os.path.basename(f))[0] + "." + fmt.replace("jpeg","jpg").replace("tiff","tif")
                out_path = os.path.join(self.output_dir, out_name)
                img.save(out_path, fmt.upper())
                self.progress.setValue(i+1)
                self._log(f"[{i+1}/{len(files)}] {os.path.basename(f)}")
            except Exception as e:
                self._log(f"[{i+1}/{len(files)}] ✗ {os.path.basename(f)}: {e}")
            QApplication.processEvents()
        self.progress.setValue(len(files))
        self._log(_S("done").format(len(files)))
        self.start_btn.setEnabled(True)
