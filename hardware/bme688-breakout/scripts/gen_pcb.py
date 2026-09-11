"""Generate bme688-breakout.kicad_pcb in the KiCad 10 board format (20250907).

Placement comes from design.PARTS; every track and via is produced by the
maze router in router.py and then re-checked by verify.py. GND is a solid
B.Cu pour, so each surface-mount GND pad gets its own stitching via.
"""
import math, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, dfm, geom, router as rt, sexp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NS = uuid.UUID('6bd2f0c8-1f4a-5c7e-9a3b-bme688brkout'.replace('bme688brkout', 'b17e688c0a1f'))

LAYERS = """	(layers
		(0 "F.Cu" signal)
		(2 "B.Cu" signal)
		(9 "F.Adhes" user "F.Adhesive")
		(11 "B.Adhes" user "B.Adhesive")
		(13 "F.Paste" user)
		(15 "B.Paste" user)
		(5 "F.SilkS" user "F.Silkscreen")
		(7 "B.SilkS" user "B.Silkscreen")
		(1 "F.Mask" user)
		(3 "B.Mask" user)
		(17 "Dwgs.User" user "User.Drawings")
		(19 "Cmts.User" user "User.Comments")
		(21 "Eco1.User" user "User.Eco1")
		(23 "Eco2.User" user "User.Eco2")
		(25 "Edge.Cuts" user)
		(27 "Margin" user)
		(31 "F.CrtYd" user "F.Courtyard")
		(29 "B.CrtYd" user "B.Courtyard")
		(35 "F.Fab" user)
		(33 "B.Fab" user)
	)"""

SETUP = """	(setup
		(stackup
			(layer "F.SilkS"
				(type "Top Silk Screen")
			)
			(layer "F.Paste"
				(type "Top Solder Paste")
			)
			(layer "F.Mask"
				(type "Top Solder Mask")
				(thickness 0.01)
			)
			(layer "F.Cu"
				(type "copper")
				(thickness 0.035)
			)
			(layer "dielectric 1"
				(type "core")
				(thickness 1.51)
				(material "FR4")
				(epsilon_r 4.5)
				(loss_tangent 0.02)
			)
			(layer "B.Cu"
				(type "copper")
				(thickness 0.035)
			)
			(layer "B.Mask"
				(type "Bottom Solder Mask")
				(thickness 0.01)
			)
			(layer "B.Paste"
				(type "Bottom Solder Paste")
			)
			(layer "B.SilkS"
				(type "Bottom Silk Screen")
			)
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
		(pad_to_mask_clearance 0.05)
		(allow_soldermask_bridges_in_footprints no)
		(tenting
			(front yes)
			(back yes)
		)
		(covering
			(front no)
			(back no)
		)
		(plugging
			(front no)
			(back no)
		)
		(capping no)
		(filling no)
	)"""


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


def sym_uuid(ref):
    """UUID shared with the schematic symbol, so the two files stay linked."""
    return uid('sym', ref)


# --------------------------------------------------------------------------
# net table
# --------------------------------------------------------------------------
NETS = design.nets()
NETNUM = design.net_numbers()
PADNET = {(r, p): n for r, p, n in design.CONNECTIONS}


def width_for(net):
    return design.POWER_W if net in design.POWER_NETS else design.TRACE_W


# --------------------------------------------------------------------------
# footprint instances
# --------------------------------------------------------------------------
SKIP_TOKENS = {'version', 'generator', 'generator_version', 'property', 'pad', 'layer', 'model'}


