# Nest flat-pattern DXFs onto sheets with bounding-box shelf packing.
# Runs with system Python (needs ezdxf): python nest_dxf.py parts.json out.dxf
# parts.json: {"sheet_w": 2500, "sheet_h": 1250, "gap": 10, "parts": [{"name": .., "dxf": .., "qty": 1}],
#              "styles": {layer: {"label", "show", "color", "ltype"}}, "legend": true}
import json, sys, os, math, datetime
# Output is always UTF-8: on Windows a piped stdout is cp1252, and the Turkish summary lines ("OZET ...") would stop
# the run with UnicodeEncodeError before the nesting DXF is written. sac_core reads the pipe as UTF-8.
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import ConstructionArc
from ezdxf.tools.standards import linetypes
from ezdxf import path as dpath, edgesmith, edgeminer
import dil
from dil import L


def say(msg):
    # a line for the result message in Fusion (sac_core shows the "OZET " lines, in the chosen language)
    print('OZET ' + msg, flush=True)

SHEET_GAP = 100  # mm between sheets in the output drawing
LTSCALE = 5  # ezdxf's standard dash patterns are ~0.5 unit; x5 gives ~2.5 mm dashes on mm drawings
LEGEND = 'ACIKLAMA'  # legend layer, kept off the parts; never nested
TR_ASCII = str.maketrans('ıİşŞğĞüÜöÖçÇ', 'iIsSgGuUoOcC')
# line kinds in Fusion's flat-pattern DXF, with today's look as the default
DEFAULT_STYLES = {
    'OUTER_PROFILES': {'label': 'Dış kesim', 'show': True, 'color': 7, 'ltype': 'CONTINUOUS'},
    'INTERIOR_PROFILES': {'label': 'İç kesim (delik)', 'show': True, 'color': 7, 'ltype': 'CONTINUOUS'},
    'BEND': {'label': 'Büküm çizgisi', 'show': True, 'color': 1, 'ltype': 'CONTINUOUS'},
    'BEND_EXTENT': {'label': 'Büküm sınırı', 'show': True, 'color': 7, 'ltype': 'CONTINUOUS'},
    # model-making mode: bends become scores (low power), living-hinge slits (cut) or heat-bend marks (not cut)
    'CIZIK': {'label': 'Çizik (düşük güç, kesmez)', 'show': True, 'color': 5, 'ltype': 'CONTINUOUS'},
    'MENTESE': {'label': 'Esnek menteşe yarığı (kesim)', 'show': True, 'color': 1, 'ltype': 'CONTINUOUS'},
    'ISARET': {'label': 'Isıyla büküm işareti (kesmez)', 'show': True, 'color': 3, 'ltype': 'CONTINUOUS'},
}
MAKET_MARK = 'SACMAKET'  # empty layer: the part DXF already has its model-making lines (never offset twice); a
# layer, since Fusion's R2000 DXFs drop header custom variables
HINGE_SLIT, HINGE_BRIDGE = 15.0, 3.0  # living hinge: slit length and the uncut bridge between slits, mm


def ensure_linetypes(doc):
    have = {lt.dxf.name.upper() for lt in doc.linetypes}
    for name, desc, pattern in linetypes():
        if name.upper() not in have: doc.linetypes.add(name, pattern=pattern, description=desc)


def styles_of(cfg):
    st = {k: dict(v) for k, v in DEFAULT_STYLES.items()}
    for k, v in (cfg.get('styles') or {}).items():
        st.setdefault(k, {}).update(v)
    for v in st.values(): v['label'] = L(v['label'])  # the dialog sends them translated already; defaults are Turkish
    return st


def apply_styles(doc, msp, styles):
    # each line kind gets its colour and line type (layer and entities both, CAM programs read either); hidden kinds
    # are removed. No text on the parts: the laser would cut or engrave it
    ensure_linetypes(doc)
    for name in {e.dxf.layer for e in msp}:  # Fusion's DXF uses layers it never declares in the table
        if name not in doc.layers: doc.layers.add(name)
    for layer, s in styles.items():
        if layer in doc.layers:
            doc.layers.get(layer).color = s['color']
            doc.layers.get(layer).dxf.linetype = s['ltype']
        for e in list(msp.query('*[layer=="%s"]' % layer)):
            if not s['show']:
                msp.delete_entity(e); continue
            e.dxf.color = s['color']
            e.dxf.linetype = s['ltype']
            e.dxf.ltscale = LTSCALE
    for e in list(msp.query('TEXT MTEXT')) + list(msp.query('*[layer=="%s"]' % LEGEND)):  # also a legend from a re-run
        if e.is_alive: msp.delete_entity(e)


def add_legend(doc, msp, x, ytop, styles, h):
    # one sample line per kind present in the drawing, with what it is, at (x, ytop) going down; outside the parts
    present = {e.dxf.layer for e in part_entities(msp)}
    # DXF before R2007 is not UTF-8 and stores Turkish letters as \U+ codes some CAM programs print as is
    txt = (lambda t: t) if doc.dxfversion >= 'AC1021' else (lambda t: t.translate(TR_ASCII))
    if LEGEND not in doc.layers: doc.layers.add(LEGEND, color=7)
    a = {'layer': LEGEND}
    msp.add_text(txt(L('AÇIKLAMA')), height=h * 1.2, dxfattribs=a).set_placement((x, ytop))
    y = ytop - h * 3
    for layer, s in styles.items():
        if not s['show'] or layer not in present: continue
        msp.add_line((x, y + h / 2), (x + h * 8, y + h / 2),
                     dxfattribs={'layer': LEGEND, 'color': s['color'], 'linetype': s['ltype'], 'ltscale': LTSCALE})
        msp.add_text(txt(s['label']), height=h, dxfattribs=a).set_placement((x + h * 9, y))
        y -= h * 2.5


def part_entities(msp):
    return [e for e in msp if e.dxf.layer != LEGEND]


def poly_area(pts):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2


def loops(ents, tol=0.2):
    # every closed contour among the entities as a polygon (mm): closed entities as they are, loose lines/arcs chained
    polys = []
    closed = [e for e in ents if edgesmith.is_closed_entity(e)]
    for e in closed:
        polys.append([(v.x, v.y) for v in dpath.make_path(e).flattening(tol)])
    edges = list(edgesmith.edges_from_entities_2d([e for e in ents if e not in closed]))
    if edges:
        for loop in edgeminer.find_all_loops(edgeminer.Deposit(edges), timeout=5):
            polys.append([(v.x, v.y) for v in edgesmith.path2d_from_chain(loop).flattening(tol)])
    return [q[:-1] if len(q) > 3 and q[0] == q[-1] else q for q in polys if len(q) >= 3]


def outline(ents, tol=0.2):
    # the part's outer cut contour as one polygon (mm): closed entities as they are, loose lines/arcs chained into
    # loops; arcs flattened to within tol. The largest loop is the outer one
    polys = []
    closed = [e for e in ents if edgesmith.is_closed_entity(e)]
    for e in closed:
        polys.append([(v.x, v.y) for v in dpath.make_path(e).flattening(tol)])
    edges = list(edgesmith.edges_from_entities_2d([e for e in ents if e not in closed]))
    if edges:
        for loop in edgeminer.find_all_loops(edgeminer.Deposit(edges), timeout=5):
            polys.append([(v.x, v.y) for v in edgesmith.path2d_from_chain(loop).flattening(tol)])
    polys = [q[:-1] if len(q) > 3 and q[0] == q[-1] else q for q in polys if len(q) >= 3]
    return max(polys, key=poly_area) if polys else None


