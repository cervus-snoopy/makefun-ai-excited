#!/usr/bin/env python3
"""Phoenix Ignition — ai-excited-01 entry.

A fully procedural, deterministic program (Python 3.13 stdlib only, no
network, no assets, no fonts) that paints one 1024x1024 image:
a firebird bursting out of a supernova sunrise over a glittering sea,
with fireworks, stars and confetti. The image is written to
/output/entry.png (or $OUTPUT_PATH when set, for local testing).

Determinism: every random choice comes from random.Random(20261116);
the PNG encoder is fixed (filter 0, zlib level 9, no ancillary chunks),
so two runs write byte-identical files.
"""

import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
SEED = 20261116
HORIZON = 700  # y of the sea line


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, r, g, b, a=1.0, add=False):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._idx(x, y)
        buf = self.buf
        if add:
            buf[i] = min(255, buf[i] + int(r * a))
            buf[i + 1] = min(255, buf[i + 1] + int(g * a))
            buf[i + 2] = min(255, buf[i + 2] + int(b * a))
        else:
            ia = 1.0 - a
            buf[i] = int(r * a + buf[i] * ia)
            buf[i + 1] = int(g * a + buf[i + 1] * ia)
            buf[i + 2] = int(b * a + buf[i + 2] * ia)

    def disc(self, cx, cy, rad, color, a=1.0, soft=False, add=False):
        """Filled circle; soft=True fades alpha to 0 at the rim."""
        r, g, b = color
        rad = float(rad)
        x0 = max(0, int(cx - rad - 1))
        x1 = min(self.w - 1, int(cx + rad + 1))
        y0 = max(0, int(cy - rad - 1))
        y1 = min(self.h - 1, int(cy + rad + 1))
        rr = rad * rad
        for y in range(y0, y1 + 1):
            dy = y - cy
            dx = math.sqrt(max(0.0, rr - dy * dy)) if abs(dy) <= rad else 0.0
            xa = max(x0, int(cx - dx))
            xb = min(x1, int(cx + dx))
            for x in range(xa, xb + 1):
                if soft:
                    d = math.sqrt((x - cx) ** 2 + dy * dy) / rad
                    aa = a * max(0.0, 1.0 - d) ** 2
                    if aa <= 0.01:
                        continue
                else:
                    aa = a
                self.set(x, y, r, g, b, aa, add)

    def glow(self, cx, cy, rad, color, a=0.5):
        """Big soft additive halo."""
        self.disc(cx, cy, rad, color, a, soft=True, add=True)

    def ellipse_rot(self, cx, cy, rx, ry, deg, color, a=1.0, add=False):
        r, g, b = color
        th = math.radians(deg)
        c, s = math.cos(th), math.sin(th)
        ext = max(rx, ry)
        x0 = max(0, int(cx - ext - 1))
        x1 = min(self.w - 1, int(cx + ext + 1))
        y0 = max(0, int(cy - ext - 1))
        y1 = min(self.h - 1, int(cy + ext + 1))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                dx, dy = x - cx, y - cy
                u = (dx * c + dy * s) / rx
                v = (-dx * s + dy * c) / ry
                d2 = u * u + v * v
                if d2 <= 1.0:
                    aa = a if d2 <= 0.85 else a * (1.0 - d2) / 0.15
                    self.set(x, y, r, g, b, max(0.0, min(1.0, aa)), add)

    def poly(self, pts, color, a=1.0, add=False):
        """Scanline polygon fill."""
        r, g, b = color
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(self.h - 1, int(max(ys)))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(xs[k]))
                xb = min(self.w - 1, int(xs[k + 1]))
                for x in range(xa, xb + 1):
                    self.set(x, y, r, g, b, a, add)

    def line(self, x0, y0, x1, y1, w, color, a=1.0, add=False):
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(dist / max(1.0, w * 0.5)))
        rad = w / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                      rad, color, a, soft=False, add=add)

    def sparkle(self, x, y, r, color, a=1.0):
        """Four-point star glint."""
        self.poly([(x - r, y), (x, y - r * 0.28), (x + r, y),
                   (x, y + r * 0.28)], color, a, add=True)
        self.poly([(x, y - r), (x + r * 0.28, y), (x, y + r),
                   (x - r * 0.28, y)], color, a, add=True)
        self.disc(x, y, r * 0.22, (255, 255, 255), a, add=True)

    def vgrad(self, stops):
        """Vertical gradient; stops = [(y, (r,g,b)), ...] sorted by y."""
        for y in range(self.h):
            for i in range(len(stops) - 1):
                y0, c0 = stops[i]
                y1, c1 = stops[i + 1]
                if y0 <= y <= y1:
                    t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
                    r = int(c0[0] + (c1[0] - c0[0]) * t)
                    g = int(c0[1] + (c1[1] - c0[1]) * t)
                    b = int(c0[2] + (c1[2] - c0[2]) * t)
                    break
            else:
                r, g, b = stops[-1][1]
            base = y * self.w * 3
            row = bytes((r, g, b)) * self.w
            self.buf[base:base + self.w * 3] = row


