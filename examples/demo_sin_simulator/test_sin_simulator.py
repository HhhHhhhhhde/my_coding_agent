import math

from sin_simulator import sin


def test_sin_known_values():
    cases = [
        0.0,
        math.pi / 6,
        math.pi / 4,
        math.pi / 3,
        math.pi / 2,
        math.pi,
        3 * math.pi / 2,
        2 * math.pi,
        -math.pi / 2,
    ]
    for x in cases:
        assert round(sin(x), 6) == round(math.sin(x), 6), f"sin({x}) failed"


def test_sin_large_angles():
    for x in range(-1000, 1001, 37):
        assert abs(sin(x) - math.sin(x)) < 1e-5, f"sin({x}) failed"
