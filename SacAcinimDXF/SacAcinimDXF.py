# Add-in: every visible sheet-metal body -> Create Flat Pattern -> one DXF each, plus a nested DXF, all in one folder.
# Button: SHEET METAL > CREATE (and UTILITIES > ADD-INS) "Sac Açınım DXF". The work itself lives in sac_core.py,
# which is reloaded on every press so edits take effect without restarting the add-in.
import adsk.core, adsk.fusion, traceback, os, sys, importlib

CMD_ID = 'SacAcinimDXF_btn'
OLD_IDS = ['SacAcinimDXF_cmd']  # stale definition from the first version can't always be deleted
PANELS = ['SheetMetalCreatePanel', 'SolidScriptsAddinsPanel']
OLD_PANELS = ['SheetMetalModifyPanel']  # earlier version put the button here too
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import sac_core, json, dil
from dil import L

EVENT_ID = 'SacAcinimDXF_run'
# Sheet types as sold in Turkey: file-name code, standard sheet sizes ("short x long" mm) and thicknesses (mm).
# Typical stock; suppliers differ, so edit these lists to match yours.
SMALL = ['1000 x 2000', '1250 x 2500', '1500 x 3000']
MATERIALS = {
    'DKP (soğuk hadde)': ('DKP', SMALL, [0.5, 0.6, 0.7, 0.8, 1, 1.2, 1.5, 2, 2.5, 3]),
    'HRP / Siyah sac (sıcak hadde)': ('HRP', SMALL + ['1500 x 6000', '2000 x 6000'],
                                      [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20]),
    'Galvaniz': ('GALVANIZ', SMALL, [0.4, 0.5, 0.6, 0.7, 0.8, 1, 1.2, 1.5, 2, 2.5, 3]),
    'Paslanmaz': ('PASLANMAZ', SMALL + ['1500 x 6000'], [0.5, 0.6, 0.8, 1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]),
    'Alüminyum': ('ALUMINYUM', SMALL + ['1500 x 6000', '2000 x 6000'], [0.5, 0.8, 1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]),
}
OTHER = 'Diğer (tüm ölçüler)'
MATERIALS[OTHER] = ('SAC', SMALL + ['1500 x 6000', '2000 x 4000', '2000 x 6000'],
                    sorted({t for m in MATERIALS.values() for t in m[2]}))
DEFAULT_MATERIAL, DEFAULT_SIZE = 'DKP (soğuk hadde)', '1250 x 2500'
# Model-making (maket) materials for laser cutting, as industrial-design students use them: code, sheet sizes (common
# laser beds first, "short x long" mm), thicknesses, starting kerf (mm, tune to your machine), how bends are drawn,
# a warning, and the starting score spacing (mm; for wood the spacing of the hinge rows). PVC foam (Forex) is left out
# on purpose: laser-cut PVC gives off chlorine gas.
LASER = ['600 x 900', '400 x 600', '700 x 1000', '900 x 1300']
# sizes the stationery shops sell card, paper and foam board in (A4, A3 and the usual cut sheets)
SHOP = ['210 x 297 (A4)', '297 x 420 (A3)', '350 x 500', '500 x 700', '700 x 1000']


def sizes_of(*lists):
    # one list, no repeats, smallest sheet first
    out = []
    for z in (z for l in lists for z in l):
        if size_mm(z) not in [size_mm(o) for o in out]: out.append(z)
    return sorted(out, key=lambda z: size_mm(z)[0] * size_mm(z)[1])


def size_mm(label):
    # "1250 x 2500" or "210 x 297 (A4)" -> (en, boy) with en the long side
    a, b = (float(x) for x in label.split(' (')[0].split(' x '))
    return max(a, b), min(a, b)


MAKET_MATERIALS = {
    'Mukavva (gri maket kartonu)': ('MUKAVVA', sizes_of(SHOP, LASER), [1, 1.5, 2, 3], 0.2, 'score', '', 1.0),
    'Kağıt / Bristol': ('KAGIT', sizes_of(SHOP, LASER), [0.3, 0.5], 0.1, 'score', '', 0.5),
    'PP levha (polipropilen)': ('PP', sizes_of(SHOP, LASER), [0.5, 0.8, 1], 0.1, 'score', '', 0.5),
    'Oluklu karton': ('OLUKLU', sizes_of(SHOP, LASER), [3, 5], 0.3, 'score', '', 1.5),
    # foam core between two glossy paper faces; the foam melts wider than the beam, so test the score power first
    'Kapa / köpük maket kartonu (içi köpük, dışı parlak)': ('KAPA', sizes_of(SHOP, LASER), [3, 5, 10], 0.4,
                                                           'score', 'Köpük erir: çizik gücünü önce artık parçada dene', 2.0),
    'Balsa': ('BALSA', ['100 x 1000', '100 x 600'] + LASER, [1, 2, 3, 5], 0.15, 'score', '', 1.5),
    'Kontrplak / MDF': ('AHSAP', LASER, [3, 4, 5, 6], 0.2, 'hinge', '', 1.5),
    'Pleksi (akrilik)': ('PLEKSI', LASER + ['1000 x 2000'], [2, 3, 4, 5, 8], 0.15, 'heat', '', 1.0),
    'Strafor (EPS/XPS)': ('STRAFOR', ['500 x 1000', '600 x 1200', '1000 x 2000'], [10, 20, 30], 0.5, 'none',
                          'Strafor lazerde erir ve tutuşabilir; sıcak telle kesin', 1.0),
    'Diğer maket malzemesi': ('MAKET', sizes_of(SHOP, LASER), [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10], 0.2, 'score', '', 1.0),
}
DEFAULT_MAKET = 'Mukavva (gri maket kartonu)'
BENDS = [('Çizik (bükümü doldurur)', 'score'), ('Esnek menteşe (kesik yarıklar)', 'hinge'),
         ('Isıyla bük (yalnız işaret)', 'heat'), ('Büküm çizme', 'none')]


