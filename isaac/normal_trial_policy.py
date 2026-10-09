"""Geometry and outcome criteria for the fixed, simulation-only normal trial."""
import math

PAIRS = (('red_ball', 'zone1'), ('blue_ball', 'zone2'))


def point(value):
    if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError('Invalid point')
    x, y, z = map(float, value)
    if not (-.325 <= x <= .325 and 0 <= y <= .52 and -.002 <= z <= .20):
        raise ValueError('Point outside the calibrated worktable')
    return [x, y, z]


def passed(samples, zones, timestamps):
    """Whole 26 mm radius ball within 55 mm half-width zone, 10 mm margin."""
    if len(samples) < 3 or len(timestamps) != len(samples):
        return False
    if not all(math.isfinite(t) for t in timestamps) or timestamps[-1] - timestamps[-3] < 2:
        return False
    try:
        for ball, _ in PAIRS:
            target = point(zones[ball])
            pts = [point(s[ball]) for s in samples[-3:]]
            if any(abs(p[i] - target[i]) > .019 for p in pts for i in (0, 1)):
                return False
            if any(not .018 <= p[2] <= .034 for p in pts):
                return False
            if any(math.dist(a, b) > .005 for a in pts for b in pts):
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True
