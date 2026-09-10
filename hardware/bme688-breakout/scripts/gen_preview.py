"""Render doc/board-preview.svg: top and bottom views of the generated board.

A convenience so the layout can be reviewed without opening KiCad. Silkscreen
text is drawn with an ordinary SVG font rather than KiCad's stroke font, so
text width is approximate; everything else is to scale.
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design, geom, sexp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 11.0
PAD = 6.0

COL = {
    'F.Cu': '#c8342b', 'B.Cu': '#2f6fbf', 'F.SilkS': '#e8e8e8', 'B.SilkS': '#e8e8e8',
    'Edge.Cuts': '#f2d34c', 'pad': '#d99b2b', 'hole': '#111820', 'via': '#9a7b2f',
    'zone': '#1d3f6b', 'board': '#0d5233',
}


class View:
    def __init__(self, ox, oy, mirror):
        b = design.BOARD
        self.bx0, self.by0 = b['x0'], b['y0']
        self.bx1 = b['x0'] + b['w']
        self.ox, self.oy, self.mirror = ox, oy, mirror

    def pt(self, x, y):
        if self.mirror:
            x = self.bx0 + self.bx1 - x
        return ((x - self.bx0) * SCALE + self.ox, (y - self.by0) * SCALE + self.oy)


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def load(path):
    return sexp.parse(open(path).read())[0]


def draw(root, view, side, out):
    b = design.BOARD
    x, y = view.pt(b['x0'], b['y0']) if not view.mirror else view.pt(b['x0'] + b['w'], b['y0'])
    out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="3" fill="%s"/>'
               % (x, y, b['w'] * SCALE, b['h'] * SCALE, COL['board']))

    cu = 'F.Cu' if side == 'front' else 'B.Cu'
    silk = 'F.SilkS' if side == 'front' else 'B.SilkS'

    # ground pour on the back
    if side == 'back':
        for z in sexp.getall(root, 'zone'):
            if str(sexp.get(z, 'layer')[1]) != 'B.Cu':
                continue
            pts = [view.pt(float(p[1]), float(p[2]))
                   for p in sexp.getall(sexp.get(sexp.get(z, 'polygon'), 'pts'), 'xy')]
            out.append('<polygon points="%s" fill="%s" fill-opacity="0.55"/>'
                       % (' '.join('%.2f,%.2f' % p for p in pts), COL['zone']))

    # tracks
    for seg in sexp.getall(root, 'segment'):
        if str(sexp.get(seg, 'layer')[1]) != cu:
            continue
        s, e = sexp.get(seg, 'start'), sexp.get(seg, 'end')
        w = float(sexp.get(seg, 'width')[1])
        a = view.pt(float(s[1]), float(s[2]))
        c = view.pt(float(e[1]), float(e[2]))
        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" '
                   'stroke-width="%.2f" stroke-linecap="round"/>'
                   % (a[0], a[1], c[0], c[1], COL[cu], w * SCALE))

    # footprint graphics on this side's silkscreen, then pads
    for fp in sexp.getall(root, 'footprint'):
        at = sexp.get(fp, 'at')
        X, Y = float(at[1]), float(at[2])
        A = float(at[3]) if len(at) > 3 else 0.0
        for g in fp:
            if not isinstance(g, list) or g[0] not in ('fp_line', 'fp_arc', 'fp_circle',
                                                       'fp_rect', 'fp_poly'):
                continue
            lay = sexp.get(g, 'layer')
            if not lay or str(lay[1]) != silk:
                continue
            wnode = sexp.get(sexp.get(g, 'stroke'), 'width') if sexp.get(g, 'stroke') else None
            lw = float(wnode[1]) if wnode else 0.12
            if g[0] in ('fp_line', 'fp_rect'):
                s, e = sexp.get(g, 'start'), sexp.get(g, 'end')
                a = view.pt(*geom.fp_xf(X, Y, A, float(s[1]), float(s[2])))
                c = view.pt(*geom.fp_xf(X, Y, A, float(e[1]), float(e[2])))
                if g[0] == 'fp_line':
                    out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" '
                               'stroke-width="%.2f"/>'
                               % (a[0], a[1], c[0], c[1], COL[silk], lw * SCALE))
                else:
                    out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                               'fill="none" stroke="%s" stroke-width="%.2f"/>'
                               % (min(a[0], c[0]), min(a[1], c[1]), abs(c[0] - a[0]),
                                  abs(c[1] - a[1]), COL[silk], lw * SCALE))
            elif g[0] == 'fp_circle':
                c0 = sexp.get(g, 'center'); e = sexp.get(g, 'end')
                cc = geom.fp_xf(X, Y, A, float(c0[1]), float(c0[2]))
                ee = geom.fp_xf(X, Y, A, float(e[1]), float(e[2]))
                r = math.hypot(ee[0] - cc[0], ee[1] - cc[1])
                p = view.pt(*cc)
                out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="none" stroke="%s" '
                           'stroke-width="%.2f"/>' % (p[0], p[1], r * SCALE, COL[silk],
                                                      lw * SCALE))
            elif g[0] == 'fp_arc':
                s, m, e = sexp.get(g, 'start'), sexp.get(g, 'mid'), sexp.get(g, 'end')
                pts = [view.pt(*geom.fp_xf(X, Y, A, float(n[1]), float(n[2])))
                       for n in (s, m, e)]
                out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.2f"/>'
                           % (' '.join('%.2f,%.2f' % p for p in pts), COL[silk], lw * SCALE))
            elif g[0] == 'fp_poly':
                pts = [view.pt(*geom.fp_xf(X, Y, A, float(n[1]), float(n[2])))
                       for n in sexp.getall(sexp.get(g, 'pts'), 'xy')]
                out.append('<polygon points="%s" fill="%s" fill-opacity="0.9"/>'
                           % (' '.join('%.2f,%.2f' % p for p in pts), COL[silk]))

        for pad in sexp.getall(fp, 'pad'):
            kind, shape = str(pad[2]), str(pad[3])
            pat = sexp.get(pad, 'at')
            size = sexp.get(pad, 'size')
            layers = {str(v) for v in sexp.get(pad, 'layers')[1:]}
            through = kind in ('thru_hole', 'np_thru_hole')
            if not through and cu not in layers and '*.Cu' not in layers:
                continue
            gx, gy = geom.fp_xf(X, Y, A, float(pat[1]), float(pat[2]))
            prot = (float(pat[3]) if len(pat) > 3 else 0.0) + A
            w = float(size[1]) if size else 0.0
            h = float(size[2]) if size else 0.0
            if int(round(prot)) % 180 == 90:
                w, h = h, w
            if shape == 'custom':
                w, h = max(w, 1.0), max(h, 1.5)
            p = view.pt(gx, gy)
            colour = COL['hole'] if kind == 'np_thru_hole' else COL['pad']
            if shape == 'circle' or kind == 'np_thru_hole':
                out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                           % (p[0], p[1], max(w, h) / 2 * SCALE, colour))
            else:
                out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" '
                           'fill="%s"/>' % (p[0] - w / 2 * SCALE, p[1] - h / 2 * SCALE,
                                            w * SCALE, h * SCALE,
                                            min(w, h) * SCALE * 0.2, colour))
            drill = sexp.get(pad, 'drill')
            if through and drill:
                d = float(drill[1])
                out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                           % (p[0], p[1], d / 2 * SCALE, COL['hole']))

    # vias
    for via in sexp.getall(root, 'via'):
        at = sexp.get(via, 'at')
        d = float(sexp.get(via, 'size')[1])
        dr = float(sexp.get(via, 'drill')[1])
        p = view.pt(float(at[1]), float(at[2]))
        out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                   % (p[0], p[1], d / 2 * SCALE, COL['via']))
        out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                   % (p[0], p[1], dr / 2 * SCALE, COL['hole']))

    # board-level silkscreen text
    for t in sexp.getall(root, 'gr_text'):
        if str(sexp.get(t, 'layer')[1]) != silk:
            continue
        at = sexp.get(t, 'at')
        rot = float(at[3]) if len(at) > 3 else 0.0
        size = float(sexp.get(sexp.get(sexp.get(t, 'effects'), 'font'), 'size')[1])
        p = view.pt(float(at[1]), float(at[2]))
        angle = -rot if not view.mirror else rot
        out.append('<text x="%.2f" y="%.2f" transform="rotate(%.1f %.2f %.2f)" '
                   'font-family="DejaVu Sans, Verdana, sans-serif" font-size="%.2f" '
                   'fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>'
                   % (p[0], p[1], angle, p[0], p[1], size * SCALE * 1.05,
                      COL[silk], esc(str(t[1]))))

    # board outline last, on top
    for g in sexp.getall(root, 'gr_line'):
        if str(sexp.get(g, 'layer')[1]) != 'Edge.Cuts':
            continue
        s, e = sexp.get(g, 'start'), sexp.get(g, 'end')
        a = view.pt(float(s[1]), float(s[2]))
        c = view.pt(float(e[1]), float(e[2]))
        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" '
                   'stroke-width="1.4"/>' % (a[0], a[1], c[0], c[1], COL['Edge.Cuts']))


def main():
    root = load(os.path.join(ROOT, 'bme688-breakout.kicad_pcb'))
    b = design.BOARD
    vw, vh = b['w'] * SCALE, b['h'] * SCALE
    width = PAD * 3 + vw * 2
    height = PAD * 2 + vh + 26
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" '
           'viewBox="0 0 %.0f %.0f">' % (width, height, width, height),
           '<rect width="%.0f" height="%.0f" fill="#16181d"/>' % (width, height)]
    for idx, (side, mirror, title) in enumerate((('front', False, 'TOP (F.Cu)'),
                                                 ('back', True, 'BOTTOM (B.Cu, mirrored)'))):
        ox = PAD + idx * (vw + PAD)
        view = View(ox, PAD + 18, mirror)
        out.append('<text x="%.2f" y="%.2f" font-family="DejaVu Sans, sans-serif" '
                   'font-size="11" fill="#9aa4b2">%s</text>' % (ox, PAD + 11, title))
        draw(root, view, side, out)
    out.append('<text x="%.2f" y="%.2f" font-family="DejaVu Sans, sans-serif" font-size="10" '
               'fill="#6b7480">%s  -  %.2f x %.2f mm, 2 layers</text>'
               % (PAD, height - 5, esc(b['title']), b['w'], b['h']))
    out.append('</svg>')
    path = os.path.join(ROOT, 'doc', 'board-preview.svg')
    open(path, 'w').write('\n'.join(out) + '\n')
    print('wrote doc/board-preview.svg (%d elements)' % len(out))


if __name__ == '__main__':
    main()
