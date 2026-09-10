"""Generate bme688-breakout.kicad_sch from design.py.

Targets the KiCad 10 schematic format (20250901). Every symbol used is written
into the schematic's lib_symbols cache with any derived symbol flattened against
its parent, so the file carries complete definitions and does not depend on the
reader's library versions matching.

Signal pins get a short wire stub and a net label; supply pins get a power
symbol turned so its graphic points away from the part. Symbol UUIDs match the
board's footprint paths, which keeps the two files linked.
"""
import math, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, geom, sexp
from gen_pcb import sym_uuid, uid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJECT = 'bme688-breakout'
STUB_LABEL = 5.08
STUB_POWER = 2.54

LIB_FILES = {
    'BME688_Breakout': os.path.join(ROOT, 'lib', 'BME688_Breakout.kicad_sym'),
}
PADNET = {(r, p): n for r, p, n in design.CONNECTIONS}

_libcache = {}


def load_lib(libname):
    if libname not in _libcache:
        path = LIB_FILES.get(libname, os.path.join(HERE, 'sym_cache', libname + '.kicad_sym'))
        _libcache[libname] = sexp.parse(open(path).read())[0]
    return _libcache[libname]


def raw_symbol(libname, name):
    for sym in sexp.getall(load_lib(libname), 'symbol'):
        if str(sym[1]) == name:
            return sym
    raise KeyError('%s:%s' % (libname, name))


def flatten(lib_id):
    """Return a standalone symbol definition named 'Lib:Name'.

    KiCad writes lib_symbols with derived symbols already merged into their
    parent, so `extends` is resolved here the same way.
    """
    libname, name = lib_id.split(':', 1)
    sym = raw_symbol(libname, name)
    ext = sexp.get(sym, 'extends')
    body_src = sym
    if ext:
        parent = raw_symbol(libname, str(ext[1]))
        body_src = parent
    out = [sexp.Str('%s:%s' % (libname, name))]
    for key in ('pin_numbers', 'pin_names', 'exclude_from_sim', 'in_bom', 'on_board',
                'in_pos_files', 'duplicate_pin_numbers_are_jumpers'):
        node = sexp.get(body_src, key) or sexp.get(sym, key)
        if node is not None:
            out.append(node)
    for prop in sexp.getall(sym, 'property'):
        out.append(prop)
    pname = str(body_src[1])
    for sub in sexp.getall(body_src, 'symbol'):
        copy = list(sub)
        copy[1] = sexp.Str(str(sub[1]).replace(pname, name, 1))
        out.append(copy)
    out.append(['embedded_fonts', 'no'])
    return ['symbol'] + out


def sym_pins(lib_id):
    """[(number, name, lx, ly, pin_angle, etype)] for a flattened symbol."""
    node = flatten(lib_id)
    pins = []
    for sub in sexp.getall(node, 'symbol'):
        for p in sexp.getall(sub, 'pin'):
            at = sexp.get(p, 'at')
            pins.append((str(sexp.get(p, 'number')[1]), str(sexp.get(p, 'name')[1]),
                         float(at[1]), float(at[2]),
                         float(at[3]) if len(at) > 3 else 0.0, str(p[1])))
    return pins


def pin_site(ref, number):
    """Sheet position and outward unit vector of one component pin."""
    lib_id = design.PARTS[ref][1]
    X, Y, A = design.SCH[ref]
    for num, _nm, lx, ly, pa, _et in sym_pins(lib_id):
        if num == number:
            px, py = geom.sym_xf(X, Y, A, lx, ly)
            out = math.radians(pa + 180 + A)
            dx, dy = round(math.cos(out), 6), round(-math.sin(out), 6)
            return (px, py, dx, dy)
    raise KeyError('%s pin %s' % (ref, number))


def power_rotation(kind, dx, dy):
    """Rotation that makes a power symbol's graphic point along (dx, dy)."""
    for A in (0, 90, 180, 270):
        s, c = round(math.sin(math.radians(A))), round(math.cos(math.radians(A)))
        if kind == 'down':                     # GND: graphic dir = (sinA, cosA)
            if (s, c) == (round(dx), round(dy)):
                return A
        else:                                  # rails: graphic dir = (-sinA, -cosA)
            if (-s, -c) == (round(dx), round(dy)):
                return A
    raise ValueError('no rotation for %s %s' % (dx, dy))


