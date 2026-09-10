# Footprint and symbol caches

`fp_cache/*.kicad_mod` and `../sym_cache/*.kicad_sym` are verbatim copies of
footprints and symbols taken from the official KiCad libraries at tag
**9.0.9**:

* <https://gitlab.com/kicad/libraries/kicad-footprints>
* <https://gitlab.com/kicad/libraries/kicad-symbols>

They are kept here only so the generators in `../` can rebuild the schematic
and board without network access. The design itself refers to the standard
library names (`Capacitor_SMD:C_0603_1608Metric` and so on), so KiCad resolves
them from the reader's own installation.

The KiCad libraries are licensed CC-BY-SA 4.0 with an exception that allows
their use in a design without imposing licence terms on that design.
