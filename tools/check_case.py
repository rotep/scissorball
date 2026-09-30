"""Interference checks + preview renders.  run: make check"""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import FreeCAD as App, Part, Mesh, MeshPart
import case as C
import layout as L
import numpy as np

V = App.Vector
import paths
ROOT = C.ROOT


def parts(side, dz):
    """PCB assembly solids in world frame (hand-local, before left mirroring)"""
    out = {}
    pcb = C.prism(C.outline_face(side), 0, C.PCB_T)
    out["pcb"] = C.xform(pcb, dz)
    caps, bodies = [], []
    for k in L.keys(side):
        cap = Part.makeBox(L.CAP, L.CAP, 3.0, V(-L.CAP / 2, -L.CAP / 2, C.PCB_T + 3.1))
        body = Part.makeBox(L.SW_BODY[0], L.SW_BODY[1], 2.0, V(-L.SW_BODY[0] / 2, -L.SW_BODY[1] / 2, C.PCB_T))
        pressed = Part.makeBox(L.CAP, L.CAP, 3.0, V(-L.CAP / 2, -L.CAP / 2, C.PCB_T + 1.1))
        for s, lst in ((cap, caps), (body, bodies), (pressed, caps)):
            s.rotate(V(0, 0, 0), V(0, 0, 1), k["rot"]); s.translate(V(k["x"], k["y"], 0))
            lst.append(C.xform(s, dz))
    out["caps"] = caps
    out["bodies"] = bodies
    m = L.MCU
    mcu = Part.makeBox(23.5, 18, 4.2, V(-11.75, -9, C.PCB_T)).fuse(
        Part.makeBox(9.0, 9.0, 3.3, V(4.5, -4.5, C.PCB_T + 1.0)))   # module + USB-C receptacle overhang (+x before rotation)
    mcu.rotate(V(0, 0, 0), V(0, 0, 1), m["rot"]); mcu.translate(V(m["x"], m["y"], 0))
    out["mcu"] = C.xform(mcu, dz)
    t = L.TRRS
    out["trrs"] = C.xform(Part.makeBox(12.1, 6.1, 5.0, V(t["x"], t["y"] - 3.05, C.PCB_T)), dz)
    # bottom-side components: diodes (1.2 mm) as thin slabs under each switch
    diodes = []
    for k in L.keys(side):
        d = Part.makeBox(1.8, 3.9, 1.3, V(-5.05 - 0.9, -1.9 - 1.95, -1.3))   # rough envelope, local switch frame (y up)
        d.rotate(V(0, 0, 0), V(0, 0, 1), k["rot"]); d.translate(V(k["x"], k["y"], 0))
        diodes.append(C.xform(d, dz))
    out["diodes"] = diodes
    return out


def vol_common(a, b):
    try:
        return a.common(b).Volume
    except Exception:
        return -1


