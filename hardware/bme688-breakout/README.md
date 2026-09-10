# BME688 4-in-1 Environmental Sensor Breakout

A KiCad 9 design for a host-agnostic breakout board around the **Bosch BME688**
(gas/VOC, humidity, pressure, temperature, LGA-8). It brings the sensor out on a
0.1" header that works with any I2C or SPI microcontroller at 1.8–5.5 V logic,
plus two Qwiic / STEMMA QT connectors for daisy-chaining on the 3.3 V side.

![Board preview](doc/board-preview.svg)

## A note on the part number

The request was for a "BLE688". No manufacturer sells a part by that name — it
does not appear in Bosch's, Nordic's, Fanstel's, Raytac's, EBYTE's or MOKO's
catalogues, nor in distributor search. The intended part was confirmed as the
Bosch **BME688**, which is what this design uses. If you actually wanted a
Bluetooth module, this is the wrong board and none of it carries over.

KiCad 9 ships a `Sensor:BME680` symbol but no BME688. The two parts are pin- and
package-compatible (Bosch LGA-8, 3.0 × 3.0 × 0.93 mm, identical pin assignment),
so `lib/BME688_Breakout.kicad_sym` restates the reviewed BME680 symbol as a
BME688 with the correct datasheet and description. The land pattern is KiCad's
own reviewed `Package_LGA:Bosch_LGA-8_3x3mm_P0.8mm_ClockwisePinNumbering`
(0.5 × 0.525 mm pads on 0.8 mm pitch), unmodified.

## Board

| | |
|---|---|
| Size | 38.10 × 27.94 mm (1.5" × 1.1") |
| Layers | 2, 1.6 mm FR4, B.Cu is a solid GND pour |
| Input | 2.5–5.5 V on `VIN` → on-board AP2112K-3.3 LDO |
| Host logic | 1.8–5.5 V, level shifted on all four signals |
| Interfaces | I2C (default, 0x76) or SPI |
| Mounting | 4 × M2 (2.2 mm) at the corners |
| Min track / clearance | 0.25 mm / 0.20 mm (0.4 mm on power nets) |
| Vias | 0.6 mm pad / 0.3 mm drill |

## Pinout

### J1 — host header (2.54 mm, level-shifted, tolerates 1.8–5.5 V)

| Pin | Name | Function |
|----:|------|----------|
| 1 | VIN | 2.5–5.5 V supply in |
| 2 | 3V3 | LDO output, ~350 mA spare |
| 3 | GND | |
| 4 | SCK | SPI clock / I2C SCL |
| 5 | SDI | SPI MOSI / I2C SDA |
| 6 | SDO | SPI MISO (unused in I2C) |
| 7 | CS | SPI chip select; leave open for I2C |
| 8 | GND | |

### J2 — expansion header (2.54 mm, 3.3 V only)

| Pin | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| | 3V3 | GND | SDA | SCL |

### J3 / J4 — Qwiic / STEMMA QT (JST SH 1.0 mm, 3.3 V only)

Standard Qwiic order: 1 = GND, 2 = 3.3 V, 3 = SDA, 4 = SCL. The two connectors
are wired in parallel so boards can be chained. Shells are grounded.

Test pads TP1–TP4 expose the sensor-side SCK, SDI, SDO and CSB.

## Choosing the interface

**I2C — as manufactured, nothing to do.** R5 holds CSB high, so leaving `CS`
unconnected selects I2C. JP1 is bridged 1–2, giving address **0x76**. Cut 1–2
and bridge 2–3 for **0x77**.

**SPI — open JP1 completely first.** In SPI mode SDO is the sensor's *output*.
JP1 ties SDO hard to GND or 3V3 to set the I2C address, so driving SPI with JP1
still bridged would short that output. Open both sides of JP1, then drive `CS`.

> This is the one footgun in the design and it is deliberate: a hard tie is what
> makes the I2C address level unambiguous. A series resistor instead would form
> a divider against the host-side SDO pull-up and leave the address level
> floating around mid-rail. The trade is documented on the back silkscreen.

## Jumpers

| | Function | As manufactured |
|---|---|---|
| JP1 | I2C address / interface select | bridged 1–2 → 0x76 |
| JP2 | sensor-side I2C pull-ups (R1, R2) | bridged (pull-ups on) |
| JP3 | power LED | bridged (LED on) |

Cut **JP2** on every board but the first when chaining several over Qwiic, so
the bus only carries one pair of pull-ups. Cut **JP3** to save the LED's ~1 mA.

## Design notes

