# Regenerate the whole design from scripts/design.py, then check it.
PY ?= python3

.PHONY: all sym pcb sch project preview verify clean
all: sym sch pcb project preview verify

sym:      ; $(PY) scripts/gen_sym.py
sch: sym  ; $(PY) scripts/gen_sch.py
pcb:      ; $(PY) scripts/gen_pcb.py
project:  ; $(PY) scripts/gen_project.py
preview: pcb ; $(PY) scripts/gen_preview.py
verify: sch pcb ; $(PY) scripts/verify.py

clean:
	rm -f bme688-breakout.kicad_pcb bme688-breakout.kicad_sch \
	      bme688-breakout.kicad_pro sym-lib-table \
	      lib/BME688_Breakout.kicad_sym doc/bom.csv doc/board-preview.svg