def load_parts(cfg, out, tol=0.2):
    # one block per part type, with its size and outer outline relative to the block's base point
    types = []
    for i, p in enumerate(cfg['parts']):
        src = ezdxf.readfile(p['dxf'])
        ents = part_entities(src.modelspace())  # the part's own legend stays out of the nesting
        box = bbox.extents(ents)
        if not box.has_data:
            print('EMPTY', p['dxf']); continue
        for e in ents:  # Fusion's DXF uses layers it never declares in the table
            if e.dxf.layer not in out.layers: out.layers.add(e.dxf.layer)
            if e.dxf.layer not in src.layers: src.layers.add(e.dxf.layer)
        block = 'PART_%02d' % (i + 1)
        imp = Importer(src, out)
        imp.import_tables()
        blk = out.blocks.new(block, base_point=(box.extmin.x, box.extmin.y))
        imp.import_entities(ents, blk)
        imp.finalize()
        try:
            pts = outline([e for e in ents if e.dxf.layer == 'OUTER_PROFILES'], tol)
        except Exception:
            pts = None
        if not pts:  # no outer contour (hidden or unreadable): its bounding box stands in
            pts = [(box.extmin.x, box.extmin.y), (box.extmax.x, box.extmin.y), (box.extmax.x, box.extmax.y), (box.extmin.x, box.extmax.y)]
            print('KONTUR YOK, kutu kullanildi', p['name'])
        local = [(x - box.extmin.x, y - box.extmin.y) for x, y in pts]
        try:  # cut-outs, where small parts may go
            holes = [[(x - box.extmin.x, y - box.extmin.y) for x, y in q]
                     for q in loops([e for e in ents if e.dxf.layer == 'INTERIOR_PROFILES'])]
        except Exception:
            holes = []
        types.append({'name': p['name'], 'label': p.get('body') or p['name'], 'block': block, 'w': box.size.x, 'h': box.size.y,
                      'qty': int(p.get('qty', 1)), 'outline': local, 'area': poly_area(local),
                      # Fusion's bend-line body holds every bend line twice (top and bottom face)
                      'bends': (len(p.get('bends') or []) + 1) // 2,
                      'holes': sorted(holes, key=poly_area, reverse=True),
                      'net': max(0.0, poly_area(local) - sum(poly_area(h) for h in holes))})
    return types


def scrap(types, sheet, sw, sh):
    # Scrap of one sheet, three ways: of the whole sheet (100 - fill); inside the rectangle the parts take (what is
    # really wasted when the rest of the sheet is kept for later; holes count as waste); and the sheet left over
    # outside that rectangle. Part area = outline minus its holes (parts nested in holes count on their own).
    net = sum(types[k].get('net', types[k]['area']) for k, *_ in sheet)
    xs, ys = [], []
    for k, x, y, rot in sheet:
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for px, py in types[k]['outline']:
            xs.append(x + c * px - s_ * py); ys.append(y + s_ * px + c * py)
    bw, bh = (max(xs) - min(xs), max(ys) - min(ys)) if xs else (0.0, 0.0)
    whole = sw * sh
    return {'fill': net / whole * 100, 'sheet_scrap': 100 - net / whole * 100, 'box': (bw, bh),
            'box_scrap': (1 - net / (bw * bh)) * 100 if bw * bh else 0.0, 'left': (whole - bw * bh) / whole * 100,
            'left_m2': (whole - bw * bh) / 1e6, 'net_m2': net / 1e6}


def rotations_for(step):
    # allowed turns of a part: every `step` degrees (90 = the four right angles)
    step = max(1.0, min(90.0, float(step)))
    return [round(i * step, 6) for i in range(int(round(360.0 / step)))]


def min_box_turn(outline):
    # the turn that makes the part's enclosing rectangle smallest (rotating calipers over the convex hull edges; the
    # idea PrusaSlicer's arrange uses before placing a part)
    pts = sorted(set(outline))
    if len(pts) < 3: return 0.0
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0: lower.pop()
        lower.append(q)
    for q in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0: upper.pop()
        upper.append(q)
    hull = lower[:-1] + upper[:-1]
    best = None
    for (x0, y0), (x1, y1) in zip(hull, hull[1:] + hull[:1]):
        a = math.atan2(y1 - y0, x1 - x0)
        c, s_ = math.cos(-a), math.sin(-a)
        xs = [c * x - s_ * y for x, y in hull]; ys = [s_ * x + c * y for x, y in hull]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best is None or area < best[0]: best = (area, -math.degrees(a))
    return best[1] % 360


def edge_turns(outline, keep=8):
    # the turns that lay one of the part's longer edges flat (horizontal or vertical): a slanted side of one part
    # can then run along a straight side of the next. Always includes the four right angles.
    edges = sorted(((math.hypot(x1 - x0, y1 - y0), math.degrees(math.atan2(y1 - y0, x1 - x0)))
                    for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1])), reverse=True)
    out = {0.0, 90.0, 180.0, 270.0}
    m = min_box_turn(outline)  # smallest enclosing rectangle, in its four right-angle variants
    for b in (m, m + 90, m + 180, m + 270):
        b = round(b % 360, 1)
        if all(min(abs(b - c), 360 - abs(b - c)) > 1.0 for c in out): out.add(b)
    for _, a in edges[:keep]:
        for b in (-a, 90 - a, 180 - a, 270 - a):
            b = round(b % 360, 1)
            if all(min(abs(b - c), 360 - abs(b - c)) > 1.0 for c in out): out.add(b)
    return sorted(out)


def turn_sets(types, mode):
    # one list of allowed turns per part type
    if mode == 'edges': return [edge_turns(t['outline']) for t in types]
    return [rotations_for(mode) for _ in types]


def compact(ironnest, types, ks, qty, sw, sh, gap, layout, rot):
    # Pack one sheet's parts into the smallest square (or sheet-shaped rectangle) at the sheet's bottom-left corner,
    # instead of the long strip along the edge the plain fill leaves. Binary search on the side with quick settings,
    # then one careful run at the size found. Returns placements [(type, x, y, rot)] or None (keep the plain fill).
    items = [types[k]['outline'] for k in ks]
    rots = [rot[k] for k in ks]
    area = sum(types[k]['area'] * q for k, q in zip(ks, qty))
    r = sw / sh if layout == 'rect' else 1.0  # width : height of the box that grows

    def box(side):
        w, h = min(side * r, sw), min(side, sh)
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def fits(side, careful):
        kw = dict(restarts=4, strategy='nfp') if careful else dict(strategy='sampling', separation_effort='fast')
        placed, unplaced = ironnest.nest(items, qty, box(side), [], float(gap), rots, 1, 400 if careful else 150, **kw)
        return None if unplaced else placed

    lo = max(math.sqrt(area / r), max(min(types[k]['w'], types[k]['h']) for k in ks) + 2 * gap)
    hi = max(sw / r, sh)
    if not fits(hi, False): return None
    for _ in range(7):
        mid = (lo + hi) / 2
        if fits(mid, False): hi = mid
        else: lo = mid
    side = hi
    while side <= max(sw / r, sh) * 1.001:
        placed = fits(side, True)
        if placed: return [(ks[i], x, y, a) for i, x, y, a in placed]
        side *= 1.05
    return None


def fill_holes(ironnest, types, gap, rot):
    # Part in part: before the sheets, every cut-out of every part (largest first) is offered to the parts small enough
    # to fit, nested inside it with the gap kept. Returns hosts [(type, [(child type, x, y, rot) in host frame])] for
    # each part copy that received parts, and the demand still left per type.
    left = [t['qty'] for t in types]
    hosts = []
    smallest = min(min(t['w'], t['h']) for t in types) + 2 * gap
    order = sorted((k for k, t in enumerate(types) if t['holes']), key=lambda k: -types[k]['area'])
    for k in order:
        for _ in range(types[k]['qty']):
            if left[k] <= 0: break
            left[k] -= 1  # this copy is the host; its children ride along
            kids = []
            for hole in types[k]['holes']:
                xs, ys = [x for x, _ in hole], [y for _, y in hole]
                if min(max(xs) - min(xs), max(ys) - min(ys)) < smallest: continue
                ks = [j for j, t in enumerate(types) if left[j] > 0 and t['area'] < poly_area(hole)]
                if not ks: continue
                try:
                    placed, _ = ironnest.nest([types[j]['outline'] for j in ks], [left[j] for j in ks], hole, [],
                                              float(gap), [rot[j] for j in ks], 1, 200, strategy='nfp')
                except Exception as e:
                    print('DELIK atlandi (%s): %s' % (types[k]['name'], e)); continue
                for i, x, y, a in placed:
                    kids.append((ks[i], x, y, a)); left[ks[i]] -= 1
            hosts.append((k, kids))
    return hosts, left