def emit_footprint(ref):
    value, lib_id, fp_id, x, y, rot, descr = design.PARTS[ref]
    fp = geom.load_fp(fp_id)
    is_smd = bool(sexp.get(fp, 'attr') and 'smd' in [str(v) for v in sexp.get(fp, 'attr')[1:]])
    lines = ['\t(footprint "%s"' % fp_id,
             '\t\t(layer "F.Cu")',
             '\t\t(uuid "%s")' % uid('fp', ref),
             '\t\t(at %s %s%s)' % (sexp.fmt(x), sexp.fmt(y),
                                   '' if rot == 0 else ' ' + sexp.fmt(float(rot)))]
    d = sexp.get(fp, 'descr')
    if d:
        lines.append('\t\t(descr %s)' % sexp.quote(str(d[1])))
    t = sexp.get(fp, 'tags')
    if t:
        lines.append('\t\t(tags %s)' % sexp.quote(str(t[1])))

    # Reference designators live on F.Fab: the board is too dense to carry 35
    # of them on the silkscreen, which is used for functional labels instead.
    lines += _prop('Reference', ref, 'F.Fab', 0, -0.1, 0.6, False)
    lines += _prop('Value', value, 'F.Fab', 0, 1.2, 0.6, True)
    lines += _prop('Footprint', fp_id, 'F.Fab', 0, 0, 0.6, True)
    lines += _prop('Datasheet', '', 'F.Fab', 0, 0, 0.6, True)
    lines += _prop('Description', descr, 'F.Fab', 0, 0, 0.6, True)

    lines.append('\t\t(path "/%s")' % sym_uuid(ref))
    lines.append('\t\t(sheetname "Root")')
    lines.append('\t\t(sheetfile "bme688-breakout.kicad_sch")')
    a = sexp.get(fp, 'attr')
    if a:
        lines.append('\t\t' + sexp.dump(a).strip())
    lines.append('\t\t(duplicate_pad_numbers_are_jumpers no)')

    for item in fp:
        if not isinstance(item, list) or item[0] in SKIP_TOKENS:
            continue
        if item[0] in ('descr', 'tags', 'attr'):
            continue
        body = sexp.dump(item, 2)
        lines.append(body)

    npads = 0
    for pad in sexp.getall(fp, 'pad'):
        npads += 1
        name = str(pad[1])
        net = PADNET.get((ref, name))
        pl = ['\t\t(pad %s %s %s' % (sexp.quote(name), pad[2], pad[3])]
        for sub in pad[4:]:
            if isinstance(sub, list):
                pl.append(sexp.dump(sub, 3))
        if net:
            pl.append('\t\t\t(net %d %s)' % (NETNUM[net], sexp.quote(net)))
            pl.append('\t\t\t(pinfunction %s)' % sexp.quote(name))
            pl.append('\t\t\t(pintype "passive")')
        pl.append('\t\t\t(uuid "%s")' % uid('pad', ref, name, npads))
        pl.append('\t\t)')
        lines.append('\n'.join(pl))

    m = sexp.get(fp, 'model')
    lines.append('\t\t(embedded_fonts no)')
    if m:
        lines.append(sexp.dump(m, 2))
    lines.append('\t)')
    return '\n'.join(lines)


def _prop(key, val, layer, dx, dy, size, hide):
    out = ['\t\t(property %s %s' % (sexp.quote(key), sexp.quote(val)),
           '\t\t\t(at %s %s 0)' % (sexp.fmt(dx), sexp.fmt(dy)),
           '\t\t\t(unlocked yes)',
           '\t\t\t(layer "%s")' % layer]
    if hide:
        out.append('\t\t\t(hide yes)')
    out += ['\t\t\t(uuid "%s")' % uid('prop', key, val, dx, dy),
            '\t\t\t(effects',
            '\t\t\t\t(font',
            '\t\t\t\t\t(size %s %s)' % (sexp.fmt(size), sexp.fmt(size)),
            '\t\t\t\t\t(thickness 0.1)',
            '\t\t\t\t)',
            '\t\t\t)',
            '\t\t)']
    return out


