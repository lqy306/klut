"""
logc.py — ARRI LogC colorspace extension.

Uses the official ARRI LogC EI 800 specification:
  cutoff = 0.385537, slope = 0.247189
  offset = 0.00015262, gain = 0.009975
"""

import math

from colorspaces import ColorSpace


class LogC(ColorSpace):
    id = "logc"
    name = "LogC"

    _cutoff = 0.385537
    _slope = 0.247189
    _offset = 0.00015262
    _gain = 0.009975

    def to_linear(self, x: float) -> float:
        """LogC → linear scene light."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        if x >= 0.0078125:
            return (math.pow(10.0, (x - self._cutoff) / self._slope) - self._offset) / self._gain
        return (x - self._cutoff) / self._slope

    def from_linear(self, x: float) -> float:
        """Linear scene light → LogC."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        linear_val = x * self._gain + self._offset
        if linear_val <= 0.0:
            return self._cutoff + self._slope * x
        return self._cutoff + self._slope * math.log10(linear_val)


def load():
    from colorspaces import register, get
    if get("logc") is None:
        register(LogC())


def unload():
    from colorspaces import unregister
    unregister("logc")
