"""Repository-relative locations used by every generator script."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")                  # scratch output (git-ignored)
PCB = os.path.join(ROOT, "hardware", "pcb")          # KiCad boards
PCB_LIB = os.path.join(PCB, "lib", "scissorball.pretty")
OUTLINE = os.path.join(PCB, "outline.json")           # board outlines (shared by PCB + case)
CASE = os.path.join(ROOT, "hardware", "case")         # printable parts
PRODUCTION = os.path.join(ROOT, "production")         # gerbers for the fab
DOCS = os.path.join(ROOT, "docs")
IMAGES = os.path.join(DOCS, "images")

# KiCad stock footprint library (KiCad 9). Override with KICAD9_FOOTPRINT_DIR.
KICAD_FOOTPRINTS = os.environ.get("KICAD9_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

for _d in (BUILD, IMAGES):
    os.makedirs(_d, exist_ok=True)
