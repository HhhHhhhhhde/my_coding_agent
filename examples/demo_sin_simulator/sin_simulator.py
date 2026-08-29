# Simulate sin(x) using Taylor series without using built-in sin function.
def sin(a: float) -> float:
    pi = 3.14159265358979323846264338327950288
    two_pi = 2.0 * pi

    # Reduce the angle into [-pi, pi] for faster convergence.
    x = a % two_pi
    if x > pi:
        x -= two_pi
    if x < -pi:
        x += two_pi

    # sin(x) = x - x^3/3! + x^5/5! - x^7/7! + ...
    term = x
    total = x
    for n in range(1, 60):
        term *= -x * x / ((2 * n) * (2 * n + 1))
        total += term
        if abs(term) < 1e-16:
            break

    return round(total, 6)
