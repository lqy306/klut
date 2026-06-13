"""
ext_lut_convert.py — LUT 色彩空间转换拓展
===========================================

将 .cube LUT 从一种色彩空间转换到另一种，使得
原本为特定 Log 格式设计的 LUT 可在其他色彩空间
下正确使用。

转换原理
--------
对目标色彩空间的每个网格点 (rt, gt, bt):

  1. rt/gt/bt → scene-linear  (target_cs.to_linear)
  2. linear → source encoding (source_cs.from_linear)
  3. 在原 LUT 中查找对应的输出值 (LUT.apply)

输出色域不变，仅改变 LUT 的输入色彩空间。

依赖
----
需要安装对应的 colorspace 拓展（rec709 内建，
vlog/slog3/logc 由对应拓展提供）。
"""

import os
import sys
import math
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QApplication, QGroupBox, QProgressBar,
    QTextEdit,
)

from engine.lut3d import LUT3D
from colorspaces import get, list_all, names
from lang import LANG, ext_tr as _ext_tr


# ---------------------------------------------------------------------------
#  String table
# ---------------------------------------------------------------------------

_STRINGS = {
    "title":             {"zh": "LUT 色彩空间转换", "en": "LUT Colorspace Converter"},
    "load_lut":          {"zh": "📂 加载 .cube LUT", "en": "📂 Load .cube LUT"},
    "from_label":        {"zh": "源色彩空间", "en": "Source CS (current)"},
    "to_label":          {"zh": "目标色彩空间", "en": "Target CS (desired)"},
    "convert":           {"zh": "🔄 转换", "en": "🔄 Convert"},
    "save_as":           {"zh": "💾 另存为 .cube", "en": "💾 Save as .cube"},
    "lut_info":          {"zh": "LUT 信息", "en": "LUT Info"},
    "status_ready":      {"zh": "加载一个 .cube 文件开始", "en": "Load a .cube file to start"},
    "status_loaded":     {"zh": "已加载: {} ({}³)", "en": "Loaded: {} ({}³)"},
    "status_converted":  {"zh": "已转换 {} → {} ({}³)", "en": "Converted {} → {} ({}³)"},
    "no_lut":            {"zh": "请先加载 LUT 文件", "en": "Load a .cube file first"},
    "no_cs":             {"zh": "源和目标色彩空间不能相同", "en": "Source and target CS must differ"},
    "unknown_cs":        {"zh": "色彩空间未注册: {}", "en": "Colorspace not registered: {}"},
    "log":               {"zh": "转换日志", "en": "Conversion Log"},
    "close":             {"zh": "关闭", "en": "Close"},
    "conv_title":        {"zh": "{} 从 {} 到 {} 的转换", "en": "{} from {} to {}"},
}


def _S(key: str) -> str:
    return _ext_tr(_STRINGS, key)


def menu_id() -> str:
    return "ext_lut_convert"


def menu_label() -> str:
    return {"zh": "LUT 色彩空间转换", "en": "LUT Converter"}.get(
        LANG.get(), "LUT Converter")


def launch(parent, images, luts, lut_paths, src_cs=0, lut_cs=0):
    dlg = LutConvertDialog(parent)
    dlg.exec_()


# ---------------------------------------------------------------------------
#  Core conversion function
# ---------------------------------------------------------------------------

def convert_lut(
    source_lut: LUT3D,
    source_cs,
    target_cs,
) -> LUT3D:
    """Convert a LUT from *source_cs* encoding to *target_cs* encoding.

    Each grid point in the new LUT is computed by:
      target_encoded → linear → source_encoded → lookup(source_lut)

    The output values (what the LUT emits) are unchanged — only the
    *input* encoding is remapped.
    """
    size = source_lut.size
    if size < 2:
        return source_lut

    result = LUT3D()
    result.size = size
    result.title = _S("conv_title").format(
        source_lut.title or "LUT",
        source_cs.name,
        target_cs.name,
    )
    result.dom_min = source_lut.dom_min[:]
    result.dom_max = source_lut.dom_max[:]

    sf = size - 1

    data = [
        [
            [[0.0, 0.0, 0.0] for _ in range(size)]
            for _ in range(size)
        ]
        for _ in range(size)
    ]

    to_lin   = target_cs.to_linear
    frm_lin  = source_cs.from_linear
    apply_lut = source_lut.apply

    for bi in range(size):
        bt = bi / sf
        for gi in range(size):
            gt = gi / sf
            for ri in range(size):
                rt = ri / sf

                # target CS → linear → source CS
                rs = frm_lin(to_lin(rt))
                gs = frm_lin(to_lin(gt))
                bs = frm_lin(to_lin(bt))

                # clamp to valid domain
                rs = max(0.0, min(1.0, rs))
                gs = max(0.0, min(1.0, gs))
                bs = max(0.0, min(1.0, bs))

                # interpolate source LUT at (rs, gs, bs)
                nr, ng, nb = apply_lut(rs, gs, bs)
                data[bi][gi][ri] = [nr, ng, nb]

    result.data = data
    return result


# ---------------------------------------------------------------------------
#  Dialog
# ---------------------------------------------------------------------------