def mat_info(name):
    return MATERIALS.get(name) or MAKET_MATERIALS[name]


# Pricing (see NOTLAR.md): sheet price by kg (metal), per sheet or per m²; laser by metres + pierces (metal shops)
# or by machine minutes (model-making workshops). Nothing is priced until a price is typed; prices are remembered
# per material + thickness in _fiyatlar.json. Densities g/cm³; cut / score speeds mm/s are rough CO2 (60-100 W)
# starting values for minute pricing, to be set to the workshop's own.
PRICES = os.path.join(HERE, '_fiyatlar.json')
DENSITY = {'DKP': 7.85, 'HRP': 7.85, 'GALVANIZ': 7.85, 'SAC': 7.85, 'PASLANMAZ': 7.93, 'ALUMINYUM': 2.70}
SPEEDS = {'MUKAVVA': (15, 100), 'KAGIT': (60, 150), 'PP': (30, 120), 'OLUKLU': (25, 100), 'KAPA': (15, 80),
          'BALSA': (20, 100), 'AHSAP': (8, 100), 'PLEKSI': (6, 100), 'STRAFOR': (20, 80), 'MAKET': (15, 100)}
# sheet metal is sold by weight (or area); model-making boards by area, so any sheet size is priced the same way.
# A sheet chosen by hand can also take its own price per sheet (not with "Otomatik", where the size is not known yet)
UNITS = {False: [('TL/kg', 'kg'), ('TL/m²', 'm2')], True: [('TL/m²', 'm2')]}
PER_SHEET = ('TL/levha', 'levha')
LMODES = [('Metre + giriş (sac atölyesi)', 'metre'), ('Dakika (maket atölyesi)', 'dakika')]
LASER_FIELDS = [('per_m', 'Kesim (TL/m)', 'Kesilen her metre çizgi için.'),
                ('per_pierce', 'Giriş (TL/adet)', 'Lazerin her kesime başlayışı (her kontur, her delik) için.'),
                ('per_min', 'Makine (TL/dk)', 'Atölyenin dakika ücreti.'),
                ('cut_speed', 'Kesim hızı (mm/sn)', 'Tahmini başlangıç değeri; atölyenin makinesine göre düzelt.'),
                ('score_speed', 'Çizik hızı (mm/sn)', 'Tahmini başlangıç değeri; atölyenin makinesine göre düzelt.'),
                ('per_bend', 'Büküm (TL/büküm)', 'Abkant: her büküm için.'),
                ('setup', 'Hazırlık (TL/iş)', 'İş başına bir kez: hazırlık, en düşük ücret vb.')]
AUTO = 'Otomatik (tek levhaya sığan en küçük)'
CUSTOM = 'Özel ölçü (elle gir)'
CUSTOM_T = 'Özel kalınlık (elle gir)'
_handlers = []
_event = None


# line kinds in the DXF (layer, name), the choices for each, and today's look as the default
STYLE_CATS = [('OUTER_PROFILES', 'Dış kesim'), ('INTERIOR_PROFILES', 'İç kesim (delik)'),
              ('BEND', 'Büküm çizgisi'), ('BEND_EXTENT', 'Büküm sınırı'),
              ('CIZIK', 'Çizik (düşük güç, kesmez)'), ('MENTESE', 'Esnek menteşe yarığı (kesim)'),
              ('ISARET', 'Isıyla büküm işareti (kesmez)')]
COLORS = [('Kırmızı', 1), ('Sarı', 2), ('Yeşil', 3), ('Camgöbeği', 4), ('Mavi', 5), ('Mor', 6),
          ('Beyaz/Siyah', 7), ('Gri', 8), ('Turuncu', 30)]
LTYPES = [('Düz', 'CONTINUOUS'), ('Kesikli', 'DASHED'), ('Kesik-nokta', 'DASHDOT'), ('Eksen', 'CENTER')]
DEFAULT_STYLES = {'OUTER_PROFILES': [True, 7, 'CONTINUOUS'], 'INTERIOR_PROFILES': [True, 7, 'CONTINUOUS'],
                  'BEND': [True, 1, 'CONTINUOUS'], 'BEND_EXTENT': [True, 7, 'CONTINUOUS'],
                  'CIZIK': [True, 5, 'CONTINUOUS'], 'MENTESE': [True, 1, 'CONTINUOUS'], 'ISARET': [True, 3, 'CONTINUOUS']}
# true shape: parts by their real outline, turned in 90 deg steps (ironnest); rectangle: bounding boxes in rows, instant
METHODS = [('Gerçek şekil (sac tasarrufu)', 'shape'), ('Dikdörtgen (hızlı)', 'rect')]
# where the parts gather on each sheet: smallest square / sheet-shaped box at the bottom left, or a strip up the left edge
# 'area' = smallest box by area, i.e. least scrap (sparrow beat the square by ~7-8 % on yeryeni2)
LAYOUTS = [('En az fire (en küçük alan)', 'area'), ('Kompakt kare (sol alt)', 'square'), ('Şerit (sol kenar)', 'strip')]
# auto tries 90° steps, edge-aligned turns and 15° steps and keeps the tightest (slow: 15° alone took 631 s for 14
# parts on 2500x1250); the run no longer has a time limit, the progress dialog can cancel it
ANGLES = [('Otomatik (en verimli)', 'auto'), ('90° (4 yön)', 90), ('45° (8 yön)', 45)]
# fast: ironnest only (seconds, like PrusaSlicer's arrange); balanced/best: sparrow squeezes each sheet further
QUALITIES = [('Dengeli (~1-3 dk)', 'balanced'), ('Hızlı (~30 sn)', 'fast'), ('En iyi (~10 dk, ana ürün)', 'best')]
SETTINGS = os.path.join(HERE, '_ayarlar.json')  # last settings, so the dialog opens as it was left
MODES = [('Sac metal (lazer / abkant)', False), ('Maket (lazer: karton, pleksi, ahşap…)', True)]
# which line kinds each mode can draw; the others are hidden in "Çizgi görünümü"
MODE_LAYERS = {False: ('OUTER_PROFILES', 'INTERIOR_PROFILES', 'BEND', 'BEND_EXTENT'),
               True: ('OUTER_PROFILES', 'INTERIOR_PROFILES', 'CIZIK', 'MENTESE', 'ISARET')}
