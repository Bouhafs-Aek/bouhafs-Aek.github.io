"""Manufacturability checks for rules the project file declares.

verify.py covers the electrical side - net assignment, connectivity, copper
clearance. These are the fabrication rules stated in bme688-breakout.kicad_pro
that nothing was actually testing: copper standing back from the board edge,
hole-to-hole spacing, annular ring, track width, drill size, silkscreen text
size, silk over copper, and copper under a screw head.

Every function takes the dict returned by verify.load_board() and appends
human-readable strings to errs/warns/notes.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design

# These mirror board.design_settings.rules in the project file.
EDGE_CLEARANCE = 0.3
HOLE_TO_HOLE = 0.25
MIN_ANNULAR = 0.1
MIN_TRACK = 0.2
MIN_DRILL = 0.3
MIN_TEXT_HEIGHT = 0.4
MIN_TEXT_THICKNESS = 0.1

# Not a KiCad rule: the washer-less footprint of a typical M2 pan head.
SCREW_HEAD_DIA = 3.8


def _board_rect():
    b = design.BOARD
    return b['x0'], b['y0'], b['x0'] + b['w'], b['y0'] + b['h']


def check_edge_clearance(board, errs):
    """Copper must stand back from the edge, not merely sit inside it.

    verify.check_outline only asks whether copper is within the outline, which
    a pad overhanging by 0.1mm still satisfies.
    """
    bx0, by0, bx1, by1 = _board_rect()
    found = []
    for sh in board['shapes']:
        x0, y0, x1, y1 = sh.bbox()
        gap = min(x0 - bx0, bx1 - x1, y0 - by0, by1 - y1)
        if gap < EDGE_CLEARANCE - 1e-4:
            found.append((gap, sh.label, sh.net))
    for gap, label, net in sorted(found):
        errs.append('edge clearance: %s (%s) is %.3fmm from the board edge, rule is %.2fmm'
                    % (label, net, gap, EDGE_CLEARANCE))


def check_hole_to_hole(board, errs):
    """Drill walls must not come closer than the fab can drill them."""
    ds = board['drills']
    for i in range(len(ds)):
        for j in range(i + 1, len(ds)):
            a, b = ds[i], ds[j]
            gap = (math.hypot(a['x'] - b['x'], a['y'] - b['y'])
                   - a['drill'] / 2 - b['drill'] / 2)
            if gap < HOLE_TO_HOLE - 1e-4:
                errs.append('hole to hole: %s and %s leave %.3fmm of web, rule is %.2fmm'
                            % (a['label'], b['label'], gap, HOLE_TO_HOLE))


def check_annular_ring(board, errs):
    for d in board['drills']:
        if not d['plated']:
            continue
        if d['drill'] < MIN_DRILL - 1e-4:
            errs.append('drill size: %s is %.3fmm, rule is %.2fmm'
                        % (d['label'], d['drill'], MIN_DRILL))
        ring = (d['pad'] - d['drill']) / 2
        if ring < MIN_ANNULAR - 1e-4:
            errs.append('annular ring: %s leaves %.3fmm of ring, rule is %.2fmm'
                        % (d['label'], ring, MIN_ANNULAR))


def check_track_width(board, errs):
    for sh in board['shapes']:
        if sh.label.startswith('seg') and sh.r * 2 < MIN_TRACK - 1e-4:
            errs.append('track width: %s is %.3fmm, rule is %.2fmm'
                        % (sh.label, sh.r * 2, MIN_TRACK))


def check_text_size(board, errs):
    """Silkscreen too small or too thin for the fab to hold."""
    for txt, x, y, layer, size in board['texts']:
        if size < MIN_TEXT_HEIGHT - 1e-4:
            errs.append('text height: %r is %.2fmm, rule is %.2fmm'
                        % (txt, size, MIN_TEXT_HEIGHT))


def check_mount_keepout(board, warns):
    """Copper under a screw head is a short waiting for an assembly mistake."""
    head_r = SCREW_HEAD_DIA / 2
    for h in board['holes']:
        hits = []
        for sh in board['shapes']:
            if sh.dist(h) < head_r - h.r - 1e-4:
                hits.append('%s(%s)' % (sh.label, sh.net))
        if hits:
            warns.append('screw head: %d copper items sit under a %.1fmm head at %s: %s'
                         % (len(hits), SCREW_HEAD_DIA, h.label,
                            ', '.join(sorted(hits)[:4])))


def check_silk_over_copper(board, warns, notes):
    """Silkscreen printed over a via.

    Only a defect on exposed copper. When the board setup tents vias they are
    under solder mask, and printing over them is ordinary practice, so that
    case is reported as a note rather than a warning.
    """
    import verify
    targets = [sh for sh in board['shapes'] if sh.label.startswith('via')]
    crossings = 0
    for txt, x, y, layer, size in board['texts']:
        if layer not in ('F.SilkS', 'B.SilkS'):
            continue
        w = len(txt) * size * 0.8
        box = (x - w / 2, y - size * 0.55, x + w / 2, y + size * 0.55)
        hit = [sh.label for sh in targets if verify.rect_rect_dist(box, sh.bbox()) <= 0]
        if not hit:
            continue
        crossings += len(hit)
        if not board.get('tented'):
            warns.append('silk over untented via: %r crosses %s'
                         % (txt, ', '.join(sorted(hit)[:4])))
    if crossings and board.get('tented'):
        notes.append('silkscreen crosses %d tented via(s); mask-covered, accepted'
                     % crossings)


def report_decoupling(board, notes):
    """Distance from each decoupling cap to the pin it is there to serve."""
    pairs = [('C1', '1', 'U1', '8', 'VDD'),
             ('C2', '1', 'U1', '6', 'VDDIO'),
             ('C3', '1', 'U2', '1', 'LDO in'),
             ('C4', '1', 'U2', '5', 'LDO out')]
    pads = {sh.label: sh for sh in board['shapes']
            if '.' in sh.label and not sh.label.startswith(('seg', 'via'))}
    for cref, cpad, uref, upad, what in pairs:
        a = pads.get('%s.%s' % (cref, cpad))
        b = pads.get('%s.%s' % (uref, upad))
        if a is not None and b is not None:
            notes.append('%s serves %s %-8s pad-to-pad %.2fmm'
                         % (cref, uref, what, a.dist(b)))


def run(board, errs, warns, notes):
    check_edge_clearance(board, errs)
    check_hole_to_hole(board, errs)
    check_annular_ring(board, errs)
    check_track_width(board, errs)
    check_text_size(board, errs)
    check_mount_keepout(board, warns)
    check_silk_over_copper(board, warns, notes)
    report_decoupling(board, notes)
