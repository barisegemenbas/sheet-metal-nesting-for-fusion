# Core of the SacAcinimDXF add-in (reloaded on every button press): every visible sheet-metal body -> Create Flat Pattern -> one DXF each, plus a nested DXF, all in one folder.
# Button: SHEET METAL tab (and UTILITIES > ADD-INS) "Sac Açınım DXF".
import adsk.core, adsk.fusion, traceback, os, sys, json, unicodedata, shutil, subprocess, datetime, glob, math, re, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import dil
from dil import L
FACE_MEMORY = os.path.join(HERE, '_yuz_hafiza.json')  # per part: the stationary face that unfolded it last time

LOG = None


def log(msg):
    if LOG:
        with open(LOG, 'a', encoding='utf8') as f: f.write(msg + '\n')


TR = str.maketrans('ıİşŞğĞüÜöÖçÇ', 'iIsSgGuUoOcC')


def safe(name):
    # ASCII only: Fusion's flat-pattern DXF export fails on paths with Turkish characters
    name = unicodedata.normalize('NFKD', unicodedata.normalize('NFC', name).translate(TR))
    name = name.encode('ascii', 'ignore').decode()
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in name).strip('_') or 'parca'


def largest_planar_face(body):
    best = None
    for f in body.faces:
        if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType and (best is None or f.area > best.area):
            best = f
    return best


def flat_face(fp):
    for attr in ('topFace', 'bottomFace'):
        try:
            f = getattr(fp, attr)
            if f: return f
        except Exception: pass
    return largest_planar_face(fp.bodies.item(0))


def plane_to2d(face):
    # 3D point -> 2D mm in the plane of a planar face, seen from its outer side
    pl = face.geometry
    o, u, v = pl.origin, pl.uDirection, pl.vDirection
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    if u.crossProduct(v).dotProduct(n) < 0: v = v.copy(); v.scaleBy(-1)
    return lambda p: [round((p.x - o.x) * u.x * 10 + (p.y - o.y) * u.y * 10 + (p.z - o.z) * u.z * 10, 5),
                      round((p.x - o.x) * v.x * 10 + (p.y - o.y) * v.y * 10 + (p.z - o.z) * v.z * 10, 5)]


def edge_ent(e, layer, to2d):
    # one edge as line, circle, 3-point arc or polyline
    g = e.geometry
    ev = e.evaluator
    ok, p0, p1 = ev.getParameterExtents()
    if isinstance(g, adsk.core.Line3D):
        return {'t': 'line', 'l': layer, 'p': [to2d(e.startVertex.geometry), to2d(e.endVertex.geometry)]}
    if isinstance(g, adsk.core.Circle3D):
        return {'t': 'circle', 'l': layer, 'c': to2d(g.center), 'r': g.radius * 10}
    if isinstance(g, adsk.core.Arc3D):
        ok, mid = ev.getPointAtParameter((p0 + p1) / 2)
        return {'t': 'arc', 'l': layer, 'p': [to2d(e.startVertex.geometry), to2d(mid), to2d(e.endVertex.geometry)]}
    ok, pts = ev.getStrokes(p0, p1, 0.001)
    return {'t': 'poly', 'l': layer, 'p': [to2d(p) for p in pts]}


def face_outline(face):
    # 2D cutting geometry (mm) of a planar face, seen from its outer side
    to2d = plane_to2d(face)
    return [edge_ent(e, 'OUTER_PROFILES' if loop.isOuter else 'INTERIOR_PROFILES', to2d)
            for loop in face.loops for e in loop.edges]


def same_line(a, b, tol):
    # two 2D lines (mm) that are parallel, overlapping and less than tol apart: top/bottom copies of one bend line
    if a['t'] != 'line' or b['t'] != 'line': return False
    (ax0, ay0), (ax1, ay1) = a['p']; (bx0, by0), (bx1, by1) = b['p']
    dx, dy = ax1 - ax0, ay1 - ay0
    la, lb = math.hypot(dx, dy), math.hypot(bx1 - bx0, by1 - by0)
    if la < 1e-6 or lb < 1e-6: return False
    if abs(dx * (by1 - by0) - dy * (bx1 - bx0)) / (la * lb) > 0.035: return False  # not parallel (> ~2 deg)
    mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
    if abs(dx * (my - ay0) - dy * (mx - ax0)) / la > tol: return False  # too far apart
    t = (dx * (mx - ax0) + dy * (my - ay0)) / la ** 2
    return -0.5 < t < 1.5  # b's midpoint lies along a, not further down the same direction


