"""Small geometry helpers for limbs."""
import math


def seg_dist(px, py, ax, ay, bx, by):
    """Distance from (px, py) to segment a->b, and the signed side (+ = left of a->b)."""
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    cx, cy = ax + vx * t, ay + vy * t
    side = (vx * (py - ay) - vy * (px - ax))
    L = math.sqrt(L2) or 1.0
    return math.hypot(px - cx, py - cy), side / L


def knee_ik(hx, hy, ax, ay, l1, l2, forward=1):
    """Knee position for a two-bone leg, bending toward +x * forward."""
    dx, dy = ax - hx, ay - hy
    d = math.hypot(dx, dy)
    d = min(d, l1 + l2 - 1e-3)
    if d < 1e-3:
        return hx, hy + l1
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    ux, uy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    mx, my = hx + ux * a, hy + uy * a
    k1 = (mx - uy * h, my + ux * h)
    k2 = (mx + uy * h, my - ux * h)
    return k1 if (k1[0] - k2[0]) * forward > 0 else k2
