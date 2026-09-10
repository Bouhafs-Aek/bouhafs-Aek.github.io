"""Emit the KiCad project file, the project symbol-library table and the BOM.

Design rules here are deliberately the same numbers verify.py enforces, so
KiCad's DRC and the generator agree: 0.2 mm clearance, 0.25 mm signal tracks,
0.4 mm power tracks, 0.6/0.3 mm vias.
"""
import csv, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
from gen_sch import SHEET_UUID

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'bme688-breakout'


def netclass(name, track, clearance, priority):
    return {
        'bus_width': 12, 'clearance': clearance, 'diff_pair_gap': 0.25,
        'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2, 'line_style': 0,
        'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'name': name,
        'pcb_color': 'rgba(0, 0, 0, 0.000)', 'priority': priority,
        'schematic_color': 'rgba(0, 0, 0, 0.000)', 'track_width': track,
        'via_diameter': design.VIA_DIA, 'via_drill': design.VIA_DRILL, 'wire_width': 6,
    }


def project():
    return {
        'board': {
            'design_settings': {
                'defaults': {
                    'board_outline_line_width': 0.1,
                    'copper_line_width': 0.2,
                    'copper_text_size_h': 1.0,
                    'copper_text_size_v': 1.0,
                    'copper_text_thickness': 0.15,
                    'other_line_width': 0.1,
                    'silk_line_width': 0.12,
                    'silk_text_size_h': 0.6,
                    'silk_text_size_v': 0.6,
                    'silk_text_thickness': 0.1,
                },
                'diff_pair_dimensions': [],
                'drc_exclusions': [],
                'rule_severities': {},
                'rules': {
                    'allow_blind_buried_vias': False,
                    'allow_microvias': False,
                    'max_error': 0.005,
                    'min_clearance': design.CLEARANCE,
                    'min_connection': 0.0,
                    'min_copper_edge_clearance': 0.3,
                    'min_hole_clearance': 0.25,
                    'min_hole_to_hole': 0.25,
                    'min_microvia_diameter': 0.2,
                    'min_microvia_drill': 0.1,
                    'min_resolved_spokes': 2,
                    'min_silk_clearance': 0.0,
                    'min_text_height': 0.4,
                    'min_text_thickness': 0.1,
                    'min_through_hole_diameter': design.VIA_DRILL,
                    'min_track_width': 0.2,
                    'min_via_annular_width': 0.1,
                    'min_via_diameter': 0.45,
                    'solder_mask_to_copper_clearance': 0.0,
                    'use_height_for_length_calcs': True,
                },
                'track_widths': [0.0, design.TRACE_W, design.POWER_W, 0.8],
                'via_dimensions': [
                    {'diameter': 0.0, 'drill': 0.0},
                    {'diameter': design.VIA_DIA, 'drill': design.VIA_DRILL},
                ],
                'zones_allow_external_fillets': False,
            },
        },
        'boards': [],
        'cvpcb': {'equivalence_files': []},
        'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
        'meta': {'filename': NAME + '.kicad_pro', 'version': 3},
        'net_settings': {
            'classes': [
                netclass('Default', design.TRACE_W, design.CLEARANCE, 2147483647),
                netclass('Power', design.POWER_W, design.CLEARANCE, 1),
            ],
            'meta': {'version': 4},
            'net_colors': None,
            'netclass_assignments': None,
            'netclass_patterns': [
                {'netclass': 'Power', 'pattern': net} for net in sorted(design.POWER_NETS)
            ] + [{'netclass': 'Power', 'pattern': design.GND_NET}],
        },
        'pcbnew': {'last_paths': {}, 'page_layout_descr_file': ''},
        'schematic': {
            'legacy_lib_dir': '',
            'legacy_lib_list': [],
            'meta': {'version': 1},
            'page_layout_descr_file': '',
        },
        'sheets': [[SHEET_UUID, 'Root']],
        'text_variables': {},
    }


def bom():
    """Group parts by value+footprint, the way an assembler wants to see them."""
    groups = defaultdict(list)
    for ref, (value, lib_id, fp_id, *_rest) in design.PARTS.items():
        if ref.startswith('H'):
            continue                          # mounting holes are not purchased parts
        groups[(value, fp_id)].append(ref)
    rows = []
    for (value, fp_id), refs in groups.items():
        refs = sorted(refs, key=lambda r: (r[0], int(''.join(c for c in r if c.isdigit()) or 0)))
        notes, seen = [], set()
        for ref in refs:                      # keep every distinct role in the group
            d = design.PARTS[ref][6]
            if d not in seen:
                seen.add(d)
                notes.append(d if len(refs) == 1 else '%s: %s' % (ref, d))
        rows.append({
            'Refs': ' '.join(refs),
            'Qty': len(refs),
            'Value': value,
            'Footprint': fp_id.split(':', 1)[1],
            'Notes': '; '.join(notes),
        })
    rows.sort(key=lambda r: (r['Refs'][0], r['Refs']))
    return rows


def main():
    path = os.path.join(ROOT, NAME + '.kicad_pro')
    with open(path, 'w') as fh:
        json.dump(project(), fh, indent=2, sort_keys=True)
        fh.write('\n')
    print('wrote', os.path.basename(path))

    tbl = os.path.join(ROOT, 'sym-lib-table')
    open(tbl, 'w').write(
        '(sym_lib_table\n'
        '  (version 7)\n'
        '  (lib (name "BME688_Breakout")(type "KiCad")'
        '(uri "${KIPRJMOD}/lib/BME688_Breakout.kicad_sym")(options "")'
        '(descr "Symbols specific to this board"))\n'
        ')\n')
    print('wrote sym-lib-table')

    rows = bom()
    csv_path = os.path.join(ROOT, 'doc', 'bom.csv')
    with open(csv_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['Refs', 'Qty', 'Value', 'Footprint', 'Notes'])
        w.writeheader()
        w.writerows(rows)
    print('wrote doc/bom.csv  (%d lines, %d placements)'
          % (len(rows), sum(r['Qty'] for r in rows)))


if __name__ == '__main__':
    main()
