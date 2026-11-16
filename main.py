#!/usr/bin/env python3
"""Phoenix Ignition — ai-excited-01 entry (rebuilt under recording).

A fully procedural, deterministic picture program (Python 3 stdlib only,
no network, no assets, no fonts) that paints one 1024x1024 image: a
firebird climbing out of a supernova sunrise over a glittering sea,
with fireworks, stars and confetti. Output goes to /output/entry.png
(or $OUTPUT_PATH for local testing).

Every random choice comes from one random.Random(20261116); the PNG
writer is fixed (filter 0, zlib level 9, no ancillary chunks), so two
runs write byte-identical files.
"""

import math
import os
import random
import struct
import zlib

SIZE = 1024
SEED = 20261116
SEA_LINE = 700


# ------------------------------------------------------------------ image
class Img:
    """Tiny RGB framebuffer with alpha-blend and additive pixel ops."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def _at(self, x, y):
        return (y * self.w + x) * 3

    def put(self, x, y, col, alpha=1.0, add=False):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._at(x, y)
        r, g, b = col
        if add:
            self.px[i] = min(255, self.px[i] + int(r * alpha))
            self.px[i + 1] = min(255, self.px[i + 1] + int(g * alpha))
            self.px[i + 2] = min(255, self.px[i + 2] + int(b * alpha))
            return
        inv = 1.0 - alpha
        self.px[i] = int(r * alpha + self.px[i] * inv)
        self.px[i + 1] = int(g * alpha + self.px[i + 1] * inv)
        self.px[i + 2] = int(b * alpha + self.px[i + 2] * inv)

    def ball(self, cx, cy, rad, col, alpha=1.0, soft=False, add=False):
        """Filled circle; soft fades the alpha quadratically to the rim."""
        r, g, b = col
        rad = float(rad)
        x0 = max(0, int(cx - rad - 1))
        x1 = min(self.w - 1, int(cx + rad + 1))
        y0 = max(0, int(cy - rad - 1))
        y1 = min(self.h - 1, int(cy + rad + 1))
        rsq = rad * rad
        for y in range(y0, y1 + 1):
            dy = y - cy
            if abs(dy) > rad:
                continue
            half = math.sqrt(max(0.0, rsq - dy * dy))
            xa = max(x0, int(cx - half))
            xb = min(x1, int(cx + half))
            for x in range(xa, xb + 1):
                if soft:
                    d = math.hypot(x - cx, dy) / rad
                    a = alpha * max(0.0, 1.0 - d) ** 2
                    if a <= 0.01:
                        continue
                else:
                    a = alpha
                self.put(x, y, col, a, add)

    def halo(self, cx, cy, rad, col, alpha=0.5):
        self.ball(cx, cy, rad, col, alpha, soft=True, add=True)

    def rellipse(self, cx, cy, rx, ry, deg, col, alpha=1.0, add=False):
        """Rotated ellipse with a soft rim (fades over the outer 15%)."""
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
                if d2 > 1.0:
                    continue
                a = alpha if d2 <= 0.85 else alpha * (1.0 - d2) / 0.15
                self.put(x, y, col, max(0.0, min(1.0, a)), add)

    def fill_poly(self, pts, col, alpha=1.0, add=False):
        """Scanline polygon fill."""
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(self.h - 1, int(max(ys)))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(xs[k]))
                xb = min(self.w - 1, int(xs[k + 1]))
                for x in range(xa, xb + 1):
                    self.put(x, y, col, alpha, add)

    def seg(self, x0, y0, x1, y1, w, col, alpha=1.0, add=False):
        """Thick line drawn as a chain of discs."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(dist / max(1.0, w * 0.5)))
        rad = w / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.ball(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                      rad, col, alpha, add=add)

    def glint(self, x, y, r, col, alpha=1.0):
        """Four-point star sparkle."""
        self.fill_poly([(x - r, y), (x, y - r * 0.28), (x + r, y),
                        (x, y + r * 0.28)], col, alpha, add=True)
        self.fill_poly([(x, y - r), (x + r * 0.28, y), (x, y + r),
                        (x - r * 0.28, y)], col, alpha, add=True)
        self.ball(x, y, r * 0.22, (255, 255, 255), alpha, add=True)

    def sky(self, stops):
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
            self.px[base:base + self.w * 3] = bytes((r, g, b)) * self.w