# --------------------------------------------------------------------------
# routing
# --------------------------------------------------------------------------
def build_router():
    b = design.BOARD
    r = rt.Router(b['x0'], b['y0'], b['x0'] + b['w'], b['y0'] + b['h'],
                  clearance=design.CLEARANCE)
    padinfo = {}
    for ref, (value, lib_id, fp_id, x, y, rot, descr) in design.PARTS.items():
        for name, gx, gy, w, h, prot, shape, kind, layers in geom.fp_pads(fp_id, x, y, rot):
            net = PADNET.get((ref, name))
            lset = set(layers)
            if kind in ('thru_hole', 'np_thru_hole'):
                lset = {'F.Cu', 'B.Cu'}
            if kind == 'np_thru_hole':
                # Keep signal copper out from under the screw head, not just
                # clear of the drill: a metal screw on a grounded standoff
                # would otherwise short whatever track passes beneath it.
                r.add_pad(net, gx, gy, dfm.SCREW_HEAD_DIA, dfm.SCREW_HEAD_DIA,
                          0, 'circle', lset)
            else:
                r.add_pad(net, gx, gy, w, h, prot, shape, lset)
            if net:
                padinfo.setdefault(net, []).append(
                    dict(ref=ref, pad=name, x=gx, y=gy, w=w, h=h, rot=prot,
                         shape=shape, kind=kind, layers=lset))
    return r, padinfo


def route_all(r, padinfo):
    tracks, vias, report = [], [], []
    order = sorted((n for n in NETS if n != design.GND_NET),
                   key=lambda n: -len(padinfo.get(n, [])))
    for net in order:
        pads = padinfo.get(net, [])
        if len(pads) < 2:
            continue
        w = width_for(net)
        pad_shapes = [(p['x'], p['y'], p['w'], p['h'], p['rot'], p['shape'], p['layers'])
                      for p in pads]
        own = r.own_cells(net, w, pad_shapes)
        blocked = r.build_blocked(net, w)
        viablocked = r.build_blocked(net, design.VIA_DIA)
        # tree starts at the pad closest to the net's centroid
        cx = sum(p['x'] for p in pads) / len(pads)
        cy = sum(p['y'] for p in pads) / len(pads)
        pads = sorted(pads, key=lambda p: (p['x'] - cx) ** 2 + (p['y'] - cy) ** 2)
        tree = _pad_cells(r, own, pads[0], blocked)
        remaining = pads[1:]
        while remaining:
            remaining.sort(key=lambda p: _dist_to_tree(r, tree, p))
            tgt = remaining.pop(0)
            targets = _pad_cells(r, own, tgt, blocked)
            if not targets or not tree:
                report.append((net, tgt['ref'] + '.' + tgt['pad'], 'no reachable pad cell'))
                continue
            path = r.search(blocked, tree, targets, via_blocked=viablocked)
            if path is None:
                report.append((net, tgt['ref'] + '.' + tgt['pad'], 'UNROUTED'))
                continue
            path = r.simplify(blocked, path)
            segs, vs = rt.path_to_geometry(r, path, w, net)
            for s in segs:
                tracks.append(s)
                r.add_track(net, s[0], s[1], s[2], s[3], s[4], s[5])
            for vx, vy in vs:
                vias.append((vx, vy, net))
                r.add_via(net, vx, vy, design.VIA_DIA)
            # grow the tree and refresh clearances for later nets
            for node in path:
                tree.add(node)
            tree |= targets
            blocked = r.build_blocked(net, w)
            viablocked = r.build_blocked(net, design.VIA_DIA)
    return tracks, vias, report


def _pad_cells(r, own, pad, blocked):
    """Walkable cells belonging to one pad, centre first."""
    ci, cj = r.cell(pad['x'], pad['y'])
    out = set()
    for li, nm in ((rt.F_CU, 'F.Cu'), (rt.B_CU, 'B.Cu')):
        if nm not in pad['layers']:
            continue
        span = int(math.ceil(max(pad['w'], pad['h']) / rt.GRID / 2)) + 1
        for i in range(max(ci - span, 0), min(ci + span + 1, r.nx)):
            for j in range(max(cj - span, 0), min(cj + span + 1, r.ny)):
                if own[li, i, j] and not blocked[li, i, j]:
                    out.add((li, i, j))
    return out


