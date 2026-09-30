# ScissorBall 36

Split 36-key keyboard with Kailh PG1425 (scissor / X-switch) and a 25 mm trackball (PMW3360) under the right thumb.

* Hardware: RP2040-Zero x2, TRRS, monkeypad PMW3360 breakout
* Build: `qmk compile -kb scissorball36 -km default`
* Flash: hold BOOT on the RP2040-Zero while plugging USB (or double-tap RESET), copy the .uf2. Same file for both halves (handedness pin GP29).