def bend_lines(fp, face):
    # bend and bend-extent lines from the flat pattern's wire bodies, in the same plane as face_outline
    # the wire bodies hold a copy for the top and for the bottom face; keep only the one nearest this face's plane,
    # as Fusion's own DXF does
    to2d = plane_to2d(face)
    o = face.geometry.origin
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    pdist = lambda p: abs((p.x - o.x) * n.x + (p.y - o.y) * n.y + (p.z - o.z) * n.z)
    dist = lambda e: pdist(e.startVertex.geometry) if e.startVertex else 0
    # bend lines of different bends sit at different depths, so split top/bottom copies at half the thickness
    try: half = pdist(fp.bottomFace.pointOnFace) / 2
    except Exception: half = 1e-4
    ents = []
    for attr, layer in (('bendLinesBody', 'BEND'), ('extentLinesBody', 'BEND_EXTENT')):
        try:
            body = getattr(fp, attr)
            edges = list(body.edges) if body else []
            if layer == 'BEND':
                # depth does not separate the copies for bends that go down, so drop a line that runs parallel and
                # close (within 2x thickness) to one already kept, nearest-to-top first
                kept = []
                for e in sorted(edges, key=dist):
                    ent = edge_ent(e, layer, to2d)
                    if not any(same_line(ent, k, max(40 * half, 0.5)) for k in kept): kept.append(ent)
                ents += kept
            else:
                near = min((dist(e) for e in edges), default=0)
                ents += [edge_ent(e, layer, to2d) for e in edges if dist(e) <= near + half]
        except Exception:
            log('  %s okunamadi: %s' % (attr, traceback.format_exc().splitlines()[-1]))
    return ents


def bend_info(fp):
    # [[degrees, up], ...] per bend line; empty when Fusion gives nothing
    out = []
    try:
        body = fp.bendLinesBody
        for e in (body.edges if body else []):
            ok, up, ang = fp.getBendInfo(e)
            if ok: out.append([round(ang * 57.29578, 1), bool(up)])
    except Exception:
        log('  getBendInfo: ' + traceback.format_exc().splitlines()[-1])
    return out


def face_key(f):
    # identifies the same face across archive copies, whose face order may differ
    c = f.centroid
    return (round(f.area, 4), round(c.x, 3), round(c.y, 3), round(c.z, 3))


def has_bends(body):
    return any(f.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType for f in body.faces)


def unfolded(fp):
    # a flat pattern that did not unfold has no bend lines at all
    try: return bool(fp.bendLinesBody and fp.bendLinesBody.edges.count)
    except Exception: return False


def geom_size(geom):
    # 2D extent (mm) of the fallback geometry, to compare with the flat body's size
    xs, ys = [], []
    for e in geom:
        if e['t'] == 'circle':
            xs += [e['c'][0] - e['r'], e['c'][0] + e['r']]; ys += [e['c'][1] - e['r'], e['c'][1] + e['r']]
        else:
            xs += [p[0] for p in e['p']]; ys += [p[1] for p in e['p']]
    return [round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)] if xs else None


class OldFlatPattern(Exception):
    pass


def clear_old_flat(doc, comp):
    # A flat pattern left in the user's design comes along into the copy and blocks createFlatPattern. FlatPattern.
    # deleteMe() does not free the component, so remove the FlatPatternProduct that holds it (copy only). Returns the
    # flat pattern still in the way, or None.
    prods = [p for p in (adsk.fusion.FlatPatternProduct.cast(x) for x in doc.products) if p]
    if not prods and not comp.flatPattern: return None
    log('  onceden kalmis flat pattern: %d urun, comp.flatPattern=%s' % (len(prods), bool(comp.flatPattern)))
    for p in prods:
        try: log('  FlatPatternProduct.deleteMe -> %s' % p.deleteMe())
        except Exception: log('  FlatPatternProduct.deleteMe hata: ' + traceback.format_exc().splitlines()[-1])
    left = comp.flatPattern
    log('  silme sonrasi comp.flatPattern=%s' % bool(left))
    return left


T_TOL = 0.05  # mm; thicknesses closer than this count as the same sheet


def part_thickness(fp, comp):
    # sheet thickness (mm): distance between the flat pattern's top and bottom faces; the component's rule otherwise
    try:
        top, bot = fp.topFace, fp.bottomFace
        o = top.geometry.origin
        ok, n = top.evaluator.getNormalAtPoint(top.pointOnFace)
        p = bot.pointOnFace
        return round(abs((p.x - o.x) * n.x + (p.y - o.y) * n.y + (p.z - o.z) * n.z) * 10, 2)
    except Exception:
        try: return round(comp.activeSheetMetalRule.thickness.value * 10, 2)
        except Exception: return None


