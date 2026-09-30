"""Close remaining unrouted connections with a simple 2-layer grid A* router.
run: $KICAD_PY tools/fixroute.py board.kicad_pcb   (see Makefile)
"""
import sys, math, heapq
import numpy as np
import pcbnew


def pip(poly, P):
    x = P[:, 0]; y = P[:, 1]
    inside = np.zeros(len(P), bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]; x2, y2 = poly[(k + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        inside ^= cond & (x < xi)
    return inside

GRID = 0.2          # mm
TW = 0.25           # track width
CLR = 0.22          # clearance used for routing (a bit above rule 0.2)
VIA_D, VIA_H = 0.6, 0.3
EDGE_CLR = 0.3
MM = pcbnew.FromMM
TOMM = pcbnew.ToMM

path = sys.argv[1]
b = pcbnew.LoadBoard(path)
layers = [pcbnew.F_Cu, pcbnew.B_Cu]
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = TOMM(bb.GetLeft()) - 1, TOMM(bb.GetTop()) - 1
NX = int((TOMM(bb.GetWidth()) + 2) / GRID) + 1
NY = int((TOMM(bb.GetHeight()) + 2) / GRID) + 1
gx = X0 + np.arange(NX) * GRID
gy = Y0 + np.arange(NY) * GRID
GXX, GYY = np.meshgrid(gx, gy, indexing="ij")
PTS = np.column_stack([GXX.ravel(), GYY.ravel()])


def raster(polyset):
    m = np.zeros(NX * NY, bool)
    for i in range(polyset.OutlineCount()):
        ol = polyset.Outline(i)
        pts = [(TOMM(ol.CPoint(j).x), TOMM(ol.CPoint(j).y)) for j in range(ol.PointCount())]
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        sel = (PTS[:, 0] >= min(xs)) & (PTS[:, 0] <= max(xs)) & (PTS[:, 1] >= min(ys)) & (PTS[:, 1] <= max(ys))
        idx = np.nonzero(sel)[0]
        if len(idx):
            inside = pip(pts, PTS[idx])
            m[idx[inside]] = True
        for h in range(polyset.HoleCount(i)):
            hl = polyset.Hole(i, h)
            hp = [(TOMM(hl.CPoint(j).x), TOMM(hl.CPoint(j).y)) for j in range(hl.PointCount())]
            hx = [q[0] for q in hp]; hy = [q[1] for q in hp]
            sel = (PTS[:, 0] >= min(hx)) & (PTS[:, 0] <= max(hx)) & (PTS[:, 1] >= min(hy)) & (PTS[:, 1] <= max(hy))
            idx = np.nonzero(sel)[0]
            if len(idx):
                m[idx[pip(hp, PTS[idx])]] = False
    return m.reshape(NX, NY)


def item_mask(item, layer, inflate):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, MM(inflate), MM(0.01), pcbnew.ERROR_OUTSIDE)
    return raster(ps)


# board area (inside edge minus clearance)
edge = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(edge)
inside = raster(edge)
# erode by edge clearance + half track: approximate with binary erosion
k = int(math.ceil((EDGE_CLR + TW / 2) / GRID))
er = inside.copy()
for dx in range(-k, k + 1):
    for dy in range(-k, k + 1):
        if dx * dx + dy * dy <= k * k:
            er &= np.roll(np.roll(inside, dx, 0), dy, 1)
# NPTH / edge cuts inside footprints: rasterized as board holes via outline -> already excluded by GetBoardPolygonOutlines holes?
allowed_base = er


def net_obstacles(netcode):
    obs = {l: np.zeros((NX, NY), bool) for l in layers}
    infl = CLR + TW / 2
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in layers:
                if p.IsOnLayer(l) and (p.GetNetCode() != netcode or p.GetNetCode() == 0):
                    extra = 0.1 if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 0.0   # hole clearance 0.25 > 0.2
                    obs[l] |= item_mask(p, l, infl + extra)
    for t in b.GetTracks():
        if t.GetNetCode() == netcode:
            continue
        for l in layers:
            if t.IsOnLayer(l):
                obs[l] |= item_mask(t, l, infl)
    return obs


def islands(netcode):
    items = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == netcode:
                items.append(p)
    for t in b.GetTracks():
        if t.GetNetCode() == netcode:
            items.append(t)
    parent = list(range(len(items)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, c = items[i], items[j]
            common = [l for l in layers if a.IsOnLayer(l) and c.IsOnLayer(l)]
            for l in common:
                sa, sc = a.GetEffectiveShape(l), c.GetEffectiveShape(l)
                if sa.Collide(sc, 0):
                    parent[f(i)] = f(j); break
    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(f(i), []).append(it)
    return list(groups.values())


def anchor_points(group):
    pts = []
    for it in group:
        if isinstance(it, pcbnew.PAD):
            q = it.GetPosition()
            pts.append((TOMM(q.x), TOMM(q.y), [l for l in layers if it.IsOnLayer(l)]))
        else:
            for q in (it.GetStart(), it.GetEnd()):
                pts.append((TOMM(q.x), TOMM(q.y), [l for l in layers if it.IsOnLayer(l)]))
    return pts


def cell(x, y):
    return int(round((x - X0) / GRID)), int(round((y - Y0) / GRID))


def astar(starts, goals, allowed):
    """starts/goals: list of (i,j,layerIndex). allowed: dict li-> bool grid"""
    goalset = set(goals)
    gi = np.array([g[0] for g in goals]); gj = np.array([g[1] for g in goals])

    def h(i, j):
        return float(np.min(np.hypot(gi - i, gj - j)))
    openh = []
    came = {}
    cost = {}
    for s in starts:
        cost[s] = 0.0
        heapq.heappush(openh, (h(s[0], s[1]), s))
    via_cost = 12.0
    nb = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    while openh:
        _, cur = heapq.heappop(openh)
        if cur in goalset:
            pathl = [cur]
            while cur in came:
                cur = came[cur]; pathl.append(cur)
            return pathl[::-1]
        i, j, li = cur
        cands = [(i + di, j + dj, li, c) for di, dj, c in nb]
        cands.append((i, j, 1 - li, via_cost))
        for ni, nj, nl, c in cands:
            if not (0 <= ni < NX and 0 <= nj < NY):
                continue
            if not allowed[nl][ni, nj] and (ni, nj, nl) not in goalset:
                continue
            if nl != li and not (allowed_via[ni, nj]):
                continue
            nc = cost[cur] + c
            n = (ni, nj, nl)
            if nc < cost.get(n, 1e18):
                cost[n] = nc; came[n] = cur
                heapq.heappush(openh, (nc + h(ni, nj), n))
    return None


def add_path(p, netcode):
    net = b.FindNet(netcode) if False else b.GetNetInfo().GetNetItem(netcode)
    # compress straight runs
    pts = [(X0 + i * GRID, Y0 + j * GRID, layers[l]) for i, j, l in p]
    segs = []
    k = 0
    while k < len(pts) - 1:
        a = pts[k]
        if pts[k + 1][2] != a[2]:
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
            v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); v.SetNet(net)
            b.Add(v)
            k += 1
            continue
        m = k + 1
        d = (round(pts[m][0] - a[0], 4), round(pts[m][1] - a[1], 4))
        while m + 1 < len(pts) and pts[m + 1][2] == a[2] and (round(pts[m + 1][0] - pts[m][0], 4), round(pts[m + 1][1] - pts[m][1], 4)) == d:
            m += 1
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(pts[m][0]), MM(pts[m][1])))
        t.SetWidth(MM(TW)); t.SetLayer(a[2]); t.SetNet(net)
        b.Add(t)
        k = m