# what the run writes, each its own tick: (id, label, default, tooltip)
OUTPUTS = [('out_parts', 'Parça başına DXF', True, 'Her parça kendi DXF dosyasında.'),
           ('out_nest', 'Nesting DXF', True, 'Bütün parçalar sacın üstünde dizili, büküm çizgileriyle.'),
           ('out_cut', 'Kesim DXF', True, 'Aynı dizilim, yalnız lazerin çizgileri (kesim, çizik): makineye giden dosya.'),
           ('png_nest', 'Nesting resmi (PNG)', True, 'Dizilimin resmi, parça adları ve başlık bloğuyla.'),
           ('png_cut', 'Kesim resmi (PNG)', True, 'Kesim DXF\'inin resmi.'),
           ('png_close', 'Yakın resim', True, 'Parçalar sacın küçük bir köşesindeyse o köşenin büyük resmi.'),
           ('out_cost', 'Maliyet tablosu (CSV)', True, 'Fiyat girildiyse parça parça maliyet; Excel açar.'),
           ('legend', 'Çizgi açıklaması (DXF)', True, 'Hangi renk çizginin ne olduğu, DXF\'te parçaların dışına yazılır.'),
           ('out_json', 'Parça listesi (_parcalar.json)', True, 'Parçaların ölçüleri, kalınlıkları ve bükümleri.')]
GROUPS = [('g_nest', 'Dizme', True), ('g_gap', 'Boşluk ve kerf', False), ('g_out', 'Çıktılar', False),
          ('g_style', 'Çizgi görünümü', False)]
_sections = {}  # k -> (section's CommandInputs, model thickness mm) for the open dialog
_in = {}  # id -> every input outside the thickness sections, for the open dialog


LANGS = [('Türkçe', 'tr'), ('English', 'en')]


def fusion_lang():
    # first run: Turkish when Fusion itself runs in Turkish, English otherwise
    try:
        ul = adsk.core.Application.get().preferences.generalPreferences.userLanguage
        return 'tr' if ul == getattr(adsk.core.UserLanguages, 'TurkishLanguage', object()) else 'en'
    except Exception:
        return 'en'


def load_settings():
    st = {'styles': {k: list(v) for k, v in DEFAULT_STYLES.items()}, 'method': 'shape',
          'layout': 'area', 'angle_step': 'auto', 'holes': True,
          'quality': 'balanced', 'gap_auto': True, 'gap': 10.0, 'kerf': 0.2, 'edge': 10.0, 'common': False,
          'maket': False, 'merge': True, 'grow_outer': False, 'grow_holes': False, 'cost': False,
          'open': {g: o for g, _, o in GROUPS}, 'lang': fusion_lang()}
    st.update({k: d for k, _, d, _ in OUTPUTS})
    try:
        with open(SETTINGS, encoding='utf8') as f: saved = json.load(f)
        # 1.8 and before: one picture tick and "cut_file"
        if 'png' in saved and 'png_nest' not in saved: saved['png_nest'] = saved['png_cut'] = saved['png']
        if 'cut_file' in saved and 'out_cut' not in saved: saved['out_cut'] = saved['cut_file']
        for k in st:
            if k not in ('styles', 'open'): st[k] = saved.get(k, st[k])
        st['open'].update(saved.get('open', {}))
        st['lang'] = saved.get('lang', 'tr')  # settings from before the language choice were made in Turkish
        if st['angle_step'] not in dict((c, n) for n, c in ANGLES): st['angle_step'] = 'auto'
        if st['layout'] not in dict((c, n) for n, c in LAYOUTS): st['layout'] = 'area'
        if st['method'] not in dict((c, n) for n, c in METHODS): st['method'] = 'shape'
        for k, v in saved.get('styles', {}).items():
            if k in st['styles']: st['styles'][k] = [v['show'], v['color'], v['ltype']]
    except Exception: pass
    return st


def save_settings(styles, opts):
    try:
        with open(SETTINGS, 'w', encoding='utf8') as f:
            json.dump(dict(opts, styles=styles), f, ensure_ascii=False, indent=1)
    except Exception: pass


def reg(x, tip=None):
    # keep the input for later and give it a hover explanation
    _in[x.id] = x
    if tip: x.tooltip = tip
    return x


def dropdown(c, id_, label, items, pick, tip=None):
    dd = c.addDropDownCommandInput(id_, label, adsk.core.DropDownStyles.TextListDropDownStyle)
    for name, code in items: dd.listItems.add(L(name), code == pick)
    if tip: dd.tooltip = tip
    return dd


def sel(x):
    # the chosen dropdown item's own (Turkish) name, whatever language it is shown in
    return dil.back(x.selectedItem.name) if x.selectedItem else None


def picked(id_, items):
    return dict(items)[sel(_in[id_])]


def lock_styles():
    maket = picked('mode', MODES)
    for i, (layer, _) in enumerate(STYLE_CATS):
        shown = layer in MODE_LAYERS[maket]
        on = _in['stshow-%d' % i].value
        _in['stshow-%d' % i].isVisible = shown
        for x in ('stcol', 'stlt'):
            _in['%s-%d' % (x, i)].isVisible = shown
            _in['%s-%d' % (x, i)].isEnabled = on


