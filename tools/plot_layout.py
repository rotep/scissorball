import sys, math, itertools
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
import layout as L
import paths
plt.rcParams["font.family"] = "Noto Sans CJK JP"

LEGEND_R = ["Y", "U", "I", "O", "P", "H", "J", "K", "L", ";", "N", "M", ",", ".", "/"]
LEGEND_L = ["T", "R", "E", "W", "Q", "G", "F", "D", "S", "A", "B", "V", "C", "X", "Z"]


def sat_gap(p, q):
    """min distance between two convex polygons if separated, negative if overlapping (approx via SAT)."""
    best = -1e9
    for poly in (p, q):
        for i in range(len(poly)):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            n = math.hypot(nx, ny); nx /= n; ny /= n
            pa = [x * nx + y * ny for x, y in p]; qa = [x * nx + y * ny for x, y in q]
            g = max(min(qa) - max(pa), min(pa) - max(qa))
            best = max(best, g)
    return best


def check(side):
    ks = L.keys(side)
    caps = {k["name"]: L.rect_corners(k["x"], k["y"], L.CAP, L.CAP, k["rot"]) for k in ks}
    worst = []
    for a, b in itertools.combinations(ks, 2):
        g = sat_gap(caps[a["name"]], caps[b["name"]])
        if g < 1.5:
            worst.append((round(g, 2), a["name"], b["name"]))
    if side == "right":
        bx, by = L.BALL_C
        for k in ks:
            d = min(math.hypot(px - bx, py - by) for px, py in caps[k["name"]])
            # also edge distance approx: sample edges
            pts = caps[k["name"]]
            for i in range(4):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % 4]
                for t in [j / 20 for j in range(21)]:
                    d = min(d, math.hypot(x1 + (x2 - x1) * t - bx, y1 + (y2 - y1) * t - by))
            if d - L.BALL_HOUSING_R < 2.0:
                worst.append((round(d - L.BALL_HOUSING_R, 2), k["name"], "BALL"))
    return sorted(worst)


def draw(ax, side, ox, mirror):
    sx = -1 if mirror else 1
    import json, os
    of = paths.OUTLINE
    if os.path.exists(of):
        pts = json.load(open(of))[side]
        ax.add_patch(Polygon([(ox + sx * x, y) for x, y in pts], closed=True, fc="#2e7d4f22", ec="#2e7d4f", lw=0.7))
    ks = L.keys(side)
    leg = LEGEND_R if side == "right" else LEGEND_L
    for k in ks:
        pts = [(ox + sx * x, y) for x, y in L.rect_corners(k["x"], k["y"], L.CAP, L.CAP, k["rot"])]
        ax.add_patch(Polygon(pts, closed=True, fc="#f4f1ea", ec="#333", lw=0.6))
        body = [(ox + sx * x, y) for x, y in L.rect_corners(k["x"], k["y"], *L.SW_BODY, k["rot"])]
        ax.add_patch(Polygon(body, closed=True, fc="none", ec="#aaa", lw=0.3, ls="--"))
        if k["name"].startswith("K"):
            t = leg[k["row"] * 5 + k["col"]]
        else:
            t = k["name"]
        ax.text(ox + sx * k["x"], k["y"], t, ha="center", va="center", fontsize=7)
    if side == "right":
        bx, by = L.BALL_C
        ax.add_patch(Circle((ox + sx * bx, by), L.BALL_HOUSING_R, fc="none", ec="#999", lw=0.5, ls=":"))
        ax.add_patch(Circle((ox + sx * bx, by), L.BALL_D / 2, fc="#d9534f", ec="#822", lw=0.6, alpha=0.8))
        ax.text(ox + sx * bx, by, "25mm\nball", ha="center", va="center", fontsize=6, color="w")
    m = L.MCU
    pts = [(ox + sx * x, y) for x, y in L.rect_corners(m["x"], m["y"], 23.5, 18, m["rot"])]
    ax.add_patch(Polygon(pts, closed=True, fc="#cfe3f7", ec="#246", lw=0.5))
    ax.text(ox + sx * m["x"], m["y"], "RP2040\nZero", ha="center", va="center", fontsize=5)
    t = L.TRRS
    pts = [(ox + sx * x, y) for x, y in L.rect_corners(t["x"] + 6.05, t["y"], 12.1, 6.1, 0)]
    ax.add_patch(Polygon(pts, closed=True, fc="#e8e8e8", ec="#444", lw=0.5))
    ax.text(ox + sx * t["x"], t["y"], "TRRS", ha="center", va="center", fontsize=5)
    for hx, hy in L.MOUNT_HOLES[side]:
        ax.add_patch(Circle((ox + sx * hx, hy), 1.1, fc="w", ec="k", lw=0.4))


def make(path_png, path_pdf):
    # A4 landscape at true scale
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-148.5, 148.5); ax.set_ylim(-110, 100); ax.set_aspect("equal"); ax.axis("off")
    # left half mirrored, placed left of centre; right half right of centre
    draw(ax, "left", -45, True)
    draw(ax, "right", 45, False)
    ax.plot([-140, -90], [-100, -100], "k-", lw=1)
    ax.text(-115, -97, "50 mm (印刷後に実寸確認)", ha="center", fontsize=7)
    ax.text(0, 92, "ScissorBall 36 – 1:1 layout (A4 landscape, 100% / 実際のサイズで印刷)", ha="center", fontsize=9)
    fig.savefig(path_pdf)
    fig.savefig(path_png, dpi=110)


if __name__ == "__main__":
    for s in ("left", "right"):
        print(s, check(s)[:10])
    make(sys.argv[1], sys.argv[2])


def hole_check(side):
    bad = []
    for hx, hy in L.MOUNT_HOLES[side]:
        for k in L.keys(side):
            pts = L.rect_corners(k["x"], k["y"], L.CAP, L.CAP, k["rot"])
            # distance point->convex polygon (0 if inside)
            import math
            inside = sat_gap(pts, [(hx - .01, hy - .01), (hx + .01, hy - .01), (hx + .01, hy + .01), (hx - .01, hy + .01)]) < 0
            d = 0 if inside else min(
                min(math.hypot(x1 + (x2 - x1) * t / 20 - hx, y1 + (y2 - y1) * t / 20 - hy) for t in range(21))
                for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
            if d < 2.2:
                bad.append((k["name"], (hx, hy), round(d, 2)))
    return bad
