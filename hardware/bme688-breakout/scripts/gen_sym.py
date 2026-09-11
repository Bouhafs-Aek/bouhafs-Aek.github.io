"""Build lib/BME688_Breakout.kicad_sym, the project symbol library.

It holds the two symbols KiCad 9 does not ship:

  BME688 - the Sensor library has a BME680 but no BME688. The parts are pin-
           and package-compatible (Bosch LGA-8, 3.0 x 3.0 x 0.93 mm, identical
           pin assignment), so the reviewed BME680 body is reused and only the
           identity properties are restated.
  VIN    - a power symbol for the board's unregulated input rail, drawn from
           the stock VCC symbol.
  VIO    - likewise for the host I/O reference rail that the level shifters
           pull up to.

Written in the KiCad 10 symbol format (20251024) and derived from the KiCad
10.0.6 symbol libraries (CC-BY-SA 4.0 with the library exception, which allows
use in a design without imposing terms on it).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BME688_PROPS = {
    'Value': 'BME688',
    'Footprint': 'Package_LGA:Bosch_LGA-8_3x3mm_P0.8mm_ClockwisePinNumbering',
    'Datasheet': ('https://www.bosch-sensortec.com/media/boschsensortec/downloads/'
                  'datasheets/bst-bme688-ds000.pdf'),
    'Description': ('4-in-1 environmental sensor with AI gas scanning: gas/VOC, humidity, '
                    'pressure, temperature, I2C and SPI, 1.71-3.6V, LGA-8'),
    'ki_keywords': 'Bosch gas VOC air quality pressure humidity temperature environmental BSEC',
    'ki_fp_filters': '*LGA*3x3mm*P0.8mm*Clockwise*',
}

VIN_PROPS = {
    'Value': 'VIN',
    'Footprint': '',
    'Datasheet': '',
    'Description': 'Power symbol for the unregulated board input rail',
    'ki_keywords': 'global power VIN',
}

VIO_PROPS = {
    'Value': 'VIO',
    'Footprint': '',
    'Datasheet': '',
    'Description': 'Power symbol for the host I/O reference rail (3.3-5.5V)',
    'ki_keywords': 'global power VIO IOREF',
}


def rename(sym, old, new, props):
    sym[1] = sexp.Str(new)
    for sub in sexp.getall(sym, 'symbol'):
        sub[1] = sexp.Str(str(sub[1]).replace(old, new, 1))
    for prop in sexp.getall(sym, 'property'):
        key = str(prop[1])
        if key in props:
            prop[2] = sexp.Str(props[key])
    return sym


def pick(path, name):
    lib = sexp.parse(open(os.path.join(HERE, 'sym_cache', path)).read())[0]
    for sym in sexp.getall(lib, 'symbol'):
        if str(sym[1]) == name:
            return sym
    raise KeyError(name)


def main():
    bme = rename(pick('Sensor.kicad_sym', 'BME680'), 'BME680', 'BME688', BME688_PROPS)
    vin = rename(pick('power.kicad_sym', 'VCC'), 'VCC', 'VIN', VIN_PROPS)
    vio = rename(pick('power.kicad_sym', 'VCC'), 'VCC', 'VIO', VIO_PROPS)
    out = ['(kicad_symbol_lib',
           '\t(version 20251024)',
           '\t(generator "bme688-breakout/scripts/gen_sym.py")',
           '\t(generator_version "10.0")',
           sexp.dump(bme, 1),
           sexp.dump(vin, 1),
           sexp.dump(vio, 1),
           ')', '']
    path = os.path.join(ROOT, 'lib', 'BME688_Breakout.kicad_sym')
    open(path, 'w').write('\n'.join(out))
    print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    main()