# ---------------------------------------------------------------- helpers
def lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


# ---------------------------------------------------------------- scene
def draw_sky(cv, rng):
    cv.vgrad([(0, (10, 5, 38)), (320, (52, 12, 88)),
              (580, (150, 30, 92)), (HORIZON, (255, 112, 38))])
    # stars in the upper sky
    for _ in range(240):
        x = rng.uniform(0, W)
        y = rng.uniform(0, 520)
        br = rng.uniform(0.25, 1.0)
        s = rng.uniform(0.6, 1.9)
        cv.disc(x, y, s, (255, 244, 214), br, add=True)
    for _ in range(26):
        x = rng.uniform(40, W - 40)
        y = rng.uniform(20, 420)
        cv.sparkle(x, y, rng.uniform(4, 9), (255, 250, 230),
                   rng.uniform(0.35, 0.8))


def draw_sun(cv, rng, sx=680, sy=706):
    # halo + rays first (behind the disc)
    cv.glow(sx, sy - 40, 430, (255, 120, 40), 0.55)
    cv.glow(sx, sy - 40, 260, (255, 170, 60), 0.6)
    for k in range(14):
        ang = math.radians(-180 + k * (180.0 / 14) + rng.uniform(-4, 4))
        length = rng.uniform(300, 460)
        wdt = rng.uniform(10, 26)
        ex, ey = sx + math.cos(ang) * length, sy + math.sin(ang) * length
        # wedge as a thin triangle
        perp = ang + math.pi / 2
        bx, by = sx + math.cos(perp) * wdt, sy + math.sin(perp) * wdt
        cx2, cy2 = sx - math.cos(perp) * wdt, sy - math.sin(perp) * wdt
        cv.poly([(bx, by), (cx2, cy2), (ex, ey)], (255, 190, 90), 0.10, add=True)
    # disc: layered
    cv.disc(sx, sy, 168, (255, 96, 26), 1.0)
    cv.disc(sx, sy, 142, (255, 158, 52), 1.0)
    cv.disc(sx, sy, 112, (255, 204, 92), 1.0)
    cv.disc(sx, sy, 78, (255, 236, 170), 1.0)
    cv.disc(sx, sy, 46, (255, 250, 220), 1.0)


def draw_firework(cv, rng, cx, cy, color, rays=30, reach=130):
    cv.glow(cx, cy, reach * 0.9, color, 0.35)
    cv.disc(cx, cy, 7, (255, 255, 255), 1.0)
    for _ in range(rays):
        ang = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(reach * 0.45, reach)
        ex, ey = cx + math.cos(ang) * ln, cy + math.sin(ang) * ln
        cv.line(cx, cy, ex, ey, rng.uniform(1.6, 3.2), color,
                rng.uniform(0.55, 0.95), add=True)
        cv.disc(ex, ey, rng.uniform(2.5, 5.5), color, 0.9, add=True)
        cv.sparkle(ex, ey, rng.uniform(3, 7), (255, 255, 255), 0.5)
    for _ in range(14):
        ang = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(reach * 0.2, reach * 0.7)
        cv.disc(cx + math.cos(ang) * ln, cy + math.sin(ang) * ln,
                rng.uniform(1.5, 3.0), (255, 255, 255), 0.8, add=True)