def nest_once(ironnest, types, sw, sh, gap, layout, rot, holes):
    # one full nesting with one set of allowed turns: parts into cut-outs, spread over sheets, each sheet compacted.
    # Returns [[(type, x, y, rot), ...] per sheet], unplaced
    # parts that received parts in their cut-outs travel as one item ("host"), the rest as before
    hosts, _ = fill_holes(ironnest, types, gap, rot) if holes and any(t['holes'] for t in types) else ([], None)
    hosts = [h for h in hosts if h[1]]
    left = [t['qty'] for t in types]
    for k, kids in hosts:
        left[k] -= 1
        for j, *_ in kids: left[j] -= 1
    if hosts: print('  DELIK %d parca %d parcanin deliklerine yerlesti' % (sum(len(c) for _, c in hosts), len(hosts)))
    items = types + [dict(types[k], qty=1, name=types[k]['name'] + '+') for k, _ in hosts]  # one item per host copy
    irot = rot + [rot[k] for k, _ in hosts]
    qtys = left + [1] * len(hosts)
    sheet = [(0.0, 0.0), (sw, 0.0), (sw, sh), (0.0, sh)]
    need = sum(t['area'] * q for t, q in zip(items, qtys))
    n = min(50, int(need / (sw * sh) * 3) + 2)
    per_sheet, unplaced = ironnest.nest_multi(
        [t['outline'] for t in items], qtys, [(sheet, [])] * n, float(gap), irot, 1, 400, restarts=4, strategy='nfp')
    while per_sheet and not per_sheet[-1]: per_sheet = per_sheet[:-1]
    if layout != 'strip':
        for i, sheet_p in enumerate(per_sheet):
            ks = sorted({k for k, *_ in sheet_p})
            qty = [sum(1 for k2, *_ in sheet_p if k2 == k) for k in ks]
            better = compact(ironnest, items, ks, qty, sw, sh, gap, layout, irot)
            if better: per_sheet[i] = better

    return per_sheet, unplaced, items, irot, hosts


def expand(types, hosts, per_sheet, unplaced):
    # host items back into their own part plus their children, children turned and moved with them
    def one(k, x, y, a):
        if k < len(types): return [(k, x, y, a)]
        host, kids = hosts[k - len(types)]
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        return [(host, x, y, a)] + [(j, x + c * cx - s_ * cy, y + s_ * cx + c * cy, (a + ca) % 360) for j, cx, cy, ca in kids]
    return ([[q for pl in sh_ for q in one(*pl)] for sh_ in per_sheet],
            [k if k < len(types) else hosts[k - len(types)][0] for k in unplaced])


def used_box(types, sheet):
    # width and height of the box the placed parts take on one sheet
    xs, ys = [], []
    for k, x, y, a in sheet:
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
        for px, py in types[k]['outline']:
            xs.append(x + c * px - s_ * py); ys.append(y + s_ * px + c * py)
    return (max(xs) - min(xs), max(ys) - min(ys)) if xs else (0.0, 0.0)


def used_area(types, sheet):
    w, h = used_box(types, sheet)
    return w * h


def box_cost(types, sheet, layout):
    # what a compact layout minimises: the side of the square, or the area (least scrap)
    w, h = used_box(types, sheet)
    return (max(w, h), w * h) if layout == 'square' else (w * h, max(w, h))


# how hard sparrow works per sheet: seconds per strip height (grows with the part count) and the heights tried
QUALITY = {
    'balanced': {'secs': (10, 25), 'square': [0.92, 1.06], 'area': [0.7, 0.9, 1.1], 'refine': 1},
    'best': {'secs': (30, 60), 'square': [0.85, 0.95, 1.05, 1.15], 'area': [0.6, 0.75, 0.9, 1.05, 1.2], 'refine': 2},
}


def sparrow_compact(items, ks, qty, sw, sh, gap, layout, rot, free, quality='best'):
    # One sheet's parts packed with sparrow (spyrrow), the strongest open irregular strip packer: for a strip height h
    # it finds the shortest strip; several heights are tried and the one giving the smallest square (or least area)
    # kept. free: any angle. Returns placements [(type, x, y, rot)] or None. Strip edges keep the gap too.
    try:
        import spyrrow
    except Exception as e:
        print('  SPARROW yok: %s' % e); return None
    n = sum(qty)
    q = QUALITY.get(quality, QUALITY['best'])
    secs = int(min(q['secs'][1], max(q['secs'][0], 10 + 2 * n)))
    area = sum(items[k]['area'] * q for k, q in zip(ks, qty))
    lo = max(min(items[k]['w'], items[k]['h']) for k in ks) + 2 * gap + 1

    def solve(h):
        its = [spyrrow.Item(str(k), items[k]['outline'] + items[k]['outline'][:1], demand=q,
                            allowed_orientations=None if free else rot[k]) for k, q in zip(ks, qty)]
        sol = spyrrow.StripPackingInstance('sac', strip_height=float(h), items=its).solve(
            spyrrow.StripPackingConfig(early_termination=True, total_computation_time=secs, min_items_separation=float(gap), seed=0))
        if sol.width + 1e-6 > sw: return None
        return [(int(pi.id), pi.translation[0], pi.translation[1], pi.rotation % 360) for pi in sol.placed_items]

    base = math.sqrt(area / 0.6)  # side of a square at ~60 % density
    steps = q['square'] if layout == 'square' else q['area']
    best = None
    tried = set()
    for f in steps + [None] * q['refine']:
        if f is None:  # refine around the best so far
            if not best: break
            f = best[2] * (0.96 if len(tried) % 2 else 1.04)
        h = round(min(sh, max(lo, base * f)), 1)
        if h in tried: continue
        tried.add(h)
        placed = solve(h)
        if placed and len(placed) == n:
            cost = box_cost(items, placed, layout)
            print('  SPARROW h=%.0f -> %.0f x %.0f' % ((h,) + used_box(items, placed)), flush=True)
            if best is None or cost < best[0]: best = (cost, placed, h / base)
    return best[1] if best else None


# Many turns make ironnest slow and no better (14 parts: 15° steps 10+ min; edge-aligned turns 12 min and a larger box
# than 90°), so 'auto' spreads parts over sheets with 90° and leaves free angles to sparrow, which barely slows down
AUTO_MODES = [(90, '90° adım')]


def true_shape(types, sw, sh, gap, layout='square', step=90, holes=True, quality='balanced'):
    # Irregular nesting with ironnest: parts by their real outline, gap kept between parts and to the sheet edge;
    # leftover demand spills onto the next sheet; unless layout is 'strip', each sheet's parts are packed into the
    # smallest square/rectangle at its bottom-left corner. step 'auto' tries several sets of turns and keeps the best:
    # fewest sheets, then fewest left over, then least area taken. Returns [[(type, x, y, rot), ...] per sheet], unplaced
    import ironnest, time
    modes = [(s_, L(n_)) for s_, n_ in AUTO_MODES] if step == 'auto' else [(step, L('%s° adım') % step)]
    best = None
    for mode, name in modes:
        t0 = time.time()
        res = nest_once(ironnest, types, sw, sh, gap, layout, turn_sets(types, mode), holes)
        per, un, items = res[0], res[1], res[2]
        score = (len(per), len(un), sum(used_area(items, s_) for s_ in per))
        print('  ACI %-22s %d sac, yerlesmeyen %d, kaplanan %.0f mm2, %.0f sn' % (name, score[0], score[1], score[2], time.time() - t0),
              flush=True)
        if best is None or score < best[0]: best = (score, res, name)
    per_sheet, unplaced, items, irot, hosts = best[1]
    name = L('Otomatik') if step == 'auto' else best[2]
    if layout != 'strip' and quality in QUALITY:  # each sheet once more with sparrow; the smaller box wins
        used_sparrow = False
        for i, sheet_p in enumerate(per_sheet):
            ks = sorted({k for k, *_ in sheet_p})
            qty = [sum(1 for k2, *_ in sheet_p if k2 == k) for k in ks]
            t0 = time.time()
            sp = sparrow_compact(items, ks, qty, sw, sh, gap, layout, irot, step == 'auto', quality)
            if sp and box_cost(items, sp, layout) < box_cost(items, sheet_p, layout):
                print('  SAC %d: sparrow daha iyi %.0fx%.0f (ironnest %.0fx%.0f), %.0f sn' % (
                    (i + 1,) + used_box(items, sp) + used_box(items, sheet_p) + (time.time() - t0,)), flush=True)
                per_sheet[i] = sp
                used_sparrow = True
            else:
                print('  SAC %d: ironnest kaldi (%.0f sn)' % (i + 1, time.time() - t0), flush=True)
        if used_sparrow: name += ' + sparrow' + (L(' serbest açı') if step == 'auto' else '')
    per_sheet, unplaced = expand(types, hosts, per_sheet, unplaced)
    return per_sheet, unplaced, name


def pack(parts, sheet_w, sheet_h, gap):
    # long side horizontal, tallest first, fill shelves left to right
    for p in parts:
        p['rot'] = p['h'] > p['w'] and p['h'] <= sheet_w
        if p['rot']: p['w'], p['h'] = p['h'], p['w']
    parts.sort(key=lambda p: (-p['h'], -p['w']))
    sheets, sheet, x, y, shelf_h = [], [], gap, gap, 0
    for p in parts:
        if x + p['w'] + gap > sheet_w and x > gap:  # next shelf
            x, y, shelf_h = gap, y + shelf_h + gap, 0
        if y + p['h'] + gap > sheet_h and sheet:  # next sheet
            sheets.append(sheet); sheet, x, y, shelf_h = [], gap, gap, 0
        p['x'], p['y'] = x, y
        sheet.append(p)
        x += p['w'] + gap
        shelf_h = max(shelf_h, p['h'])
    if sheet: sheets.append(sheet)
    return sheets