**Level shifting.** Four BSS138 + pull-up shifters (Q1–Q4), one per signal,
rather than a translator IC. The discrete shifter is bidirectional with no
direction pin, which matters here because SCK/SDI are shared between open-drain
I2C and push-pull SPI — an auto-direction part like the TXS0104E would have to
arbitrate against its own internal pull-ups, and a push-pull-only part like the
TXB0104 cannot do I2C at all. Cost is speed: with 10 kΩ pull-ups the SPI clock
is practical to a few MHz, not the BME688's 10 MHz maximum.

**SDO has no sensor-side pull-up.** Deliberate — see the SPI note above. The
host-side pull-up R7 draws ~330 µA through Q3 while JP1 holds SDO at GND in I2C
mode. That is negligible next to the sensor's ~0.9 mA typical and ~3.7 mA heater
current, but it does mean the board is not a good fit for a µA-budget sleep
design without cutting JP3 and reworking R7.

**Gas sensor placement.** The BME688's gas element is heated, and its readings
follow board temperature, so U1 sits at the top edge with the LDO diagonally
opposite ~13 mm away, and the LED and its resistor kept off that end. Thermal
isolation here is by placement only — there is no plane cutout under the sensor,
so expect the usual self-heating offset and calibrate it out.

**Handling.** The gas sensor is sensitive to siloxanes and solvent vapour: no
conformal coating, no silicone adhesives or sealants nearby, and follow Bosch's
reflow profile. Gas output needs Bosch's BSEC library and a burn-in period
before readings settle; the raw resistance is not an air-quality index.

## Files

| Path | |
|---|---|
| `bme688-breakout.kicad_pro` | project, with design rules matching the checks |
| `bme688-breakout.kicad_sch` | schematic |
| `bme688-breakout.kicad_pcb` | board |
| `lib/BME688_Breakout.kicad_sym` | BME688 and VIN symbols |
| `doc/bom.csv` | BOM, 31 placements in 19 lines |
| `doc/board-preview.svg` | top and bottom render |
| `scripts/design.py` | **the single source of truth**: parts, nets, placement |
| `scripts/verify.py` | the checks described below |

Standard footprints are referenced by their normal library names
(`Capacitor_SMD:C_0603_1608Metric` etc.) and resolve from your KiCad
installation; `scripts/fp_cache/` and `scripts/sym_cache/` hold copies from
KiCad 9.0.9 purely so the generators can run offline.

## Regenerating

`scripts/design.py` holds every part, net and coordinate; the schematic and
board are generated from it, so they cannot disagree about a connection. Edit
that file, then:

```sh
make          # regenerate symbols, schematic, board, project, preview + verify
make verify   # checks only
```

Routing is done by a small maze router (`scripts/router.py`) on a 0.1 mm grid
with a turn penalty, so tracks come out as straight runs and 45° corners. A full
regeneration takes about three minutes, most of it routing.

## What has been checked, and what has not

KiCad is not installed in the environment this was authored in, so the files
were written directly against the KiCad 9 formats (`kicad_sch` 20250114,
`kicad_pcb` 20241229), with the coordinate transforms validated against a real
KiCad 9 project. `scripts/verify.py` re-parses the emitted files and checks:

- every pad's net matches `design.py`, and no pad is silently left floating
- **electrical connectivity** of all 14 nets, including a simulated pour fill —
  the GND pour is cut back around every foreign track, pad and via and
  flood-filled, so a pour split into islands is reported rather than assumed
  away (currently: one region, all 19 GND items in it)
- copper-to-copper and hole-to-copper clearance ≥ 0.20 mm
- no footprint courtyard overlaps, all copper inside the board outline
- no silkscreen over pads
- the **schematic netlist matches `design.py` exactly**, pin for pin, and every
  unconnected pin carries a no-connect
- no overlapping symbols, everything on the A3 sheet

All of the above passes. What has **not** happened:

- KiCad's own DRC and ERC have never run on these files
- no fab has looked at them, and no board has been built
- zones are defined but not pre-filled — the `filled_polygon` geometry is
  KiCad's to compute, so **press `B` in pcbnew** to fill the pour on first open
- reference designators are on **F.Fab**, not silkscreen: at 35 parts on 1.5" ×
  1.1" the silkscreen is used for functional labels instead
- SPI has not been validated at speed; treat the few-MHz figure as an estimate
  from the pull-up RC, not a measurement

Open it in KiCad, fill zones, run DRC and ERC, and review the placement against
your enclosure before ordering anything.

## Licence and attribution

Symbols and footprints are derived from the official KiCad libraries
(CC-BY-SA 4.0 with the library exception, which permits use in a design without
imposing terms on the design). See `scripts/fp_cache/README.md`.
