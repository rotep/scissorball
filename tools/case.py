"""3D-printable case for ScissorBall 36 (FreeCAD scripting).  run: make case
World frame: mm, z up, z=0 = desk (bottom of case).  Hand-local x/y as in layout.py.
The key PCB is tilted (tent + negative tilt); the trackball unit sits level on the floor.
"""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import FreeCAD as App, Part, Mesh, MeshPart
import layout as L

V = App.Vector
import paths
ROOT = paths.ROOT
OUT = paths.CASE
os.makedirs(OUT, exist_ok=True)

# ---------------- parameters ----------------
FLOOR = 1.6            # bottom thickness
PCB_T = 1.6
UNDER_GAP = 1.8        # min clearance under PCB (SOD-123 diodes + trimmed pins)
WALL = 2.4
GAP = 0.5              # PCB edge to wall
LIP = 1.0              # wall top above PCB top
STANDOFF_R = 2.5
PILOT_R = 0.85         # M2 self-tapping pilot
# trackball unit
BALL_R = L.BALL_D / 2
LENS_TO_BALL = 7.2     # breakout lens-side face -> ball bottom (PMW3360 + LM19-LSI, 2.4 mm Z)
BRK_Z = 2.8            # breakout underside height (chip hangs into a floor window)
BRK_W, BRK_H = 32.0, 28.0    # monkeypad PMW3360 breakout, header edge facing +x
LENS_OFF = -1.8        # lens centre relative to breakout centre along x (away from header)
BRK_HOLES = [(-14, -12), (-14, 12), (14, -12), (14, 12)]
CUP_GAP = 1.0          # radial gap ball <-> cup
BEAR_D = 2.5           # ceramic bearing balls
BEAR_POLAR = 55.0      # contact direction, degrees from straight down
TOWER_R = 15.2
BEZEL_H = 3.5
TENT, TILT = L.TENT_DEG, L.TILT_DEG
Z_PCB_MIN = FLOOR + UNDER_GAP

ROT = App.Rotation(V(1, 0, 0), -TILT).multiply(App.Rotation(V(0, 1, 0), TENT))


def xf_point(p, dz):
    q = ROT.multVec(p)
    return V(q.x, q.y, q.z + dz)


def xform(shape, dz):
    s = shape.copy()
    s.transformShape(App.Placement(V(0, 0, 0), ROT).toMatrix())
    s.translate(V(0, 0, dz))
    return s


def outline_face(side, off=0.0):
    pts = json.load(open(paths.OUTLINE))["right"]
    if side == "left":
        pts = json.load(open(paths.OUTLINE))["left"]
    vs = []
    for x, y in pts:
        v = V(x, y, 0)
        if not vs or (v - vs[-1]).Length > 0.05:
            vs.append(v)
    if (vs[0] - vs[-1]).Length < 0.05:
        vs.pop()
    w = Part.makePolygon(vs + [vs[0]])
    f = Part.Face(w)
    if off:
        f = f.makeOffset2D(off, join=0)
    return f


def prism(face, w0, w1):
    f = face.copy()
    f.translate(V(0, 0, w0))
    return f.extrude(V(0, 0, w1 - w0))


def local_box(u0, u1, v0, v1, w0, w1):
    return Part.makeBox(u1 - u0, v1 - v0, w1 - w0, V(u0, v0, w0))