def lock_top():
    # show only what applies: the mode's own settings, the nesting options the method uses, the gap when typed
    maket = picked('mode', MODES)
    for i in ('kerf', 'common'): _in[i].isVisible = not maket
    for i in ('merge', 'grow_outer', 'grow_holes'): _in[i].isVisible = maket
    shape = picked('method', METHODS) == 'shape'
    for i in ('layout', 'angle', 'quality', 'holes'): _in[i].isVisible = shape
    _in['gap'].isVisible = not _in['gap_auto'].value
    lock_styles()


def t_label(t):
    return dil.num(t) + ' mm'


def fill_sizes(inp, k, material, keep=None):
    dd = inp.itemById('size_%d' % k)
    sizes = mat_info(material)[1]
    pick = keep if keep in sizes or keep in (CUSTOM, AUTO) else AUTO
    dd.listItems.clear()
    dd.listItems.add(L(AUTO), pick == AUTO)
    for s in sizes: dd.listItems.add(s, s == pick)
    dd.listItems.add(L(CUSTOM), pick == CUSTOM)
    apply_size(inp, k, pick)


def apply_size(inp, k, label):
    # a standard sheet fills in en/boy; "Özel ölçü" shows them for typing
    if label == AUTO:  # the largest listed sheet stands in until the run picks the smallest that fits
        sizes = mat_info(sel(inp.itemById('mat_%d' % k)))[1]
        label = max(sizes, key=lambda z: size_mm(z)[0] * size_mm(z)[1])
    if label != CUSTOM:
        w, h = size_mm(label)
        inp.itemById('w_%d' % k).value, inp.itemById('h_%d' % k).value = w / 10, h / 10  # mm -> internal cm
    lock_section(inp, k)


def fill_thicknesses(inp, k, material, want):
    # list the type's thicknesses with the wanted one selected (or "Özel kalınlık" holding it)
    dd = inp.itemById('tp_%d' % k)
    ts = mat_info(material)[2]
    hit = next((t for t in ts if want is not None and abs(t - want) < 0.01), None)
    dd.listItems.clear()
    for t in ts: dd.listItems.add(t_label(t), t == hit)
    dd.listItems.add(L(CUSTOM_T), hit is None)
    if want is not None: inp.itemById('t_%d' % k).value = want / 10
    lock_section(inp, k)


def fill_materials(inp, k, maket):
    # the section's material list: sheet metals, or model-making materials in maket mode
    dd = inp.itemById('mat_%d' % k)
    pick = DEFAULT_MAKET if maket else DEFAULT_MATERIAL
    dd.listItems.clear()
    for m in (MAKET_MATERIALS if maket else MATERIALS): dd.listItems.add(L(m), m == pick)
    return pick


def apply_maket(inp, k, material):
    # a model-making material fills in its kerf, bend handling and score spacing (all can be changed)
    info = MAKET_MATERIALS.get(material)
    if info:
        inp.itemById('kerf_%d' % k).value = info[3] / 10
        inp.itemById('pitch_%d' % k).value = info[6] / 10
        for it in inp.itemById('bend_%d' % k).listItems:
            if dict(BENDS)[dil.back(it.name)] == info[4]: it.isSelected = True
    lock_section(inp, k)


def set_mode(maket):
    # sheet metal / maket: every section switches its material list; inputs of the other mode are hidden
    for k, (c, model_t) in _sections.items():
        material = fill_materials(c, k, maket)
        fill_sizes(c, k, material)
        fill_thicknesses(c, k, material, c.itemById('t_%d' % k).value * 10 if c.itemById('chg_%d' % k).value else model_t)
        apply_maket(c, k, material)
        fill_prices(c, k)
    lock_top()


def lock_section(inp, k):
    # "Dahil et" off folds the section to that one tick; sheet en/boy show for "Özel ölçü"; thickness opens only
    # with "Kalınlığı değiştir"; kerf, bend and score spacing belong to maket materials
    use, chg = inp.itemById('use_%d' % k).value, inp.itemById('chg_%d' % k).value
    maket = MAKET_MATERIALS.get(sel(inp.itemById('mat_%d' % k))) is not None
    for i in ('mat', 'size', 'chg', 'tp'): inp.itemById('%s_%d' % (i, k)).isVisible = use
    size, tp = inp.itemById('size_%d' % k).selectedItem, inp.itemById('tp_%d' % k).selectedItem  # empty while filling
    custom_size = size is not None and dil.back(size.name) == CUSTOM
    for i in ('w', 'h'): inp.itemById('%s_%d' % (i, k)).isVisible = use and custom_size
    inp.itemById('tp_%d' % k).isEnabled = chg
    inp.itemById('t_%d' % k).isVisible = use and chg and tp is not None and dil.back(tp.name) == CUSTOM_T
    bend = inp.itemById('bend_%d' % k)
    for i in ('kerf', 'bend'): inp.itemById('%s_%d' % (i, k)).isVisible = use and maket
    inp.itemById('pitch_%d' % k).isVisible = use and maket and dict(BENDS)[sel(bend)] in ('score', 'hinge')
    cost = use and inp.itemById('cost_%d' % k).value
    lm = inp.itemById('lmode_%d' % k).selectedItem
    minutes = lm is not None and dict(LMODES)[dil.back(lm.name)] == 'dakika'
    for i in ('punit', 'price', 'lmode', 'setup'): inp.itemById('%s_%d' % (i, k)).isVisible = cost
    for i in ('per_m', 'per_pierce'): inp.itemById('%s_%d' % (i, k)).isVisible = cost and not minutes
    for i in ('per_min', 'cut_speed', 'score_speed'): inp.itemById('%s_%d' % (i, k)).isVisible = cost and minutes
    inp.itemById('per_bend_%d' % k).isVisible = cost and not maket


def load_prices():
    try:
        with open(PRICES, encoding='utf8') as f: return json.load(f)
    except Exception: return {'malzeme': {}, 'lazer': {}}


def price_key(inp, k):
    # material code + thickness the parts are cut from
    return '%s|%g' % (mat_info(sel(inp.itemById('mat_%d' % k)))[0], round(inp.itemById('t_%d' % k).value * 10, 2))