def _dist_to_tree(r, tree, pad):
    ci, cj = r.cell(pad['x'], pad['y'])
    return min(((i - ci) ** 2 + (j - cj) ** 2) for _, i, j in tree) if tree else 1e9


def gnd_vias(r, padinfo):
    """One stitching via beside every SMD GND pad, plus its short stub."""
    tracks, vias, unstitched = [], [], []
    w = design.TRACE_W
    blocked = r.build_blocked(design.GND_NET, w)
    viablocked = r.build_blocked(design.GND_NET, design.VIA_DIA)
    for pad in padinfo.get(design.GND_NET, []):
        if pad['kind'] != 'smd':
            continue                        # through-hole pads meet the pour directly
        placed = False
        for dist in [x * 0.1 for x in range(6, 26)]:
            for ang in range(0, 360, 15):
                vi, vj = r.cell(pad['x'] + dist * math.cos(math.radians(ang)),
                                pad['y'] + dist * math.sin(math.radians(ang)))
                if not (0 <= vi < r.nx and 0 <= vj < r.ny):
                    continue
                if viablocked[rt.F_CU, vi, vj] or viablocked[rt.B_CU, vi, vj]:
                    continue
                # Snap to the cell that was actually tested: placing the via at
                # the unrounded polar coordinate let it drift up to half a cell
                # past the clearance the grid had cleared.
                vx, vy = r.pos(vi, vj)
                if not _stub_clear(r, blocked, pad['x'], pad['y'], vx, vy):
                    continue
                vias.append((vx, vy, design.GND_NET))
                tracks.append((pad['x'], pad['y'], vx, vy, w, 'F.Cu', design.GND_NET))
                r.add_via(design.GND_NET, vx, vy, design.VIA_DIA)
                r.add_track(design.GND_NET, pad['x'], pad['y'], vx, vy, w, 'F.Cu')
                blocked = r.build_blocked(design.GND_NET, w)
                viablocked = r.build_blocked(design.GND_NET, design.VIA_DIA)
                placed = True
                break
            if placed:
                break
        if not placed:
            unstitched.append(pad['ref'] + '.' + pad['pad'])
    return tracks, vias, unstitched