def build_part_dxf(geom, path):
    # cut geometry read from the flat pattern in Fusion (used when Fusion's own DXF export fails)
    doc = ezdxf.new('R2010', units=4)
    msp = doc.modelspace()
    for e in geom:
        if e['l'] not in doc.layers: doc.layers.add(e['l'])
        a = {'layer': e['l']}
        if e['t'] == 'line': msp.add_line(e['p'][0], e['p'][1], dxfattribs=a)
        elif e['t'] == 'circle': msp.add_circle(e['c'], e['r'], dxfattribs=a)
        elif e['t'] == 'arc':
            (sx, sy), (mx, my), (ex, ey) = e['p']
            ccw = (mx - sx) * (ey - sy) - (my - sy) * (ex - sx) > 0  # from_3p always runs counter-clockwise
            start, end = (e['p'][0], e['p'][2]) if ccw else (e['p'][2], e['p'][0])
            arc = ConstructionArc.from_3p(start, end, e['p'][1])
            arc.add_to_layout(msp, dxfattribs=a)
        else: msp.add_lwpolyline(e['p'], dxfattribs=a)
    doc.saveas(path)


def segments(ents, tol=0.02):
    # every entity as straight pieces [((x0, y0), (x1, y1))], arcs flattened to within tol
    out = []
    for e in ents:
        try: pts = [(v.x, v.y) for v in dpath.make_path(e).flattening(tol)]
        except Exception: continue
        out += [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-6]
    return out


def bend_zones(bends, extents, reach=60.0):
    # each bend line with the strip it bends over: the nearest bend-extent line on either side, parallel to it and
    # alongside it. Returns [(p0, p1, unit along, unit normal, centre offset, width)]; width 0 = no extents found
    zones = []
    for p0, p1 in bends:
        L = math.dist(p0, p1)
        u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
        n = (-u[1], u[0])
        pos, neg = None, None
        for q0, q1 in extents:
            lq = math.dist(q0, q1)
            if abs(u[0] * (q1[1] - q0[1]) - u[1] * (q1[0] - q0[0])) > 0.02 * lq: continue  # not parallel
            t0 = u[0] * (q0[0] - p0[0]) + u[1] * (q0[1] - p0[1]); t1 = u[0] * (q1[0] - p0[0]) + u[1] * (q1[1] - p0[1])
            if min(L, max(t0, t1)) - max(0.0, min(t0, t1)) < 0.3 * min(L, lq): continue  # not alongside
            d = n[0] * (q0[0] - p0[0]) + n[1] * (q0[1] - p0[1])
            if 0.01 < d < reach and (pos is None or d < pos): pos = d
            if -reach < d < -0.01 and (neg is None or d > neg): neg = d
        if pos is None and neg is None: zones.append((p0, p1, u, n, 0.0, 0.0)); continue
        pos = pos if pos is not None else -neg
        neg = neg if neg is not None else -pos
        zones.append((p0, p1, u, n, (pos + neg) / 2, pos - neg))
    return zones


