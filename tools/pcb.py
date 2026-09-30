"""Generate KiCad PCBs for both halves.  run: make pcb-left / pcb-right
stage 'place'  -> hardware/pcb/<side>/scissorball_<side>.kicad_pcb (unrouted) + build/*.dsn
stage 'finish' -> import .ses, add ground pours, save
"""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import layout as L

import paths
ROOT = paths.ROOT
LIB = paths.PCB_LIB
KLIB = paths.KICAD_FOOTPRINTS
OX, OY = 150.0, 100.0
MM = pcbnew.FromMM

PINMAP = {  # RP2040-Zero pad -> net
    "GP26": "COL0", "GP27": "COL1", "GP28": "COL2", "GP15": "COL3", "GP14": "COL4",
    "GP5": "ROW0", "GP6": "ROW1", "GP7": "ROW2", "GP8": "ROW3",
    "GP1": "DATA", "5V": "VBUS", "GND": "GND", "3V3": "3V3",
}
PINMAP_RIGHT = {"GP2": "SCK", "GP3": "MOSI", "GP4": "MISO", "GP13": "CS", "GP29": "GND"}
PINMAP_LEFT = {"GP29": "3V3"}
SENSOR_PINS = ["CS", "MISO", "MOSI", "SCK", None, None, "VBUS", "GND"]  # MOTION unused by QMK driver


def to_board(side, x, y):
    sx = -1 if side == "left" else 1
    return OX + sx * x, OY - y


def rot_for(side, r):
    return -r if side == "left" else r


def local_to_board(px, py, dx, dy, deg):
    """footprint-local offset (KiCad y-down) rotated by KiCad orientation deg (CCW on screen)"""
    a = math.radians(deg)
    return px + dx * math.cos(a) + dy * math.sin(a), py - dx * math.sin(a) + dy * math.cos(a)


