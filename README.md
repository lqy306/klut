# klut — Kirigami 3D LUT Viewer

A 3D LUT preview tool built with KDE Kirigami framework.

## Quick Start

```bash
# Install dependencies
pip install PySide6 Pillow

# Run
python3 main.py                        # Chinese UI
python3 main.py --lang=en              # English UI
python3 main.py --debug                # Debug mode
python3 main.py image.jpg luts/        # Open directly
```

## Features

- **Split-screen preview** — drag the divider to compare original vs LUT
- **Colorspace support** — Rec.709 built-in, extensible log colorspaces
- **Extension system** — install colorspace and tool extensions
- **Thumbnail navigation** — quick image switching
- **Watermark overlay** — LUT name display on preview
- **Keyboard shortcuts** — efficient workflow

## Interface

| Action | Key | Description |
|--------|-----|-------------|
| Open image | `O` | Select image files |
| Load LUT | `L` | Load .cube files |
| Export PNG | `E` | Save LUT result |
| Watermark | `W` | Toggle LUT watermark |
| Debug | `D` | Toggle debug panel |
| Switch LUT | `↑↓` | Browse LUT list |
| Switch image | `←→` | Browse images |
| Colorspace | `C` / `Shift+C` | Cycle source/LUT CS |
| Split line | Drag | Compare original/LUT |

## Colorspace Extensions

klut ships with **Rec.709** built-in. Additional colorspaces are available as extensions:

| Extension | Description |
|-----------|-------------|
| **V-Log** | Panasonic V-Log/V-Gamut |
| **S-Log3** | Sony S-Log3 |
| **LogC** | ARRI LogC EI 800 |

Extensions auto-load from the `extensions/` directory.

## Extension System

Extensions are self-contained directories under `extensions/` with a `manifest.json`:

```json
{
    "name": "V-Log",
    "id": "vlog",
    "version": "1.0.0",
    "type": "colorspace",
    "entry": "__init__.py"
}
```

Two extension types:
- **colorspace** — registers `load()`/`unload()` hooks
- **python** — general extensions with a `launch()` entry point

## Dependencies

| Package | Purpose |
|---------|---------|
| PySide6 | Qt6/Kirigami GUI |
| Pillow | Image processing |

## License

BSD 2-Clause License
