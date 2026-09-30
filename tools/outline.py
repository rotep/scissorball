"""Compute PCB outlines (hand-local frame) with FreeCAD 2D booleans -> hardware/pcb/outline.json
run: make outline
"""
import sys, json, math
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import FreeCAD as App, Part
import layout as L
import paths

V = App.Vector


def rect_face(cx, cy, w, h, rot=0):
    pts = [V(x, y, 0) for x, y in L.rect_corners(cx, cy, w, h, rot)]
    return Part.Face(Part.makePolygon(pts + [pts[0]]))


def circ_face(cx, cy, r):
    return Part.Face(Part.Wire(Part.makeCircle(r, V(cx, cy, 0))))


def fuse_all(faces):
    sol = [f.extrude(V(0, 0, 1)) for f in faces]
    s = sol[0].multiFuse(sol[1:]).removeSplitter()
    bottoms = [f for f in s.Faces if abs(f.Surface.Axis.z) > 0.99 and abs(f.CenterOfMass.z) < 1e-6] if s.Faces else []
    bottoms = [f for f in s.Faces if f.BoundBox.ZMax < 1e-6]
    return Part.Compound(bottoms) if len(bottoms) > 1 else bottoms[0]


def build(side):
    fs = []
    for k in L.keys(side):
        fs.append(rect_face(k["x"], k["y"], 17.2, 17.2, k["rot"]))
    m = L.MCU
    fs.append(rect_face(m["x"], m["y"], 23.5 + 1.0, 18 + 2.0, m["rot"]))
    t = L.TRRS
    fs.append(rect_face(t["x"] + 6.6, t["y"], 13.2, 8.0))
    for hx, hy in L.MOUNT_HOLES[side]:
        fs.append(circ_face(hx, hy, 3.2))
    if side == "right":
        h = L.SENSOR_HDR
        fs.append(rect_face(h["x"] + 3.5 * 2.54, h["y"], 8 * 2.54 + 3, 5))
    # closing (fill gaps between islands): dilate each primitive, fuse, erode
    s = fuse_all([f.makeOffset2D(12.0, join=0) for f in fs])
    print(side, "faces after fuse", len(s.Faces))
    s = s.makeOffset2D(-12.0, join=0)
    s = s.makeOffset2D(-3.0, join=0).makeOffset2D(3.0, join=0)
    # cut-outs
    cuts = []
    # USB-C plug zone: board must end flush with the RP2040-Zero edge
    usb_edge = m["y"] + 23.5 / 2
    cuts.append(rect_face(m["x"], usb_edge + 20, 15.0, 40.0))
    # TRRS plug zone: board ends at jack mouth
    cuts.append(rect_face(t["x"] - 20, t["y"], 40.0, 10.0))
    if side == "right":
        bx, by = L.BALL_C
        cuts.append(circ_face(bx, by, L.BALL_HOUSING_R + 1.0))
    sol = s.extrude(V(0, 0, 1))
    for c in cuts:
        sol = sol.cut(c.extrude(V(0, 0, 1)))
    sol = sol.removeSplitter()
    s = Part.Compound([f for f in sol.Faces if f.BoundBox.ZMax < 1e-6])
    faces = s.Faces
    faces.sort(key=lambda f: -f.Area)
    face = faces[0]
    if len(faces) > 1:
        print(side, "WARNING: extra islands", [round(f.Area, 1) for f in faces[1:]])
    w = face.OuterWire
    pts = [(round(p.x, 4), round(p.y, 4)) for p in w.discretize(Deflection=0.02)]
    bb = face.BoundBox
    print(side, "outline pts", len(pts), "bbox", round(bb.XLength, 1), "x", round(bb.YLength, 1), "area", round(face.Area))
    return pts


out = {}
for side in ("left", "right"):
    out[side] = build(side)
json.dump(out, open(paths.OUTLINE, "w"))