fixed = 0
for netcode in range(1, b.GetNetCount()):
    ni = b.GetNetInfo().GetNetItem(netcode)
    if ni is None or ni.GetNetname() in ("GND", ""):
        continue
    for _ in range(10):
        gs = islands(netcode)
        if len(gs) <= 1:
            break
        print("net", ni.GetNetname(), "islands", len(gs))
        obs = net_obstacles(netcode)
        allowed = [allowed_base & ~obs[l] for l in layers]
        # via allowed where both layers free with via radius
        global allowed_via
        vk = int(math.ceil((VIA_D / 2 - TW / 2) / GRID))
        av = allowed[0] & allowed[1]
        allowed_via = av.copy()
        for dx in range(-vk, vk + 1):
            for dy in range(-vk, vk + 1):
                allowed_via &= np.roll(np.roll(av, dx, 0), dy, 1)
        g0 = gs[0]; rest = [it for g in gs[1:] for it in g]
        starts = [(*cell(x, y), layers.index(l)) for x, y, ls in anchor_points(g0) for l in ls]
        goals = [(*cell(x, y), layers.index(l)) for x, y, ls in anchor_points(rest) for l in ls]
        # snap: make anchor cells allowed on their layers
        for i, j, l in starts + goals:
            allowed[l][max(0, i - 1):i + 2, max(0, j - 1):j + 2] = True
        p = astar(starts, goals, allowed)
        if not p:
            print("  no path found"); break
        add_path(p, netcode); fixed += 1
