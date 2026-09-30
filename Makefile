# ScissorBall 36 – regenerate everything from tools/layout.py
#
# Interpreters / tools (override on the command line or in the environment):
#   KICAD_PY     Python that can `import pcbnew` (KiCad 9)
#   FREECAD_PY   Python that can `import FreeCAD, Part` (FreeCAD 1.0)
#   KICAD_CLI    kicad-cli (KiCad 9)
#   FREEROUTING  path to freerouting-2.x.jar (needs Java 21)
#   QMK_HOME     qmk_firmware checkout (for `make firmware`)
KICAD_PY    ?= python3
FREECAD_PY  ?= python3
KICAD_CLI   ?= kicad-cli
JAVA        ?= java
FREEROUTING ?= freerouting.jar
QMK_HOME    ?= $(HOME)/qmk_firmware

SIDES := left right
PCB   := hardware/pcb
B     := build

.PHONY: all layout outline pcb production case check images firmware clean
all: layout outline pcb production case check

layout:                      ## key layout preview + 1:1 printable PDF
	python3 tools/plot_layout.py docs/images/layout.png docs/layout_1to1.pdf

outline:                     ## PCB outlines (FreeCAD 2D booleans) -> hardware/pcb/outline.json
	$(FREECAD_PY) tools/outline.py

pcb: $(addprefix pcb-,$(SIDES))

pcb-%:                       ## place -> autoroute -> close leftovers -> DRC
	$(KICAD_PY) tools/pcb.py place $*
	$(JAVA) -Djava.awt.headless=true -jar $(FREEROUTING) \
	    -de $(B)/scissorball_$*.dsn -do $(B)/scissorball_$*.ses -mp 150 --gui.enabled=false > $(B)/freerouting_$*.log 2>&1 || true
	$(KICAD_PY) tools/pcb.py finish $*
	$(KICAD_PY) tools/fixroute.py $(PCB)/$*/scissorball_$*.kicad_pcb
	$(KICAD_CLI) pcb drc -o $(PCB)/$*/drc.rpt $(PCB)/$*/scissorball_$*.kicad_pcb
	@grep -E "^\*\* Found" $(PCB)/$*/drc.rpt

production:                  ## gerbers + drill zip per half, 1:1 PDFs, board STEP, renders
	@for s in $(SIDES); do \
	  d=$(B)/fab_$$s; rm -rf $$d; mkdir -p $$d; \
	  $(KICAD_CLI) pcb export gerbers --no-protel-ext -l F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts -o $$d/ $(PCB)/$$s/scissorball_$$s.kicad_pcb >/dev/null; \
	  $(KICAD_CLI) pcb export drill --format excellon --excellon-separate-th -o $$d/ $(PCB)/$$s/scissorball_$$s.kicad_pcb >/dev/null; \
	  rm -f production/scissorball_$${s}_gerber.zip; (cd $$d && zip -q ../../production/scissorball_$${s}_gerber.zip *); \
	  $(KICAD_CLI) pcb export step --subst-models -o $(PCB)/$$s/scissorball_$${s}_pcb.step $(PCB)/$$s/scissorball_$$s.kicad_pcb >/dev/null || true; \
	  $(KICAD_CLI) pcb export pdf -l F.Cu,F.SilkS,Edge.Cuts --mode-single --drill-shape-opt 2 --black-and-white -o docs/pcb_$${s}_1to1.pdf $(PCB)/$$s/scissorball_$$s.kicad_pcb >/dev/null; \
	  tools/render_pcb.sh $(PCB)/$$s/scissorball_$$s.kicad_pcb docs/images/pcb_$$s.png; \
	done

case:                        ## printable case parts -> hardware/case (STEP/STL/3MF)
	$(FREECAD_PY) tools/case.py

check:                       ## interference checks + 3D preview renders
	$(FREECAD_PY) tools/check_case.py

firmware:                    ## build the QMK firmware (same .uf2 for both halves)
	rm -rf $(QMK_HOME)/keyboards/scissorball36
	cp -r firmware/scissorball36 $(QMK_HOME)/keyboards/
	cd $(QMK_HOME) && qmk compile -kb scissorball36 -km default
	cp $(QMK_HOME)/scissorball36_default.uf2 $(B)/

clean:
	rm -rf $(B)
