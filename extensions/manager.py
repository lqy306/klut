"""
manager.py — Extension discovery, loading, and lifecycle management.

Extension types:
  - colorspace: register a colorspace (load/unload hooks)
  - python: general Python extension launched via launch()

Extensions are auto-discovered from the extensions/ directory.
Each extension is a directory with a manifest.json.
"""

import os
import sys
import json
import importlib
import logging
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
#  Logger
# ---------------------------------------------------------------------------

_log = logging.getLogger("klut.ext_manager")


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
#  Registry
# ---------------------------------------------------------------------------

_ext_registry: Dict[str, dict] = {}  # ext_id -> {path, manifest, enabled, loaded}


def ext_dir() -> str:
    """Return the extensions directory path."""
    return os.path.dirname(os.path.abspath(__file__))


def _read_manifest(dirpath: str) -> Optional[dict]:
    """Read manifest.json from an extension directory."""
    mf_path = os.path.join(dirpath, "manifest.json")
    if not os.path.exists(mf_path):
        return None
    try:
        with open(mf_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def scan():
    """Scan extensions directory and populate the registry."""
    _ext_registry.clear()
    base = ext_dir()

    if not os.path.isdir(base):
        return

    for fn in sorted(os.listdir(base)):
        fpath = os.path.join(base, fn)
        if not os.path.isdir(fpath) or fn.startswith(".") or fn.startswith("__"):
            continue

        mf = _read_manifest(fpath)
        if mf is None:
            continue

        eid = mf.get("id", fn)
        _ext_registry[eid] = {
            "path": fpath,
            "manifest": mf,
            "enabled": True,
            "loaded": False,
        }

    # Auto-load colorspace extensions
    for eid, reg in _ext_registry.items():
        mf = reg["manifest"]
        if mf.get("type") == "colorspace" and reg["enabled"] and not reg["loaded"]:
            _load_extension(eid)


def _load_extension(ext_id: str) -> bool:
    """Load a single extension. Returns True on success."""
    reg = _ext_registry.get(ext_id)
    if reg is None:
        return False

    mf = reg["manifest"]
    etype = mf.get("type", "python")
    entry = mf.get("entry", "__init__.py")
    mod_name = entry.rsplit(".", 1)[0]
    pkg_path = reg["path"]

    # Add extension path to sys.path if not there
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)

    try:
        # Clear cached module
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        mod = importlib.import_module(mod_name)

        if etype == "colorspace":
            # Colorspace extensions have load() function
            if hasattr(mod, "load"):
                mod.load()
            reg["loaded"] = True
        else:
            # General python extensions
            reg["loaded"] = True

        return True
    except Exception as e:
        _log.error("Failed to load extension %s: %s", ext_id, e)
        import traceback
        traceback.print_exc()
        return False


def unload_extension(ext_id: str):
    """Unload a single extension."""
    reg = _ext_registry.get(ext_id)
    if reg is None:
        return

    mf = reg["manifest"]
    entry = mf.get("entry", "__init__.py")
    mod_name = entry.rsplit(".", 1)[0]

    try:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "unload"):
                mod.unload()
    except Exception:
        pass

    reg["loaded"] = False


def list_extensions() -> List[dict]:
    """Return info for all registered extensions (including i18n fields)."""
    result = []
    for eid, reg in _ext_registry.items():
        mf = reg["manifest"]
        result.append({
            "id": eid,
            "name": mf.get("name", eid),
            "name_zh": mf.get("name_zh", ""),
            "version": mf.get("version", "?"),
            "type": mf.get("type", "python"),
            "description": mf.get("description", ""),
            "description_zh": mf.get("description_zh", ""),
            "author": mf.get("author", "?"),
            "enabled": reg.get("enabled", True),
            "loaded": reg.get("loaded", False),
        })
    return result


def get_extension(ext_id: str) -> Optional[dict]:
    """Get extension info by id (includes i18n fields)."""
    reg = _ext_registry.get(ext_id)
    if reg is None:
        return None
    mf = reg["manifest"]
    return {
        "id": ext_id,
        "name": mf.get("name", ext_id),
        "name_zh": mf.get("name_zh", ""),
        "version": mf.get("version", "?"),
        "type": mf.get("type", "python"),
        "description": mf.get("description", ""),
        "description_zh": mf.get("description_zh", ""),
        "author": mf.get("author", "?"),
        "enabled": reg.get("enabled", True),
        "loaded": reg.get("loaded", False),
    }


def launch_extension(ext_id: str, **kwargs):
    """Launch a general-purpose Python extension."""
    reg = _ext_registry.get(ext_id)
    if reg is None:
        return

    mf = reg["manifest"]
    entry = mf.get("entry", "__init__.py")
    mod_name = entry.rsplit(".", 1)[0]
    pkg_path = reg["path"]

    # Add extension path to sys.path if not there
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)

    try:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        mod = importlib.import_module(mod_name)

        if hasattr(mod, "launch"):
            mod.launch(**kwargs)
    except Exception as e:
        _log.error("Failed to launch %s: %s", ext_id, e)
        import traceback
        traceback.print_exc()


def pack_extension(ext_id: str, output_path: str) -> bool:
    """Pack an extension directory into a .lutx (ZIP) file.

    Returns True on success.
    """
    reg = _ext_registry.get(ext_id)
    if reg is None:
        return False

    import zipfile
    ext_path = reg["path"]

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(ext_path):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, ext_path)
                zf.write(full, rel)
    return True


def unpack_extension(lutx_path: str) -> Optional[str]:
    """Unpack a .lutx file into the extensions directory.

    Re-scans the registry after unpacking.  Returns the extension
    id on success, None on failure.
    """
    import zipfile

    if not os.path.isfile(lutx_path):
        return None

    ext_name = os.path.splitext(os.path.basename(lutx_path))[0]
    target = os.path.join(ext_dir(), ext_name)

    try:
        with zipfile.ZipFile(lutx_path, 'r') as zf:
            zf.extractall(target)
    except Exception:
        return None

    # Re-scan to register newly imported extension
    scan()
    return ext_name


# Auto-scan on import
scan()