def mix(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


# ------------------------------------------------------------------ scene
def paint_sky(img, rng):
    img.sky([(0, (12, 6, 40)), (320, (54, 13, 90)),
             (580, (152, 32, 94)), (SEA_LINE, (255, 114, 40))])
    for _ in range(240):
        x = rng.uniform(0, SIZE)
        y = rng.uniform(0, 520)
        img.ball(x, y, rng.uniform(0.6, 1.9), (255, 244, 214),
                 rng.uniform(0.25, 1.0), add=True)
    for _ in range(26):
        img.glint(rng.uniform(40, SIZE - 40), rng.uniform(20, 420),
                  rng.uniform(4, 9), (255, 250, 230),
                  rng.uniform(0.35, 0.8))


def paint_sun(img, rng, sx=680, sy=710):
    # halo and rays first, behind the disc
    img.halo(sx, sy - 44, 430, (255, 120, 40), 0.55)
    img.halo(sx, sy - 44, 260, (255, 170, 60), 0.6)
    for k in range(14):
        ang = math.radians(-180 + k * (180.0 / 14) + rng.uniform(-4, 4))
        ln = rng.uniform(300, 460)
        wd = rng.uniform(10, 26)
        ex, ey = sx + math.cos(ang) * ln, sy + math.sin(ang) * ln
        perp = ang + math.pi / 2
        bx, by = sx + math.cos(perp) * wd, sy + math.sin(perp) * wd
        cx2, cy2 = sx - math.cos(perp) * wd, sy - math.sin(perp) * wd
        img.fill_poly([(bx, by), (cx2, cy2), (ex, ey)],
                      (255, 190, 90), 0.10, add=True)
    # layered disc, deep orange out to pale core
    for rad, col in [(170, (255, 96, 26)), (144, (255, 158, 52)),
                     (114, (255, 204, 92)), (80, (255, 236, 170)),
                     (48, (255, 250, 220))]:
        img.ball(sx, sy, rad, col, 1.0)


def paint_burst(img, rng, cx, cy, col, rays=30, reach=130):
    img.halo(cx, cy, reach * 0.9, col, 0.35)
    img.ball(cx, cy, 7, (255, 255, 255), 1.0)
    for _ in range(rays):
        ang = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(reach * 0.45, reach)
        ex, ey = cx + math.cos(ang) * ln, cy + math.sin(ang) * ln
        img.seg(cx, cy, ex, ey, rng.uniform(1.6, 3.2), col,
                rng.uniform(0.55, 0.95), add=True)
        img.ball(ex, ey, rng.uniform(2.5, 5.5), col, 0.9, add=True)
        img.glint(ex, ey, rng.uniform(3, 7), (255, 255, 255), 0.5)
    for _ in range(14):
        ang = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(reach * 0.2, reach * 0.7)
        img.ball(cx + math.cos(ang) * ln, cy + math.sin(ang) * ln,
                 rng.uniform(1.5, 3.0), (255, 255, 255), 0.8, add=True)


def paint_sea(img, rng):
    for y in range(SEA_LINE, SIZE):
        t = (y - SEA_LINE) / (SIZE - SEA_LINE)
        c = mix((24, 66, 96), (5, 16, 40), t)
        base = y * SIZE * 3
        img.px[base:base + SIZE * 3] = bytes(c) * SIZE
    # sun glitter path on the water, widening toward the viewer
    for yy in range(SEA_LINE + 12, SIZE - 6, 13):
        t = (yy - SEA_LINE) / (SIZE - SEA_LINE)
        half = 26 + t * 150
        for _ in range(6):
            x = 680 + rng.uniform(-half, half)
            ln = rng.uniform(10, 42) * (0.5 + t)
            col = (255, 190 + int(40 * rng.random()), 80)
            img.seg(x - ln / 2, yy, x + ln / 2, yy,
                    rng.uniform(2.0, 4.5), col,
                    rng.uniform(0.25, 0.75), add=True)
    # wave crests, two parallel strokes each
    for k in range(6):
        yb = SEA_LINE + 34 + k * 46
        amp = 9 + k * 2
        pts = [(x, yb + amp * math.sin(x / 95.0 + k * 1.7))
               for x in range(0, SIZE + 32, 32)]
        for i in range(len(pts) - 1):
            img.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                    4.0, (46, 138, 168), 0.42, add=True)
            img.seg(pts[i][0], pts[i][1] - 4, pts[i + 1][0],
                    pts[i + 1][1] - 4, 2.0, (180, 232, 244), 0.38, add=True)