# ---------------------------------------------------------------- emitters
def wire(x1, y1, x2, y2):
    return ('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
            '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)') % (sexp.fmt(x1), sexp.fmt(y1), sexp.fmt(x2), sexp.fmt(y2),
                                       uid('wire', x1, y1, x2, y2))


def label(text, x, y, dx, dy):
    if dx > 0.5:
        rot, just = 0, 'left'
    elif dx < -0.5:
        rot, just = 180, 'right'
    elif dy < -0.5:
        rot, just = 90, 'left'
    else:
        rot, just = 270, 'right'
    return ('\t(label %s\n\t\t(at %s %s %d)\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify %s bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)') % (
        sexp.quote(text), sexp.fmt(x), sexp.fmt(y), rot, just, uid('lbl', text, x, y))


def no_connect(x, y):
    return '\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)' % (
        sexp.fmt(x), sexp.fmt(y), uid('nc', x, y))


def symbol_instance(lib_id, ref, value, X, Y, A, uuid_str, props_hidden=(),
                    pins=(), ref_dy=-6.35, val_dy=6.35, show_value=True):
    out = ['\t(symbol',
           '\t\t(lib_id %s)' % sexp.quote(lib_id),
           '\t\t(at %s %s %d)' % (sexp.fmt(X), sexp.fmt(Y), A),
           '\t\t(unit 1)',
           '\t\t(body_style 1)',
           '\t\t(exclude_from_sim no)',
           '\t\t(in_bom yes)',
           '\t\t(on_board yes)',
           '\t\t(dnp no)',
           '\t\t(uuid "%s")' % uuid_str]
    out += _sch_prop('Reference', ref, X, Y + ref_dy, hide=ref.startswith('#'))
    out += _sch_prop('Value', value, X, Y + val_dy, hide=not show_value)
    for key, val in props_hidden:
        out += _sch_prop(key, val, X, Y, hide=True)
    for num in pins:
        out.append('\t\t(pin %s\n\t\t\t(uuid "%s")\n\t\t)' % (
            sexp.quote(num), uid('pin', ref, num)))
    out += ['\t\t(instances',
            '\t\t\t(project %s' % sexp.quote(PROJECT),
            '\t\t\t\t(path "/%s"' % SHEET_UUID,
            '\t\t\t\t\t(reference %s)' % sexp.quote(ref),
            '\t\t\t\t\t(unit 1)',
            '\t\t\t\t)',
            '\t\t\t)',
            '\t\t)',
            '\t)']
    return '\n'.join(out)


def _sch_prop(key, val, x, y, hide=False):
    """One symbol property. KiCad 10 puts `hide` on the property, not in effects."""
    out = ['\t\t(property %s %s' % (sexp.quote(key), sexp.quote(val)),
           '\t\t\t(at %s %s 0)' % (sexp.fmt(x), sexp.fmt(y))]
    if hide:
        out.append('\t\t\t(hide yes)')
    out += ['\t\t\t(effects',
            '\t\t\t\t(font',
            '\t\t\t\t\t(size 1.27 1.27)',
            '\t\t\t\t)',
            '\t\t\t)',
            '\t\t)']
    return out


SHEET_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'bme688-breakout/root-sheet'))