def sheet_key(inp, k):
    # "1300x900" for the chosen (or typed) sheet; None for "Otomatik"
    size = sel(inp.itemById('size_%d' % k))
    if size == AUTO: return None
    w, h = inp.itemById('w_%d' % k).value * 10, inp.itemById('h_%d' % k).value * 10
    return '%gx%g' % (round(max(w, h), 1), round(min(w, h), 1))


def stored_price(mat, unit, sheet):
    # a remembered price: per kg / m² for the material + thickness, per sheet for that sheet size
    if unit == 'levha': return (mat.get('levha') or {}).get(sheet, 0) if sheet else 0
    if unit in mat: return mat[unit]
    if mat.get('unit') == unit: return mat.get('price', 0)  # 1.11.0 kept one price with its unit
    if unit == 'm2' and mat.get('unit') == 'levha' and mat.get('ref'):  # 1.10.x: a big sheet's price -> per m²
        rw, rh = mat['ref']
        return round(mat.get('price', 0) / (rw * rh / 1e6), 2) if rw * rh else 0
    return 0


def fill_prices(inp, k):
    # the remembered prices of this material + thickness (and sheet size, per sheet), or empty ones
    maket = MAKET_MATERIALS.get(sel(inp.itemById('mat_%d' % k))) is not None
    code = mat_info(sel(inp.itemById('mat_%d' % k)))[0]
    pr = load_prices()
    mat, las = pr.get('malzeme', {}).get(price_key(inp, k), {}), pr.get('lazer', {}).get(price_key(inp, k), {})
    sheet = sheet_key(inp, k)
    units = UNITS[maket] + ([PER_SHEET] if sheet else [])
    unit = mat.get('unit') if mat.get('unit') in dict((c, n) for n, c in units) else units[0][1]
    if unit == 'levha' and not stored_price(mat, 'levha', sheet): unit = units[0][1]  # no price for this sheet yet
    dd = inp.itemById('punit_%d' % k)
    dd.listItems.clear()
    for name, c in units: dd.listItems.add(L(name), c == unit)
    inp.itemById('price_%d' % k).value = stored_price(mat, unit, sheet)
    mode = las.get('mode', 'dakika' if maket else 'metre')
    for it in inp.itemById('lmode_%d' % k).listItems:
        if dict(LMODES)[dil.back(it.name)] == mode: it.isSelected = True
    cs, ss = SPEEDS.get(code, (15, 100))
    defaults = {'cut_speed': cs, 'score_speed': ss}
    for f, _, _ in LASER_FIELDS: inp.itemById('%s_%d' % (f, k)).value = las.get(f, defaults.get(f, 0))
    lock_section(inp, k)


