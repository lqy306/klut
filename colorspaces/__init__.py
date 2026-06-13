"""
colorspaces — 色彩空间子系统

内置: Rec.709
扩展: V-Log, S-Log3, LogC (通过扩展系统加载)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
#  Base colorspace interface
# ---------------------------------------------------------------------------

class ColorSpace(ABC):
    """Abstract colorspace — to_linear / from_linear operate on 0–1 floats."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier, e.g. 'rec709', 'vlog'."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name, e.g. 'Rec.709'."""
        ...

    @abstractmethod
    def to_linear(self, x: float) -> float:
        """Decode from display encoding to linear scene light."""
        ...

    @abstractmethod
    def from_linear(self, x: float) -> float:
        """Encode from linear scene light to display encoding."""
        ...


# ---------------------------------------------------------------------------
#  Colorspace registry
# ---------------------------------------------------------------------------

_registry: Dict[str, ColorSpace] = {}


def register(cs: ColorSpace):
    """Register a colorspace."""
    _registry[cs.id] = cs


def unregister(cs_id: str):
    """Unregister a colorspace."""
    _registry.pop(cs_id, None)


def get(cs_id: str) -> Optional[ColorSpace]:
    """Get a registered colorspace by id."""
    return _registry.get(cs_id)


def list_all() -> List[ColorSpace]:
    """Return all registered colorspaces in registration order."""
    return list(_registry.values())


def names() -> List[str]:
    """Return display names of all registered colorspaces."""
    return [cs.name for cs in _registry.values()]


def ids() -> List[str]:
    """Return ids of all registered colorspaces."""
    return list(_registry.keys())


def index_of(cs_id: str) -> int:
    """Return the index of a colorspace in the registry, or -1."""
    try:
        return list(_registry.keys()).index(cs_id)
    except ValueError:
        return -1


def by_index(idx: int) -> Optional[ColorSpace]:
    """Get colorspace by index in the registry."""
    keys = list(_registry.keys())
    if 0 <= idx < len(keys):
        return _registry[keys[idx]]
    return None


# ---------------------------------------------------------------------------
#  Image-level colorspace conversion
# ---------------------------------------------------------------------------

def convert_image(img: 'Image', src_id: str, dst_id: str) -> 'Image':
    """Convert an image between two colorspaces using raw byte processing."""
    if src_id == dst_id or not HAS_PIL:
        return img

    src_cs = get(src_id)
    dst_cs = get(dst_id)
    if src_cs is None or dst_cs is None:
        return img

    img = img.convert("RGB")
    w, h = img.size
    n = w * h

    raw = img.tobytes()
    out = bytearray(n * 3)

    src_to_lin = src_cs.to_linear
    dst_frm_lin = dst_cs.from_linear
    idx = 0

    for _ in range(n):
        r = raw[idx]     / 255.0
        g = raw[idx + 1] / 255.0
        b = raw[idx + 2] / 255.0

        lr = src_to_lin(r)
        lg = src_to_lin(g)
        lb = src_to_lin(b)

        nr = dst_frm_lin(lr)
        ng = dst_frm_lin(lg)
        nb = dst_frm_lin(lb)

        out[idx]     = _clamp(nr)
        out[idx + 1] = _clamp(ng)
        out[idx + 2] = _clamp(nb)
        idx += 3

    return Image.frombuffer("RGB", (w, h), bytes(out))


def _clamp(v: float) -> int:
    """Clamp 0-1 float to 0-255 int."""
    x = int(v * 255.0)
    if x < 0:
        return 0
    if x > 255:
        return 255
    return x


# ---------------------------------------------------------------------------
#  Built-in: Rec.709
# ---------------------------------------------------------------------------

class Rec709(ColorSpace):
    id = "rec709"
    name = "Rec.709"

    def to_linear(self, x: float) -> float:
        if x > 0.04045:
            return ((x + 0.055) / 1.055) ** 2.4
        return x / 12.92

    def from_linear(self, x: float) -> float:
        if x > 0.0031308:
            return 1.055 * (x ** (1.0 / 2.4)) - 0.055
        return 12.92 * x


# Register built-in Rec.709
register(Rec709())