def _stub_clear(r, blocked, x1, y1, x2, y2):
    n = max(int(math.hypot(x2 - x1, y2 - y1) / (rt.GRID / 2)), 1)
    for k in range(n + 1):
        t = k / n
        i, j = r.cell(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        if not (0 <= i < r.nx and 0 <= j < r.ny) or blocked[rt.F_CU, i, j]:
            return False
    return True


# --------------------------------------------------------------------------
# board graphics
# --------------------------------------------------------------------------
def gr_text(txt, x, y, layer, size=0.6, rot=0, thickness=0.1, mirror=False):
    just = '\n\t\t\t(justify mirror)' if mirror else ''
    return ('\t(gr_text %s\n'
            '\t\t(at %s %s%s)\n'
            '\t\t(layer "%s")\n'
            '\t\t(uuid "%s")\n'
            '\t\t(effects\n'
            '\t\t\t(font\n'
            '\t\t\t\t(size %s %s)\n'
            '\t\t\t\t(thickness %s)\n'
            '\t\t\t)%s\n'
            '\t\t)\n'
            '\t)') % (sexp.quote(txt), sexp.fmt(x), sexp.fmt(y),
                      '' if rot == 0 else ' ' + sexp.fmt(float(rot)), layer,
                      uid('txt', txt, x, y, layer), sexp.fmt(size), sexp.fmt(size),
                      sexp.fmt(thickness), just)


def gr_line(x1, y1, x2, y2, layer, width=0.1):
    return ('\t(gr_line\n\t\t(start %s %s)\n\t\t(end %s %s)\n'
            '\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type solid)\n\t\t)\n'
            '\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)') % (
        sexp.fmt(x1), sexp.fmt(y1), sexp.fmt(x2), sexp.fmt(y2),
        sexp.fmt(width), layer, uid('line', x1, y1, x2, y2, layer))


def silkscreen():
    b = design.BOARD
    out = []
    # 2.54mm header pin functions, read running up the board
    for k, lab in enumerate(design.J1_LABELS):
        x = design.PARTS['J1'][3] + k * 2.54
        out.append(gr_text(lab, x, 97.6, 'F.SilkS', size=0.65, rot=90))
    for k, lab in enumerate(design.J2_LABELS):
        x = design.PARTS['J2'][3] + k * 2.54
        out.append(gr_text(lab, x, 80.0, 'F.SilkS', size=0.6))
    # test pads
    for ref, lab in (('TP1', 'SCK'), ('TP2', 'SDI'), ('TP3', 'SDO'), ('TP4', 'CSB')):
        out.append(gr_text(lab, design.PARTS[ref][3], 82.75, 'F.SilkS', size=0.5))
    # jumpers and connectors
    out.append(gr_text('ADDR', 113.9, 87.6, 'F.SilkS', size=0.6))
    out.append(gr_text('I2C PU', 125.0, 87.9, 'F.SilkS', size=0.55))
    out.append(gr_text('LED', 130.0, 89.9, 'F.SilkS', size=0.55))
    out.append(gr_text('VIO=VIN', 104.5, 93.3, 'F.SilkS', size=0.5))
    out.append(gr_text('QWIIC', 103.0, 84.3, 'F.SilkS', size=0.55))
    out.append(gr_text('QWIIC', 135.0, 84.3, 'F.SilkS', size=0.55))
    # board identity (the long form is on the back, where there is room)
    out.append(gr_text('BME688', 103.8, 98.3, 'F.SilkS', size=0.75, thickness=0.13))
    # usage notes on the back, where there is room
    notes = [
        'BME688 4-in-1 ENVIRONMENTAL SENSOR BREAKOUT  rev %s' % b['rev'],
        'VIN 2.5-5.5V -> on-board 3V3 LDO. Host logic = VIO, 3.3-5.5V.',
        'I2C (default): addr 0x76 = JP1 1-2, 0x77 = JP1 2-3',
        'SPI: open JP1 completely, then drive CS',
        'JP2: cut to remove sensor-side I2C pull-ups (daisy chain)',
        'JP3: cut to disable the power LED',
        'VIO = host I/O rail (3.3-5.5V). JP4 bridges it to VIN;',
        'cut JP4 and feed VIO when host logic differs from VIN.',
        'Qwiic / STEMMA QT connectors are 3.3V only',
    ]
    for k, line in enumerate(notes):
        out.append(gr_text(line, 119.05, 81.0 + k * 2.2, 'B.SilkS',
                           size=0.7, thickness=0.12, mirror=True))
    return out


def edge_cuts():
    b = design.BOARD
    x0, y0 = b['x0'], b['y0']
    x1, y1 = x0 + b['w'], y0 + b['h']
    return [gr_line(x0, y0, x1, y0, 'Edge.Cuts'),
            gr_line(x1, y0, x1, y1, 'Edge.Cuts'),
            gr_line(x1, y1, x0, y1, 'Edge.Cuts'),
            gr_line(x0, y1, x0, y0, 'Edge.Cuts')]


def gnd_zone():
    b = design.BOARD
    inset = 0.25
    x0, y0 = b['x0'] + inset, b['y0'] + inset
    x1, y1 = b['x0'] + b['w'] - inset, b['y0'] + b['h'] - inset
    pts = '(xy %s %s) (xy %s %s) (xy %s %s) (xy %s %s)' % (
        sexp.fmt(x0), sexp.fmt(y0), sexp.fmt(x1), sexp.fmt(y0),
        sexp.fmt(x1), sexp.fmt(y1), sexp.fmt(x0), sexp.fmt(y1))
    return ('\t(zone\n'
            '\t\t(net %d)\n'
            '\t\t(net_name "GND")\n'
            '\t\t(layer "B.Cu")\n'
            '\t\t(uuid "%s")\n'
            '\t\t(name "GND")\n'
            '\t\t(hatch edge 0.508)\n'
            '\t\t(connect_pads\n'
            '\t\t\t(clearance %s)\n'
            '\t\t)\n'
            '\t\t(min_thickness 0.2)\n'
            '\t\t(fill yes\n'
            '\t\t\t(thermal_gap 0.3)\n'
            '\t\t\t(thermal_bridge_width 0.4)\n'
            '\t\t\t(smoothing fillet)\n'
            '\t\t\t(radius 0.3)\n'
            '\t\t\t(island_removal_mode 0)\n'
            '\t\t)\n'
            '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n'
            '\t)') % (NETNUM['GND'], uid('zone', 'gnd', 'b.cu'),
                      sexp.fmt(design.CLEARANCE), pts)


# --------------------------------------------------------------------------
def main():
    r, padinfo = build_router()
    tracks, vias, report = route_all(r, padinfo)
    gt, gv, unstitched = gnd_vias(r, padinfo)
    tracks += gt
    vias += gv

    b = design.BOARD
    out = ['(kicad_pcb',
           '\t(version 20250907)',
           '\t(generator "bme688-breakout/scripts/gen_pcb.py")',
           '\t(generator_version "10.0")',
           '\t(general',
           '\t\t(thickness 1.6)',
           '\t\t(legacy_teardrops no)',
           '\t)',
           '\t(paper "A4")',
           LAYERS,
           SETUP,
           '\t(net 0 "")']
    for name, num in sorted(NETNUM.items(), key=lambda kv: kv[1]):
        out.append('\t(net %d %s)' % (num, sexp.quote(name)))

    for ref in design.PARTS:
        out.append(emit_footprint(ref))

    out += edge_cuts()
    out += silkscreen()

    for x1, y1, x2, y2, w, layer, net in tracks:
        out.append('\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n'
                   '\t\t(width %s)\n\t\t(layer "%s")\n\t\t(net %d)\n\t\t(uuid "%s")\n\t)' % (
                       sexp.fmt(x1), sexp.fmt(y1), sexp.fmt(x2), sexp.fmt(y2),
                       sexp.fmt(w), layer, NETNUM[net],
                       uid('seg', x1, y1, x2, y2, layer, net)))
    for x, y, net in vias:
        out.append('\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n'
                   '\t\t(layers "F.Cu" "B.Cu")\n'
                   '\t\t(tenting\n\t\t\t(front none)\n\t\t\t(back none)\n\t\t)\n'
                   '\t\t(capping none)\n'
                   '\t\t(covering\n\t\t\t(front none)\n\t\t\t(back none)\n\t\t)\n'
                   '\t\t(plugging\n\t\t\t(front none)\n\t\t\t(back none)\n\t\t)\n'
                   '\t\t(filling none)\n'
                   '\t\t(net %d)\n\t\t(uuid "%s")\n\t)' % (
                       sexp.fmt(x), sexp.fmt(y), sexp.fmt(design.VIA_DIA),
                       sexp.fmt(design.VIA_DRILL), NETNUM[net], uid('via', x, y, net)))
    out.append(gnd_zone())
    out.append('\t(embedded_fonts no)')
    out.append(')')
    out.append('')

    path = os.path.join(ROOT, 'bme688-breakout.kicad_pcb')
    open(path, 'w').write('\n'.join(out))
    print('wrote %s  (%d footprints, %d segments, %d vias)' % (
        os.path.relpath(path, ROOT), len(design.PARTS), len(tracks), len(vias)))
    if report:
        print('ROUTING PROBLEMS:', report)
    if unstitched:
        print('UNSTITCHED GND PADS:', unstitched)


if __name__ == '__main__':
    main()
