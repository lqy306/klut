"""
slog3.py — Sony S-Log3 colorspace extension.

Uses the official S-Log3 specification:
  a = 0.01125, b = 0.125, c = 0.3466
"""

import math

from colorspaces import ColorSpace


class SLog3(ColorSpace):
    id = "slog3"
    name = "S-Log3"

    _a = 0.01125
    _b = 0.125
    _c = 0.3466

    def to_linear(self, x: float) -> float:
        """S-Log3 → linear scene light."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        if x >= self._a:
            return (math.exp((x - self._b) / self._c) - 1.0) / self._c
        return (x - self._b) / self._c

    def from_linear(self, x: float) -> float:
        """Linear scene light → S-Log3."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        threshold = self._a * self._c + self._b
        if x >= threshold:
            return self._c * math.log(x * self._c + 1.0) + self._b
        return self._c * x + self._b


def load():
    from colorspaces import register, get
    if get("slog3") is None:
        register(SLog3())


def unload():
    from colorspaces import unregister
    unregister("slog3")