# ---------------------------------------------------------------- assembly
def main():
    body, items = [], []
    used = set(lib_id for _v, lib_id, *_r in
               ((p[0], p[1]) + tuple(p[2:]) for p in design.PARTS.values()))
    for net, (lib_id, _kind) in design.POWER_SYMBOLS.items():
        used.add(lib_id)
    used.add('power:PWR_FLAG')

    direct = {}
    for a, b in design.DIRECT_WIRES:
        direct[a] = b
        direct[b] = a

    pwr_n = [0]
    flg_n = [0]

    def place_power(net, x, y, dx, dy):
        lib_id, kind = design.POWER_SYMBOLS[net]
        ex, ey = x + dx * STUB_POWER, y + dy * STUB_POWER
        A = power_rotation(kind, dx, dy)
        pwr_n[0] += 1
        ref = '#PWR%02d' % pwr_n[0]
        items.append(wire(x, y, ex, ey))
        items.append(symbol_instance(
            lib_id, ref, net, ex, ey, A, uid('pwr', ref),
            props_hidden=(('Footprint', ''), ('Datasheet', ''), ('Description', '')),
            pins=('1',), ref_dy=3.81, val_dy=-3.81 if kind == 'up' else 3.81))

    # ---- components
    for ref, (value, lib_id, fp_id, _px, _py, _pr, descr) in design.PARTS.items():
        X, Y, A = design.SCH[ref]
        pins = sym_pins(lib_id)
        items.append(symbol_instance(
            lib_id, ref, value, X, Y, A, sym_uuid(ref),
            props_hidden=(('Footprint', fp_id), ('Datasheet', ''), ('Description', descr)),
            pins=tuple(p[0] for p in pins)))
        for num, _nm, _lx, _ly, _pa, _et in pins:
            px, py, dx, dy = pin_site(ref, num)
            net = PADNET.get((ref, num))
            if (ref, num) in direct:
                continue                       # drawn as a wire below
            if net is None:
                items.append(no_connect(px, py))
            elif net in design.POWER_SYMBOLS:
                place_power(net, px, py, dx, dy)
            else:
                ex, ey = px + dx * STUB_LABEL, py + dy * STUB_LABEL
                items.append(wire(px, py, ex, ey))
                items.append(label(net, ex, ey, dx, dy))

    # ---- wires drawn directly between two pins, labelled so the net keeps its
    #      name instead of picking up an auto-generated one
    for (ra, pa), (rb, pb) in design.DIRECT_WIRES:
        ax, ay, _dx, _dy = pin_site(ra, pa)
        bx, by, _dx2, _dy2 = pin_site(rb, pb)
        items.append(wire(ax, ay, bx, by))
        net = PADNET[(ra, pa)]
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        vertical = abs(bx - ax) < abs(by - ay)
        items.append(label(net, mx, my, 0.0, -1.0) if vertical
                     else label(net, mx, my, 1.0, 0.0))

    # ---- PWR_FLAGs so ERC sees GND and VIN as driven
    for net, x, y in design.PWR_FLAGS:
        flg_n[0] += 1
        ref = '#FLG%02d' % flg_n[0]
        items.append(symbol_instance(
            'power:PWR_FLAG', ref, 'PWR_FLAG', x, y, 0, uid('flg', ref),
            props_hidden=(('Footprint', ''), ('Datasheet', ''), ('Description', '')),
            pins=('1',), ref_dy=-3.81, val_dy=-6.35))
        place_power(net, x, y, 0.0, 1.0)

    # ---- lib_symbols cache
    lib_lines = ['\t(lib_symbols']
    for lib_id in sorted(used):
        lib_lines.append(sexp.dump(flatten(lib_id), 2))
    lib_lines.append('\t)')

    b = design.BOARD
    out = ['(kicad_sch',
           '\t(version 20250901)',
           '\t(generator "bme688-breakout/scripts/gen_sch.py")',
           '\t(generator_version "10.0")',
           '\t(uuid "%s")' % SHEET_UUID,
           '\t(paper "A3")',
           '\t(title_block',
           '\t\t(title %s)' % sexp.quote(b['title']),
           '\t\t(rev %s)' % sexp.quote(b['rev']),
           '\t\t(comment 1 "Generated from scripts/design.py - edit the design there")',
           '\t)']
    out += lib_lines
    out += items
    out += ['\t(sheet_instances',
            '\t\t(path "/"',
            '\t\t\t(page "1")',
            '\t\t)',
            '\t)',
            '\t(embedded_fonts no)',
            ')', '']
    path = os.path.join(ROOT, PROJECT + '.kicad_sch')
    open(path, 'w').write('\n'.join(out))
    print('wrote %s  (%d symbols, %d power symbols, %d lib_symbols)' % (
        os.path.relpath(path, ROOT), len(design.PARTS), pwr_n[0], len(used)))


if __name__ == '__main__':
    main()