def draw_ocean(cv, rng):
    # sea body
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        c = lerp((24, 66, 96), (5, 16, 40), t)
        base = y * W * 3
        cv.buf[base:base + W * 3] = bytes(c) * W
    # sun glitter path on the water (under the sun at x=680)
    for yy in range(HORIZON + 12, H - 6, 13):
        t = (yy - HORIZON) / (H - HORIZON)
        half = 26 + t * 150
        for _ in range(6):
            x = 680 + rng.uniform(-half, half)
            ln = rng.uniform(10, 42) * (0.5 + t)
            col = (255, 190 + int(40 * rng.random()), 80)
            cv.line(x - ln / 2, yy, x + ln / 2, yy,
                    rng.uniform(2.0, 4.5), col,
                    rng.uniform(0.25, 0.75), add=True)
    # wave crests
    for k in range(6):
        yb = HORIZON + 34 + k * 46
        amp = 9 + k * 2
        pts = []
        for x in range(0, W + 32, 32):
            pts.append((x, yb + amp * math.sin(x / 95.0 + k * 1.7)))
        for i in range(len(pts) - 1):
            cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                    4.0, (46, 138, 168), 0.42, add=True)
            cv.line(pts[i][0], pts[i][1] - 4, pts[i + 1][0],
                    pts[i + 1][1] - 4, 2.0, (180, 232, 244), 0.38, add=True)


def draw_phoenix(cv, rng):
    """Side-profile phoenix in flight, climbing up-right toward the sun.

    Order: far wing (dark, behind) -> tail ribbons -> near wing (bright,
    raised) -> body -> head in profile. The bird flies from lower-left
    to upper-right on a diagonal, so the silhouette reads as a bird,
    not a symmetric flower.
    """
    # halo behind the bird
    cv.glow(440, 400, 300, (255, 150, 50), 0.45)
    cv.glow(440, 400, 170, (255, 210, 90), 0.5)

    def feather_fan(shoulder, a0, a1, count, dist, lmin, lmax,
                    width, col, core):
        """Fan of long rotated-ellipse feathers from one shoulder."""
        for i in range(count):
            t = i / (count - 1) if count > 1 else 0.5
            ang = a0 + (a1 - a0) * t
            rad = math.radians(ang)
            fx = shoulder[0] + math.cos(rad) * dist
            fy = shoulder[1] + math.sin(rad) * dist
            ln = lmin + (lmax - lmin) * (0.25 + 0.75 * abs(t - 0.5) * 2)
            cv.ellipse_rot(fx, fy, ln / 2, width, ang, col, 0.96)
            cv.ellipse_rot(fx, fy, ln / 2 * 0.70, width * 0.42, ang,
                           core, 0.8, add=True)

    # ---- far wing: darker, sweeping up-right behind the body ----
    feather_fan((452, 396), -112, -58, 8, 118, 110, 190, 15,
                (176, 34, 20), (255, 150, 40))

    # ---- tail ribbons: S-curves trailing down-left ----
    # Starts fanned across the rear of the body (no solid wedge), each
    # ribbon its own curve; colour runs orange -> deep red along length.
    tail_cols = [(255, 160, 40), (238, 84, 24), (198, 36, 22),
                 (150, 18, 20)]
    ribbons = [
        ((404, 452), (300, 540), (210, 650), (158, 736)),
        ((424, 466), (326, 580), (248, 700), (200, 796)),
        ((444, 478), (352, 612), (292, 732), (258, 822)),
        ((462, 488), (378, 632), (338, 744), (322, 816)),
        ((478, 496), (402, 640), (382, 736), (378, 788)),
    ]
    for (p0, p1, p2, p3) in ribbons:
        steps = 52
        for i in range(steps + 1):
            t = i / steps
            # cubic bezier
            u = 1.0 - t
            x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
                 + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
            y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
                 + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
            rad = 14.0 * (1.0 - t * 0.78)
            col = tail_cols[min(3, int(t * 4))]
            cv.disc(x, y, rad, col, 0.95)
            if i % 3 == 0:
                cv.disc(x, y, rad * 0.45, (255, 226, 120), 0.7, add=True)

    # ---- near wing: big, raised, sweeping up-left ----
    feather_fan((438, 402), -172, -102, 10, 132, 130, 250, 19,
                (255, 140, 26), (255, 226, 120))
    feather_fan((438, 402), -168, -108, 7, 96, 90, 170, 15,
                (255, 206, 80), (255, 240, 160))

    # ---- body: elongated flame ellipse, nose up-right ----
    for rx, ry, col in [(104, 52, (198, 36, 22)), (88, 44, (238, 96, 22)),
                        (68, 34, (255, 164, 44)), (46, 24, (255, 220, 96))]:
        cv.ellipse_rot(452, 436, rx, ry, -28, col, 0.98)
    cv.ellipse_rot(470, 424, 30, 16, -28, (255, 244, 190), 0.9, add=True)

    # ---- head in profile, facing up-right ----
    cv.disc(548, 366, 40, (226, 52, 22), 1.0)
    cv.disc(548, 366, 31, (255, 150, 34), 1.0)
    cv.disc(548, 364, 20, (255, 208, 90), 1.0)
    # crest: three flame tongues swept back (pointing down-left)
    for dx, dy, hgt, wd in [(-14, -30, 46, 11), (-26, -16, 56, 12),
                            (-32, 0, 48, 11)]:
        cv.poly([(548 + dx - wd, 366 + dy), (548 + dx + wd, 366 + dy),
                 (548 + dx - hgt * 0.55, 366 + dy - hgt * 0.45)],
                (255, 170, 40), 0.98)
    # beak: open, pointing up-right
    cv.poly([(572, 344), (600, 330), (580, 366)], (255, 196, 60), 1.0)
    cv.poly([(576, 350), (592, 342), (580, 358)], (120, 20, 10), 1.0)
    # eye (profile: one eye)
    cv.disc(556, 356, 9, (255, 255, 255), 1.0)
    cv.disc(557, 356, 5, (20, 8, 8), 1.0)
    cv.disc(555, 354, 2, (255, 255, 255), 1.0)

    # sparks around the bird
    for _ in range(70):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(150, 330)
        x = 440 + math.cos(ang) * rr * 1.15
        y = 400 + math.sin(ang) * rr * 0.8
        if 60 < y < 900:
            cv.sparkle(x, y, rng.uniform(2.5, 6), (255, 214, 110),
                       rng.uniform(0.4, 0.9))