def build(side):
    # PCB-local -> world: find dz so that the lowest PCB-bottom point sits at Z_PCB_MIN
    pcb = outline_face(side)
    tmp = xform(pcb, 0)
    dz = Z_PCB_MIN - tmp.BoundBox.ZMin
    print(side, "dz", round(dz, 2))
    big = 80.0
    outer_l = prism(outline_face(side, GAP + WALL), -big, PCB_T + LIP)
    cav_l = prism(outline_face(side, GAP), -big, big)
    outer = xform(outer_l, dz)
    cav = xform(cav_l, dz)
    halfspace = Part.makeBox(400, 400, 200, V(-200, -200, 0))
    above_floor = Part.makeBox(400, 400, 200, V(-200, -200, FLOOR))
    outer = outer.common(halfspace)
    cav = cav.common(above_floor)

    extra_solid = []
    extra_void = []
    info = {}
    # ---- trackball unit (right) ----
    if side == "right":
        bc = xf_point(V(L.BALL_C[0], L.BALL_C[1], 0), dz)
        cx, cy = bc.x, bc.y
        lens_top = BRK_Z + PCB_T
        cz = lens_top + LENS_TO_BALL + BALL_R
        info.update(ball_center=(round(cx, 2), round(cy, 2), round(cz, 2)), ball_top=round(cz + BALL_R, 2))
        tower_top = cz + 1.5
        tower = Part.makeCylinder(TOWER_R, tower_top, V(cx, cy, 0))
        bx, by = cx - LENS_OFF, cy          # breakout centre
        base = Part.makeBox(BRK_W + 2 * WALL + 1, BRK_H + 2 * WALL + 1, 1, V(bx - BRK_W / 2 - WALL - .5, by - BRK_H / 2 - WALL - .5, 0))
        # pedestal: breakout footprint + walls, up to just under the key plane (cut later by the plane)
        ped_l = None
        ped = Part.makeBox(BRK_W + 2 * WALL + 1, BRK_H + 2 * WALL + 1, tower_top,
                           V(bx - BRK_W / 2 - WALL - .5, by - BRK_H / 2 - WALL - .5, 0))
        ped = ped.makeFillet(5.0, [e for e in ped.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1])
        # clip pedestal by key plane top (so it never pokes above the wall line)
        plane_top = xform(prism(Part.Face(Part.makePolygon([V(-300, -300, 0), V(300, -300, 0), V(300, 300, 0), V(-300, 300, 0), V(-300, -300, 0)])), -big * 3, PCB_T + LIP), dz)
        ped = ped.common(plane_top)
        # ear bosses for the bezel screws
        ears = []
        for az in (-60.0, -120.0):
            ex, ey = cx + 18.0 * math.cos(math.radians(az)), cy + 18.0 * math.sin(math.radians(az))
            ears.append((ex, ey))
            extra_solid.append(Part.makeCylinder(3.2, tower_top, V(ex, ey, 0)))
            extra_void.append(Part.makeCylinder(PILOT_R, 8, V(ex, ey, tower_top - 7.5)))
        extra_solid += [tower, ped]
        # voids: cup, lens window, breakout pocket, chip window, bearing sockets
        cup = Part.makeSphere(BALL_R + CUP_GAP, V(cx, cy, cz))
        cup = cup.fuse(Part.makeCylinder(BALL_R + CUP_GAP, 50, V(cx, cy, cz)))
        extra_void.append(cup)
        extra_void.append(Part.makeBox(18, 18, cz - lens_top, V(cx - 9, cy - 9, lens_top - 0.01)))
        # breakout is inserted from below: pocket open through the floor
        pocket = Part.makeBox(BRK_W + 1.0, BRK_H + 1.0, FLOOR + 4.6 + 0.1, V(bx - BRK_W / 2 - .5, by - BRK_H / 2 - .5, -0.1))
        extra_void.append(pocket)
        # wire channel from pocket toward J2 (+x side, stays inside the tray cavity)
        extra_void.append(Part.makeBox(8, 6, 4.6, V(bx + BRK_W / 2 - 2, by + 7, FLOOR)))
        # datum posts: from pocket ceiling down to the breakout lens-side face (sets lens->ball distance)
        sup = []
        post_holes = []
        info["post_holes"] = post_holes
        for hx, hy in BRK_HOLES:
            px, py = bx + hx, by + hy
            sup.append(Part.makeCylinder(1.7, FLOOR + 4.6 - lens_top + 0.01, V(px, py, lens_top)))
            post_holes.append(Part.makeCylinder(PILOT_R, 6.0, V(px, py, lens_top - 0.01)))       # M2 pilot, screw from below
        info["sup"] = sup
        # bearing sockets
        socks = []
        for k in range(3):
            az = math.radians(90 + 120 * k)
            pol = math.radians(BEAR_POLAR)
            d = V(math.sin(pol) * math.cos(az), math.sin(pol) * math.sin(az), -math.cos(pol))
            c_b = V(cx, cy, cz) + d * (BALL_R + BEAR_D / 2)
            start = V(cx, cy, cz) + d * (BALL_R + CUP_GAP - 0.3)
            depth = (BALL_R + BEAR_D / 2 + BEAR_D / 2 + 0.2) - (BALL_R + CUP_GAP - 0.3)
            socks.append(Part.makeCylinder(BEAR_D / 2 - 0.02, depth, start, d))
        extra_void += socks
        info["cz"] = cz
        info["tower_top"] = tower_top
        info["ears"] = ears
        info["c"] = (cx, cy)

    case = outer
    for s in extra_solid:
        case = case.fuse(s)
    if side == "right":
        tower_keep = Part.makeCylinder(TOWER_R, 200, V(info["c"][0], info["c"][1], -1))
        cav = cav.cut(tower_keep)
    case = case.cut(cav)
    # standoffs
    for hx, hy in L.MOUNT_HOLES[side]:
        so = xform(Part.makeCylinder(STANDOFF_R, big, V(hx, hy, -big)), dz).common(above_floor.fuse(Part.makeBox(400, 400, FLOOR + .01, V(-200, -200, 0))))
        case = case.fuse(so)
        case = case.cut(xform(Part.makeCylinder(PILOT_R, 9.0, V(hx, hy, -7.0)), dz))
    for v in extra_void:
        case = case.cut(v)
    if side == "right":
        for s in info["sup"]:
            case = case.fuse(s)
        for h in info["post_holes"]:
            case = case.cut(h)
    # connector openings (PCB-local boxes)
    m, t = L.MCU, L.TRRS
    usb_v = m["y"] + 23.5 / 2
    op = [local_box(m["x"] - 7.0, m["x"] + 7.0, usb_v - 1.2, usb_v + 12, 0.3, 30),
          local_box(t["x"] - 12, t["x"] + 1.0, t["y"] - 4.8, t["y"] + 4.8, 0.3, 30)]
    for o in op:
        case = case.cut(xform(o, dz))
    case = case.removeSplitter()
    # ---- bezel ----
    bezel = None
    if side == "right":
        cx, cy = info["c"]; cz = info["cz"]; z0 = info["tower_top"]
        ring = Part.makeCylinder(TOWER_R, BEZEL_H, V(cx, cy, z0))
        for ex, ey in info["ears"]:
            ring = ring.fuse(Part.makeCylinder(3.2, BEZEL_H, V(ex, ey, z0)))
            ring = ring.fuse(Part.makeBox(1, 1, 1, V(ex, ey, z0)))
        # join ears to ring with webs
        for ex, ey in info["ears"]:
            dx, dy = ex - cx, ey - cy
            ang = math.degrees(math.atan2(dy, dx))
            web = Part.makeBox(18.0, 5.0, BEZEL_H, V(0, -2.5, 0))
            web.rotate(V(0, 0, 0), V(0, 0, 1), ang)
            web.translate(V(cx, cy, z0))
            ring = ring.fuse(web)
        ring = ring.cut(Part.makeSphere(BALL_R + 0.5, V(cx, cy, cz)))
        ring = ring.cut(Part.makeCylinder(BALL_R - 0.5, 50, V(cx, cy, cz)))   # top opening < ball -> retains ball
        for ex, ey in info["ears"]:
            ring = ring.cut(Part.makeCylinder(1.15, 20, V(ex, ey, z0 - 1)))
            ring = ring.cut(Part.makeCylinder(2.1, 2, V(ex, ey, z0 + BEZEL_H - 1.2)))
        bezel = ring.removeSplitter()
    info["dz"] = dz
    return case, bezel, info