def paint_phoenix(img, rng):
    """Side-profile phoenix climbing up-right toward the sun.

    Draw order: far wing (dark, behind) -> flowing tail ribbons ->
    near wing (bright, raised) -> body -> head in profile. The bird
    flies lower-left to upper-right, so the silhouette reads as a
    bird, not a symmetric flower.
    """
    img.halo(440, 400, 300, (255, 150, 50), 0.45)
    img.halo(440, 400, 170, (255, 210, 90), 0.5)

    def fan(shoulder, a0, a1, count, reach, short, long, wide, col, core):
        """Fan of long rotated-ellipse feathers from one shoulder."""
        for i in range(count):
            t = i / (count - 1) if count > 1 else 0.5
            ang = a0 + (a1 - a0) * t
            rad = math.radians(ang)
            fx = shoulder[0] + math.cos(rad) * reach
            fy = shoulder[1] + math.sin(rad) * reach
            # middle feathers longest, edges shorter
            ln = short + (long - short) * (0.25 + 0.75 * abs(t - 0.5) * 2)
            img.rellipse(fx, fy, ln / 2, wide, ang, col, 0.96)
            img.rellipse(fx, fy, ln / 2 * 0.70, wide * 0.42, ang,
                         core, 0.8, add=True)

    # ---- far wing: darker, raised higher so it peeks above the near
    # wing instead of hiding behind it ----
    fan((458, 392), -98, -32, 8, 142, 150, 230, 15,
        (150, 20, 18), (255, 150, 40))

    # ---- tail ribbons: each one its own S-curve, not a straight
    # stick. A sine wobble perpendicular to the bezier keeps them
    # flowing like flame; colour runs orange -> deep red along length.
    tail_cols = [(255, 160, 40), (238, 84, 24), (198, 36, 22),
                 (150, 18, 20)]
    ribbons = [
        # (start, ctrl1, ctrl2, end, wobble amplitude, wobble cycles)
        ((404, 452), (290, 520), (230, 640), (150, 720), 26, 1.5),
        ((424, 466), (310, 560), (250, 690), (190, 800), 30, 1.5),
        ((444, 478), (330, 590), (280, 720), (250, 830), 34, 2.0),
        ((462, 488), (350, 610), (320, 730), (315, 820), 30, 2.0),
        ((478, 496), (380, 620), (360, 720), (375, 795), 24, 1.5),
    ]
    for (p0, p1, p2, p3, wob, cyc) in ribbons:
        steps = 56
        # unit normal of the overall ribbon direction, for the wobble
        nx, ny = p3[0] - p0[0], p3[1] - p0[1]
        nl = math.hypot(nx, ny) or 1.0
        nx, ny = -ny / nl, nx / nl
        for i in range(steps + 1):
            t = i / steps
            u = 1.0 - t
            x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
                 + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
            y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
                 + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
            # lateral flame wobble, strongest mid-ribbon, gone at tips
            wob_t = wob * math.sin(t * math.pi * cyc) * math.sin(t * math.pi)
            x += nx * wob_t
            y += ny * wob_t
            rad = 14.0 * (1.0 - t * 0.78)
            col = tail_cols[min(3, int(t * 4))]
            img.ball(x, y, rad, col, 0.95)
            if i % 3 == 0:
                img.ball(x, y, rad * 0.45, (255, 226, 120), 0.7, add=True)
        # ember dots drifting off the ribbon tip
        for _ in range(3):
            ex = p3[0] + rng.uniform(-14, 14)
            ey = p3[1] + rng.uniform(-6, 22)
            img.glint(ex, ey, rng.uniform(2, 4.5), (255, 200, 90),
                      rng.uniform(0.5, 0.9))

    # ---- near wing: big, raised, sweeping up-left ----
    fan((438, 402), -172, -102, 10, 132, 130, 250, 19,
        (255, 140, 26), (255, 226, 120))
    fan((438, 402), -168, -108, 7, 96, 90, 170, 15,
        (255, 206, 80), (255, 240, 160))

    # ---- body: elongated flame ellipse, nose up-right ----
    for rx, ry, col in [(104, 52, (198, 36, 22)), (88, 44, (238, 96, 22)),
                        (68, 34, (255, 164, 44)), (46, 24, (255, 220, 96))]:
        img.rellipse(452, 436, rx, ry, -28, col, 0.98)
    img.rellipse(470, 424, 30, 16, -28, (255, 244, 190), 0.9, add=True)

    # ---- head in profile, facing up-right ----
    img.ball(550, 366, 42, (226, 52, 22), 1.0)
    img.ball(550, 366, 33, (255, 150, 34), 1.0)
    img.ball(550, 364, 21, (255, 208, 90), 1.0)
    # crest: four flame tongues swept back (pointing down-left)
    for dx, dy, hgt, wd in [(-12, -32, 48, 11), (-25, -20, 60, 12),
                            (-33, -4, 52, 11), (-36, 12, 40, 10)]:
        img.fill_poly([(550 + dx - wd, 366 + dy), (550 + dx + wd, 366 + dy),
                       (550 + dx - hgt * 0.55, 366 + dy - hgt * 0.45)],
                      (255, 170, 40), 0.98)
    # beak: open, pointing up-right
    img.fill_poly([(574, 342), (604, 328), (582, 368)], (255, 196, 60), 1.0)
    img.fill_poly([(578, 350), (596, 340), (582, 360)], (120, 20, 10), 1.0)
    # eye (profile: one eye) with a glint
    img.ball(558, 356, 9, (255, 255, 255), 1.0)
    img.ball(559, 356, 5, (20, 8, 8), 1.0)
    img.ball(557, 354, 2, (255, 255, 255), 1.0)

    # sparks around the bird
    for _ in range(70):
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(150, 330)
        x = 440 + math.cos(ang) * rr * 1.15
        y = 400 + math.sin(ang) * rr * 0.8
        if 60 < y < 900:
            img.glint(x, y, rng.uniform(2.5, 6), (255, 214, 110),
                      rng.uniform(0.4, 0.9))