def draw_confetti(cv, rng):
    palette = [(255, 90, 90), (255, 210, 80), (90, 240, 255),
               (255, 90, 200), (140, 255, 140), (255, 255, 255)]
    for _ in range(130):
        x = rng.uniform(10, W - 10)
        y = rng.uniform(10, H - 10)
        # keep the bird's face readable
        if abs(x - 548) < 75 and 315 < y < 415:
            continue
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(5, 11)
        wd = rng.uniform(2.5, 4.5)
        c, s = math.cos(ang), math.sin(ang)
        dx, dy = c * ln / 2, s * ln / 2
        px, py = -s * wd / 2, c * wd / 2
        col = palette[rng.randrange(len(palette))]
        cv.poly([(x - dx + px, y - dy + py), (x + dx + px, y + dy + py),
                 (x + dx - px, y + dy - py), (x - dx - px, y - dy - py)],
                col, rng.uniform(0.6, 0.95), add=True)


def render():
    rng = random.Random(SEED)
    cv = Canvas(W, H)
    draw_sky(cv, rng)
    draw_sun(cv, rng)
    draw_firework(cv, rng, 208, 228, (90, 235, 255))
    draw_firework(cv, rng, 836, 186, (255, 80, 205))
    draw_firework(cv, rng, 884, 420, (255, 208, 80), rays=24, reach=100)
    draw_ocean(cv, rng)
    draw_phoenix(cv, rng)
    draw_confetti(cv, rng)
    return cv


# ---------------------------------------------------------------- PNG out
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: none
        raw += cv.buf[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = os.environ.get("OUTPUT_PATH", "/output/entry.png")
    cv = render()
    n = write_png(cv, out)
    print(f"wrote {out} ({n} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
