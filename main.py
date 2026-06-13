#!/usr/bin/env python3
"""
klut — Kirigami-based 3D LUT viewer.

Usage:
    python3 main.py [image_path] [lut_dir]
    python3 main.py --debug
    python3 main.py --lang=en

Shortcuts:
    O        Open image
    L        Load LUT files
    E        Export PNG
    W        Toggle watermark
    D        Toggle debug panel
    C        Cycle source colorspace
    Shift+C  Cycle LUT colorspace
    ↑/↓     Switch LUT
    ←/→     Switch image
"""

import os
import sys
import glob

# Force software rendering — required in VM environments without OpenGL
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

from app import KlutBackend
from lang import LANG


def main():
    # Parse flags
    debug = "--debug" in sys.argv
    if debug:
        sys.argv.remove("--debug")

    for arg in sys.argv[:]:
        if arg.startswith("--lang="):
            lang = arg.split("=", 1)[1]
            if lang in ("zh", "en"):
                LANG.set(lang)
            sys.argv.remove(arg)

    # Must use QApplication for Kirigami menu bars and event handling
    app = QApplication(sys.argv)
    app.setApplicationName("klut")
    app.setOrganizationName("klut")

    # Load F1.8 font if available
    _load_fonts(app)

    # Create QML engine
    engine = QQmlApplicationEngine()

    # Register backend as context property
    backend = KlutBackend()
    engine.rootContext().setContextProperty("Backend", backend)

    # Load QML
    qml_path = os.path.join(os.path.dirname(__file__), "ui", "main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if engine.rootObjects():
        # Auto-load images/LUTs from CLI args
        _handle_args(backend, sys.argv[1:])
        _auto_load_luts(backend)
        sys.exit(app.exec())
    else:
        sys.exit(1)


def _load_fonts(app: QApplication):
    """Load F1.8 font for UI."""
    base = os.path.dirname(__file__)
    font_path = os.path.join(base, "resources", "F1.8-Regular.otf")

    if os.path.exists(font_path):
        fid = QFontDatabase.addApplicationFont(font_path)
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                font = QFont(families[0], 11)
                app.setFont(font)
                return

    app.setFont(QFont("sans-serif", 11))


def _handle_args(backend: KlutBackend, args: list):
    """Handle command-line image/LUT arguments."""
    image_paths = []
    lut_paths = []

    for arg in args:
        if os.path.isfile(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext == '.cube':
                lut_paths.append(arg)
            elif ext in ('.png', '.jpg', '.jpeg', '.ppm', '.tif', '.bmp', '.webp'):
                image_paths.append(arg)

    if image_paths:
        backend.openImages(";".join(image_paths))
    if lut_paths:
        backend.openLutFiles(";".join(lut_paths))

    for arg in args:
        if os.path.isdir(arg):
            cubes = sorted(glob.glob(os.path.join(arg, "*.cube")))
            if cubes:
                backend.openLutFiles(";".join(cubes))


def _auto_load_luts(backend: KlutBackend):
    """Auto-detect LUTs from standard directories."""
    base = os.path.dirname(__file__)
    search_dirs = [
        os.path.join(base, "luts"),
        os.path.join(base, "..", "luts"),
    ]

    for d in search_dirs:
        if os.path.isdir(d):
            cubes = sorted(glob.glob(os.path.join(d, "*.cube")))
            if cubes:
                backend.openLutFiles(";".join(cubes))
                break


if __name__ == "__main__":
    main()