def paint_confetti(img, rng):
    palette = [(255, 90, 90), (255, 210, 80), (90, 240, 255),
               (255, 90, 200), (140, 255, 140), (255, 255, 255)]
    for _ in range(130):
        x = rng.uniform(10, SIZE - 10)
        y = rng.uniform(10, SIZE - 10)
        # keep the bird's face readable
        if abs(x - 550) < 75 and 315 < y < 415:
            continue
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(5, 11)
        wd = rng.uniform(2.5, 4.5)
        c, s = math.cos(ang), math.sin(ang)
        dx, dy = c * ln / 2, s * ln / 2
        px, py = -s * wd / 2, c * wd / 2
        col = palette[rng.randrange(len(palette))]
        img.fill_poly([(x - dx + px, y - dy + py), (x + dx + px, y + dy + py),
                       (x + dx - px, y + dy - py), (x - dx - px, y - dy - py)],
                      col, rng.uniform(0.6, 0.95), add=True)


def paint():
    rng = random.Random(SEED)
    img = Img(SIZE, SIZE)
    paint_sky(img, rng)
    paint_sun(img, rng)
    paint_burst(img, rng, 208, 228, (90, 235, 255))
    paint_burst(img, rng, 836, 186, (255, 80, 205))
    paint_burst(img, rng, 884, 420, (255, 208, 80), rays=24, reach=100)
    paint_sea(img, rng)
    paint_phoenix(img, rng)
    paint_confetti(img, rng)
    return img


# ------------------------------------------------------------------ PNG out
def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(img, path):
    raw = bytearray()
    stride = SIZE * 3
    for y in range(SIZE):
        raw.append(0)  # filter: none
        raw += img.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = os.environ.get("OUTPUT_PATH", "/output/entry.png")
    img = paint()
    n = write_png(img, out)
    print(f"wrote {out} ({n} bytes, {SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