def keycap_tops(side, dz):
    res = {}
    for k in L.keys(side):
        p = xf_point(V(k["x"], k["y"], PCB_T + 6.5), dz)
        res[k["name"]] = round(p.z, 1)
    return res


def export(shape, name):
    shape.exportStep(os.path.join(OUT, name + ".step"))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False)
    mesh.write(os.path.join(OUT, name + ".stl"))
    try:
        mesh.write(os.path.join(OUT, name + ".3mf"))
    except Exception as e:
        print("3mf export failed", e)
    print(name, "volume cm3", round(shape.Volume / 1000, 1), "bbox", [round(v, 1) for v in (shape.BoundBox.XLength, shape.BoundBox.YLength, shape.BoundBox.ZLength)], "valid", shape.isValid())


if __name__ == "__main__":
    summary = {}
    for side in ("right", "left"):
        case, bezel, info = build(side)
        if side == "left":
            case = case.mirror(V(0, 0, 0), V(1, 0, 0))
        export(case, f"scissorball_case_{side}")
        if bezel:
            export(bezel, "scissorball_ball_bezel")
        summary[side] = dict(dz=round(info["dz"], 2), keycap_top_z=keycap_tops(side, info["dz"]))
        if side == "right":
            summary[side].update(ball_center=info["ball_center"], ball_top=info["ball_top"], tower_top=round(info["tower_top"], 2))
    json.dump(summary, open(os.path.join(paths.BUILD, "case_summary.json"), "w"), indent=1)
    print(json.dumps(summary["right"], indent=0)[:900])
