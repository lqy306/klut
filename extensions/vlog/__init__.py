"""
vlog.py — Panasonic V-Log colorspace extension.

Uses the official V-Log/V-Gamut specification:
  - Decode:  L = 10^((V - cutoff) / slope)  for V >= 0.01
  - Encode:  V = cutoff + slope * log10(L)

where cutoff = 0.00873, slope = 0.2413.
"""

import math

from colorspaces import ColorSpace


class VLog(ColorSpace):
    id = "vlog"
    name = "V-Log"

    # V-Log specification constants
    _cutoff = 0.00873
    _slope = 0.2413

    def to_linear(self, x: float) -> float:
        """V-Log → linear scene light (0–1)."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        if x < 0.01:
            return x / 10.0
        return math.pow(10.0, (x - self._cutoff) / self._slope)

    def from_linear(self, x: float) -> float:
        """Linear scene light → V-Log (0–1)."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        if x < 0.001:
            return x * 10.0
        return self._slope * math.log10(x) + self._cutoff


def load():
    """Extension entry point: register this colorspace."""
    from colorspaces import register, get
    if get("vlog") is None:
        register(VLog())


def unload():
    """Extension teardown: unregister this colorspace."""
    from colorspaces import unregister
    unregister("vlog")
