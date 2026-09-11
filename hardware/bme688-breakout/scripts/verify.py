"""Independent checks on the generated board and schematic.

The board is re-parsed from the emitted file (not from the router's state) and
checked for: net assignment against design.py, electrical connectivity of every
net, copper-to-copper clearance, hole-to-copper clearance, footprint courtyard
overlap, and copper inside the board outline. The schematic is checked for pin
coverage and for labels that do not match any net.
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, sexp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 1e-6

# ---------------------------------------------------------------- geometry
def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def seg_seg_dist(a, b, c, d):
    """Distance between segments ab and cd."""
    ux, uy = b[0] - a[0], b[1] - a[1]
    vx, vy = d[0] - c[0], d[1] - c[1]
    wx, wy = a[0] - c[0], a[1] - c[1]
    A = ux * ux + uy * uy
    B = ux * vx + uy * vy
    C = vx * vx + vy * vy
    D = ux * wx + uy * wy
    E = vx * wx + vy * wy
    den = A * C - B * B
    if den > 1e-12:
        s = _clamp((B * E - C * D) / den, 0.0, 1.0)
        t = _clamp((A * E - B * D) / den, 0.0, 1.0)
    else:                                     # parallel
        s = 0.0
        t = _clamp(E / C, 0.0, 1.0) if C > 1e-12 else 0.0
    px, py = a[0] + s * ux, a[1] + s * uy
    qx, qy = c[0] + t * vx, c[1] + t * vy
    # refine for the parallel case
    best = math.hypot(px - qx, py - qy)
    for p in (a, b):
        best = min(best, pt_seg_dist(p, c, d))
    for q in (c, d):
        best = min(best, pt_seg_dist(q, a, b))
    return best


def pt_seg_dist(p, a, b):
    ux, uy = b[0] - a[0], b[1] - a[1]
    L2 = ux * ux + uy * uy
    if L2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = _clamp(((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) / L2, 0.0, 1.0)
    return math.hypot(p[0] - (a[0] + t * ux), p[1] - (a[1] + t * uy))


def pt_rect_dist(p, r):
    x0, y0, x1, y1 = r
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


def rect_seg_dist(r, a, b):
    x0, y0, x1, y1 = r
    if _seg_hits_rect(a, b, r):
        return 0.0
    best = min(pt_rect_dist(a, r), pt_rect_dist(b, r))
    for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        best = min(best, pt_seg_dist(c, a, b))
    return best


def _seg_hits_rect(a, b, r):
    x0, y0, x1, y1 = r
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return True
    if x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
             ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for c, d in edges:
        if seg_seg_dist(a, b, c, d) < TOL:
            return True
    return False


def rect_rect_dist(r, s):
    dx = max(r[0] - s[2], 0.0, s[0] - r[2])
    dy = max(r[1] - s[3], 0.0, s[1] - r[3])
    return math.hypot(dx, dy)


class Shape:
    """Copper item: an axis-aligned rect, or a capsule (segment + radius)."""
    __slots__ = ('kind', 'rect', 'a', 'b', 'r', 'net', 'layers', 'label')

    def __init__(self, kind, net, layers, label, rect=None, a=None, b=None, r=0.0):
        self.kind, self.net, self.layers, self.label = kind, net, layers, label
        self.rect, self.a, self.b, self.r = rect, a, b, r

    def dist(self, o):
        if self.kind == 'rect' and o.kind == 'rect':
            return rect_rect_dist(self.rect, o.rect)
        if self.kind == 'rect':
            return rect_seg_dist(self.rect, o.a, o.b) - o.r
        if o.kind == 'rect':
            return rect_seg_dist(o.rect, self.a, self.b) - self.r
        return seg_seg_dist(self.a, self.b, o.a, o.b) - self.r - o.r

    def bbox(self):
        if self.kind == 'rect':
            return self.rect
        return (min(self.a[0], self.b[0]) - self.r, min(self.a[1], self.b[1]) - self.r,
                max(self.a[0], self.b[0]) + self.r, max(self.a[1], self.b[1]) + self.r)


def rect_shape(net, layers, label, cx, cy, w, h, rot):
    if int(round(rot)) % 180 == 90:
        w, h = h, w
    return Shape('rect', net, layers, label,
                 rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))


# ---------------------------------------------------------------- union-find
class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


# ---------------------------------------------------------------- board load
def load_board(path):
    root = sexp.parse(open(path).read())[0]
    nets = {int(n[1]): str(n[2]) for n in sexp.getall(root, 'net')}
    shapes, courtyards, holes = [], [], []
    for fp in sexp.getall(root, 'footprint'):
        at = sexp.get(fp, 'at')
        X, Y = float(at[1]), float(at[2])
        A = float(at[3]) if len(at) > 3 else 0.0
        ref = None
        for prop in sexp.getall(fp, 'property'):
            if str(prop[1]) == 'Reference':
                ref = str(prop[2])
        import geom
        for pad in sexp.getall(fp, 'pad'):
            name = str(pad[1])
            kind, shape = str(pad[2]), str(pad[3])
            pat = sexp.get(pad, 'at')
            size = sexp.get(pad, 'size')
            lx, ly = float(pat[1]), float(pat[2])
            prot = (float(pat[3]) if len(pat) > 3 else 0.0) + A
            gx, gy = geom.fp_xf(X, Y, A, lx, ly)
            w = float(size[1]) if size else 0.0
            h = float(size[2]) if size else 0.0
            nt = sexp.get(pad, 'net')
            net = str(nt[2]) if nt else None
            layers = set(str(v) for v in sexp.get(pad, 'layers')[1:])
            if kind in ('thru_hole', 'np_thru_hole'):
                layers |= {'F.Cu', 'B.Cu'}
            cu = {l for l in layers if l in ('F.Cu', 'B.Cu', '*.Cu')}
            if '*.Cu' in cu:
                cu = {'F.Cu', 'B.Cu'}
            label = '%s.%s' % (ref, name)
            if kind == 'np_thru_hole':
                holes.append(Shape('cap', None, {'F.Cu', 'B.Cu'}, label,
                                   a=(gx, gy), b=(gx, gy), r=max(w, h) / 2))
                continue
            if shape == 'circle':
                shapes.append(Shape('cap', net, cu, label,
                                     a=(gx, gy), b=(gx, gy), r=max(w, h) / 2))
            else:
                if shape == 'custom':
                    w, h = max(w, 1.0), max(h, 1.5)
                shapes.append(rect_shape(net, cu, label, gx, gy, w, h, prot))
        fp_id = str(fp[1])
        courtyards.append((ref, geom.fp_courtyard(fp_id, X, Y, A)))
    for i, seg in enumerate(sexp.getall(root, 'segment')):
        s, e = sexp.get(seg, 'start'), sexp.get(seg, 'end')
        w = float(sexp.get(seg, 'width')[1])
        layer = str(sexp.get(seg, 'layer')[1])
        net = nets[int(sexp.get(seg, 'net')[1])]
        shapes.append(Shape('cap', net, {layer}, 'seg%d' % i,
                            a=(float(s[1]), float(s[2])), b=(float(e[1]), float(e[2])),
                            r=w / 2))
    for i, via in enumerate(sexp.getall(root, 'via')):
        at = sexp.get(via, 'at')
        d = float(sexp.get(via, 'size')[1])
        net = nets[int(sexp.get(via, 'net')[1])]
        p = (float(at[1]), float(at[2]))
        shapes.append(Shape('cap', net, {'F.Cu', 'B.Cu'}, 'via%d' % i, a=p, b=p, r=d / 2))
    zones = []
    for z in sexp.getall(root, 'zone'):
        layer = str(sexp.get(z, 'layer')[1])
        net = str(sexp.get(z, 'net_name')[1])
        pts = [(float(p[1]), float(p[2]))
               for p in sexp.getall(sexp.get(sexp.get(z, 'polygon'), 'pts'), 'xy')]
        zones.append((net, layer, pts))
    edges = []
    for g in sexp.getall(root, 'gr_line'):
        if str(sexp.get(g, 'layer')[1]) == 'Edge.Cuts':
            s, e = sexp.get(g, 'start'), sexp.get(g, 'end')
            edges.append(((float(s[1]), float(s[2])), (float(e[1]), float(e[2]))))
    texts = []
    for t in sexp.getall(root, 'gr_text'):
        at = sexp.get(t, 'at')
        texts.append((str(t[1]), float(at[1]), float(at[2]),
                      str(sexp.get(t, 'layer')[1]),
                      float(sexp.get(sexp.get(sexp.get(t, 'effects'), 'font'), 'size')[1])))
    return dict(shapes=shapes, courtyards=courtyards, holes=holes,
                zones=zones, edges=edges, texts=texts, nets=nets)


# ---------------------------------------------------------------- pour fill
def pour_mask(shapes, znet, zlayer, poly, res=0.1, holes=()):
    """Rasterise where the pour survives after clearance cut-back.

    Returns (mask, x0, y0, res): mask[i, j] is True where copper remains. Any
    foreign track, pad or via is subtracted with the design clearance around it.
    Thermal reliefs are not modelled - same-net pads are left solid, which is
    conservative for connectivity (a thermal still connects) but means the
    raster shows no spokes.
    """
    import numpy as np
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    nx = int(math.ceil((x1 - x0) / res)) + 1
    ny = int(math.ceil((y1 - y0) / res)) + 1
    gx = x0 + np.arange(nx) * res
    gy = y0 + np.arange(ny) * res
    mask = np.ones((nx, ny), dtype=bool)

    def stamp(shape, margin):
        bb = shape.bbox()
        i0 = max(int((bb[0] - margin - x0) / res), 0)
        i1 = min(int(math.ceil((bb[2] + margin - x0) / res)), nx - 1)
        j0 = max(int((bb[1] - margin - y0) / res), 0)
        j1 = min(int(math.ceil((bb[3] + margin - y0) / res)), ny - 1)
        if i0 > i1 or j0 > j1:
            return
        px = gx[i0:i1 + 1][:, None]
        py = gy[j0:j1 + 1][None, :]
        if shape.kind == 'cap':
            ax, ay = shape.a
            bx, by = shape.b
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 < 1e-12:
                d = np.sqrt((px - ax) ** 2 + (py - ay) ** 2)
            else:
                t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0.0, 1.0)
                d = np.sqrt((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2)
            hit = d <= shape.r + margin
        else:
            rx0, ry0, rx1, ry1 = shape.rect
            ddx = np.maximum(np.maximum(rx0 - px, 0.0), px - rx1)
            ddy = np.maximum(np.maximum(ry0 - py, 0.0), py - ry1)
            hit = np.sqrt(ddx ** 2 + ddy ** 2) <= margin
        mask[i0:i1 + 1, j0:j1 + 1] &= ~hit

    for sh in shapes:
        if zlayer not in sh.layers or sh.net == znet:
            continue
        stamp(sh, design.CLEARANCE)
    for h in holes:
        stamp(h, design.CLEARANCE)
    return mask, x0, y0, res


def plane_regions(shapes, znet, zlayer, poly, res=0.1):
    """Simulate the pour fill and label its connected regions.

    Returns (region_count, lookup) where lookup(shape) gives the region id the
    shape lands in, or None if the fill does not reach it.
    """
    import numpy as np
    mask, x0, y0, res = pour_mask(shapes, znet, zlayer, poly, res, HOLES_FOR_POUR)
    nx, ny = mask.shape

    # 4-connected flood fill over the surviving copper
    label = np.zeros((nx, ny), dtype=np.int32)
    cur = 0
    idx = np.argwhere(mask)
    for si, sj in idx:
        if label[si, sj]:
            continue
        cur += 1
        stack = [(int(si), int(sj))]
        label[si, sj] = cur
        while stack:
            i, j = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if 0 <= ni < nx and 0 <= nj < ny and mask[ni, nj] and not label[ni, nj]:
                    label[ni, nj] = cur
                    stack.append((ni, nj))

    def lookup(shape):
        """Region touching this shape, searching outward a little."""
        bb = shape.bbox()
        i0 = max(int((bb[0] - 0.35 - x0) / res), 0)
        i1 = min(int(math.ceil((bb[2] + 0.35 - x0) / res)), nx - 1)
        j0 = max(int((bb[1] - 0.35 - y0) / res), 0)
        j1 = min(int(math.ceil((bb[3] + 0.35 - y0) / res)), ny - 1)
        best = None
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if label[i, j]:
                    best = int(label[i, j])
                    break
            if best:
                break
        return best

    return cur, lookup


HOLES_FOR_POUR = []


# ---------------------------------------------------------------- checks
def pt_in_poly(p, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > p[1]) != (y2 > p[1]):
            xin = x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1)
            if p[0] < xin:
                inside = not inside
    return inside


def check_nets(board, errs):
    want = {}
    for ref, pad, net in design.CONNECTIONS:
        want[(ref, pad)] = net
    seen = {}
    for s in board['shapes']:
        if '.' not in s.label or s.label.startswith(('seg', 'via')):
            continue
        ref, pad = s.label.split('.', 1)
        seen.setdefault((ref, pad), set()).add(s.net)
    for key, net in want.items():
        if key not in seen:
            errs.append('net assignment: pad %s.%s missing from board' % key)
        elif seen[key] != {net}:
            errs.append('net assignment: pad %s.%s is %s, design says %s'
                        % (key[0], key[1], seen[key], net))
    for key, nets in seen.items():
        if key not in want and nets != {None}:
            errs.append('net assignment: pad %s.%s has net %s but design leaves it open'
                        % (key[0], key[1], nets))


def check_connectivity(board, errs):
    global HOLES_FOR_POUR
    HOLES_FOR_POUR = board['holes']
    shapes = board['shapes']
    dsu = DSU()
    n = len(shapes)
    for i in range(n):
        a = shapes[i]
        if a.net is None:
            continue
        ab = a.bbox()
        for j in range(i + 1, n):
            b = shapes[j]
            if b.net is None or a.net != b.net or not (a.layers & b.layers):
                continue
            bb = b.bbox()
            if (ab[0] > bb[2] + 0.01 or bb[0] > ab[2] + 0.01
                    or ab[1] > bb[3] + 0.01 or bb[1] > ab[3] + 0.01):
                continue
            if a.dist(b) <= 0.001:
                dsu.union(i, j)
    # A pour only joins items that end up in the same piece of copper once the
    # fill is cut back around every foreign track, pad and via, so the fill is
    # simulated on a grid rather than assumed to be one solid region.
    for znet, zlayer, poly in board['zones']:
        regions, cellof = plane_regions(shapes, znet, zlayer, poly)
        byregion = {}
        for i, s in enumerate(shapes):
            if s.net != znet or zlayer not in s.layers:
                continue
            reg = cellof(s)
            if reg is None:
                errs.append('pour: %s (%s) does not reach the %s pour'
                            % (s.label, s.net, zlayer))
                continue
            byregion.setdefault(reg, []).append(i)
        if len(byregion) > 1:
            errs.append('pour: the %s %s pour is split into %d islands: %s'
                        % (znet, zlayer, len(byregion),
                           [sorted(shapes[i].label for i in v)[:4] for v in byregion.values()]))
        for members in byregion.values():
            for k in members[1:]:
                dsu.union(members[0], k)
    bynet = {}
    for i, s in enumerate(shapes):
        if s.net:
            bynet.setdefault(s.net, []).append(i)
    for net, idxs in bynet.items():
        roots = {dsu.find(i) for i in idxs}
        if len(roots) > 1:
            groups = {}
            for i in idxs:
                groups.setdefault(dsu.find(i), []).append(shapes[i].label)
            pieces = [sorted(v)[:5] for v in groups.values()]
            errs.append('connectivity: net %s is in %d pieces: %s'
                        % (net, len(roots), pieces))


def check_clearance(board, errs):
    shapes = board['shapes']
    n = len(shapes)
    worst = []
    for i in range(n):
        a = shapes[i]
        ab = a.bbox()
        for j in range(i + 1, n):
            b = shapes[j]
            if not (a.layers & b.layers):
                continue
            if a.net == b.net and a.net is not None:
                continue
            if a.net is None and b.net is None:
                continue
            bb = b.bbox()
            lim = design.CLEARANCE
            if (ab[0] > bb[2] + lim or bb[0] > ab[2] + lim
                    or ab[1] > bb[3] + lim or bb[1] > ab[3] + lim):
                continue
            d = a.dist(b)
            if d < design.CLEARANCE - 1e-4:
                worst.append((d, a.label, a.net, b.label, b.net))
    worst.sort()
    for d, la, na, lb, nb in worst[:25]:
        errs.append('clearance: %s(%s) to %s(%s) = %.3fmm < %.2fmm'
                    % (la, na, lb, nb, d, design.CLEARANCE))
    if len(worst) > 25:
        errs.append('clearance: ... and %d more' % (len(worst) - 25))


def check_holes(board, errs):
    for h in board['holes']:
        for s in board['shapes']:
            if not (h.layers & s.layers):
                continue
            d = h.dist(s)
            if d < design.CLEARANCE - 1e-4:
                errs.append('hole clearance: %s to %s(%s) = %.3fmm'
                            % (h.label, s.label, s.net, d))


def check_courtyards(board, errs):
    cy = board['courtyards']
    for i in range(len(cy)):
        ra, ba = cy[i]
        for j in range(i + 1, len(cy)):
            rb, bb = cy[j]
            ox = min(ba[2], bb[2]) - max(ba[0], bb[0])
            oy = min(ba[3], bb[3]) - max(ba[1], bb[1])
            if ox > 1e-4 and oy > 1e-4:
                errs.append('courtyard overlap: %s and %s overlap %.3f x %.3f mm'
                            % (ra, rb, ox, oy))


def check_outline(board, errs):
    b = design.BOARD
    x0, y0, x1, y1 = b['x0'], b['y0'], b['x0'] + b['w'], b['y0'] + b['h']
    for s in board['shapes']:
        bx = s.bbox()
        if bx[0] < x0 - 1e-6 or bx[1] < y0 - 1e-6 or bx[2] > x1 + 1e-6 or bx[3] > y1 + 1e-6:
            errs.append('outline: copper %s(%s) extends outside the board edge'
                        % (s.label, s.net))
    got = {(round(a[0], 3), round(a[1], 3), round(bb[0], 3), round(bb[1], 3))
           for a, bb in board['edges']}
    if len(got) != 4:
        errs.append('outline: expected 4 Edge.Cuts lines, found %d' % len(got))


def check_silk(board, warns):
    pads = [s for s in board['shapes'] if not s.label.startswith(('seg', 'via'))]
    for txt, x, y, layer, size in board['texts']:
        if layer not in ('F.SilkS', 'B.SilkS'):
            continue
        side = 'F.Cu' if layer == 'F.SilkS' else 'B.Cu'
        w = len(txt) * size * 0.8
        h = size * 1.1
        box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        for s in pads:
            if side not in s.layers:
                continue
            if rect_rect_dist(box, s.bbox()) <= 0:
                warns.append('silkscreen %r overlaps pad %s' % (txt, s.label))
                break


# ---------------------------------------------------------------- schematic
def load_sch(path):
    import gen_sch
    root = sexp.parse(open(path).read())[0]
    wires = []
    for w in sexp.getall(root, 'wire'):
        pts = sexp.getall(sexp.get(w, 'pts'), 'xy')
        wires.append(((float(pts[0][1]), float(pts[0][2])),
                      (float(pts[1][1]), float(pts[1][2]))))
    labels = [(str(l[1]), float(sexp.get(l, 'at')[1]), float(sexp.get(l, 'at')[2]))
              for l in sexp.getall(root, 'label')]
    ncs = [(float(sexp.get(n, 'at')[1]), float(sexp.get(n, 'at')[2]))
           for n in sexp.getall(root, 'no_connect')]
    syms = []
    for sym in sexp.getall(root, 'symbol'):
        lid = str(sexp.get(sym, 'lib_id')[1])
        at = sexp.get(sym, 'at')
        X, Y = float(at[1]), float(at[2])
        A = float(at[3]) if len(at) > 3 else 0.0
        props = {str(p[1]): str(p[2]) for p in sexp.getall(sym, 'property')}
        pins = [str(p[1]) for p in sexp.getall(sym, 'pin')]
        syms.append(dict(lib_id=lid, x=X, y=Y, rot=A, ref=props.get('Reference'),
                         value=props.get('Value'), pins=pins))
    return dict(wires=wires, labels=labels, ncs=ncs, syms=syms, root=root)


def check_sch_netlist(sch, errs):
    import gen_sch
    dsu = DSU()
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    for a, b in sch['wires']:
        dsu.union(key(a), key(b))

    def attach(pt):
        """Join a point to every wire that passes through it.

        KiCad connects a pin or label anywhere along a wire, not only at its
        endpoints, so a mid-wire label has to be resolved the same way.
        """
        k = key(pt)
        dsu.find(k)
        for a, b in sch['wires']:
            if pt_seg_dist(pt, a, b) <= 0.01:
                dsu.union(k, key(a))
        return dsu.find(k)
    pinsites = []          # (ref, pad, point)
    powersites = []        # (netname, point)
    for s in sch['syms']:
        ref = s['ref']
        try:
            pins = gen_sch.sym_pins(s['lib_id'])
        except KeyError:
            errs.append('schematic: unknown lib_id %s' % s['lib_id'])
            continue
        for num, _nm, lx, ly, _pa, _et in pins:
            import geom
            pt = key(geom.sym_xf(s['x'], s['y'], s['rot'], lx, ly))
            attach(pt)
            if ref and ref.startswith('#PWR'):
                powersites.append((s['value'], pt))
            elif ref and ref.startswith('#FLG'):
                pass
            else:
                pinsites.append((ref, num, pt))
    labelnet = {}
    for name, x, y in sch['labels']:
        labelnet.setdefault(attach((x, y)), set()).add(name)
    for name, pt in powersites:
        labelnet.setdefault(attach(pt), set()).add(name)
    # every group must carry exactly one net name
    for root_pt, names in labelnet.items():
        if len(names) > 1:
            errs.append('schematic: one node carries conflicting names %s' % sorted(names))
    got = {}
    for ref, num, pt in pinsites:
        names = labelnet.get(attach(pt))
        if names:
            got[(ref, num)] = sorted(names)[0]
    want = {(r, p): n for r, p, n in design.CONNECTIONS}
    for k, n in want.items():
        if k not in got:
            errs.append('schematic: pin %s.%s is not on net %s' % (k[0], k[1], n))
        elif got[k] != n:
            errs.append('schematic: pin %s.%s is on %s, design says %s'
                        % (k[0], k[1], got[k], n))
    for k, n in got.items():
        if k not in want:
            errs.append('schematic: pin %s.%s is on net %s but design leaves it open'
                        % (k[0], k[1], n))
    # unconnected pins must be marked no-connect
    ncset = {key(p) for p in sch['ncs']}
    for ref, num, pt in pinsites:
        if (ref, num) not in want and pt not in ncset:
            errs.append('schematic: pin %s.%s is neither connected nor marked no-connect'
                        % (ref, num))


def sym_body_box(sch_sym):
    """Graphic bounding box of a placed symbol, in sheet coordinates."""
    import gen_sch, geom
    node = gen_sch.flatten(sch_sym['lib_id'])
    xs, ys = [], []
    for sub in sexp.getall(node, 'symbol'):
        for g in sub:
            if not isinstance(g, list):
                continue
            local = []
            if g[0] == 'rectangle':
                for k in ('start', 'end'):
                    v = sexp.get(g, k)
                    local.append((float(v[1]), float(v[2])))
            elif g[0] in ('polyline', 'arc', 'bezier'):
                pts = sexp.get(g, 'pts')
                if pts:
                    local += [(float(p[1]), float(p[2])) for p in sexp.getall(pts, 'xy')]
                for k in ('start', 'mid', 'end'):
                    v = sexp.get(g, k)
                    if v:
                        local.append((float(v[1]), float(v[2])))
            elif g[0] == 'circle':
                c = sexp.get(g, 'center')
                r = float(sexp.get(g, 'radius')[1])
                local += [(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)]
            for lx, ly in local:
                gx, gy = geom.sym_xf(sch_sym['x'], sch_sym['y'], sch_sym['rot'], lx, ly)
                xs.append(gx); ys.append(gy)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def check_sch_overlaps(sch, errs, warns):
    boxes = []
    for s in sch['syms']:
        if s['ref'] and s['ref'].startswith(('#PWR', '#FLG')):
            continue
        box = sym_body_box(s)
        if box:
            boxes.append((s['ref'], box))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ra, ba = boxes[i]
            rb, bb = boxes[j]
            ox = min(ba[2], bb[2]) - max(ba[0], bb[0])
            oy = min(ba[3], bb[3]) - max(ba[1], bb[1])
            if ox > 1e-4 and oy > 1e-4:
                errs.append('schematic: symbols %s and %s overlap (%.2f x %.2f mm)'
                            % (ra, rb, ox, oy))
    for name, x, y in sch['labels']:
        w = len(name) * 1.27 * 0.8
        lb = (x - w, y - 1.4, x + w, y + 0.4)
        for ref, box in boxes:
            if rect_rect_dist(lb, box) <= 0:
                warns.append('schematic: label %r may overlap symbol %s' % (name, ref))
                break
    b = design.BOARD
    for ref, box in boxes:
        if box[0] < 5 or box[1] < 5 or box[2] > 415 or box[3] > 292:
            errs.append('schematic: symbol %s falls outside the A3 sheet' % ref)


def main():
    errs, warns = [], []
    pcb = os.path.join(ROOT, 'bme688-breakout.kicad_pcb')
    board = load_board(pcb)
    check_nets(board, errs)
    check_connectivity(board, errs)
    check_clearance(board, errs)
    check_holes(board, errs)
    check_courtyards(board, errs)
    check_outline(board, errs)
    check_silk(board, warns)
    sch_path = os.path.join(ROOT, 'bme688-breakout.kicad_sch')
    sch = load_sch(sch_path)
    check_sch_netlist(sch, errs)
    check_sch_overlaps(sch, errs, warns)
    print('=== board: %s' % os.path.basename(pcb))
    print('    %d copper items, %d nets, %d footprints'
          % (len(board['shapes']), len(design.nets()), len(design.PARTS)))
    for e in errs:
        print('  ERROR   ' + e)
    for w in warns:
        print('  WARN    ' + w)
    print('=== schematic: %s' % os.path.basename(sch_path))
    print('    %d symbols, %d wires, %d labels'
          % (len(sch['syms']), len(sch['wires']), len(sch['labels'])))
    if not errs:
        print('  all board and schematic checks passed')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