def body_thickness(body):
    # sheet thickness (mm) of a folded body: gap from its largest flat face to the nearest face facing the other way
    try:
        planar = [f for f in body.faces if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType]
        big = max(planar, key=lambda f: f.area)
        ok, n = big.evaluator.getNormalAtPoint(big.pointOnFace)
        o = big.pointOnFace
        best = None
        for f in planar:
            ok, m = f.evaluator.getNormalAtPoint(f.pointOnFace)
            if n.dotProduct(m) > -0.999: continue  # not facing the opposite way
            p = f.pointOnFace
            d = abs((p.x - o.x) * n.x + (p.y - o.y) * n.y + (p.z - o.z) * n.z)
            if d > 1e-5 and (best is None or d < best): best = d
        return round(best * 10, 2) if best else None
    except Exception:
        return None


def thickness_groups(root):
    # visible sheet-metal parts grouped by thickness, for the dialog: [{'t': mm or None, 'n': pieces, 'parts': n}]
    out = {}
    for g in visible_sheet_bodies(root):
        t = body_thickness(g['body_obj'])
        key = next((k for k in out if k is not None and t is not None and abs(k - t) <= T_TOL), t)
        e = out.setdefault(key, {'t': key, 'n': 0, 'parts': 0})
        e['n'] += g['qty']; e['parts'] += 1
    return sorted(out.values(), key=lambda e: (e['t'] is None, e['t'] or 0))


def step_info(design, nm):
    # A timeline step by name and the bodies it touches (copy only). Known kinds: Combine (target, tools, result) and
    # Split Body (bodies split, a body used as the splitting tool, the pieces). Inputs are read with the timeline
    # rolled back to the step, results with it at the end.
    tl = design.timeline
    for i in range(tl.count):
        to = tl.item(i)
        if to.name != nm: continue
        info = {'obj': to, 'pos': '%d/%d' % (i + 1, tl.count), 'known': False, 'op': None, 'bodies': set()}
        names = lambda coll: {coll.item(j).name for j in range(coll.count)} if coll else set()
        try:
            cf = adsk.fusion.CombineFeature.cast(to.entity)
            sf = adsk.fusion.SplitBodyFeature.cast(to.entity)
            if cf or sf: to.rollTo(True)  # a step's inputs can only be read with the timeline rolled back to it
            if cf:
                FO = adsk.fusion.FeatureOperations
                ops = {FO.JoinFeatureOperation: 'Join', FO.CutFeatureOperation: 'Cut', FO.IntersectFeatureOperation: 'Intersect',
                       FO.NewBodyFeatureOperation: 'NewBody', FO.NewComponentFeatureOperation: 'NewComponent'}
                info.update(known=True, op='Combine ' + str(ops.get(cf.operation, cf.operation)))
                if cf.targetBody: info['bodies'].add(cf.targetBody.name)
                info['bodies'] |= names(cf.toolBodies)
            elif sf:
                info.update(known=True, op='Split')
                info['bodies'] |= names(sf.splitBodies)
                tool = adsk.fusion.BRepBody.cast(sf.splittingTool)
                if tool: info['bodies'].add(tool.name)
            else:
                info['op'] = to.entity.objectType if to.entity else '?'
        except Exception:
            info['known'] = False
            log('  ADIM %s okunamadi: %s' % (nm, traceback.format_exc().splitlines()[-1]))
        finally:
            try: tl.moveToEnd()
            except Exception: pass
        try:
            if info['known']: info['bodies'] |= names(to.entity.bodies)  # what the step left behind
        except Exception: pass
        return info
    return None