class Builder:
    def __init__(self, side):
        self.side = side
        self.b = pcbnew.BOARD()
        self.nets = {}
        ds = self.b.GetDesignSettings()
        ds.SetBoardThickness(MM(1.6))
        ds.m_TrackMinWidth = MM(0.2)
        ds.m_MinClearance = MM(0.2)
        ds.m_ViasMinSize = MM(0.6)
        ds.m_MinThroughDrill = MM(0.3)
        ds.m_CopperEdgeClearance = MM(0.2)
        ds.m_MinResolvedSpokes = 1
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetTrackWidth(MM(0.25)); nc.SetClearance(MM(0.2)); nc.SetViaDiameter(MM(0.6)); nc.SetViaDrill(MM(0.3))

    def net(self, name):
        if name is None:
            return None
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def add_fp(self, lib, name, ref, x, y, deg=0.0, back=False, value=None):
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetReference(ref)
        if value:
            fp.SetValue(value)
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fp.SetOrientationDegrees(deg)
        self.b.Add(fp)
        if back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        return fp

    def setpad(self, fp, num, netname):
        for p in fp.Pads():
            if p.GetNumber() == num and netname:
                p.SetNet(self.net(netname))

    def seg(self, a, b, layer=pcbnew.Edge_Cuts, w=0.1):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        s.SetLayer(layer); s.SetWidth(MM(w))
        self.b.Add(s)

    def text(self, t, x, y, layer=pcbnew.F_SilkS, size=1.2, deg=0):
        tx = pcbnew.PCB_TEXT(self.b)
        tx.SetText(t); tx.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        tx.SetLayer(layer); tx.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        tx.SetTextThickness(MM(size * 0.15)); tx.SetTextAngleDegrees(deg)
        if layer in (pcbnew.B_SilkS,):
            tx.SetMirrored(True)
        self.b.Add(tx)

    def build(self):
        side = self.side
        # --- outline
        pts = json.load(open(paths.OUTLINE))[side]
        bp = []
        for x, y in pts:
            q = to_board(side, x, y)
            if not bp or math.hypot(q[0] - bp[-1][0], q[1] - bp[-1][1]) > 0.01:
                bp.append(q)
        if math.hypot(bp[0][0] - bp[-1][0], bp[0][1] - bp[-1][1]) < 0.01:
            bp.pop()
        for i in range(len(bp)):
            self.seg(bp[i], bp[(i + 1) % len(bp)])
        # --- switches + diodes
        for i, k in enumerate(L.keys(side)):
            x, y = to_board(side, k["x"], k["y"])
            deg = rot_for(side, k["rot"])
            ref = f"SW{i + 1}"
            sw = self.add_fp(LIB, "SB_Kailh_PG1425", ref, x, y, deg, value=k["name"])
            dnet = f"D{i + 1}"
            self.setpad(sw, "1", f"COL{k['col']}")
            self.setpad(sw, "2", dnet)
            dx, dy = local_to_board(x, y, -5.05, 1.9, deg)
            d = self.add_fp(KLIB + "/Diode_SMD.pretty", "D_SOD-123", f"D{i + 1}", dx, dy, deg + 90, back=True, value="1N4148W")
            self.setpad(d, "1", f"ROW{k['row']}")   # cathode -> row (COL2ROW)
            self.setpad(d, "2", dnet)
        # --- MCU
        m = L.MCU
        x, y = to_board(side, m["x"], m["y"])
        u = self.add_fp(LIB, "SB_RP2040_Zero", "U1", x, y, -90.0, value="RP2040-Zero")
        pm = dict(PINMAP)
        pm.update(PINMAP_RIGHT if side == "right" else PINMAP_LEFT)
        for p in u.Pads():
            if p.GetNumber() in pm:
                p.SetNet(self.net(pm[p.GetNumber()]))
        # --- TRRS
        t = L.TRRS
        x, y = to_board(side, t["x"], t["y"])
        j = self.add_fp(LIB, "SB_TRRS_PJ-320A", "J1", x, y, 90.0 if side == "right" else -90.0, value="PJ-320A")
        for num, n in (("1", "GND"), ("2", "DATA"), ("3", "VBUS")):
            self.setpad(j, num, n)
        # --- sensor header (right)
        if side == "right":
            h = L.SENSOR_HDR
            x, y = to_board(side, h["x"], h["y"])
            s = self.add_fp(KLIB + "/Connector_PinHeader_2.54mm.pretty", "PinHeader_1x08_P2.54mm_Vertical",
                            "J2", x, y, 90.0, value="PMW3360 breakout")
            for i, n in enumerate(SENSOR_PINS):
                self.setpad(s, str(i + 1), n)
            names = ["CS", "MISO", "MOSI", "SCK", "MOT", "NC", "VCC", "GND"]
            for i, n in enumerate(names):
                self.text(n, x + 2.54 * i, y + 2.6, size=0.8, deg=90)
        # --- mounting holes
        for i, (hx, hy) in enumerate(L.MOUNT_HOLES[side]):
            x, y = to_board(side, hx, hy)
            self.add_fp(KLIB + "/MountingHole.pretty", "MountingHole_2.2mm_M2", f"H{i + 1}", x, y)
        # --- labels
        cx, cy = to_board(side, 27, 14)
        self.text(f"ScissorBall 36  {side.upper()}", cx, OY - 50.5 + 0, size=1.3)
        self.text("rev 1.0  2026", cx, OY - 48.7 + 3.0, pcbnew.B_SilkS, size=1.0)
        return self.b


def place(side):
    d = os.path.join(paths.PCB, side)
    os.makedirs(d, exist_ok=True)
    b = Builder(side).build()
    path = os.path.join(d, f"scissorball_{side}.kicad_pcb")
    b.SetFileName(path)
    pcbnew.SaveBoard(path, b)
    b = pcbnew.LoadBoard(path)
    add_zones(b)
    pcbnew.SaveBoard(path, b)
    ok = pcbnew.ExportSpecctraDSN(b, os.path.join(paths.BUILD, f"scissorball_{side}.dsn"))
    print(side, "saved", path, "dsn", ok, "footprints", len(b.GetFootprints()), "nets", b.GetNetCount())


def add_zones(b):
    gnd = b.FindNet("GND")
    # outline polygon for zones = board edge bbox (zone is clipped by edge)
    bb = b.GetBoardEdgesBoundingBox()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer); z.SetNet(gnd)
        z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.4))
        ol = z.Outline(); ol.NewOutline()
        for px, py in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
            ol.Append(px, py)
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())


def finish(side):
    d = os.path.join(paths.PCB, side)
    path = os.path.join(d, f"scissorball_{side}.kicad_pcb")
    b = pcbnew.LoadBoard(path)
    ses = os.path.join(paths.BUILD, f"scissorball_{side}.ses")
    ok = pcbnew.ImportSpecctraSES(b, ses)
    print("ses import", ok)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    print(side, "finished; tracks", len(b.GetTracks()))


if __name__ == "__main__":
    stage = sys.argv[1]
    sides = sys.argv[2:] or ["left", "right"]
    for s in sides:
        (place if stage == "place" else finish)(s)