class LutConvertDialog(QDialog):
    """LUT colorspace converter dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_S("title"))
        self.setMinimumSize(520, 480)

        self._source_lut:  Optional[LUT3D] = None
        self._converted:    Optional[LUT3D] = None
        self._source_path:  str = ""

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---- Load LUT section ----
        load_group = QGroupBox("LUT")
        load_layout = QVBoxLayout(load_group)

        btn_row = QHBoxLayout()
        self._load_btn = QPushButton(_S("load_lut"))
        self._load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(self._load_btn)
        btn_row.addStretch()
        load_layout.addLayout(btn_row)

        self._info_label = QLabel(_S("status_ready"))
        self._info_label.setStyleSheet("color: #888; font-size: 11px;")
        load_layout.addWidget(self._info_label)

        layout.addWidget(load_group)

        # ---- CS selection ----
        cs_group = QGroupBox(_S("lut_info"))
        cs_layout = QFormLayout(cs_group)

        self._from_cb = QComboBox()
        self._to_cb   = QComboBox()
        self._populate_cs()

        cs_layout.addRow(_S("from_label"), self._from_cb)
        cs_layout.addRow(_S("to_label"),   self._to_cb)

        layout.addWidget(cs_group)

        # ---- Convert button ----
        self._convert_btn = QPushButton(_S("convert"))
        self._convert_btn.clicked.connect(self._on_convert)
        self._convert_btn.setStyleSheet(
            "QPushButton { border-color: #f90; color: #f90; }")
        layout.addWidget(self._convert_btn)

        # ---- Progress ----
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ---- Log ----
        log_group = QGroupBox(_S("log"))
        log_layout = QVBoxLayout(log_group)
        self._log_widget = QTextEdit()
        self._log_widget.setReadOnly(True)
        self._log_widget.setStyleSheet(
            "font: 11px monospace; background: #0d0d18; color: #ccc;")
        self._log_widget.setMaximumHeight(120)
        log_layout.addWidget(self._log_widget)
        layout.addWidget(log_group)

        # ---- Save + Close ----
        btn_row2 = QHBoxLayout()
        self._save_btn = QPushButton(_S("save_as"))
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setEnabled(False)
        btn_row2.addWidget(self._save_btn)
        btn_row2.addStretch()

        close_btn = QPushButton(_S("close"))
        close_btn.clicked.connect(self.accept)
        btn_row2.addWidget(close_btn)
        layout.addLayout(btn_row2)

    # ---- helpers ----

    def _populate_cs(self):
        """Fill the colorspace dropdowns from the registry."""
        all_cs = list_all()
        self._from_cb.clear()
        self._to_cb.clear()
        for cs in all_cs:
            self._from_cb.addItem(cs.name, cs.id)
            self._to_cb.addItem(cs.name, cs.id)

        # Default: source = first log, target = Rec.709
        for i in range(self._from_cb.count()):
            cid = self._from_cb.itemData(i)
            if cid != "rec709":
                self._from_cb.setCurrentIndex(i)
                break
        for i in range(self._to_cb.count()):
            cid = self._to_cb.itemData(i)
            if cid == "rec709":
                self._to_cb.setCurrentIndex(i)
                break

    def _log(self, msg: str):
        self._log_widget.append(msg)
        QApplication.processEvents()

    def _cs_from_cb(self, cb: QComboBox):
        """Get ColorSpace object from combo selection."""
        cid = cb.currentData()
        return get(cid)

    # ---- slots ----

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open .cube LUT", "", "LUT (*.cube);;All (*)")
        if not path:
            return
        try:
            lut = LUT3D()
            lut.load(path)
            self._source_lut = lut
            self._source_path = path
            self._converted = None
            self._save_btn.setEnabled(False)

            name = os.path.splitext(os.path.basename(path))[0]
            self._info_label.setText(
                _S("status_loaded").format(name, lut.size))
            self._log(f"Loaded: {path}  ({lut.size}³, {lut.title})")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load LUT:\n{e}")
            self._log(f"Error: {e}")

    def _on_convert(self):
        if self._source_lut is None:
            QMessageBox.warning(self, "Error", _S("no_lut"))
            return

        src_cs = self._cs_from_cb(self._from_cb)
        dst_cs = self._cs_from_cb(self._to_cb)

        if src_cs is None:
            QMessageBox.warning(self, "Error",
                _S("unknown_cs").format(self._from_cb.currentText()))
            return
        if dst_cs is None:
            QMessageBox.warning(self, "Error",
                _S("unknown_cs").format(self._to_cb.currentText()))
            return
        if src_cs.id == dst_cs.id:
            QMessageBox.warning(self, "Error", _S("no_cs"))
            return

        self._convert_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)   # indeterminate
        self._log(
            f"Converting: {src_cs.name} → {dst_cs.name}  "
            f"({self._source_lut.size}³) ..."
        )
        QApplication.processEvents()

        try:
            result = convert_lut(self._source_lut, src_cs, dst_cs)
            self._converted = result

            name = os.path.splitext(
                os.path.basename(self._source_path))[0]
            self._log(
                _S("status_converted").format(
                    name, dst_cs.name, result.size))
            self._info_label.setText(
                _S("status_converted").format(name, dst_cs.name, result.size))
            self._save_btn.setEnabled(True)
        except Exception as e:
            self._log(f"Conversion failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._progress.setRange(0, 100)
            self._progress.setValue(100)
            self._convert_btn.setEnabled(True)

    def _on_save(self):
        if self._converted is None:
            return

        default_name = "converted.cube"
        if self._source_path:
            base = os.path.splitext(os.path.basename(self._source_path))[0]
            src_id = self._from_cb.currentData() or "src"
            dst_id = self._to_cb.currentData() or "dst"
            default_name = f"{base}_{src_id}_to_{dst_id}.cube"

        path, _ = QFileDialog.getSaveFileName(
            self, _S("save_as"), default_name, "LUT (*.cube)")
        if not path:
            return

        try:
            self._converted.save(path)
            self._log(f"Saved: {path}")
            QMessageBox.information(
                self, "Exported",
                f"Saved {self._converted.size}³ LUT\n→ {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Save failed:\n{e}")
            self._log(f"Save error: {e}")