print("added paths", fixed)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)


# ---- ground pads that the pour could not reach -------------------------------
gnd = b.FindNet("GND")
gcode = gnd.GetNetCode()
fill = {l: np.zeros((NX, NY), bool) for l in layers}
MAIN = {}
for z in b.Zones():
    if z.GetNetCode() != gcode:
        continue
    for l in layers:
        if z.IsOnLayer(l):
            fp_ = z.GetFilledPolysList(l)
            areas = [abs(fp_.Outline(i).Area()) for i in range(fp_.OutlineCount())]
            mi = int(np.argmax(areas))
            main = pcbnew.SHAPE_POLY_SET()
            main.AddOutline(fp_.Outline(mi))
            for h in range(fp_.HoleCount(mi)):
                main.AddHole(fp_.Hole(mi, h))
            fill[l] |= raster(main)
            MAIN[l] = fp_.Outline(mi)


def pad_on_pour(p):
    q = p.GetPosition()
    r = max(p.GetSize().x, p.GetSize().y) / 2 + MM(0.1)
    for l in layers:
        if p.IsOnLayer(l) and l in MAIN and MAIN[l].Collide(q, int(r)):
            return True
    return False


def has_track(p):
    for t in b.GetTracks():
        if t.GetNetCode() == gcode and t.GetEffectiveShape(t.GetLayer()).Collide(p.GetEffectiveShape(t.GetLayer()), 0):
            return True
    return False


todo = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gcode and not pad_on_pour(p) and not has_track(p)]
for p in todo:
    print("GND pad off-pour:", p.GetParentFootprint().GetReference(), p.GetNumber())
    obs = net_obstacles(gcode)
    allowed = [allowed_base & ~obs[l] for l in layers]
    vk = int(math.ceil((VIA_D / 2 - TW / 2) / GRID))
    av = allowed[0] & allowed[1]
    allowed_via = av.copy()
    for dx in range(-vk, vk + 1):
        for dy in range(-vk, vk + 1):
            allowed_via &= np.roll(np.roll(av, dx, 0), dy, 1)
    q = p.GetPosition(); sx, sy = cell(TOMM(q.x), TOMM(q.y))
    starts = [(sx, sy, li) for li, l in enumerate(layers) if p.IsOnLayer(l)]
    for i, j, l in starts:
        allowed[l][max(0, i - 1):i + 2, max(0, j - 1):j + 2] = True
    goals = []
    for li, l in enumerate(layers):
        g = fill[l] & allowed[li]
        # keep goals at least 2 cells away from start
        ii, jj = np.nonzero(g)
        far = np.hypot(ii - sx, jj - sy) > 8
        goals += [(int(a), int(c), li) for a, c in zip(ii[far], jj[far])]
    pth = astar(starts, goals, allowed)
    if pth:
        add_path(pth, gcode); print("  connected")
    else:
        print("  no path")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(path, b)
