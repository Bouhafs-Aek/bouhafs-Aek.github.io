"""Footprint loading and the KiCad coordinate transforms."""
import math, os, sexp

FP_CACHE = os.path.join(os.path.dirname(__file__), 'fp_cache')
_loaded = {}


def load_fp(fp_id):
    """Load a cached footprint by its 'Lib:Name' id."""
    name = fp_id.split(':', 1)[1]
    if name not in _loaded:
        path = os.path.join(FP_CACHE, name + '.kicad_mod')
        _loaded[name] = sexp.parse(open(path).read())[0]
    return _loaded[name]


def fp_xf(x, y, rot, lx, ly):
    """Footprint-local -> board coordinates (both y-down, rot counter-clockwise)."""
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    return (x + lx * c + ly * s, y - lx * s + ly * c)


def sym_xf(X, Y, rot, lx, ly):
    """Symbol-local (y-up) -> schematic sheet coordinates (y-down)."""
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    return (X + (lx * c - ly * s), Y - (lx * s + ly * c))


def fp_pads(fp_id, x, y, rot):
    """[(pad_name, gx, gy, w, h, rot, shape, kind, layers)] in board coordinates."""
    fp = load_fp(fp_id)
    out = []
    for p in sexp.getall(fp, 'pad'):
        at = sexp.get(p, 'at')
        size = sexp.get(p, 'size')
        lx, ly = float(at[1]), float(at[2])
        prot = float(at[3]) if len(at) > 3 else 0.0
        gx, gy = fp_xf(x, y, rot, lx, ly)
        w = float(size[1]) if size else 0.0
        h = float(size[2]) if size else 0.0
        layers = [str(v) for v in sexp.get(p, 'layers')[1:]]
        out.append((str(p[1]), gx, gy, w, h, (prot + rot) % 360, str(p[3]), str(p[2]), layers))
    return out


def fp_courtyard(fp_id, x, y, rot):
    """Bounding box of the footprint courtyard in board coordinates."""
    fp = load_fp(fp_id)
    xs, ys = [], []
    for g in fp:
        if not isinstance(g, list):
            continue
        lay = sexp.get(g, 'layer')
        if not lay or not str(lay[1]).endswith('CrtYd'):
            continue
        for key in ('start', 'end', 'mid', 'center'):
            v = sexp.get(g, key)
            if v:
                gx, gy = fp_xf(x, y, rot, float(v[1]), float(v[2]))
                xs.append(gx); ys.append(gy)
    if not xs:                       # e.g. mounting holes: fall back to pads
        for _, gx, gy, w, h, _, _, _, _ in fp_pads(fp_id, x, y, rot):
            xs += [gx - w / 2, gx + w / 2]
            ys += [gy - h / 2, gy + h / 2]
    return min(xs), min(ys), max(xs), max(ys)