def maket_part(doc, msp, mk, pitch):
    # Model-making (laser on card, foam board, wood, acrylic). Cut lines stay as drawn: the laser program usually
    # compensates the kerf itself. Only when asked (grow_outer / grow_holes) the outer line moves out by half the kerf
    # and the holes' in by half, so a beam cutting on the line's centre leaves the true size. Bend lines are replaced by what the material needs over the bend's own strip (between its two extent lines):
    #   score: parallel score lines filling a wide (smooth) bend, one line in the middle of a sharp one
    #   hinge: rows of staggered slits (living hinge) for wood; one row for a sharp bend
    #   heat : two marks where the heating starts and ends (one in the middle for a sharp bend), never cut
    #   none : nothing (foam that cannot be laser-bent)
    from shapely.geometry import Polygon, LineString
    if MAKET_MARK in doc.layers: return
    kerf, how = float(mk.get('kerf', 0.0)), mk.get('bend', 'score')
    ents = part_entities(msp)
    outer = outline([e for e in ents if e.dxf.layer == 'OUTER_PROFILES'], 0.02)
    if not outer: return
    holes = loops([e for e in ents if e.dxf.layer == 'INTERIOR_PROFILES'], 0.02)
    part = Polygon(outer, [h for h in holes if len(h) >= 3]).buffer(0)
    bends = segments([e for e in ents if e.dxf.layer == 'BEND'])
    extents = segments([e for e in ents if e.dxf.layer == 'BEND_EXTENT'])
    grow_outer, grow_holes = kerf > 0 and mk.get('grow_outer'), kerf > 0 and mk.get('grow_holes')
    redraw = {'BEND', 'BEND_EXTENT'} | ({'OUTER_PROFILES'} if grow_outer else set()) | ({'INTERIOR_PROFILES'} if grow_holes else set())
    for e in ents:
        if e.dxf.layer in redraw: msp.delete_entity(e)
    for name in ('OUTER_PROFILES', 'INTERIOR_PROFILES', 'CIZIK', 'MENTESE', 'ISARET'):
        if name not in doc.layers: doc.layers.add(name)

    def ring(pts, layer):
        msp.add_lwpolyline([(round(x, 4), round(y, 4)) for x, y in pts[:-1]], close=True, dxfattribs={'layer': layer})
    if grow_outer:
        ring(list(Polygon(outer).buffer(kerf / 2, join_style='mitre', mitre_limit=4).exterior.coords), 'OUTER_PROFILES')
    for h in holes if grow_holes else []:
        hp = Polygon(h).buffer(-kerf / 2, join_style='mitre', mitre_limit=4)
        if hp.is_empty or hp.geom_type != 'Polygon': hp = Polygon(h)  # a hole thinner than the kerf: as drawn
        ring(list(hp.exterior.coords), 'INTERIOR_PROFILES')

    def line(p0, p1, u, n, off, layer, a=0.0, b=None):
        # the bend line moved `off` across, between a and b along it, kept inside the part
        L = math.dist(p0, p1)
        b = L if b is None else b
        s = LineString([(p0[0] + n[0] * off + u[0] * a, p0[1] + n[1] * off + u[1] * a),
                        (p0[0] + n[0] * off + u[0] * b, p0[1] + n[1] * off + u[1] * b)]).intersection(part)
        for g in getattr(s, 'geoms', [s]):
            if g.geom_type == 'LineString' and g.length > 0.05:
                msp.add_line(g.coords[0], g.coords[-1], dxfattribs={'layer': layer})

    p = max(float(pitch), 2 * kerf, 0.2)  # burnt lines closer than two kerfs would merge and cut through
    for p0, p1, u, n, c, w in bend_zones(bends, extents):
        L = math.dist(p0, p1)
        if how == 'none': continue
        if how == 'heat':
            for off in ((c - w / 2, c + w / 2) if w >= 2 * p else (c,)): line(p0, p1, u, n, off, 'ISARET')
            continue
        step = p if how == 'score' else max(p, 4 * kerf, 1.0)
        span = w - kerf  # the outer lines' burn stays inside the strip
        rows = int(span // step) + 1 if w >= 2 * step else 1
        offs = [c] if rows == 1 else [c - span / 2 + i * span / (rows - 1) for i in range(rows)]
        for r, off in enumerate(offs):
            if how == 'score':
                line(p0, p1, u, n, off, 'CIZIK'); continue
            # living hinge: slits with uncut bridges, every other row shifted half a pitch; the part's own edges
            # always keep a bridge, so no row cuts the part apart
            pitch_ = HINGE_SLIT + HINGE_BRIDGE
            a = HINGE_BRIDGE - (pitch_ / 2 if r % 2 else 0)
            while a < L - HINGE_BRIDGE:
                s0, s1 = max(a, HINGE_BRIDGE), min(a + HINGE_SLIT, L - HINGE_BRIDGE)
                if s1 - s0 > 1.0: line(p0, p1, u, n, off, 'MENTESE', s0, s1)
                a += pitch_
    doc.layers.add(MAKET_MARK)


def merge_edges(msp, tol=0.1):
    # Parts nested edge to edge: where two outer cut lines run on top of each other, keep one, so the laser goes
    # along a shared edge once. Lines are compared by direction and position (buckets), the later one loses the
    # stretch the earlier one already covers. Returns the merged length, mm
    ents = [e for e in msp if e.dxf.layer == 'OUTER_PROFILES']
    segs = []  # (entity no., p0, p1, unit, normal offset, angle bucket, offset bucket)
    for i, e in enumerate(ents):
        for a, b in segments([e]):
            L = math.dist(a, b)
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            if u[1] < -1e-12 or (abs(u[1]) <= 1e-12 and u[0] < 0): u = (-u[0], -u[1])  # one direction per line
            ang = math.degrees(math.atan2(u[1], u[0])) % 180
            d = -u[1] * a[0] + u[0] * a[1]
            segs.append((i, a, b, u, d, round(ang / 0.5) % 360, round(d / 0.5)))
    buckets = {}
    for j, s in enumerate(segs): buckets.setdefault((s[5], s[6]), []).append(j)
    cut = {}  # segment no. -> covered stretches along it
    for j, (i, a, b, u, d, ka, kd) in enumerate(segs):
        ta, tb = sorted((u[0] * a[0] + u[1] * a[1], u[0] * b[0] + u[1] * b[1]))
        for da in (-1, 0, 1):
            for dd in (-1, 0, 1):
                # near 0/180 deg the same line flips its direction and the sign of its offset
                for key in {((ka + da) % 360, kd + dd), ((ka + da) % 360, -(kd + dd))}:
                    for o in buckets.get(key, ()):
                        oi, oa, ob, ou, od, *_ = segs[o]
                        if oi >= i: continue  # only earlier parts' lines win
                        if abs(u[0] * ou[1] - u[1] * ou[0]) > 0.005: continue
                        if any(abs(-u[1] * q[0] + u[0] * q[1] - d) > tol for q in (oa, ob)): continue
                        oa_, ob_ = sorted((u[0] * oa[0] + u[1] * oa[1], u[0] * ob[0] + u[1] * ob[1]))
                        lo, hi = max(ta, oa_), min(tb, ob_)
                        if hi - lo > 0.05: cut.setdefault(j, []).append((lo, hi))
    if not cut: return 0.0
    merged = 0.0
    for i in sorted({segs[j][0] for j in cut}):
        e = ents[i]
        layer = e.dxf.layer
        for j, (si, a, b, u, d, *_) in enumerate(segs):
            if si != i: continue
            ta, tb = sorted((u[0] * a[0] + u[1] * a[1], u[0] * b[0] + u[1] * b[1]))
            keep, pos = [], ta
            for lo, hi in sorted(cut.get(j, [])):
                if lo > pos: keep.append((pos, lo))
                merged += max(0.0, min(hi, tb) - max(lo, pos)); pos = max(pos, hi)
            if pos < tb: keep.append((pos, tb))
            f = (-u[1] * d, u[0] * d)  # foot of the line's normal from the origin; points are f + t*u
            for lo, hi in keep:
                if hi - lo > 0.01:
                    msp.add_line((f[0] + u[0] * lo, f[1] + u[1] * lo), (f[0] + u[0] * hi, f[1] + u[1] * hi),
                                 dxfattribs={'layer': layer})
        msp.delete_entity(e)
    return merged


def style_part(path, styles, legend, maket=None, pitch=1.0):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    if maket: maket_part(doc, msp, maket, pitch)
    apply_styles(doc, msp, styles)
    box = bbox.extents(part_entities(msp))
    if legend and box.has_data:
        add_legend(doc, msp, box.extmax.x + 15, box.extmax.y, styles, 3.5)
    doc.saveas(path)


CUT_LAYERS = ('OUTER_PROFILES', 'INTERIOR_PROFILES', 'CIZIK', 'MENTESE', 'ISARET')  # the laser's lines, any power


# Pricing, the way laser shops quote (see NOTLAR.md): material = the sheets bought (by kg, m² or per sheet); laser =
# metal shops: metres of cut + one price per pierce (every start of a cut); model-making workshops: machine minutes,
# from cut and score lengths over the machine's speeds plus a second per pierce; bending (press brake) per bend; one
# set-up fee per job. Prices are typed in the dialog and kept in _fiyatlar.json; nothing is priced unless given.
CUT_PRICED, SCORE_PRICED = ('OUTER_PROFILES', 'INTERIOR_PROFILES', 'MENTESE'), ('CIZIK', 'ISARET')
PIERCE_S, SCORE_START_S = 1.0, 0.3  # seconds per pierce / per score line start, minute pricing


def sheet_price(cost, w, h):
    # price of one w x h sheet, TL; per-sheet prices: the size's own price, else the reference sheet's by area
    unit, price = cost.get('unit', 'levha'), float(cost.get('price', 0) or 0)
    if unit == 'kg': return w * h * float(cost.get('t', 0)) * float(cost.get('density', 7.85)) / 1e6 * price
    if unit == 'm2': return w * h / 1e6 * price
    own = (cost.get('sizes') or {}).get('%gx%g' % (max(w, h), min(w, h)))
    if own: return float(own)
    rw, rh = cost.get('ref') or (w, h)
    return price * (w * h) / (rw * rh) if rw * rh else price


def job_cost(doc, types, sheets, sw, sh, cost, merged, maket):
    # material, laser, bending and set-up for one nesting; per sheet and per part type
    las = cost.get('laser') or {}
    per_type = []
    for t in types:
        ents = list(doc.blocks.get(t['block']))
        cut = sum(math.dist(a, b) for a, b in segments([e for e in ents if e.dxf.layer in CUT_PRICED]))
        score = sum(math.dist(a, b) for a, b in segments([e for e in ents if e.dxf.layer in SCORE_PRICED]))
        pierces = 1 + len(t['holes']) + sum(1 for e in ents if e.dxf.layer == 'MENTESE')
        starts = sum(1 for e in ents if e.dxf.layer in SCORE_PRICED)
        per_type.append({'cut': cut / 1000, 'score': score / 1000, 'pierces': pierces, 'starts': starts,
                         'bends': 0 if maket else t.get('bends', 0)})

    def laser(cut_m, score_m, pierces, starts):
        if las.get('mode') == 'dakika':
            cs, ss = float(las.get('cut_speed') or 0), float(las.get('score_speed') or 0)
            mins = ((cut_m * 1000 / cs if cs else 0) + (score_m * 1000 / ss if ss else 0) +
                    pierces * PIERCE_S + starts * SCORE_START_S) / 60
            return mins * float(las.get('per_min') or 0), mins
        return (cut_m * float(las.get('per_m') or 0) + pierces * float(las.get('per_pierce') or 0) +
                score_m * float(las.get('per_score_m') or 0)), None

    sp = sheet_price(cost, sw, sh)
    rows, tot = [], {'sheet': 0.0, 'share': 0.0, 'laser': 0.0, 'bend': 0.0, 'mins': 0.0}
    for n, sheet in enumerate(sheets):
        f = scrap(types, sheet, sw, sh)
        cut = sum(per_type[k]['cut'] for k, *_ in sheet) - (merged / 1000 if n == 0 else 0)  # shared edges cut once
        score = sum(per_type[k]['score'] for k, *_ in sheet)
        pierces = sum(per_type[k]['pierces'] for k, *_ in sheet)
        lz, mins = laser(cut, score, pierces, sum(per_type[k]['starts'] for k, *_ in sheet))
        bend = sum(per_type[k]['bends'] for k, *_ in sheet) * float(cost.get('per_bend') or 0)
        share = sp * f['fill'] / 100
        rows.append({'sheet': sp, 'share': share, 'box_scrap': sp * (f['box'][0] * f['box'][1]) / (sw * sh) - share,
                     'laser': lz, 'mins': mins, 'cut': cut, 'score': score, 'pierces': pierces, 'bend': bend})
        for k in ('sheet', 'share', 'laser', 'bend'): tot[k] += rows[-1][k]
        tot['mins'] += mins or 0
    setup = float(cost.get('setup') or 0)
    tot['setup'] = setup
    tot['all'] = tot['sheet'] + tot['laser'] + tot['bend'] + setup
    tot['parts_only'] = tot['share'] + tot['laser'] + tot['bend'] + setup
    lines = []
    for n, r in enumerate(rows):
        lines.append('MALIYET sac %d: levha %.2f TL (parcalarin payi %.2f, bolgedeki fire %.2f) | lazer %.2f TL (%.2f m kesim, '
                     '%.2f m cizik, %d giris%s)%s' % (n + 1, r['sheet'], r['share'], r['box_scrap'], r['laser'], r['cut'],
                                                     r['score'], r['pierces'], L(', %.1f dk') % r['mins'] if r['mins'] is not None else '',
                                                     ' | bukum %.2f TL' % r['bend'] if r['bend'] else ''))
    lines.append('MALIYET TOPLAM: %.2f TL (levhalarin tamami) / %.2f TL (yalniz parcalarin payi)%s' % (
        tot['all'], tot['parts_only'], ', hazirlik %.2f TL dahil' % setup if setup else ''))
    # each part type: its share of the sheet by area, its own cut and score, bends; set-up shared by area
    unit_area = sp / (sw * sh)
    all_net = sum(t.get('net', t['area']) * t['qty'] for t in types) or 1
    parts = []
    for t, c in zip(types, per_type):
        lz, mins = laser(c['cut'], c['score'], c['pierces'], c['starts'])
        mat = t.get('net', t['area']) * unit_area
        bend = c['bends'] * float(cost.get('per_bend') or 0)
        one = mat + lz + bend + setup * t.get('net', t['area']) / all_net
        parts.append({'name': t['name'], 'qty': t['qty'], 'area_m2': t.get('net', t['area']) / 1e6, 'mat': mat,
                      'cut_m': c['cut'], 'score_m': c['score'], 'pierces': c['pierces'], 'mins': mins, 'laser': lz,
                      'bends': c['bends'], 'bend': bend, 'one': one, 'all': one * t['qty']})
    return {'rows': rows, 'tot': tot, 'parts': parts, 'lines': lines, 'unit': cost.get('unit', 'levha'),
            'mode': las.get('mode', 'metre')}


def write_cost_csv(costs, out_path):
    # per part cost table; ";" and decimal commas so Turkish Excel opens it straight
    stem = os.path.basename(out_path)
    path = os.path.join(os.path.dirname(out_path), stem.replace('00_NESTING_', L('00_MALIYET_')) if '00_NESTING_' in stem
                        else os.path.splitext(stem)[0] + '_MALIYET.dxf')
    path = os.path.splitext(path)[0] + '.csv'
    # Turkish Excel: ";" between columns and decimal commas; English: "," and decimal points
    num = lambda v, d=2: dil.num(v, '%%.%df' % d)
    sep = ';' if dil.LANG != 'en' else ','
    rows = [L('Parça;Adet;Alan (m²);Malzeme payı (TL);Kesim (m);Çizik (m);Giriş;Lazer (TL);Büküm adedi;Büküm (TL);'
            'Bir adet (TL);Toplam (TL)')]
    for p in costs['parts']:
        rows.append(';'.join([p['name'], str(p['qty']), num(p['area_m2'], 4), num(p['mat']), num(p['cut_m']),
                              num(p['score_m']), str(p['pierces']), num(p['laser']), str(p['bends']), num(p['bend']),
                              num(p['one']), num(p['all'])]))
    t = costs['tot']
    rows += ['', L('Levhaların tamamı (TL);') + num(t['sheet']), L('Parçaların levha payı (TL);') + num(t['share']),
             L('Lazer (TL);') + num(t['laser']), L('Büküm (TL);') + num(t['bend']), L('Hazırlık (TL);') + num(t['setup']),
             L('TOPLAM, levhaların tamamıyla (TL);') + num(t['all']), L('TOPLAM, yalnız parçaların payıyla (TL);') + num(t['parts_only'])]
    rows = [sep.join('"%s"' % c if sep in c else c for c in r.split(';')) for r in rows]  # a name holding sep is quoted
    with open(path, 'w', encoding='utf-8-sig') as f: f.write('\n'.join(rows) + '\n')
    print('MALIYET tablosu: %s' % os.path.basename(path))


def nest(cfg, parts, out_path, sw, sh, styles, info=None, maket=None, sizes=None, cost=None):
    gap = cfg['gap']
    kerf = float(cfg.get('kerf', 0.0))
    edge = float(cfg.get('edge', gap))
    common = bool(cfg.get('common', False))
    merge = bool(maket and cfg.get('merge'))
    # between parts: the gap plus the beam's width; common-line cutting: the beam's width only, so one cut along the
    # middle trims both parts (the CAM program does the shared cut). Sheet edge: its own margin. Parts are nested on an
    # inner sheet shrunk by (margin - spacing) on every side, then shifted back, so every packer keeps both distances.
    # Model-making: the outlines already carry half the kerf, so parts touch (merged edges) or keep just the gap
    if maket:
        kerf, common = float(maket.get('kerf', 0.0)), False
        sep = 0.0 if merge else gap
    else:
        sep = kerf if common else gap + kerf
    m = max(0.0, edge - sep)
    out = ezdxf.new('R2010', units=4)  # mm
    ensure_linetypes(out)
    out.layers.add('SHEET', color=8)
    msp = out.modelspace()
    # parts nested edge to edge: arcs flattened finely, or a chord's bulge could cross into the neighbour
    types = load_parts({'parts': parts}, out, 0.02 if merge else 0.2)
    for layer, s in styles.items():  # load_parts adds the part layers in default white
        if layer in out.layers:
            out.layers.get(layer).color = s['color']
            out.layers.get(layer).dxf.linetype = s['ltype']

    def packing(sw, sh, quality):
        # one nesting on sw x sh: (sheets of placements in sheet coordinates, unplaced, method, turns)
        sw2, sh2 = sw - 2 * m, sh - 2 * m
        sheets, unplaced, how, turns = None, [], 'gercek sekil', ''
        if cfg.get('method', 'shape') == 'shape':
            try:
                sheets, unplaced, turns = true_shape(types, sw2, sh2, sep, cfg.get('layout', 'square'),
                                                     cfg.get('angle_step', 90), cfg.get('holes', True), quality)
            except Exception as e:  # ironnest missing or failing: the rectangle packer still gives a usable nesting
                print('GERCEK SEKIL OLMADI, dikdortgene donuldu: %s' % e)
                say(L('Gerçek şekil dizim olmadı, dikdörtgen kullanıldı.'))
        if sheets is None:
            how = 'dikdortgen'
            inst = [dict(t, type=k) for k, t in enumerate(types) for _ in range(t['qty'])]
            sheets = [[(p['type'], p['x'] + (p['w'] if p['rot'] else 0), p['y'], 90.0 if p['rot'] else 0.0) for p in sh_]
                      for sh_ in pack(inst, sw2, sh2, sep)]
        return [[(k, x + m, y + m, r) for k, x, y, r in sh_] for sh_ in sheets], unplaced, how, turns

    quality = cfg.get('quality', 'balanced')
    auto, res = '', None
    if sizes:
        # "Otomatik": the smallest standard sheet that takes every part at once. Sheets too small for the biggest
        # part or for the parts' total area (+15 %) are skipped unseen; the rest get a quick nesting (no sparrow)
        # from small to large, and the final nesting runs on the first one that holds everything
        net = sum(t.get('net', t['area']) * t['qty'] for t in types)
        boxes = []
        for t in types:
            a = min_box_turn(t['outline'])
            c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
            xs = [c * x - s_ * y for x, y in t['outline']]; ys = [s_ * x + c * y for x, y in t['outline']]
            boxes.append(sorted((max(xs) - min(xs), max(ys) - min(ys))))
        tried = 0
        cands = sorted({(max(a, b), min(a, b)) for a, b in sizes}, key=lambda z: z[0] * z[1])
        for w, h in cands:
            iw, ih = w - 2 * edge, h - 2 * edge
            if iw <= 0 or ih <= 0 or net > 0.85 * iw * ih: continue
            if any(b[0] > ih + 1e-6 or b[1] > iw + 1e-6 for b in boxes): continue
            tried += 1
            r = packing(w, h, 'fast')
            if len(r[0]) == 1 and not r[1]:
                sw, sh = w, h
                res = r if quality == 'fast' or r[2] == 'dikdortgen' else None
                break
        else:
            sw, sh = cands[-1]  # nothing takes it all: the largest sheet, as many as needed
        auto = L('%g × %g (otomatik, %d aday denendi)') % (sw, sh, tried)
        print('OTOMATIK LEVHA %g x %g (%d aday denendi)' % (sw, sh, tried))
        say(L('Otomatik levha: %g × %g (%d aday denendi)') % (sw, sh, tried))
    sheets, unplaced, how, turns = res or packing(sw, sh, quality)
    for s, sheet in enumerate(sheets):
        oy = -s * (sh + SHEET_GAP)
        msp.add_lwpolyline([(0, oy), (sw, oy), (sw, oy + sh), (0, oy + sh)], close=True, dxfattribs={'layer': 'SHEET'})
        for k, x, y, rot in sheet:
            # block base = part's lower-left corner; ironnest places Rot(rot)*local + (x, y), as INSERT does
            msp.add_blockref(types[k]['block'], (x, oy + y), dxfattribs={'rotation': rot}).explode()
    merged = merge_edges(msp) if merge else 0.0
    if merge:
        print('BIRLESEN KENAR %.0f mm (tek kesim)' % merged)
        say(L('Birleşen kenar: %.0f mm (tek kesim).') % merged)
    priced = cost and (float(cost.get('price') or 0) or any(float(v or 0) for v in (cost.get('sizes') or {}).values()) or
                       float(cost.get('per_bend') or 0) or float(cost.get('setup') or 0) or
                       any(float((cost.get('laser') or {}).get(f) or 0) for f in ('per_m', 'per_pierce', 'per_min')))
    if cost and not priced:
        print('MALIYET: fiyat girilmedi, hesaplanmadi')
        say(L('Fiyat girilmedi: maliyet hesaplanmadı.'))
    costs = job_cost(out, types, sheets, sw, sh, cost, merged, maket) if priced else None
    if cfg.get('legend', True):  # right of the first sheet, clear of every part
        add_legend(out, msp, sw + 50, sh, styles, 10)
    if cfg.get('out_nest', True): out.saveas(out_path)  # off: only the cut file and/or pictures are wanted
    placed = sum(len(s_) for s_ in sheets)
    fill = sum(types[k]['area'] for s_ in sheets for k, *_ in s_) / (len(sheets) * sw * sh) * 100 if sheets else 0
    for n_, s_ in enumerate(sheets):
        f = scrap(types, s_, sw, sh)
        print('FIRE sac %d: parcalar %.3f m2 | levhaya gore fire %%%.1f | parcalarin bolgesi %.0f x %.0f mm, icinde fire %%%.1f'
              ' | kalan levha %%%.0f (%.2f m2)' % (n_ + 1, f['net_m2'], f['sheet_scrap'], f['box'][0], f['box'][1],
                                                 f['box_scrap'], f['left'], f['left_m2']))
        say(L('%d. levha: parçalar %.3f m², fire %%%.1f (parça bölgesi %.0f × %.0f mm içinde %%%.1f), kalan %%%.0f') % (
            n_ + 1, f['net_m2'], f['sheet_scrap'], f['box'][0], f['box'][1], f['box_scrap'], f['left']))
    say(L('%d parça %d levhaya dizildi (%s).') % (placed, len(sheets), L(HOW_TR.get(how, how))))
    print('NESTED %d parts on %d sheet(s) [%s, doluluk %%%.1f]%s' % (placed, len(sheets), how, fill,
          ' -> ' + out_path if cfg.get('out_nest', True) else ' (nesting DXF istenmedi)'))
    if unplaced:
        print('SIGMADI (sactan buyuk): ' + ', '.join(types[k]['name'] for k in unplaced))
        say(L('Levhaya sığmayan (levhadan büyük): %s') % ', '.join(types[k]['name'] for k in unplaced))
    pinfo = dict(info or {}, gap=gap, how=how, layout=cfg.get('layout', 'square'), turns=turns, kerf=kerf, edge=edge,
                 common=common, quality=cfg.get('quality', 'balanced'), maket=maket, merge=merge, merged=merged,
                 pitch=(maket or {}).get('pitch', cfg.get('pitch', 1.0)), close=cfg.get('png_close', True), auto=auto,
                 costs=costs)
    if costs:
        for line in costs['lines']: print(line)
        t_ = costs['tot']
        say(L('Maliyet: %.2f (levhaların tamamıyla) / %.2f (yalnız parçaların payıyla)%s') % (
            t_['all'], t_['parts_only'], L(', hazırlık %.2f dahil') % t_['setup'] if t_['setup'] else ''))
        if cfg.get('out_cost', True): write_cost_csv(costs, out_path)

    def picture(path, sty, title, want):
        if not (want and cfg.get('png', True) and sheets): return
        try:
            pngs = render_png(out, sheets, types, sw, sh, sty, dict(pinfo, title=title), path)
            print('PNG %d resim: %s' % (len(pngs), ', '.join(os.path.basename(x) for x in pngs)))
        except Exception as e:  # the picture is a convenience; the DXF is already written
            print('PNG OLMADI: %s' % e)
    picture(out_path, styles, L('MAKET — NESTING') if maket else L('SAC AÇINIM — NESTING'), cfg.get('png_nest', True))
    want_cut, want_cut_png = cfg.get('out_cut', cfg.get('cut_file', True)), cfg.get('png_cut', True)
    if (want_cut or want_cut_png) and sheets:
        # the same nesting with the cut lines only (no bend lines, sheet frame or legend): ready for the cutting program
        for e in list(msp):
            if e.dxf.layer not in CUT_LAYERS: msp.delete_entity(e)
        stem = os.path.basename(out_path)
        cut_path = os.path.join(os.path.dirname(out_path), stem.replace('00_NESTING_', L('00_KESIM_')) if '00_NESTING_' in stem
                                else os.path.splitext(stem)[0] + '_KESIM.dxf')
        if want_cut:
            out.saveas(cut_path)
            print('KESIM dosyasi: %s' % os.path.basename(cut_path))
        picture(cut_path, {k: v for k, v in styles.items() if k in CUT_LAYERS}, L('KESİM + ÇİZİK') if maket else L('KESİM HATLARI'),
                want_cut_png)


MPL_LINES = {'CONTINUOUS': '-', 'DASHED': (0, (6, 3)), 'DASHDOT': (0, (8, 3, 1, 3)), 'CENTER': (0, (12, 3, 3, 3))}


def rgb(aci):
    # ACI colour for a white page: 7 (white/black) is drawn black
    if aci == 7: return (0, 0, 0)
    from ezdxf.colors import aci2rgb
    r, g, b = aci2rgb(aci)
    return (r / 255, g / 255, b / 255)


def centroid(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
    if abs(a) < 1e-9: return sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    return cx / (3 * a), cy / (3 * a)


HOW_TR = {'gercek sekil': 'Gerçek şekil', 'dikdortgen': 'Dikdörtgen'}
QUALITY_TR = {'fast': 'Hızlı', 'balanced': 'Dengeli', 'best': 'En iyi'}
BEND_TR = {'score': 'Çizik', 'hinge': 'Esnek menteşe', 'heat': 'Isıyla (işaret)', 'none': 'Çizilmedi'}
LAYOUT_TR = {'square': 'Kompakt kare', 'area': 'En az fire', 'rect': 'Kompakt dikdörtgen', 'strip': 'Şerit'}


def render_png(doc, sheets, types, sw, sh, styles, info, out_path):
    # One picture per sheet, so the nesting can be checked without a CAD program: the cut geometry as in the DXF,
    # each part's name on it, and a title block at the bottom right below the sheet (technical-drawing habit), clear
    # of the parts: drawing, sheet, thickness, sheet no., parts, fill, method, gap, date and what each line means.
    # When the parts take a small corner of a big sheet, a second, close-up picture of that corner follows.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy
    msp = doc.modelspace()
    base = os.path.splitext(out_path)[0]
    shown = [(layer, s) for layer, s in styles.items() if s['show'] and any(True for _ in msp.query('*[layer=="%s"]' % layer))]
    LONG_IN = 16  # the longer side of every picture, inches

    def view(x0, x1, y0, y1):
        # a figure whose shape matches the view, so 1 mm is the same on both axes and text sizes in mm hold
        r = (y1 - y0) / (x1 - x0)
        w_in = LONG_IN if r <= 1 else LONG_IN / r
        fig = plt.figure(figsize=(w_in, w_in * r))
        ax = fig.add_axes([0, 0, 1, 1])
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=Configuration(background_policy=BackgroundPolicy.WHITE)
                 ).draw_layout(msp, finalize=False, filter_func=lambda e: e.dxf.layer != LEGEND)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal', adjustable='box'); ax.axis('off')
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, lw=1.5, ec='#444444'))  # drawing frame
        return fig, ax, w_in * 72 / (x1 - x0)  # font points per mm

    def placed(sheet, oy):
        for k, x, y, rot in sheet:
            t = types[k]
            c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            yield t, [(x + c * px - s_ * py, oy + y + s_ * px + c * py) for px, py in t['outline']]

    def names(ax, sheet, oy, pt, cap):
        for t, pts in placed(sheet, oy):  # name on each part, at its outline's centroid
            cx, cy = centroid(pts)
            # the part's own long axis, from its smallest enclosing rectangle (turned or slanted parts included)
            turn = min_box_turn(pts)
            c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            xs = [c * x - s_ * y for x, y in pts]; ys = [s_ * x + c * y for x, y in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            axis = (-turn if w >= h else 90 - turn) % 180  # direction of the long side, 0..180
            if axis > 90: axis -= 180  # keep the text upright
            long_, short = max(w, h), min(w, h)
            narrow = long_ > 1.8 * short  # a narrow part gets its name along its length, so the name can be bigger
            size = min(short * 0.6, long_ / max(len(t['label']), 1) * 1.3) if narrow else short * 0.25
            ax.text(cx, cy, t['label'], ha='center', va='center', rotation=axis if narrow else 0, rotation_mode='anchor',
                    fontsize=max(5, min(size, cap) * pt),
                    color='#003399', bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.75))

    pngs = []
    for n, sheet in enumerate(sheets):
        oy = -n * (sh + SHEET_GAP)
        th = max(sh * 0.018, 8.0)  # title-block text height, mm on the sheet
        f = scrap(types, sheet, sw, sh)
        rows = [(L('Belge'), info.get('belge', '')), (L('Malzeme') if info.get('maket') else L('Sac'),
                                                    '%s  %s mm' % (info.get('tur', ''), info.get('kalinlik', ''))),
                (L('Levha ölçüsü') if info.get('maket') else L('Sac ölçüsü'), info.get('auto') or '%g × %g mm' % (sw, sh)),
                (L('Levha no') if info.get('maket') else L('Sac no'), '%d / %d' % (n + 1, len(sheets))),
                (L('Parça'), L('%d adet, %.3f m²') % (len(sheet), f['net_m2'])), (L('Doluluk'), dil.pct(f['fill'])),
                (L('Fire (levha)'), dil.pct(f['sheet_scrap'])),
                (L('Fire (parça bölgesi)'), dil.pct(f['box_scrap']) + '  (%.0f × %.0f mm)' % f['box']),
                (L('Kalan levha'), dil.pct(f['left'], '%.0f') + '  (%.2f m²)' % f['left_m2']),
                (L('Yöntem'), L(HOW_TR.get(info.get('how'), info.get('how', ''))))]
        if info.get('how') == 'gercek sekil':
            rows += [(L('Dizilim'), L(LAYOUT_TR.get(info.get('layout'), ''))), (L('Döndürme'), info.get('turns', ''))]
        mk = info.get('maket')
        if mk:
            rows += [(L('Parça arası'), L('birleşik kenar, %.0f mm tek kesim') % info.get('merged', 0) if info.get('merge')
                      else '%g mm' % info.get('gap', 0)),
                     (L('Kerf'), L('%g mm, yarısı eklendi: %s') % (info.get('kerf', 0), ', '.join(
                         n for n, k in ((L('dış çizgi'), 'grow_outer'), (L('delikler'), 'grow_holes')) if mk.get(k)) or L('yok (lazer programı)'))),
                     (L('Büküm'), L(BEND_TR.get(mk.get('bend'), '')) + (L(', aralık %g mm') % info.get('pitch', 1)
                                                                  if mk.get('bend') in ('score', 'hinge') else ''))]
            if mk.get('warn'): rows.append((L('UYARI'), mk['warn']))
        else:
            rows += [(L('Parça arası'), L('kerf kadar (ortak kesim)') if info.get('common') else L('%g mm + kerf') % info.get('gap', 0)),
                     (L('Kerf'), '%g mm' % info.get('kerf', 0))]
        cs = info.get('costs')
        if cs:
            r, t = cs['rows'][n], cs['tot']
            unit = {'kg': L('TL/kg'), 'm2': L('TL/m²'), 'levha': L('TL/levha')}.get(cs['unit'], '')
            rows += [(L('Levha'), L('%.2f TL (%s)') % (r['sheet'], unit)),
                     (L('  parça payı / fire'), L('%.2f / %.2f TL') % (r['share'], r['box_scrap'])),
                     (L('Lazer'), L('%.2f TL  (%.2f m, %d giriş%s)') % (r['laser'], r['cut'] + r['score'], r['pierces'],
                                                               L(', %.1f dk') % r['mins'] if r['mins'] is not None else ''))]
            if r['bend']: rows.append((L('Büküm'), L('%.2f TL') % r['bend']))
            rows.append((L('İş toplamı'), L('%.2f TL  (parça payıyla %.2f)') % (t['all'], t['parts_only'])))
        rows += [(L('Kenar payı'), '%g mm' % info.get('edge', 0)),
                 (L('Kalite'), L(QUALITY_TR.get(info.get('quality'), ''))),
                (L('Tarih'), datetime.datetime.now().strftime('%d.%m.%Y %H:%M'))]
        line = th * 1.9
        tb_h = line * (len(rows) + len(shown) + 2)
        tb_w = th * 42
        m = max(sw, sh) * 0.02
        x0, x1 = -m, sw + m
        y1, y0 = oy + sh + m, oy - th - tb_h - m
        fig, ax, pt = view(x0, x1, y0, y1)
        # the sheet outline, also for the cut-only drawing, which has no frame line of its own
        ax.add_patch(Rectangle((0, oy), sw, sh, fill=False, lw=0.8, ec='#888888'))
        names(ax, sheet, oy, pt, th * 1.2)
        bx, by = sw - tb_w, oy - th - tb_h  # title block: bottom right, under the sheet
        ax.add_patch(Rectangle((bx, by), tb_w, tb_h, fill=False, lw=1.2, ec='black'))
        fs = th * pt
        yy = by + tb_h - line
        ax.text(bx + th, yy, info.get('title', L('SAC AÇINIM — NESTING')), fontsize=fs * 1.1, weight='bold', va='center')
        yy -= line * 1.2
        for key, val in rows:
            ax.text(bx + th, yy, key, fontsize=fs, va='center', color='#333333')
            ax.text(bx + th * 13, yy, str(val), fontsize=fs, va='center', weight='bold')
            yy -= line
        ax.plot([bx, bx + tb_w], [yy + line * 0.5, yy + line * 0.5], color='black', lw=0.8)
        for layer, st in shown:  # what each line means, drawn in its own colour and line type
            yy -= line * 0.2
            ax.plot([bx + th, bx + th * 8], [yy, yy], color=rgb(st['color']), lw=2, linestyle=MPL_LINES.get(st['ltype'], '-'))
            ax.text(bx + th * 10, yy, st['label'], fontsize=fs, va='center')
            yy -= line * 0.8
        png = base + ('' if len(sheets) == 1 else '_sac%d' % (n + 1))
        fig.savefig(png + '.png', dpi=110, facecolor='white')
        plt.close(fig)
        pngs.append(png + '.png')
        # close-up when the parts fill little of the sheet: their area only, names larger
        xs = [x for _, pts in placed(sheet, oy) for x, _ in pts]
        ys = [y for _, pts in placed(sheet, oy) for _, y in pts]
        if info.get('close', True) and xs and (max(xs) - min(xs)) * (max(ys) - min(ys)) < 0.4 * sw * sh:
            span = max(max(xs) - min(xs), max(ys) - min(ys))
            mz = span * 0.06
            fig, ax, pt = view(min(xs) - mz, max(xs) + mz, min(ys) - mz, max(ys) + mz)
            names(ax, sheet, oy, pt, span * 0.012)
            fig.savefig(png + '_yakin.png', dpi=110, facecolor='white')
            plt.close(fig)
            pngs.append(png + '_yakin.png')
    return pngs


def main(cfg_path, out_path):
    cfg = json.load(open(cfg_path, encoding='utf8'))
    dil.LANG = cfg.get('lang', 'tr')
    styles = styles_of(cfg)
    for p in cfg['parts']:
        if 'geom' in p:
            build_part_dxf(p['geom'], p['dxf'])
            print('DXF yazildi', p['name'])
        style_part(p['dxf'], styles, cfg.get('legend', True), p.get('maket'), (p.get('maket') or {}).get('pitch', cfg.get('pitch', 1.0)))
    # nest_files: one nesting per sheet thickness, each with its own parts; out_path is the single-file form
    files = cfg.get('nest_files') or ([] if out_path == '-' else [{'path': out_path, 'names': None}])
    for f in files:
        parts = [p for p in cfg['parts'] if f['names'] is None or p['name'] in f['names']]
        if parts: nest(dict(cfg, gap=f.get('gap', cfg['gap'])), parts, f['path'], f.get('sheet_w', cfg['sheet_w']),
                       f.get('sheet_h', cfg['sheet_h']), styles, f.get('info'), f.get('maket'), f.get('sizes'), f.get('cost'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
