"""
app.py — klut application backend bridge.

Exposes Python objects/state to the Kirigami QML frontend via
context properties and signal/slot connections.
"""

import os
import sys
import io
import time
import json
import tempfile
import logging
from typing import Optional, List

from PySide6.QtCore import (
    Qt, QPoint, QObject, Signal, Slot, Property, QUrl, QRect, QSize,
    QTimer,
)
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QFont

from engine.lut3d import LUT3D, load_lut, clear_lut_cache, scan_luts
from engine.image import qimage_to_pil, pil_to_qimage
from colorspaces import list_all, index_of, by_index, names, ids, convert_image
from lang import tr, LANG

# Force early extension scan so colorspace extensions (V-Log, S-Log3,
# LogC) are registered before the QML UI renders their dropdowns.
import extensions.manager as _ext_mgr  # triggers scan() via module-level call


# ---------------------------------------------------------------------------
#  File logger — appends to <app-dir>/log.txt with timestamps
# ---------------------------------------------------------------------------

_log_path = os.path.join(os.path.dirname(__file__), "log.txt")

_logger = logging.getLogger("klut")
_logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(_log_path, mode="a", encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)-5s %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")
_fh.setFormatter(_fmt)
_logger.addHandler(_fh)

# Also mirror to stderr for interactive sessions
_sh = logging.StreamHandler(sys.stderr)
_sh.setLevel(logging.DEBUG if "--debug" in sys.argv else logging.WARNING)
_sh.setFormatter(_fmt)
_logger.addHandler(_sh)