def set_thickness(design, model_t, target_t, body_name):
    # In the throwaway copy: every sheet metal rule at the model thickness gets the target one, so the body rebuilds
    # (and unfolds) at the new thickness. When that breaks a Combine or Split step that touches none of this body
    # (e.g. two other parts joined, failing once they thicken), the step is suppressed in the copy and the change
    # retried. Any other failing step, or one involving this body, is left alone: the part stays at the model
    # thickness. Returns (rules changed, steps suppressed).
    suppressed = []

    def give_up():
        # the change did not take: put back what was suppressed, or the copy keeps a model that never existed (bodies
        # renamed or gone, as bıdık3/4 were after six suppressions and a failing Extrude)
        for to in reversed(suppressed):
            try: to.isSuppressed = False
            except Exception: log('  geri acilamadi: %s' % to.name)
        if suppressed: log('  kalinlik tutmadi, bastirilan %d adim geri acildi' % len(suppressed))
        adsk.doEvents()
        return 0, []

    for _ in range(10):
        failed, n = [], 0
        for i in range(design.designSheetMetalRules.count):
            r = design.designSheetMetalRules.item(i)
            try:
                if model_t is None or abs(r.thickness.value * 10 - model_t) <= T_TOL:
                    r.thickness.expression = '%g mm' % target_t; n += 1
            except Exception:
                msg = traceback.format_exc().splitlines()[-1]
                failed += [f for f in re.findall(r'(\w+) / Compute Failed', msg) if f not in failed]
                if not failed: log('  kural kalinligi degismedi (%s): %s' % (r.name, msg))
        adsk.doEvents()
        if not failed: return n, [to.name for to in suppressed]
        for nm in failed:
            info = step_info(design, nm)
            if info is None: return give_up()
            desc = 'ADIM %s (%s): %s govdeler=%s' % (nm, info['pos'], info['op'], sorted(info['bodies']))
            if not info['known'] or body_name in info['bodies']:
                log('  %s -> bu parcayi etkiliyor ya da tanimadigim adim, bastirilmadi' % desc)
                return give_up()
            info['obj'].isSuppressed = True
            suppressed.append(info['obj'])
            log('  %s -> bu parcayla ilgisiz, kopyada bastirildi' % desc)
    return give_up()


def find_body(design, g):
    # same body in the archive copy; the root component is renamed on import, so it is matched by role
    comp = design.rootComponent if g['root'] else next((c for c in design.allComponents if c.name == g['comp']), None)
    if comp is None: return None, None
    idx = g['key'][1]
    if 0 <= idx < comp.bRepBodies.count and comp.bRepBodies.item(idx).name == g['body']:
        return comp, comp.bRepBodies.item(idx)
    return comp, comp.bRepBodies.itemByName(g['body'])


def body_index(comp, body):
    for i, b in enumerate(comp.bRepBodies):
        if b.entityToken == body.entityToken: return i
    return -1


def visible_sheet_bodies(root):
    # the same native body seen in several occurrences -> one DXF with qty n
    items = [(root, b) for b in root.bRepBodies if b.isVisible]
    for occ in root.allOccurrences:
        if not occ.isVisible: continue
        items += [(occ.component, b.nativeObject or b) for b in occ.bRepBodies if b.isVisible]
    groups = {}
    for comp, body in items:
        if not body.isSheetMetal:
            log('ATLANDI (sheet metal degil): %s / %s' % (comp.name, body.name)); continue
        key = (comp.name, body_index(comp, body))
        g = groups.setdefault(key, {'key': key, 'comp': comp.name, 'body': body.name, 'root': comp == root, 'qty': 0,
                                    'comp_obj': comp, 'body_obj': body})
        g['qty'] += 1
    return list(groups.values())


def clean_env():
    # Fusion's embedded Python sets PYTHONHOME/PYTHONPATH etc. for itself; passed on, they break the system Python
    return {k: v for k, v in os.environ.items() if not k.startswith('PYTHON') and k != '__PYVENV_LAUNCHER__'}


def find_python():
    # system Python that has ezdxf; Fusion started from the Dock/Finder on macOS has a minimal PATH, so look in the
    # usual install places too
    log('PYTHON env: ' + ', '.join('%s=%s' % (k, v) for k, v in os.environ.items() if k.startswith('PYTHON')))
    # first the add-in's own Python, put next to it by the installer (Kur.command / Kur.bat)
    cands = [os.path.join(HERE, '_python', 'bin', 'python3'), os.path.join(HERE, '_python', 'python.exe'),
             shutil.which('python3'), shutil.which('python'), shutil.which('py'),
             '/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3']
    cands += glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python3*', 'python.exe'))
    cands += sorted(glob.glob('/Library/Frameworks/Python.framework/Versions/3*/bin/python3'), reverse=True)
    for c in dict.fromkeys(cands):
        # skip the Microsoft Store stub and Fusion's own interpreter
        if not c or 'WindowsApps' in c or 'webdeploy' in c.lower() or not os.path.exists(c): continue
        try:
            r = subprocess.run([c, '-c', 'import ezdxf'], capture_output=True, env=clean_env(),
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=30)
            if r.returncode == 0: return c
            log('  python adayi olmadi: %s: %s' % (c, (r.stderr or b'').decode(errors='replace').strip().splitlines()[-1:]))
        except Exception: log('  python adayi olmadi: %s: %s' % (c, traceback.format_exc().splitlines()[-1]))
    return None


def open_folder(path):
    try:
        if sys.platform == 'darwin': subprocess.Popen(['open', path])
        else: os.startfile(path)
    except Exception: pass


