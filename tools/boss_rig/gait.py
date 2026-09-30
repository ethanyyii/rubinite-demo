"""The Boss's walk as numbers: one side-view gait model that all four directions read.

Units: final px. x = forward from the hip joint, z = up from the ground. Phase p in [0, 1):
the near leg (side view) / the Boss's right leg strikes the ground at p = 0, the other leg
at p = 0.5.

Numbers and where they come from:
  STRIDE 80 px per cycle. The game walks 60 px/s (boss-veltharis §2), so a cycle is 80 combat
      frames (1.33 s, 0.67 s per step): a slow, heavy step. A step is 40 px = 0.25 of the
      height. POSES 20 -> every pose is held 4 combat frames and the planted foot moves back
      4 px per pose = exactly what the game moves the Boss in 4 frames (no sliding,
      animation-review §4.2). The fast approach (120 px/s) plays the same poses 2 frames each.
  STANCE 0.6: each foot is on the ground 60% of the cycle, so both are down for 10% twice a
      cycle (a heavy walk; a run would be < 0.5).
  Leg: hip -> knee 28.8, knee -> ankle 33.8, ankle 16.27 above the sole (the side view's leg:
      hip (143, 350), knee (140, 472), ankle (127, 615), sole 683 in local px, x 0.2356;
      limb.py poses the concept's leg on these joints).
      The foot never reaches further than the leg is long (hip drop DROP keeps the knee
      bent a little in every pose; checked in checks.py).
  DROP: the hips are lowest when both feet are down and highest over the planted foot.
"""
import math

STRIDE = 80.0
POSES = 20
HOLD = 4                 # combat frames per pose at 60 px/s (2 at 120 px/s)
STANCE = 0.6
THIGH = 28.8
SHIN = 33.8
ANKLE_H = 16.27          # ankle above the sole's bottom edge (the standing sprite's ankle row)
HIP_REST = ANKLE_H + THIGH + SHIN      # standing, leg straight: 77.7
HEEL = -10.0             # heel and toe pivot: x relative to the ankle (foot flat). The armoured
                         # boot is rigid: it rolls off its toe tip, so nothing dips under the ground
BALL = 18.0
STRIKE_PITCH = 10.0      # degrees toe-up at heel strike
TOEOFF_PITCH = -25.0     # heel raised at toe-off
LIFT = 6.0               # extra ankle height at mid swing
REACH = STRIDE * STANCE / 2            # 24: where the foot lands ahead of / leaves behind the hip


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


def drop(p):
    """How far the hips are below standing height (px, not rounded): 1 .. 4."""
    mid_double = (STANCE - 0.5) / 2
    return 2.5 + 1.5 * math.cos(4 * math.pi * (p - mid_double))


def hip_z(p):
    return HIP_REST - round(drop(p))


def _stance(phi):
    u = phi / STANCE
    xf = REACH - STRIDE * phi            # the flat foot's ankle, moving back with the ground
    if u < 0.15:                         # heel strike: toe up, pivoting on the heel
        pitch = STRIKE_PITCH * (1 - u / 0.15)
        hx, hz = rot((-HEEL, ANKLE_H), pitch)
        return (xf + HEEL + hx, hz), pitch
    if u < 0.7:                          # foot flat
        return (xf, ANKLE_H), 0.0
    pitch = TOEOFF_PITCH * smooth((u - 0.7) / 0.3)      # heel rises, pivoting on the ball
    bx, bz = rot((-BALL, ANKLE_H), pitch)
    return (xf + BALL + bx, bz), pitch


def foot(phi):
    """One leg at phase phi (0 = its heel strike): (ankle (x, z), foot pitch in degrees,
    + = toe up), on_ground."""
    phi %= 1.0
    if phi < STANCE:
        a, pitch = _stance(phi)
        return a, pitch, True
    v = (phi - STANCE) / (1 - STANCE)
    (x0, z0), p0 = _stance(STANCE - 1e-9)
    (x1, z1), p1 = _stance(0.0)
    s = smooth(v)
    x = x0 + (x1 - x0) * s
    z = z0 + (z1 - z0) * v + LIFT * math.sin(math.pi * v) ** 1.5
    pitch = p0 + (p1 - p0) * smooth((v - 0.15) / 0.85)
    return (x, z), pitch, False


def solve(hip_height, ankle, pitch, down=True):
    """A leg from its hip height, ankle (x, z) and foot pitch: hip, knee (bent forwards), ankle."""
    hip = (0.0, hip_height)
    dx, dz = ankle[0] - hip[0], ankle[1] - hip[1]
    d = math.hypot(dx, dz)
    reach = THIGH + SHIN
    stretched = d > reach + 1e-6
    if d >= reach:                        # pull the ankle in (checks.py: must not happen in the walk)
        ankle = (hip[0] + dx * reach / d, hip[1] + dz * reach / d)
        dx, dz = ankle[0] - hip[0], ankle[1] - hip[1]
        d = reach
    a = (THIGH ** 2 - SHIN ** 2 + d ** 2) / (2 * d)
    h = math.sqrt(max(0.0, THIGH ** 2 - a ** 2))
    ux, uz = dx / d, dz / d
    knee = (hip[0] + ux * a + uz * h, hip[1] + uz * a - ux * h)
    if knee[0] < hip[0] + ux * a:         # pick the solution with the knee in front
        knee = (hip[0] + ux * a - uz * h, hip[1] + uz * a + ux * h)
    return {'hip': hip, 'knee': knee, 'ankle': ankle, 'pitch': pitch, 'down': down, 'stretched': stretched}


def leg(p, other=False):
    """Hip, knee, ankle (x, z) and foot pitch of a leg at cycle phase p (other = the leg that
    strikes at p = 0.5)."""
    phi = (p + (0.5 if other else 0.0)) % 1.0
    ankle, pitch, down = foot(phi)
    L = solve(hip_z(p), ankle, pitch, down)
    L['phi'] = phi
    return L


def standing_leg():
    """The standing pose's leg: straight, under the hip."""
    return solve(HIP_REST, (0.0, ANKLE_H), 0.0)


def phase(i):
    return i / POSES


if __name__ == '__main__':
    for i in range(POSES):
        p = phase(i)
        a, b = leg(p), leg(p, True)
        print('%2d drop %d | near ankle (%6.1f,%5.1f) knee (%5.1f,%5.1f) pitch %5.1f %s | far ankle (%6.1f,%5.1f) %s'
              % (i, round(drop(p)), *a['ankle'], *a['knee'], a['pitch'], 'G' if a['down'] else ' ',
                 *b['ankle'], 'G' if b['down'] else ' '))
