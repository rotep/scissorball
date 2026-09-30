#!/bin/sh
# usage: tools/render_pcb.sh board.kicad_pcb out.png [layers]   (needs kicad-cli, pdftoppm, ImageMagick)
set -e
L=${3:-F.Cu,B.Cu,F.SilkS,Edge.Cuts}
T=$(mktemp -d)
${KICAD_CLI:-kicad-cli} pcb export pdf -l "$L" --mode-single -o "$T/r.pdf" "$1" >/dev/null
pdftoppm -r 200 -png -singlefile "$T/r.pdf" "$T/r"
convert "$T/r.png" -trim +repage -bordercolor white -border 20 "$2"
rm -rf "$T"