def version():
    # the add-in's version as in its manifest (Fusion's own add-in list only re-reads it when Fusion restarts)
    try:
        with open(os.path.join(HERE, 'SacAcinimDXF.manifest'), encoding='utf8') as f: return json.load(f).get('version', '?')
    except Exception: return '?'


def export_all(gap, do_nest, keep_separate, sheets, styles=None, legend=True, method='shape', png=True, opts=None):
    # sheets: one entry per model thickness from the dialog: {model_t, use, target_t, material, sheet_w, sheet_h}
    global LOG
    dil.LANG = (opts or {}).get('lang', 'tr')
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        ui.messageBox(L('Aktif bir tasarım yok.')); return
    doc_name = safe(app.activeDocument.name)
    # Documents/Sac_Acinim_DXF (Turkish) or Documents/SheetMetal_Nesting_DXF (English)
    out = os.path.join(os.path.expanduser('~'), 'Documents', L('Sac_Acinim_DXF'), '%s_%s' % (doc_name, datetime.datetime.now().strftime('%Y%m%d_%H%M')))
    os.makedirs(out, exist_ok=True)
    LOG = os.path.join(out, '_log.txt')
    log('BELGE %s | eklenti surumu %s' % (app.activeDocument.name, version()))
    # nesting reads the per-part DXFs; when they are not wanted they go to a temp subfolder removed at the end
    part_dir = out if keep_separate else os.path.join(out, '_gecici')
    os.makedirs(part_dir, exist_ok=True)

    groups = visible_sheet_bodies(design.rootComponent)
    if not groups:
        ui.messageBox(L('Görünür sheet metal gövde bulunamadı.')); return
    excluded = []
    for g in groups:
        t = body_thickness(g['body_obj'])
        g['model_t'] = t
        g['sheet'] = next((k for k, sh in enumerate(sheets) if (sh['model_t'] is None and t is None) or
                           (sh['model_t'] is not None and t is not None and abs(sh['model_t'] - t) <= T_TOL)), None)
        if g['sheet'] is None:  # a thickness the dialog did not list (design changed meanwhile): its own sheet
            sheets.append({'model_t': t, 'use': True, 'target_t': t, 'material': sheets[0]['material'] if sheets else 'SAC',
                           'sheet_w': sheets[0]['sheet_w'] if sheets else 2500, 'sheet_h': sheets[0]['sheet_h'] if sheets else 1250})
            g['sheet'] = len(sheets) - 1
        if not sheets[g['sheet']]['use']:
            excluded.append(g['body']); log('DAHIL DEGIL (%s mm): %s / %s' % (t, g['comp'], g['body']))
    groups = [g for g in groups if sheets[g['sheet']]['use']]
    if not groups:
        ui.messageBox(L('Dahil edilen kalınlıkta parça yok.')); return
    rethick = []  # parts whose thickness change did not take
    try:
        with open(FACE_MEMORY, encoding='utf8') as f: memory = json.load(f)
    except Exception:
        memory = {}
    # A component holds one flat pattern and a deleted one keeps blocking the next (API reports it gone, the
    # component doesn't), so every body gets its own throwaway copy of the design, closed unsaved after the export.
    # The user's design is never changed.
    src_doc = app.activeDocument
    archive = os.path.join(out, '_kopya.f3d')
    design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(archive))
    prog = ui.createProgressDialog()
    prog.show(L('Sac Açınım DXF'), 'Flat pattern %v / %m', 0, len(groups))
    results, fails, partial, skipped, blocked = [], [], [], [], {}  # blocked: comp -> body owning the old flat pattern

    def close_copy(doc):
        try:
            if doc: doc.close(False)
        except Exception: log('  kopya kapatilamadi: ' + traceback.format_exc().splitlines()[-1])
        try: src_doc.activate()
        except Exception: pass

    try:
        for i, g in enumerate(groups, 1):
            name = '%02d_%s' % (i, safe(g['body']) if g['root'] else safe(g['comp']) + '_' + safe(g['body']))
            tmp = None
            if g['comp'] in blocked and blocked[g['comp']] != g['body']:
                skipped.append(name); log('ATLANDI %s: componentte silinemeyen eski flat pattern' % name)
                prog.progressValue = i; continue
            try:
                # Fusion sometimes leaves a body folded (no bend lines) for a given stationary face, and which face
                # the largest-area pick lands on varies between copies; retry in a fresh copy with the next face
                tried, ok = [], False
                for attempt in range(1, 4):
                    close_copy(tmp); tmp = None
                    tmp = app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(archive))
                    tdes = adsk.fusion.Design.cast(tmp.products.itemByProductType('DesignProductType'))
                    comp, body = find_body(tdes, g)
                    if body is None: raise RuntimeError('govde kopyada bulunamadi')
                    old = clear_old_flat(tmp, comp)
                    if old:
                        try: same = old.foldedBody is not None and old.foldedBody.name == body.name
                        except Exception: same = False
                        if not same:
                            try: owner = old.foldedBody.name
                            except Exception: owner = None
                            raise OldFlatPattern(owner)
                        # the leftover flat pattern is this body's own: use it as is (its stationary face is fixed)
                        fp, ok = old, unfolded(old) or not has_bends(body)
                        log('  eski flat pattern bu govdenin, o kullaniliyor')
                        t_want = sheets[g['sheet']]['target_t']
                        if t_want is not None and g['model_t'] is not None and abs(t_want - g['model_t']) > T_TOL:
                            rethick.append(name)  # the old flat pattern stays at the model thickness
                        break
                    sh = sheets[g['sheet']]
                    if sh['target_t'] is not None and (g['model_t'] is None or abs(sh['target_t'] - g['model_t']) > T_TOL):
                        n, supp = set_thickness(tdes, g['model_t'], sh['target_t'], g['body'])
                        if supp: g['suppressed'] = supp
                        comp, body = find_body(tdes, g)
                        now = body_thickness(body) if body else None
                        if attempt == 1: log('  kalinlik %s -> %s mm: %d kural, govde simdi %s mm' % (g['model_t'], sh['target_t'], n, now))
                        if body is None: raise RuntimeError('govde kalinlik degisince kayboldu')
                        if now is None or abs(now - sh['target_t']) > T_TOL:
                            if name not in rethick: rethick.append(name)
                    planar = sorted((f for f in body.faces if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType),
                                    key=lambda f: -f.area)
                    # a face that unfolded this part before (same thickness) goes first: Fusion sometimes leaves the
                    # part folded for the largest face, and each miss costs a fresh copy
                    mkey = '%s|%s|%s|%s' % (doc_name, g['comp'], g['body'], sheets[g['sheet']]['target_t'])
                    known = tuple(memory[mkey]) if mkey in memory else None
                    face = (next((f for f in planar if face_key(f) == known and known not in tried), None) or
                            next((f for f in planar if face_key(f) not in tried), None))
                    if face is None: break
                    tried.append(face_key(face))
                    try:
                        fp = comp.createFlatPattern(face)
                    except RuntimeError as e:
                        if 'already exists' in str(e): raise OldFlatPattern()
                        raise
                    ok = unfolded(fp) or not has_bends(body)
                    if ok:
                        if attempt > 1: log('  %d. denemede acildi (sabit yuz alan=%.4f)' % (attempt, face.area))
                        elif known and face_key(face) == known: log('  hatirlanan yuzle ilk denemede acildi')
                        memory[mkey] = list(face_key(face))
                        break
                    log('  ACILMADI deneme %d (sabit yuz alan=%.4f, saglik=%s %s), baska yuzle deneniyor' % (
                        attempt, face.area, fp.healthState, fp.errorOrWarningMessage))
                if not ok:
                    partial.append(name)
                    log('  UYARI %s: %d denemede acilmadi, DXF EKSIK ACINIM' % (name, len(tried)))
                path = os.path.join(part_dir, name + '.dxf')
                part = {}
                try:
                    tdes.exportManager.execute(tdes.exportManager.createDXFFlatPatternExportOptions(path, fp))
                except Exception:
                    # Fusion's flat-pattern DXF export fails on some designs; write the cut geometry ourselves instead
                    log('  Fusion DXF aktarimi basarisiz, kesim geometrisi okunuyor: ' + traceback.format_exc().splitlines()[-1])
                    face = flat_face(fp)
                    bends = bend_lines(fp, face)
                    part['geom'] = face_outline(face) + bends
                    log('  yedek DXF: %d BEND, %d BEND_EXTENT' % (sum(e['l'] == 'BEND' for e in bends),
                                                                   sum(e['l'] == 'BEND_EXTENT' for e in bends)))
                box = fp.bodies.item(0).boundingBox if fp.bodies.count else None
                size = [round((box.maxPoint.x - box.minPoint.x) * 10, 1), round((box.maxPoint.y - box.minPoint.y) * 10, 1)] if box else None
                part.update({'name': name, 'body': g['body'], 'comp': g['comp'], 'qty': g['qty'], 'dxf': path, 'flat_mm': size,
                             'bastirilan_adimlar': g.get('suppressed', []), 'model_kalinlik_mm': g['model_t'], 'kalinlik_mm': part_thickness(fp, comp), 'sac': g['sheet'],
                             'bends': bend_info(fp)})
                if not ok: part['eksik_acinim'] = True
                gs = geom_size(part.get('geom', []))
                if gs and size and any(abs(a - b) > max(1.0, 0.02 * b) for a, b in zip(sorted(gs), sorted(size))):
                    log('  UYARI %s: DXF olcusu %s, acinim olcusu %s' % (name, gs, size))
                    if name not in partial: partial.append(name)
                results.append(part)
                log('OK %s adet=%d %s bukum(derece,yukari)=%s' % (name, g['qty'], size, part['bends']))
            except OldFlatPattern as e:
                # the rest of this component's bodies would hit the same wall: skip them without opening copies
                blocked[g['comp']] = e.args[0] if e.args else None; skipped.append(name)
                log('ATLANDI %s: componentte silinemeyen eski flat pattern' % name)
            except Exception:
                fails.append(name)
                log('HATA %s\n%s' % (name, traceback.format_exc()))
            finally:
                close_copy(tmp)
            prog.progressValue = i
            adsk.doEvents()
    finally:
        prog.hide()
        try: os.remove(archive)
        except Exception: pass
    # one nesting per sheet (thickness group), on that group's own sheet size, named by its type and thickness
    nest_files = []
    # model-making mode: each part carries its material's kerf and bend handling (nest_dxf.py redraws its lines)
    for p in results:
        if sheets[p['sac']].get('maket'): p['maket'] = sheets[p['sac']]['maket']
    # parts whose thickness change did not take were unfolded at the model thickness: they get their own file named so,
    # never one labelled with the thickness that was asked for
    for k, sh in enumerate(sheets):
        mine = [p['name'] for p in results if p['sac'] == k]
        if not (do_nest and sh['use'] and mine): continue
        t = sh['target_t'] if sh['target_t'] is not None else sh['model_t']
        for names, tt, tag in (([n for n in mine if n not in rethick], t, ''),
                               ([n for n in mine if n in rethick], sh['model_t'], L('_KALINLIK_DEGISMEDI'))):
            if not names: continue
            nest_files.append({'path': os.path.join(out, '00_NESTING_%s_%s_%smm%s.dxf' % (
                doc_name, sh['material'], '%g' % tt if tt is not None else 'X', tag)),
                'names': names, 'sheet_w': sh['sheet_w'], 'sheet_h': sh['sheet_h'],
                # automatic gap: as thick as the sheet, at least 3 mm; otherwise the dialog's value
                'gap': max(3.0, tt or 0.0) if (opts or {}).get('gap_auto') else gap,
                'maket': sh.get('maket'),
                # "Otomatik" sheet size: the material's standard sizes, nest_dxf takes the smallest that holds all
                'sizes': sh.get('auto_sizes'),
                'cost': dict(sh['cost'], t=tt) if sh.get('cost') and tt is not None else sh.get('cost'),
                'info': {'belge': src_doc.name, 'tur': sh.get('material_name') or sh['material'],
                         'kalinlik': '%g' % tt if tt is not None else '?'}})
    nest_msg, nest_ok = '', False
    # nest_dxf.py also writes the fallback DXFs and marks bend lines red in every part DXF, so it always runs
    if results:
        py = find_python()
        if not py:
            log('NESTING: ezdxf olan sistem Python bulunamadi')
            nest_msg = L('\nSistem Python bulunamadı (ezdxf gerekli): DXF yazılamadı/dizilemedi.')
        else:
            cfg = os.path.join(out, '_girdi.json')
            prog.isCancelButtonShown = True
            prog.cancelButtonText = L('İptal (hızlı dikdörtgen dizilim)')
            prog.show(L('Sac Açınım DXF'), L('DXF yazılıyor ve diziliyor...'), 0, 1)
            adsk.doEvents()

            def run_nest(how):
                # nest_dxf.py runs on its own while Fusion keeps drawing: the dialog shows the time taken and its
                # Cancel stops the run. Returns (returncode, stdout, stderr), or None when cancelled
                with open(cfg, 'w', encoding='utf8') as f:
                    json.dump({'sheet_w': 2500, 'sheet_h': 1250, 'gap': gap, 'parts': results, 'nest_files': nest_files,
                               'styles': styles or {}, 'legend': legend, 'method': how,
                               'png': png, **(opts or {})}, f, ensure_ascii=False)
                proc = subprocess.Popen([py, os.path.join(HERE, 'nest_dxf.py'), cfg, '-'], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, env=clean_env(),
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                t0 = time.time()
                while proc.poll() is None:
                    el = int(time.time() - t0)
                    prog.message = L('%s dizim sürüyor: %d dk %02d sn') % (L('Gerçek şekil') if how == 'shape' else L('Dikdörtgen'),
                                                                        el // 60, el % 60)
                    adsk.doEvents()
                    if prog.wasCancelled:
                        proc.kill(); proc.communicate()
                        return None
                    time.sleep(0.25)
                out_, err_ = proc.communicate()
                return proc.returncode, out_, err_
            try:
                r = run_nest(method)
                if r is None:  # cancelled: the instant rectangle packing still gives a usable nesting
                    log('NESTING iptal edildi, dikdortgen yontemle yeniden')
                    prog.hide(); prog.show(L('Sac Açınım DXF'), L('Dikdörtgen dizim...'), 0, 1); adsk.doEvents()
                    r = run_nest('rect') or (1, '', 'iptal')
                    r = (r[0], L('Gerçek şekil iptal edildi, dikdörtgen yöntem kullanıldı.\n') + r[1], r[2])
            finally:
                prog.hide()
            r = types.SimpleNamespace(returncode=r[0], stdout=r[1], stderr=r[2])
            log('NESTING %s\n%s\n%s' % (py, r.stdout, r.stderr))
            nest_ok = r.returncode == 0
            # the message shows nest_dxf.py's summary lines ("OZET "), in the chosen language; the rest is for the log
            summary = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith('OZET ')]
            nest_msg = ('\n' + '\n'.join(summary)) if r.returncode == 0 else L('\nDXF/nesting hatası, _log.txt dosyasına bak.')
            try: os.remove(cfg)
            except Exception: pass
    if (opts or {}).get('out_json', True):
        with open(os.path.join(out, '_parcalar.json'), 'w', encoding='utf8') as f:
            json.dump({'saclar': sheets,
                       'parcalar': [{k: v for k, v in p.items() if k != 'geom'} for p in results]}, f, indent=2, ensure_ascii=False)
    # part DXFs not wanted: their temp folder goes once the nesting has read them
    if not keep_separate and nest_ok:
        shutil.rmtree(part_dir, ignore_errors=True)
    log('BITTI %d ok, %d hata, %d eksik acinim, %d atlandi' % (len(results), len(fails), len(partial), len(skipped)))
    warn = (L('\n\nEKSİK AÇINIM, kontrol et: ') + ', '.join(partial)) if partial else ''
    if skipped:
        warn += (L('\n\nATLANDI (componentte önceden kalmış Flat Pattern silinemedi): %s\n'
                 'Browser → Flat Pattern → sağ tık → Delete, sonra tekrar çalıştırın.') % ', '.join(skipped))
    if rethick:
        warn += (L('\n\nKALINLIK DEĞİŞMEDİ: Fusion modeli yeni kalınlıkla yeniden oluşturamadı (ayrıntı _log.txt). '
                 'Bu parçalar modeldeki kalınlıkla açıldı, ayrı dosyada: ') + ', '.join(rethick))
        log('UYARI kalinlik degismedi: ' + ', '.join(rethick))
    supp = sorted({nm for p in results for nm in p.get('bastirilan_adimlar', [])})
    if supp:
        warn += (L('\n\nKalınlık için kopyalarda bastırılan adımlar (ilgili parçayı etkilemeyen Combine): ') + ', '.join(supp) +
                 L('. Asıl tasarım değişmedi.'))
    for sh in sheets:
        if sh['use'] and (sh.get('maket') or {}).get('warn'):
            warn += '\n\n%s %s: %s' % (L('UYARI'), sh.get('material_name') or sh['material'], sh['maket']['warn'])
    if excluded:
        warn += L('\n\nDahil edilmeyen: %d parça') % len(excluded)
    made = sorted(n for n in os.listdir(out) if n.startswith('00_') and n.endswith(('.dxf', '.png')))
    warn += '\n' + ''.join('\n' + n for n in made)
    ui.messageBox(L('%d parça DXF olarak aktarıldı%s.%s%s\n\nKlasör:\n%s\n\nSac Açınım DXF sürüm %s') % (
        len(results), (L(', %d hata (%s)') % (len(fails), ', '.join(fails))) if fails else '', nest_msg, warn, out, version()))
    try:
        with open(FACE_MEMORY, 'w', encoding='utf8') as f: json.dump(memory, f, ensure_ascii=False, indent=0)
    except Exception: log('  yuz hafizasi yazilamadi')
    open_folder(out)