def check(side):
    case, bezel, info = C.build(side)
    dz = info["dz"]
    P = parts(side, dz)
    rep = {}
    rep["pcb"] = round(vol_common(case, P["pcb"]), 2)
    rep["caps"] = round(sum(vol_common(case, c) for c in P["caps"]), 2)
    rep["bodies"] = round(sum(vol_common(case, c) for c in P["bodies"]), 2)
    rep["mcu"] = round(vol_common(case, P["mcu"]), 2)
    rep["trrs"] = round(vol_common(case, P["trrs"]), 2)
    rep["diodes"] = round(sum(vol_common(case, c) for c in P["diodes"]), 2)
    extra = []
    if side == "right":
        cx, cy = info["c"]; cz = info["cz"]
        ball = Part.makeSphere(C.BALL_R, V(cx, cy, cz))
        rep["ball_vs_case"] = round(vol_common(case, ball), 3)
        rep["ball_vs_bezel"] = round(vol_common(bezel, ball), 3)
        rep["ball_vs_caps"] = round(sum(vol_common(ball, c) for c in P["caps"]), 3)
        rep["bezel_vs_caps"] = round(sum(vol_common(bezel, c) for c in P["caps"]), 3)
        rep["bezel_vs_pcb"] = round(vol_common(bezel, P["pcb"]), 3)
        bx = cx - C.LENS_OFF
        brk = Part.makeBox(C.BRK_W, C.BRK_H, C.PCB_T, V(bx - C.BRK_W / 2, cy - C.BRK_H / 2, C.BRK_Z))
        chip = Part.makeBox(16, 12, 2.45, V(cx - 8, cy - 6, C.BRK_Z - 2.45))
        lens = Part.makeBox(16, 11, 4.8, V(cx - 8, cy - 5.5, C.BRK_Z + C.PCB_T))
        comps = Part.makeBox(C.BRK_W - 2, C.BRK_H - 2, 1.6, V(bx - C.BRK_W / 2 + 1, cy - C.BRK_H / 2 + 1, C.BRK_Z + C.PCB_T))
        rep["breakout"] = round(vol_common(case, brk), 2)
        rep["chip"] = round(vol_common(case, chip), 2)
        rep["lens"] = round(vol_common(case, lens), 2)
        for hx, hy in C.BRK_HOLES:   # datum posts sit on the breakout's mounting-hole pads
            comps = comps.cut(Part.makeCylinder(2.3, 10, V(bx + hx, cy + hy, 0)))
        rep["brk_components_top"] = round(vol_common(case, comps.cut(lens)), 2)
        # bearing contact check: distance from ball centre to bearing centres
        rep["ball_bottom_to_lens_face"] = round(cz - C.BALL_R - (C.BRK_Z + C.PCB_T), 2)
        extra = [ball, brk, chip, lens]
    return case, bezel, P, extra, rep


def render(shapes_colors, path, elev=28, azim=-60, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 8), dpi=110)
    fig.subplots_adjust(0, 0, 1, 1)
    ax = fig.add_subplot(111, projection="3d")
    light = np.array([0.3, -0.5, 0.8]); light /= np.linalg.norm(light)
    allp = []; alltris = []; allfc = []
    for shp, col in shapes_colors:
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.4, AngularDeflection=0.5, Relative=False)
        tris = np.array([[list(p) for p in f.Points] for f in m.Facets])
        if len(tris) == 0:
            continue
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-9)
        sh = 0.45 + 0.55 * np.clip(np.abs(n @ light), 0, 1)
        base = np.array(matplotlib.colors.to_rgb(col))
        fc = np.clip(base[None, :] * sh[:, None], 0, 1)
        alltris.append(tris); allfc.append(fc)
        allp.append(tris.reshape(-1, 3))
    pc = Poly3DCollection(np.vstack(alltris), facecolors=np.vstack(allfc), edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)
    P = np.vstack(allp)
    mn, mx = P.min(0), P.max(0)
    c = (mn + mx) / 2; r = (mx - mn).max() / 2 * 0.62
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r * 0.6, c[2] + r * 0.6)
    ax.set_box_aspect((1, 1, 0.6))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    if title:
        ax.set_title(title)
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    reps = {}
    for side in ("right", "left"):
        case, bezel, P, extra, rep = check(side)
        reps[side] = rep
        print(side, rep)
        sc = [(case, "#e9e4da")]
        if bezel:
            sc.append((bezel, "#cfc8b8"))
        sc.append((P["pcb"], "#2e6b3f"))
        for cp in P["caps"][0::2]:
            sc.append((cp, "#3a3a3a"))
        sc.append((P["mcu"], "#3d6db3"))
        sc.append((P["trrs"], "#999999"))
        if extra:
            sc.append((extra[0], "#c0392b"))
        render(sc, os.path.join(paths.IMAGES, f"render_{side}.png"), title=f"ScissorBall 36 – {side} (hand-local, before mirroring)" if side == "left" else "ScissorBall 36 – right")
        if side == "right":
            render(sc, os.path.join(paths.IMAGES, "render_right_front.png"), elev=12, azim=-100)
            render([(case, "#e9e4da")] + ([(e, c) for e, c in zip(extra[1:], ["#1f7a3a", "#222", "#88aadd"])]), os.path.join(paths.IMAGES, "render_right_case_only.png"), elev=55, azim=-70)
    json.dump(reps, open(os.path.join(paths.BUILD, "interference.json"), "w"), indent=1)