class KlutBackend(QObject):
    """Main backend object exposed to QML via context property as 'Backend'."""

    # Signals
    previewChanged = Signal()
    lutListChanged = Signal()
    currentLutIndexChanged = Signal()
    imageListChanged = Signal()
    colorspaceListChanged = Signal()
    statusChanged = Signal(str)
    debugLog = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_paths: List[str] = []
        self._current_image_idx: int = -1
        self._src_cs_per_image: List[int] = []   # one entry per image
        self._qimage_cache: Dict[str, QImage] = {}  # path → scaled QImage
        self._lut_paths: List[str] = []
        self._lut_names: List[str] = []
        self._lut_cs_per_lut: List[int] = []      # one entry per LUT
        self._current_lut_idx: int = -1
        self._src_cs_index: int = 0
        self._lut_cs_index: int = 0
        self._show_watermark: bool = True
        self._max_preview: int = 1024
        self._split_pos: float = 0.5
        self._accent_color: str = "#ff9900"

        self._orig_qimage: Optional[QImage] = None
        self._lut_qimage: Optional[QImage] = None
        self._lut_image_path: str = ""
        self._render_counter: int = 0

        # Debounce timer — applies LUT 150ms after user stops dragging
        self._lut_timer = QTimer()
        self._lut_timer.setSingleShot(True)
        self._lut_timer.timeout.connect(self._apply_lut)

        # Load settings
        self._settings = self._load_settings()
        self._accent_color = self._settings.get("accent", "#ff9900")

        # Wire debugLog → file logger
        self.debugLog.connect(self._on_debug_log)
        _logger.info("klut backend initialized")

    # ---- Properties ----

    def _get_accent(self) -> str:
        return self._accent_color

    def _set_accent(self, color: str):
        self._accent_color = color
        self._settings["accent"] = color
        self._save_settings(self._settings)

    accentColor = Property(str, _get_accent, _set_accent, notify=previewChanged)

    def _get_split_pos(self) -> float:
        return self._split_pos

    def _set_split_pos(self, v: float):
        self._split_pos = max(0.0, min(1.0, v))

    @Slot(float)
    def setSplit(self, pos: float):
        """Called from QML MouseArea during drag — just stores the
        position; the split is rendered natively in QML."""
        self._split_pos = max(0.0, min(1.0, pos))

    splitPos = Property(float, _get_split_pos, _set_split_pos, notify=previewChanged)

    def _get_show_wm(self) -> bool:
        return self._show_watermark

    def _set_show_wm(self, v: bool):
        self._show_watermark = v

    showWatermark = Property(bool, _get_show_wm, _set_show_wm, notify=previewChanged)

    def _get_max_preview(self) -> int:
        return self._max_preview

    def _set_max_preview(self, v: int):
        self._max_preview = v

    maxPreview = Property(int, _get_max_preview, _set_max_preview, notify=previewChanged)

    def _get_lut_image_path(self) -> str:
        return self._lut_image_path

    lutImagePath = Property(str, _get_lut_image_path, notify=previewChanged)

    # ---- Path helpers ----

    @staticmethod
    def _strip_url_prefix(path: str) -> str:
        """Convert file:///... URL to a plain local path."""
        if path.startswith("file://"):
            return path[7:]
        return path

    @staticmethod
    def _clean_path_list(paths: list) -> list:
        """Strip file:// prefix from every path in the list."""
        return [KlutBackend._strip_url_prefix(p) for p in paths]

    # ---- QML Properties (with notify signals for reactive bindings) ----

    def _get_image_count(self) -> int:
        return len(self._image_paths)

    def _get_current_img_idx(self) -> int:
        return self._current_image_idx

    def _get_lut_count(self) -> int:
        return len(self._lut_names)

    def _get_current_lut_idx(self) -> int:
        return self._current_lut_idx

    def _get_src_cs_idx(self) -> int:
        return self._src_cs_index

    def _get_lut_cs_idx(self) -> int:
        return self._lut_cs_index

    def _get_current_lut_name(self) -> str:
        if 0 <= self._current_lut_idx < len(self._lut_names):
            return self._lut_names[self._current_lut_idx]
        return ""

    def _get_src_cs_name(self) -> str:
        cs = by_index(self._src_cs_index)
        return cs.name if cs else ""

    def _get_lut_cs_name(self) -> str:
        cs = by_index(self._lut_cs_index)
        return cs.name if cs else ""

    imageCount       = Property(int,   _get_image_count,       notify=imageListChanged)
    currentImageIndex = Property(int,   _get_current_img_idx,   notify=imageListChanged)
    lutCount         = Property(int,   _get_lut_count,         notify=lutListChanged)
    currentLutIndex  = Property(int,   _get_current_lut_idx,   notify=currentLutIndexChanged)
    srcCsIndex       = Property(int,   _get_src_cs_idx,        notify=colorspaceListChanged)
    lutCsIndex       = Property(int,   _get_lut_cs_idx,        notify=colorspaceListChanged)
    currentLutName   = Property(str,   _get_current_lut_name,  notify=lutListChanged)
    srcCsName        = Property(str,   _get_src_cs_name,       notify=colorspaceListChanged)
    lutCsName        = Property(str,   _get_lut_cs_name,       notify=colorspaceListChanged)

    # ---- Parameterised Slots (keep as Slots — called from QML with args) ----
    def appTitle(self) -> str:
        return tr("app_title")

    @Slot(result="QStringList")
    def colorspaceNames(self) -> List[str]:
        return names()

    @Slot(int, result=str)
    def lutName(self, idx: int) -> str:
        if 0 <= idx < len(self._lut_names):
            return self._lut_names[idx]
        return ""

    @Slot(int, result=str)
    def imagePath(self, idx: int) -> str:
        if 0 <= idx < len(self._image_paths):
            return self._image_paths[idx]
        return ""

    @Slot(str)
    def openImages(self, paths_str: str):
        if not paths_str:
            return
        paths = [p for p in paths_str.split(";") if p.strip()]
        if not paths:
            return
        self._image_paths = self._clean_path_list(paths)
        self._qimage_cache.clear()
        self._src_cs_per_image = [self._src_cs_index] * len(self._image_paths)
        self._current_image_idx = 0
        self._save_session()
        self._load_current_image()
        self.imageListChanged.emit()
        self.debugLog.emit(f"Loaded {len(paths)} image(s)", "info")

    @Slot(str)
    def openLutFiles(self, paths_str: str):
        if not paths_str:
            return
        paths = [p for p in paths_str.split(";") if p.strip()]
        if not paths:
            return
        self._add_lut_files(self._clean_path_list(paths))
        self._save_session()
        self.lutListChanged.emit()

    @Slot(int)
    def selectImage(self, idx: int):
        if 0 <= idx < len(self._image_paths):
            self._current_image_idx = idx
            # Restore per-image source colorspace
            if idx < len(self._src_cs_per_image):
                self._src_cs_index = self._src_cs_per_image[idx]
            self.imageListChanged.emit()
            self.colorspaceListChanged.emit()
            self._load_current_image()

    @Slot(int)
    def selectLut(self, idx: int):
        if 0 <= idx < len(self._lut_names):
            self._current_lut_idx = idx
            # Restore per-LUT colorspace
            if idx < len(self._lut_cs_per_lut):
                self._lut_cs_index = self._lut_cs_per_lut[idx]
            self.currentLutIndexChanged.emit()
            self.colorspaceListChanged.emit()
            self._apply_lut()

    @Slot(int)
    def setSrcCs(self, idx: int):
        if 0 <= idx < len(list_all()):
            self._src_cs_index = idx
            # Save per-image
            if 0 <= self._current_image_idx < len(self._src_cs_per_image):
                self._src_cs_per_image[self._current_image_idx] = idx
            self.colorspaceListChanged.emit()
            self._apply_lut()

    @Slot(int)
    def setLutCs(self, idx: int):
        if 0 <= idx < len(list_all()):
            self._lut_cs_index = idx
            # Save per-LUT
            if 0 <= self._current_lut_idx < len(self._lut_cs_per_lut):
                self._lut_cs_per_lut[self._current_lut_idx] = idx
            self.colorspaceListChanged.emit()
            self._apply_lut()

    @Slot()
    def cycleSrcCs(self):
        total = len(list_all())
        if total > 0:
            self._src_cs_index = (self._src_cs_index + 1) % total
            self.colorspaceListChanged.emit()
            self._apply_lut()

    @Slot()
    def cycleLutCs(self):
        total = len(list_all())
        if total > 0:
            self._lut_cs_index = (self._lut_cs_index + 1) % total
            self.colorspaceListChanged.emit()
            self._apply_lut()

    @Slot()
    def toggleWatermark(self):
        self._show_watermark = not self._show_watermark
        self.previewChanged.emit()

    @Slot(str, result=str)
    def translate(self, key: str) -> str:
        return tr(key)

    @Slot(str)
    def exportPng(self, path: str):
        path = self._strip_url_prefix(path)
        if self._lut_qimage and not self._lut_qimage.isNull():
            self._lut_qimage.save(path)
            self.debugLog.emit(f"Exported: {path}", "info")

    @Slot()
    def nextImage(self):
        if self._current_image_idx < len(self._image_paths) - 1:
            self._current_image_idx += 1
            self._load_current_image()
            self.imageListChanged.emit()

    @Slot()
    def prevImage(self):
        if self._current_image_idx > 0:
            self._current_image_idx -= 1
            self._load_current_image()
            self.imageListChanged.emit()

    @Slot()
    def nextLut(self):
        if self._current_lut_idx < len(self._lut_names) - 1:
            self._current_lut_idx += 1
            self.currentLutIndexChanged.emit()
            self._apply_lut()

    @Slot()
    def prevLut(self):
        if self._current_lut_idx > 0:
            self._current_lut_idx -= 1
            self.currentLutIndexChanged.emit()
            self._apply_lut()

    @Slot(result="QVariantList")
    def extensionList(self) -> list:
        """Return list of all extensions for menu & manager display.

        Resolves localized name/description based on current language.
        """
        from extensions.manager import list_extensions
        exts = list_extensions()
        is_zh = LANG.get() == "zh"
        result = []
        for e in exts:
            name = e.get("name_zh") or e["name"] if is_zh else e["name"]
            desc = (e.get("description_zh") or e.get("description", "")
                    if is_zh else e.get("description", ""))
            result.append({
                "id": e["id"],
                "name": name,
                "version": e.get("version", "?"),
                "type": e.get("type", "python"),
                "description": desc,
            })
        return result

    @Slot()
    def restoreSession(self):
        """Call from QML Component.onCompleted so signals are not lost."""
        self._restore_session()

    @Slot(str)
    def launchExtension(self, ext_id: str):
        """Launch a python extension."""
        from extensions.manager import launch_extension
        _logger.info("Launching extension: %s", ext_id)
        launch_extension(ext_id,
            parent=None,  # dialogs float as top-level windows
            images=self._image_paths,
            luts=self._lut_names,
            lut_paths=self._lut_paths,
            src_cs=self._src_cs_index,
            lut_cs=self._lut_cs_index)
        self.debugLog.emit(f"Extension launched: {ext_id}", "info")

    @Slot(str, str, result=bool)
    def exportExtension(self, ext_id: str, output_path: str) -> bool:
        """Pack an extension as .lutx and save to *output_path*."""
        from extensions.manager import pack_extension
        ok = pack_extension(ext_id, output_path)
        if ok:
            self.debugLog.emit(f"Exported: {ext_id} → {output_path}", "info")
        else:
            self.debugLog.emit(f"Export failed: {ext_id}", "error")
        return ok

    @Slot(str, result=str)
    def importExtension(self, lutx_path: str) -> str:
        """Import a .lutx package.  Returns the extension id on success."""
        from extensions.manager import unpack_extension
        ext_id = unpack_extension(lutx_path)
        if ext_id:
            self.debugLog.emit(f"Imported extension: {ext_id}", "info")
        else:
            self.debugLog.emit(f"Import failed: {lutx_path}", "error")
        return ext_id or ""

    # ---- Internal ----

    def _on_debug_log(self, msg: str, level: str):
        """Route debugLog signal to the file logger."""
        level_map = {
            "info":  logging.INFO,
            "warn":  logging.WARNING,
            "error": logging.ERROR,
            "debug": logging.DEBUG,
        }
        _logger.log(level_map.get(level, logging.INFO), "%s", msg)

    def _load_settings(self):
        settings_path = os.path.join(
            os.path.dirname(__file__), "extensions", "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_settings(self, data):
        settings_dir = os.path.join(os.path.dirname(__file__), "extensions")
        os.makedirs(settings_dir, exist_ok=True)
        settings_path = os.path.join(settings_dir, "settings.json")
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_session(self):
        """Persist image / LUT paths for next-launch restore."""
        self._settings["session_images"] = self._image_paths[:]
        self._settings["session_luts"]   = self._lut_paths[:]
        self._save_settings(self._settings)

    def _restore_session(self):
        """Re-import images & LUTs from last session if files still exist."""
        imgs = self._settings.get("session_images", [])
        imgs = [p for p in imgs if os.path.isfile(p)]
        luts = self._settings.get("session_luts", [])
        luts = [p for p in luts if os.path.isfile(p)]

        if imgs:
            self._image_paths = imgs
            self._src_cs_per_image = [self._src_cs_index] * len(imgs)
            self._current_image_idx = 0
            self._load_current_image()
            self.imageListChanged.emit()
            _logger.info("Restored %d image(s)", len(imgs))

        if luts:
            self._add_lut_files(luts)
            self.lutListChanged.emit()
            _logger.info("Restored %d LUT(s)", len(luts))

    def _add_lut_files(self, paths: list):
        for p in paths:
            name = os.path.splitext(os.path.basename(p))[0]
            if p not in self._lut_paths:
                self._lut_paths.append(p)
                self._lut_names.append(name)
                self._lut_cs_per_lut.append(self._lut_cs_index)
                load_lut(name, os.path.dirname(p))
        if self._current_lut_idx < 0 and self._lut_names:
            self._current_lut_idx = 0
            # If an image is already loaded, apply the newly-loaded LUT now
            if self._orig_qimage is not None:
                self._apply_lut()

    def _load_current_image(self):
        if self._current_image_idx < 0 or self._current_image_idx >= len(self._image_paths):
            return
        path = self._image_paths[self._current_image_idx]

        # Cache check — avoids re-reading from disk for recent images
        img = self._qimage_cache.get(path)
        if img is None:
            img = QImage(path)
            if img.isNull():
                return
            w, h = img.width(), img.height()
            max_dim = max(w, h)
            if max_dim > self._max_preview:
                scale = self._max_preview / max_dim
                img = img.scaled(int(w * scale), int(h * scale),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.statusChanged.emit(
                    f"Preview scaled: {w}x{h} → {img.width()}x{img.height()} "
                    f"(limit: {self._max_preview}px)")
            # LRU cache: keep at most 8 images
            if len(self._qimage_cache) > 8:
                self._qimage_cache.pop(next(iter(self._qimage_cache)))
            self._qimage_cache[path] = img

        self._orig_qimage = img

        # Apply LUT synchronously — always shows the correct result
        self._apply_lut()

        self.debugLog.emit(
            f"Loaded: {os.path.basename(path)} ({img.width()}x{img.height()})",
            "info")

    def _apply_lut(self):
        if self._orig_qimage is None or self._current_lut_idx < 0:
            return
        if self._current_lut_idx >= len(self._lut_names):
            return
        if self._current_image_idx < 0 or self._current_image_idx >= len(self._image_paths):
            return

        lut_name = self._lut_names[self._current_lut_idx]
        t0 = time.time()

        pil_img = qimage_to_pil(self._orig_qimage)
        if pil_img is None:
            return

        src_cs = by_index(self._src_cs_index)
        lut_cs = by_index(self._lut_cs_index)

        # Colorspace conversion: source → LUT space
        if src_cs and lut_cs and src_cs.id != lut_cs.id:
            pil_img = convert_image(pil_img, src_cs.id, lut_cs.id)

        # Apply LUT
        lut = None
        if self._current_lut_idx < len(self._lut_paths):
            lut_dir = os.path.dirname(self._lut_paths[self._current_lut_idx])
            lut = load_lut(lut_name, lut_dir)
        if lut:
            pil_img = lut.apply_image(pil_img)

        # Colorspace conversion: LUT space → source (display)
        if src_cs and lut_cs and src_cs.id != lut_cs.id:
            pil_img = convert_image(pil_img, lut_cs.id, src_cs.id)

        self._lut_qimage = pil_to_qimage(pil_img)

        # Save LUT-only image — cycle filenames so QML always reloads
        counter = self._render_counter
        self._render_counter = (counter + 1) % 3
        lut_path = os.path.join(
            tempfile.gettempdir(), f"klut_lut_{counter}.png")
        self._lut_qimage.save(lut_path)
        self._lut_image_path = lut_path

        elapsed = (time.time() - t0) * 1000

        self.previewChanged.emit()

        img_name = os.path.basename(
            self._image_paths[self._current_image_idx])
        self.statusChanged.emit(
            f"{img_name} | {lut_name} | "
            f"{src_cs.name if src_cs else '?'} → "
            f"{lut_cs.name if lut_cs else '?'} | {elapsed:.0f}ms")
        self.debugLog.emit(
            f"{img_name} | {lut_name} | {elapsed:.0f}ms", "info")

    def _render_combined(self):
        """Render split-view preview via QPainter.

        Cycles through 3 filenames (*_0.png, *_1.png, *_2.png) so that
        the QML Image element always sees a *different* URL each time
        this method is called, forcing it to reload from disk.
        """
        if self._orig_qimage is None or self._lut_qimage is None:
            return
        if self._orig_qimage.isNull() or self._lut_qimage.isNull():
            return

        try:
            orig = self._orig_qimage
            lut  = self._lut_qimage
            dw = orig.width()
            dh = orig.height()
            if dw < 2 or dh < 2:
                return

            combined = QImage(dw, dh, QImage.Format_ARGB32)
            combined.fill(Qt.black)

            p = QPainter(combined)
            try:
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                split_x = int(dw * self._split_pos)

                p.save()
                p.setClipRect(0, 0, split_x, dh)
                p.drawImage(QRect(0, 0, dw, dh), orig)
                p.restore()

                p.save()
                p.setClipRect(split_x, 0, dw - split_x, dh)
                p.drawImage(QRect(0, 0, dw, dh), lut)
                p.restore()

                accent = QColor(self._accent_color)
                p.setPen(QPen(accent, 2))
                p.drawLine(split_x, 0, split_x, dh)

                p.setBrush(accent)
                p.setPen(QPen(QColor("#fff"), 2))
                p.drawEllipse(QPoint(split_x, dh // 2), 14, 14)
                p.setFont(QFont("sans-serif", 10, QFont.Bold))
                p.setPen(QColor("#1a1a2e"))
                p.drawText(QRect(split_x - 14, dh // 2 - 8, 28, 16),
                           Qt.AlignCenter, "◀▶")
            finally:
                p.end()

            counter = self._render_counter
            self._render_counter = (counter + 1) % 3
            tmp_path = os.path.join(
                tempfile.gettempdir(), f"klut_preview_{counter}.png")
            combined.save(tmp_path)
            self._lut_image_path = tmp_path

        except Exception as e:
            _logger.error("_render_combined failed: %s", e)
            self._lut_image_path = ""
            self._lut_qimage = None
