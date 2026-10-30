"""Koordinat yumuşatma: imleç titremesini azaltır."""
import math
from typing import Optional, Tuple

Point = Tuple[float, float]


class ExponentialSmoother:
    """Basit EMA alpha küçük = daha yumuşak ama daha gecikmeli."""

    def __init__(self, alpha: float = 0.4):
        self.alpha = alpha
        self._prev: Optional[Point] = None

    def reset(self) -> None:
        self._prev = None

    def update(self, point: Point) -> Point:
        prev = self._prev
        if prev is None:
            result = point
        else:
            a = self.alpha
            result = (a * point[0] + (1 - a) * prev[0],
                      a * point[1] + (1 - a) * prev[1])
        self._prev = result
        return result


class _LowPass:
    def __init__(self):
        self.y: Optional[float] = None

    def __call__(self, x: float, alpha: float) -> float:
        prev = self.y
        result = x if prev is None else alpha * x + (1 - alpha) * prev
        self.y = result
        return result


class OneEuroFilter:
    """One Euro Filter: durağanken güçlü yumuşatır, hızlı harekette gecikmeyi azaltır.
    min_cutoff: düşük = durgunken daha az titreme.
    beta: yüksek = hızlı harekette daha az gecikme."""

    def __init__(self, freq: float = 60.0, min_cutoff: float = 1.0, beta: float = 0.02, d_cutoff: float = 1.0):
        self.freq = freq
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_x: Optional[float] = None

    def reset(self) -> None:
        self._x, self._dx, self._last_x = _LowPass(), _LowPass(), None

    @staticmethod
    def _alpha(cutoff: float, freq: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau * freq)

    def __call__(self, x: float, freq: Optional[float] = None) -> float:
        f = freq or self.freq
        dx = 0.0 if self._last_x is None else (x - self._last_x) * f
        self._last_x = x
        edx = self._dx(dx, self._alpha(self.d_cutoff, f))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x(x, self._alpha(cutoff, f))


class PointSmoother:
    """(x,y) için iki One Euro filtresi. Lazer kaybolursa reset() çağır"""

    def __init__(self, freq: float = 60.0, min_cutoff: float = 1.0, beta: float = 0.02):
        self._fx = OneEuroFilter(freq, min_cutoff, beta)
        self._fy = OneEuroFilter(freq, min_cutoff, beta)

    def reset(self) -> None:
        self._fx.reset()
        self._fy.reset()

    def update(self, point: Point, freq: Optional[float] = None) -> Point:
        return self._fx(point[0], freq), self._fy(point[1], freq)
    