def save_prices(inp, k):
    # remember what was typed, by material + thickness; returns the run's cost
    pr = load_prices()
    key, unit = price_key(inp, k), dict(UNITS[False] + UNITS[True] + [PER_SHEET])[sel(inp.itemById('punit_%d' % k))]
    price = inp.itemById('price_%d' % k).value
    sheet = sheet_key(inp, k)
    mat = pr.setdefault('malzeme', {}).setdefault(key, {})
    for u in ('kg', 'm2'):  # earlier layouts (one price with its unit): kept under their unit before they go
        if u not in mat and stored_price(mat, u, None): mat[u] = stored_price(mat, u, None)
    for old in ('price', 'ref', 'sizes'): mat.pop(old, None)
    mat['unit'] = unit
    if unit == 'levha': mat.setdefault('levha', {})[sheet] = price
    else: mat[unit] = price
    size = sel(inp.itemById('size_%d' % k))
    las = {f: inp.itemById('%s_%d' % (f, k)).value for f, _, _ in LASER_FIELDS}
    las['mode'] = dict(LMODES)[sel(inp.itemById('lmode_%d' % k))]
    pr.setdefault('lazer', {})[key] = las
    try:
        with open(PRICES, 'w', encoding='utf8') as f: json.dump(pr, f, ensure_ascii=False, indent=1)
    except Exception: pass
    code = key.split('|')[0]
    return {'unit': unit, 'price': price, 'ref': [float(v) for v in sheet.split('x')] if unit == 'levha' else None,
            't': round(inp.itemById('t_%d' % k).value * 10, 2), 'density': DENSITY.get(code, 7.85),
            'per_bend': las['per_bend'] if code in DENSITY else 0, 'setup': las['setup'], 'laser': las,
            'auto': size == AUTO}


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            importlib.reload(sac_core)
            cmd = args.command
            # Fusion's default is as tall as the content (it ran off the screen); a fixed size scrolls instead
            cmd.setDialogInitialSize(420, 600)
            cmd.setDialogMinimumSize(360, 300)
            inp = cmd.commandInputs
            design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
            groups = sac_core.thickness_groups(design.rootComponent) if design else []
            st = load_settings()
            dil.LANG = st['lang'] if st['lang'] in dict((c, n) for n, c in LANGS) else 'en'
            _in.clear(); _sections.clear()
            reg(dropdown(inp, 'lang', 'Dil / Language', LANGS, dil.LANG),
                'Türkçe / English. Pencere kapatılıp açılınca uygulanır. Applies when the dialog is reopened.')
            reg(dropdown(inp, 'mode', L('Ne için?'), MODES, st['maket']),
                L('Sac metal: kesim + büküm çizgileri. Maket: karton, pleksi, ahşap için çizik / menteşe / işaret çizgileri.'))
            # 1) material: one section per sheet thickness in the design
            if not groups:
                inp.addTextBoxCommandInput('none', '', L('Görünür sheet metal gövde bulunamadı.'), 1, True)
            for k, gr in enumerate(groups):
                t = gr['t']
                title = L('%d. %s — %d parça%s') % (k + 1, t_label(t) if t is not None else L('kalınlık ölçülemedi'), gr['parts'],
                                                L(' (%d adet)') % gr['n'] if gr['n'] != gr['parts'] else '')
                sec = inp.addGroupCommandInput('sec_%d' % k, title)
                sec.isExpanded = True
                c = sec.children
                c.addBoolValueInput('use_%d' % k, L('Dahil et'), True, '', True).tooltip = L('Kapalıysa bu kalınlıktaki parçalar çıkarılmaz.')
                dropdown(c, 'mat_%d' % k, L('Malzeme'), [(m, m) for m in MATERIALS], DEFAULT_MATERIAL,
                              L('Malzeme seçince ölçü, kalınlık ve (makette) kerf, büküm, çizik aralığı kendiliğinden dolar.'))
                dropdown(c, 'size_%d' % k, L('Sac ölçüsü'), [], None, L('Standart levha ya da "Özel ölçü" ile elle.'))
                c.addValueInput('w_%d' % k, L('   En'), 'mm', adsk.core.ValueInput.createByString('2500 mm'))
                c.addValueInput('h_%d' % k, L('   Boy'), 'mm', adsk.core.ValueInput.createByString('1250 mm'))
                c.addBoolValueInput('chg_%d' % k, L('Kalınlığı değiştir'), True, '', False).tooltip = (
                    L('Kapalı: modeldeki kalınlık. Açık: açınım seçilen kalınlıkla yeniden hesaplanır (asıl tasarım değişmez).'))
                dropdown(c, 'tp_%d' % k, L('Kalınlık'), [], None)
                c.addValueInput('t_%d' % k, L('   Kalınlık (mm)'), 'mm', adsk.core.ValueInput.createByString('%g mm' % (t or 1)))
                c.addValueInput('kerf_%d' % k, L('Kerf'), 'mm', adsk.core.ValueInput.createByString('0.2 mm')).tooltip = (
                    L('Lazerin yaktığı genişlik. Çizik aralığı bunun en az 2 katı olur; kerf tikleri açıksa çizgilere yarısı eklenir.'))
                dropdown(c, 'bend_%d' % k, L('Büküm'), BENDS, 'score',
                         L('Çizik: büküm şeridini paralel çiziklerle doldurur. Menteşe: ahşapta kesik yarıklar. '
                         'Isıyla: pleksi için yalnız işaret. Geniş bükümde şerit dolar, dar bükümde ortaya tek çizgi.'))
                c.addValueInput('pitch_%d' % k, L('Çizik aralığı'), 'mm', adsk.core.ValueInput.createByString('1 mm')).tooltip = (
                    L('İki çizik (ahşapta iki menteşe sırası) arası. Büküm sertse küçült, kırılgansa büyüt.'))
                c.addBoolValueInput('cost_%d' % k, L('Fiyat hesapla'), True, '', False).tooltip = (
                    L('Levha fiyatı ve lazer ücretiyle maliyet çıkarır. Girdiğin fiyatlar bu malzeme ve kalınlık için hatırlanır.'))
                dropdown(c, 'punit_%d' % k, L('   Fiyat birimi'), [], None,
                         L('TL/kg: sacın kilo fiyatı (levhanın ağırlığı en × boy × kalınlık × yoğunluktan). '
                         'TL/m²: malzemenin metrekare fiyatı; levha ölçüsü ne olursa olsun alanıyla hesaplanır. '
                         'TL/levha: seçtiğin levhanın tanesinin fiyatı (Otomatik ölçüde yok).'))
                c.addValueInput('price_%d' % k, L('   Fiyat (TL)'), '', adsk.core.ValueInput.createByReal(0))
                dropdown(c, 'lmode_%d' % k, L('   Lazer ücreti'), LMODES, 'metre',
                         L('Sac atölyeleri genelde kesilen metre + giriş sayısıyla, maket atölyeleri makine dakikasıyla ücretlendirir.'))
                for f, label, tip in LASER_FIELDS:
                    c.addValueInput('%s_%d' % (f, k), '   ' + L(label), '', adsk.core.ValueInput.createByReal(0)).tooltip = L(tip)
                _sections[k] = (c, t)
                fill_sizes(c, k, DEFAULT_MATERIAL)
                fill_thicknesses(c, k, DEFAULT_MATERIAL, t)
                c.itemById('cost_%d' % k).value = st.get('cost', False)
            # 2) nesting
            g = inp.addGroupCommandInput('g_nest', L('Dizme')); c = g.children; _in['g_nest'] = g
            reg(dropdown(c, 'method', L('Yöntem'), METHODS, st['method'],
                         L('Gerçek şekil: parçaların kendi şekliyle, en az fire. Dikdörtgen: çevreleyen kutularla, anında.')))
            reg(dropdown(c, 'layout', L('Dizilim'), LAYOUTS, st['layout'],
                         L('En az fire: en küçük alan. Kompakt kare: sol altta kareye yakın. Şerit: sol kenar boyunca.')))
            reg(dropdown(c, 'angle', L('Döndürme'), ANGLES, st['angle_step'], L('Otomatik: her parçayı en verimli açıyla döndürür.')))
            reg(dropdown(c, 'quality', L('Kalite'), QUALITIES, st['quality'], L('Uzun sürdükçe daha sıkı dizer.')))
            reg(c.addBoolValueInput('holes', L('Küçük parçaları deliklere yerleştir'), True, '', st['holes']),
                L('Büyük parçaların içindeki deliklere sığan küçük parçaları koyar.'))
            # 3) spacing and kerf
            g = inp.addGroupCommandInput('g_gap', L('Boşluk ve kerf')); c = g.children; _in['g_gap'] = g
            reg(c.addBoolValueInput('gap_auto', L('Boşluk = sac kalınlığı (en az 3 mm)'), True, '', st['gap_auto']),
                L('Her kalınlık kendi boşluğunu alır. Kapatınca elle girilir.'))
            reg(c.addValueInput('gap', L('Parça arası boşluk'), 'mm', adsk.core.ValueInput.createByString('%g mm' % st['gap'])))
            reg(c.addValueInput('edge', L('Sac kenar payı'), 'mm', adsk.core.ValueInput.createByString('%g mm' % st['edge'])),
                L('Parçalarla sacın kenarı arası.'))
            reg(c.addValueInput('kerf', L('Kerf (kesim genişliği)'), 'mm', adsk.core.ValueInput.createByString('%g mm' % st['kerf'])),
                L('Parça arası boşluğa eklenir; DXF ölçüleri değişmez (kerfi kesim programı düzeltir).'))
            reg(c.addBoolValueInput('common', L('Ortak kesime hazırla (parça arası = kerf)'), True, '', st['common']),
                L('Parçalar kerf kadar yakın dizilir; ortak kenarı kesim programı tek seferde keser.'))
            reg(c.addBoolValueInput('merge', L('Kenarları birleştir (ortak kenar tek kesim)'), True, '', st['merge']),
                L('Parçalar boşluksuz dizilir, üst üste gelen düz kenarlar tek çizgiye iner.'))
            reg(c.addBoolValueInput('grow_outer', L('Dış çizgiye yarım kerf ekle'), True, '', st['grow_outer']),
                L('Lazer programın kerfi düzeltiyorsa kapalı bırak.'))
            reg(c.addBoolValueInput('grow_holes', L('Deliklere yarım kerf ekle'), True, '', st['grow_holes']),
                L('Lazer programın kerfi düzeltiyorsa kapalı bırak.'))
            # 4) outputs
            g = inp.addGroupCommandInput('g_out', L('Çıktılar')); c = g.children; _in['g_out'] = g
            for id_, label, _, tip in OUTPUTS: reg(c.addBoolValueInput(id_, L(label), True, '', st[id_]), L(tip))
            # 5) line look
            g = inp.addGroupCommandInput('g_style', L('Çizgi görünümü')); c = g.children; _in['g_style'] = g
            for i, (layer, label) in enumerate(STYLE_CATS):
                show, color, ltype = st['styles'][layer]
                reg(c.addBoolValueInput('stshow-%d' % i, L(label), True, '', show), L('Kapalıysa bu çizgiler çıktıya girmez.'))
                reg(dropdown(c, 'stcol-%d' % i, L('   rengi'), COLORS, color))
                reg(dropdown(c, 'stlt-%d' % i, L('   çizgisi'), LTYPES, ltype))
            for gid, _, _ in GROUPS: _in[gid].isExpanded = st['open'].get(gid, False)
            inp.addTextBoxCommandInput('ver', '', L('Sac Açınım DXF  sürüm %s') % sac_core.version(), 1, True)
            set_mode(st['maket'])
            h = ExecuteHandler(); cmd.execute.add(h); _handlers.append(h)
            h = ChangedHandler(); cmd.inputChanged.add(h); _handlers.append(h)
        except Exception:
            adsk.core.Application.get().userInterface.messageBox(L('Hata:\n') + traceback.format_exc())


class ChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            i = args.input
            if i.id == 'lang':  # remembered now, shown from the next opening (labels cannot be renamed in place)
                st = load_settings()
                st['lang'] = picked('lang', LANGS)
                styles = {k: {'show': v[0], 'color': v[1], 'ltype': v[2]} for k, v in st.pop('styles').items()}
                save_settings(styles, st)
                adsk.core.Application.get().userInterface.messageBox(
                    'Dil değişikliği pencere kapatılıp yeniden açılınca uygulanır.\n'
                    'The new language applies when you close and reopen this dialog.')
                return
            if i.id == 'mode':
                set_mode(picked('mode', MODES)); return
            if i.id in ('method', 'gap_auto') or i.id.startswith('stshow-'):
                lock_top(); return
            base, _, k = i.id.rpartition('_')
            if not k.isdigit() or int(k) not in _sections: return
            k = int(k)
            c, model_t = _sections[k]
            if base == 'mat':
                material = sel(i)
                fill_sizes(c, k, material, sel(c.itemById('size_%d' % k)))
                fill_thicknesses(c, k, material, c.itemById('t_%d' % k).value * 10)
                apply_maket(c, k, material)
                fill_prices(c, k)
            elif base == 'size':
                apply_size(c, k, sel(i))
                fill_prices(c, k)
            elif base == 'tp':
                label = sel(i)
                if label != CUSTOM_T: c.itemById('t_%d' % k).value = float(label.split()[0].replace(',', '.')) / 10
                fill_prices(c, k)
            elif base == 't':
                fill_prices(c, k)
            elif base == 'chg':
                if not i.value:  # back to the model's own thickness
                    fill_thicknesses(c, k, sel(c.itemById('mat_%d' % k)), model_t)
                fill_prices(c, k)
            elif base == 'punit':  # another unit: its own remembered price
                pr = load_prices().get('malzeme', {}).get(price_key(c, k), {})
                c.itemById('price_%d' % k).value = stored_price(pr, dict(UNITS[False] + UNITS[True] + [PER_SHEET])[sel(i)],
                                                                sheet_key(c, k))
            elif base in ('w', 'h'):
                fill_prices(c, k)
            elif base in ('use', 'bend', 'cost', 'lmode'):
                lock_section(c, k)
        except Exception:
            adsk.core.Application.get().userInterface.messageBox(L('Hata:\n') + traceback.format_exc())


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            ui = adsk.core.Application.get().userInterface
            maket = picked('mode', MODES)
            out = {id_: _in[id_].value for id_, _, _, _ in OUTPUTS}
            if not any(out[k] for k in ('out_parts', 'out_nest', 'out_cut', 'png_nest', 'png_cut')):
                ui.messageBox(L('En az bir çıktı seçilmeli (Çıktılar bölmesi).')); return
            sheets = []
            for k, (c, model_t) in sorted(_sections.items()):
                chg = c.itemById('chg_%d' % k).value
                mname = sel(c.itemById('mat_%d' % k))
                mk = MAKET_MATERIALS.get(mname) if maket else None
                sheets.append({'model_t': model_t, 'use': c.itemById('use_%d' % k).value,
                               'target_t': round(c.itemById('t_%d' % k).value * 10, 2) if chg else model_t,
                               'material': mat_info(mname)[0], 'material_name': L(mname),
                               'maket': {'kerf': round(c.itemById('kerf_%d' % k).value * 10, 3), 'warn': L(mk[5]) if mk[5] else '',
                                         'pitch': round(c.itemById('pitch_%d' % k).value * 10, 3),
                                         'grow_outer': _in['grow_outer'].value, 'grow_holes': _in['grow_holes'].value,
                                         'bend': dict(BENDS)[sel(c.itemById('bend_%d' % k))]} if mk else None,
                               'sheet_w': c.itemById('w_%d' % k).value * 10, 'sheet_h': c.itemById('h_%d' % k).value * 10,
                               'auto_sizes': [list(size_mm(z)) for z in mat_info(mname)[1]]
                               if sel(c.itemById('size_%d' % k)) == AUTO else None,
                               'cost': save_prices(c, k) if c.itemById('use_%d' % k).value and c.itemById('cost_%d' % k).value
                               else None})
            if not any(s['use'] for s in sheets):
                ui.messageBox(L('En az bir kalınlık dahil edilmeli.')); return
            colors, ltypes = dict(COLORS), dict(LTYPES)
            styles = {layer: {'label': L(label), 'show': _in['stshow-%d' % i].value,
                              'color': colors[sel(_in['stcol-%d' % i])],
                              'ltype': ltypes[sel(_in['stlt-%d' % i])]}
                      for i, (layer, label) in enumerate(STYLE_CATS)}
            method = picked('method', METHODS)
            gap = round(_in['gap'].value * 10, 3)
            opts = dict(out, layout=picked('layout', LAYOUTS), angle_step=picked('angle', ANGLES), holes=_in['holes'].value,
                        quality=picked('quality', QUALITIES), gap_auto=_in['gap_auto'].value, gap=gap,
                        kerf=round(_in['kerf'].value * 10, 3), edge=round(_in['edge'].value * 10, 3),
                        common=_in['common'].value, maket=maket, merge=_in['merge'].value,
                        grow_outer=_in['grow_outer'].value, grow_holes=_in['grow_holes'].value,
                        cut_file=out['out_cut'],
                        cost=any(c.itemById('cost_%d' % k).value for k, (c, _) in _sections.items()),
                        open={gid: _in[gid].isExpanded for gid, _, _ in GROUPS})
            opts['lang'] = dil.LANG
            save_settings(styles, dict(opts, method=method))
            # nesting runs whenever a nesting file or picture is wanted
            do_nest = any(out[k] for k in ('out_nest', 'out_cut', 'png_nest', 'png_cut'))
            # run outside the command: inside it Fusion holds every change in one transaction, so a deleted flat
            # pattern still blocks the next one and the flat-pattern DXF export fails
            adsk.core.Application.get().fireCustomEvent(EVENT_ID, json.dumps(
                [gap, do_nest, out['out_parts'], sheets, styles, out['legend'], method,
                 out['png_nest'] or out['png_cut'], opts]))
        except Exception:
            adsk.core.Application.get().userInterface.messageBox(L('Hata:\n') + traceback.format_exc())


class RunHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        try:
            importlib.reload(sac_core)
            sac_core.export_all(*json.loads(args.additionalInfo))
        except Exception:
            adsk.core.Application.get().userInterface.messageBox(L('Hata:\n') + traceback.format_exc())


def remove_ui(ui):
    for pid in PANELS + OLD_PANELS:
        panel = ui.allToolbarPanels.itemById(pid)
        ctl = panel.controls.itemById(CMD_ID) if panel else None
        if ctl: ctl.deleteMe()
        for old in OLD_IDS:
            ctl = panel.controls.itemById(old) if panel else None
            if ctl: ctl.deleteMe()
    for cid in [CMD_ID] + OLD_IDS:
        cd = ui.commandDefinitions.itemById(cid)
        if cd:
            try: cd.deleteMe()
            except Exception: pass


def run(context):
    try:
        ui = adsk.core.Application.get().userInterface
        remove_ui(ui)
        dil.LANG = load_settings()['lang']  # the button's name and tooltip in the chosen language
        global _event
        app = adsk.core.Application.get()
        try: app.unregisterCustomEvent(EVENT_ID)
        except Exception: pass
        _event = app.registerCustomEvent(EVENT_ID)
        h = RunHandler(); _event.add(h); _handlers.append(h)
        res = os.path.join(HERE, 'resources')
        cd = ui.commandDefinitions.itemById(CMD_ID) or ui.commandDefinitions.addButtonDefinition(CMD_ID, L('Sac Açınım DXF'),
                                                       L('Görünür tüm sheet metal gövdeleri flat pattern yapıp DXF + nesting çıkarır.'),
                                                       res if os.path.isdir(res) else '')
        h = CreatedHandler(); cd.commandCreated.add(h); _handlers.append(h)
        for pid in PANELS:
            panel = ui.allToolbarPanels.itemById(pid)
            if panel and not panel.controls.itemById(CMD_ID):
                ctl = panel.controls.addCommand(cd)
                ctl.isPromoted = pid != 'SolidScriptsAddinsPanel'
    except Exception:
        adsk.core.Application.get().userInterface.messageBox(L('SacAcinimDXF yüklenemedi:\n') + traceback.format_exc())


def stop(context):
    remove_ui(adsk.core.Application.get().userInterface)
    try: adsk.core.Application.get().unregisterCustomEvent(EVENT_ID)
    except Exception: pass
