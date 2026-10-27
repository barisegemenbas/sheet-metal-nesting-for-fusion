# Builds the user guides docs/USER_GUIDE.pdf (English) and docs/KULLANIM.pdf (Turkish) from the pictures in
# docs/images. Needs reportlab, Pillow and matplotlib (its DejaVu font has the Turkish letters):
#   python3 tools/build_guides.py
import os, json, datetime
import matplotlib
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICS = os.path.join(ROOT, 'docs', 'images')
VER = json.load(open(os.path.join(ROOT, 'SacAcinimDXF', 'SacAcinimDXF.manifest'), encoding='utf8'))['version']

ttf = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data', 'fonts', 'ttf')
pdfmetrics.registerFont(TTFont('DV', os.path.join(ttf, 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DVB', os.path.join(ttf, 'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('DV', normal='DV', bold='DVB')

ACCENT = colors.HexColor('#1f4e79')
base = ParagraphStyle('base', fontName='DV', fontSize=9.6, leading=13.5, alignment=TA_LEFT, spaceAfter=4)
H1 = ParagraphStyle('h1', parent=base, fontName='DVB', fontSize=20, leading=24, textColor=ACCENT, spaceAfter=6)
H2 = ParagraphStyle('h2', parent=base, fontName='DVB', fontSize=13, leading=17, textColor=ACCENT, spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle('h3', parent=base, fontName='DVB', fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=3)
SMALL = ParagraphStyle('small', parent=base, fontSize=8.2, leading=11, textColor=colors.HexColor('#555555'))
NOTE = ParagraphStyle('note', parent=base, backColor=colors.HexColor('#fff4d6'), borderPadding=6, spaceBefore=4, spaceAfter=8)
CELL = ParagraphStyle('cell', parent=base, fontSize=8.8, leading=12, spaceAfter=0)
CELLB = ParagraphStyle('cellb', parent=CELL, fontName='DVB')
W = A4[0] - 36 * mm
LANG = 'en'


def t(tr, en):
    return en if LANG == 'en' else tr


def p(text, st=base): return Paragraph(text, st)


def bullets(items):
    return [Paragraph('• ' + x, ParagraphStyle('b', parent=base, leftIndent=10, firstLineIndent=-7)) for x in items]


def steps(items):
    return [Paragraph('<b>%d.</b> %s' % (i + 1, x), ParagraphStyle('s', parent=base, leftIndent=12, firstLineIndent=-12))
            for i, x in enumerate(items)]


def table(rows, widths):
    data = [[Paragraph(str(c), CELLB if r == 0 else CELL) for c in row] for r, row in enumerate(rows)]
    tb = Table(data, colWidths=widths, repeatRows=1)
    tb.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b8c4d0')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e3ebf3'))]))
    return tb


def picture(name, width, caption=None, crop=None, keep=True):
    path = os.path.join(PICS, name)
    if crop:  # (left, top, right, bottom) as fractions of the picture
        im = Image.open(path)
        w, h = im.size
        path = os.path.join(PICS, '_crop_' + name)
        im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))).save(path)
    w, h = Image.open(path).size
    out = [RLImage(path, width=width, height=width * h / w)]
    if caption: out.append(p(caption, SMALL))
    return KeepTogether(out) if keep else out  # a table cell takes the plain list


def footer(c, doc):
    c.saveState()
    c.setFont('DV', 7.5)
    c.setFillColor(colors.HexColor('#777777'))
    c.drawString(18 * mm, 10 * mm, t('Autodesk Fusion için Sac Açınım / Nesting — kullanım kılavuzu (sürüm %s)',
                                     'Sheet Metal Nesting for Autodesk Fusion — user guide (version %s)') % VER)
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
    c.restoreState()


def story():
    s = [p(t('Sac Açınım / Nesting', 'Sheet Metal Nesting'), H1),
         p(t('Autodesk® Fusion™ için eklenti — kullanım kılavuzu, sürüm %s', 'An add-in for Autodesk® Fusion™ — user guide, version %s') % VER, SMALL),
         Spacer(1, 6)]
    s += [p(t('Ne işe yarar?', 'What does it do?'), H2),
          p(t('Fusion\'da sheet metal ile çizdiğin parçaları tek tuşla lazer kesime hazırlar:',
              'It gets the parts you drew as sheet metal in Fusion ready for laser cutting, in one click:')),
          *bullets([t('Görünür her sheet metal gövdenin açınımını (flat pattern) çıkarır. <b>Asıl tasarımına dokunmaz</b>; '
                      'her şeyi geçici kopyalarda yapar.',
                      'Flattens every visible sheet metal body. <b>Your design is never changed</b>; all work happens in '
                      'temporary copies.'),
                    t('Her parçayı ayrı bir DXF yapar ve hepsini levhaya en az fireyle dizer (nesting).',
                      'Writes each part as a DXF and nests them all on sheets with as little scrap as it can.'),
                    t('<b>Sac metal</b> için: kesim çizgileri ve kırmızı büküm çizgileri.',
                      '<b>Sheet metal</b>: cut lines and red bend lines.'),
                    t('<b>Maket</b> için (mukavva, kapa, kağıt, PP, pleksi, ahşap): bükülecek yerlere çizik, ahşapta esnek '
                      'menteşe, pleksi için ısıyla büküm işareti.',
                      '<b>Model making</b> (greyboard, foam board, paper, PP, acrylic, wood): score lines where it bends, '
                      'living hinges for wood, heat-bend marks for acrylic.'),
                    t('Dizilimin resmini (PNG), yalnız lazere gidecek kesim dosyasını, fire oranını ve istersen maliyeti verir.',
                      'Also gives a picture of the layout (PNG), a cut-only file for the laser, scrap figures and, if you '
                      'want, a cost estimate.')])]
    s += [p(t('Başlamadan önce', 'Before you start'), H2),
          *bullets([t('Parçalar Fusion\'da <b>sheet metal</b> olarak çizilmiş olmalı. Her parça ayrı bir gövde (body) olsun.',
                      'The parts must be drawn as <b>sheet metal</b> in Fusion, each part its own body.'),
                    t('Yalnız <b>görünür</b> gövdeler alınır. Dahil etmek istemediğin gövdeyi Browser\'da gizle.',
                      'Only <b>visible</b> bodies are taken. Hide the ones you want left out in the Browser.'),
                    t('Farklı kalınlıktaki parçalar otomatik olarak gruplanır; her kalınlık kendi levhasına dizilir.',
                      'Parts of different thicknesses are grouped automatically; each thickness is nested on its own sheet.'),
                    t('Çıktılar: <b>Belgeler &gt; Sac_Acinim_DXF &gt; &lt;belge adı&gt;_&lt;tarih-saat&gt;</b>. Her çalıştırma '
                      'yeni bir klasör açar, eskiler silinmez. İş bitince klasör kendiliğinden açılır.',
                      'Output: <b>Documents &gt; SheetMetal_Nesting_DXF &gt; &lt;document&gt;_&lt;date-time&gt;</b>. Each run '
                      'makes a new folder; old ones are kept. The folder opens by itself when the run ends.')])]
    s += [p(t('Pencere, yukarıdan aşağı', 'The dialog, top to bottom'), H2),
          p(t('Fusion\'da <b>SHEET METAL</b> sekmesinde (ayrıca UTILITIES &gt; ADD-INS altında) butona bas. Ayarların '
              'üstüne fareyle gelince ne işe yaradıkları yazar. Pencere son ayarlarını hatırlar.',
              'Click the button on the <b>SHEET METAL</b> tab (also under UTILITIES &gt; ADD-INS). Hover over any setting '
              'to see what it does. The dialog remembers your last settings.')),
          table([[t('Bölüm', 'Section'), t('Ne yapar', 'What it does')],
                 ['<b>Dil / Language</b>', t('Türkçe ya da İngilizce; pencere yeniden açılınca uygulanır.',
                                             'Turkish or English; applies when the dialog is reopened.')],
                 [t('<b>Ne için?</b>', '<b>Made for</b>'), t('Sac metal ya da Maket. O moda ait olmayan ayarlar gizlenir.',
                                                           'Sheet metal or Model making. Settings of the other mode are hidden.')],
                 [t('<b>Kalınlık bölmeleri</b>', '<b>Thickness sections</b>'),
                  t('Her kalınlık için bir bölme: <b>Dahil et</b>, <b>Malzeme</b>, <b>Sac ölçüsü</b> (en başta "Otomatik": '
                    'parçaların hepsinin sığdığı en küçük levha), <b>Kalınlığı değiştir</b> (açınımı başka kalınlıkla '
                    'yeniden hesaplar). Makette ayrıca <b>Kerf</b>, <b>Büküm</b> ve <b>Çizik aralığı</b>. <b>Fiyat hesapla</b> '
                    'açılırsa fiyat alanları çıkar.',
                    'One section per thickness: <b>Include</b>, <b>Material</b>, <b>Sheet size</b> (first: "Automatic", the '
                    'smallest sheet that takes all parts), <b>Change thickness</b> (recomputes the flat pattern at another '
                    'thickness). Model making adds <b>Kerf</b>, <b>Bends</b> and <b>Score spacing</b>. <b>Calculate cost</b> '
                    'shows the price fields.')],
                 [t('<b>Dizme</b>', '<b>Nesting</b>'),
                  t('Yöntem (Gerçek şekil: en az fire; Dikdörtgen: hızlı), Dizilim (En az fire / Kompakt kare / Şerit), '
                    'Döndürme, Kalite (Hızlı ~30 sn, Dengeli ~1-3 dk, En iyi ~10 dk), küçük parçaları deliklere yerleştirme.',
                    'Method (True shape: least scrap; Rectangle: fast), Layout (Least scrap / Compact square / Strip), '
                    'Rotation, Quality (Fast ~30 s, Balanced ~1-3 min, Best ~10 min), small parts into holes.')],
                 [t('<b>Boşluk ve kerf</b>', '<b>Spacing and kerf</b>'),
                  t('Parça arası boşluk (varsayılan: sac kalınlığı, en az 3 mm), kenar payı. Sac metalde kerf ve ortak kesim; '
                    'makette kenarları birleştir ve "yarım kerf ekle" tikleri.',
                    'Gap between parts (default: the sheet thickness, at least 3 mm), edge margin. Sheet metal: kerf and '
                    'common-line cutting; model making: merge edges and the "add half kerf" ticks.')],
                 [t('<b>Çıktılar</b>', '<b>Outputs</b>'), t('Hangi dosyaların yazılacağı, her biri ayrı tik.',
                                                           'Which files are written, each its own tick.')],
                 [t('<b>Çizgi görünümü</b>', '<b>Line look</b>'), t('Her çizgi türünün rengi ve tipi; kapatılan tür çıktıya girmez.',
                                                                  'Colour and line type of each kind of line; a kind turned off is left out.')]],
                [40 * mm, W - 40 * mm])]
    s += [PageBreak(), p(t('Sac metal: adım adım', 'Sheet metal, step by step'), H2),
          *steps([t('Tasarımı aç, kesilecek sheet metal gövdeler görünür olsun.', 'Open the design; the bodies to cut must be visible.'),
                  t('Butona bas. <b>Ne için?</b> = Sac metal.', 'Click the button. <b>Made for</b> = Sheet metal.'),
                  t('Her kalınlık bölmesinde <b>Malzeme</b> ve <b>Sac ölçüsü</b> seç. Bilmiyorsan "Otomatik" bırak.',
                    'In each thickness section pick the <b>Material</b> and <b>Sheet size</b>. Not sure? Leave "Automatic".'),
                  t('<b>Dizme</b>: Gerçek şekil + En az fire + Otomatik döndürme + Dengeli, çoğu iş için en iyisi.',
                    '<b>Nesting</b>: True shape + Least scrap + Automatic rotation + Balanced suits most jobs.'),
                  t('OK. İlerleme penceresi geçen süreyi gösterir; "İptal" hızlı dikdörtgen dizime geçer.',
                    'OK. A progress window shows the time taken; "Cancel" switches to fast rectangle nesting.'),
                  t('Bitince bir özet çıkar (parça sayısı, fire, varsa maliyet) ve çıktı klasörü açılır.',
                    'At the end a summary appears (parts, scrap, cost if priced) and the output folder opens.')]),
          picture('sheet_metal_nesting.png', 85 * mm,
                  t('Sac metal örneği: siyah kesim, kırmızı büküm çizgileri; parça adları yalnız resimde (DXF\'te yazı yok, '
                    'lazer yazıyı da keserdi).',
                    'Sheet metal example: black cut lines, red bend lines; part names only in the picture (no text in the DXF, '
                    'the laser would cut it).'))]
    s += [PageBreak(), p(t('Maket: adım adım', 'Model making, step by step'), H2),
          *steps([t('<b>Ne için?</b> = Maket.', '<b>Made for</b> = Model making.'),
                  t('<b>Malzeme</b> seç: mukavva, kağıt/bristol, PP, oluklu karton, kapa, balsa, kontrplak/MDF, pleksi, strafor. '
                    'Kerf, büküm ve çizik aralığı malzemeye göre dolar.',
                    'Pick the <b>Material</b>: greyboard, paper/Bristol, PP, corrugated board, foam board, balsa, plywood/MDF, '
                    'acrylic, Styrofoam. Kerf, bend handling and score spacing fill in to suit it.'),
                  t('<b>Levha ölçüsü</b>: kırtasiye ölçüleri (A4, A3, 350×500, 500×700, 700×1000) ve lazer tablası ölçüleri; '
                    '"Otomatik" en küçük uygun levhayı seçer.',
                    '<b>Sheet size</b>: shop sizes (A4, A3, 350×500, 500×700, 700×1000) and laser bed sizes; "Automatic" '
                    'picks the smallest that fits.'),
                  t('Sac metalin prototipini yapıyorsan malzeme kalınlığını sacınkiyle aynı seç ve "Kalınlığı değiştir"i açma: '
                    'maketin açınımı sacınkiyle aynı olur.',
                    'Prototyping a sheet metal part? Pick the same thickness as the metal and leave "Change thickness" off: '
                    'the model\'s flat pattern is then the metal one.'),
                  t('OK. Kesim dosyasında kesim ve çizik çizgileri birlikte gelir.', 'OK. The cut file holds the cut and score lines together.')]),
          table([[t('Büküm', 'Bends'), t('Ne çizer', 'What it draws'), t('Nerede', 'For')],
                 [t('Çizik', 'Score'), t('Büküm şeridini paralel çiziklerle doldurur (yuvarlak büküm); dar bükümde ortaya tek '
                                         'çizik. Çizikler arası en az iki kerf, parçanın dışına taşmaz.',
                                         'Fills the bend strip with parallel score lines (round bend); a sharp bend gets one '
                                         'line in the middle. At least two kerfs apart, never past the part\'s edge.'),
                  t('Mukavva, kağıt, PP, oluklu, kapa, balsa', 'Greyboard, paper, PP, corrugated, foam board, balsa')],
                 [t('Esnek menteşe', 'Living hinge'), t('Şaşırtmalı kısa yarıklar (15 mm yarık, 3 mm köprü); ahşap kıvrılır, '
                                                       'parça kopmaz.',
                                                       'Staggered short slits (15 mm slit, 3 mm bridge); the wood flexes and '
                                                       'never falls apart.'), t('Kontrplak, MDF', 'Plywood, MDF')],
                 [t('Isıyla bük', 'Heat bend'), t('Isıtılacak şeridin başına ve sonuna işaret; kesmez.',
                                                 'Marks where the heated strip starts and ends; no cut.'), t('Pleksi', 'Acrylic')],
                 [t('Büküm çizme', 'No bend lines'), t('Hiçbir şey.', 'Nothing.'), t('Strafor (lazer önerilmez)', 'Styrofoam (no laser)')]],
                [28 * mm, W - 28 * mm - 48 * mm, 48 * mm]),
          Spacer(1, 6),
          Table([[picture(t('model_cut_tr.png', 'model_cut_en.png'), 68 * mm,
                          t('Mukavva kesim dosyası: siyah = kesim, mavi = çizik.', 'Greyboard cut file: black = cut, blue = score.'),
                          crop=(0.0, 0.0, 0.72, 0.43), keep=False),
                  picture('living_hinge.png', 92 * mm, t('Kontrplak: kırmızı = esnek menteşe yarıkları.',
                                                         'Plywood: red = living-hinge slits.'), keep=False)]],
                colWidths=[74 * mm, W - 74 * mm], style=[('VALIGN', (0, 0), (-1, -1), 'TOP')])]
    s += [PageBreak(), p(t('Lazer programında hangi renge ne verilir?', 'Which colour gets what in the laser software?'), H2),
          p(t('Lazer programları (LightBurn, RDWorks vb.) çizgileri <b>renge göre</b> ayırır. Her renge ayrı güç ve hız ver.',
              'Laser software (LightBurn, RDWorks and so on) separates lines <b>by colour</b>. Give each colour its own '
              'power and speed.')),
          table([[t('Çizgi', 'Line'), t('Renk', 'Colour'), t('Lazerde', 'On the laser')],
                 [t('Dış kesim, iç kesim (delik)', 'Outer cut, inner cut (hole)'), t('Siyah / beyaz', 'Black / white'),
                  t('<b>Kes</b> (tam güç).', '<b>Cut</b> (full power).')],
                 [t('Esnek menteşe yarığı', 'Living-hinge slit'), t('Kırmızı', 'Red'), t('<b>Kes</b>.', '<b>Cut</b>.')],
                 [t('Çizik', 'Score'), t('Mavi', 'Blue'),
                  t('<b>Düşük güç, yüksek hız</b>: yüzeyin yarısına kadar, arkadan görünmesin. Kesim gücü verirsen parça büküm '
                    'yerinden kopar. Önce artık parçada dene.',
                    '<b>Low power, high speed</b>: halfway into the material, not visible from the back. At cutting power the '
                    'part falls apart at the bend. Test on scrap first.')],
                 [t('Isıyla büküm işareti', 'Heat-bend mark'), t('Yeşil', 'Green'),
                  t('Çok düşük güç (hafif iz) ya da hiç kesme.', 'Very low power (a light mark) or skip it.')],
                 [t('Büküm çizgisi (sac metal)', 'Bend line (sheet metal)'), t('Kırmızı', 'Red'),
                  t('<b>Kesilmez</b>; abkant için bilgi. Kesim dosyasında yok.', '<b>Not cut</b>; for the press brake. Not in the cut file.')]],
                [48 * mm, 26 * mm, W - 74 * mm]),
          p(t('<b>Kerf:</b> lazerin yaktığı genişlik. Çoğu lazer programı bunu kendisi düzeltir (LightBurn: katman başına '
              '"Kerf offset", varsayılanı 0). Bu yüzden eklenti çizgileri gerçek ölçüde bırakır. Programında böyle bir ayar '
              'yoksa "Dış çizgiye / Deliklere yarım kerf ekle" tiklerini aç.',
              '<b>Kerf:</b> the width the beam burns. Most laser software compensates it (LightBurn: "Kerf offset" per layer, '
              'default 0). So the add-in leaves lines at true size. If your software has no such setting, turn on '
              '"Add half kerf to outer lines / holes".'), NOTE),
          p(t('Katman adları: OUTER_PROFILES / INTERIOR_PROFILES (kesim), BEND / BEND_EXTENT (büküm), CIZIK (çizik), '
              'MENTESE (menteşe), ISARET (işaret).',
              'Layer names: OUTER_PROFILES / INTERIOR_PROFILES (cut), BEND / BEND_EXTENT (bend), CIZIK (score), '
              'MENTESE (living hinge), ISARET (heat-bend mark).'), SMALL)]
    s += [p(t('Çıktı dosyaları', 'Output files'), H2),
          table([[t('Dosya', 'File'), t('Ne', 'What')],
                 [t('00_KESIM_….dxf', '00_CUT_….dxf'), t('<b>Lazere giden dosya.</b> Yalnız kesim ve çizik çizgileri.',
                                                         '<b>The file for the laser.</b> Cut and score lines only.')],
                 ['00_NESTING_….dxf', t('Dizilim, büküm çizgileri ve levha çerçevesiyle.', 'The layout with bend lines and the sheet frame.')],
                 [t('00_NESTING_….png, 00_KESIM_….png', '00_NESTING_….png, 00_CUT_….png'),
                  t('Resimler: parça adları, sağ altta başlık bloğu. "_yakin": parçalar küçük bir köşedeyse o köşe, büyük.',
                    'Pictures: part names, title block at the bottom right. "_yakin": a close-up when the parts take a small corner.')],
                 [t('00_MALIYET_….csv', '00_COST_….csv'), t('Parça parça maliyet; Excel açar.', 'Cost part by part; opens in Excel.')],
                 [t('01_….dxf, 02_….dxf …', '01_….dxf, 02_….dxf …'), t('Her parça ayrı.', 'Each part on its own.')],
                 ['_parcalar.json, _log.txt', t('Parça listesi ve çalışma kaydı. Sorun olursa _log.txt\'yi ekle.',
                                                'Part list and run log. Attach _log.txt when reporting a problem.')]],
                [52 * mm, W - 52 * mm])]
    s += [PageBreak(), p(t('Fire ve maliyeti okumak', 'Reading scrap and cost'), H2),
          picture(t('model_title_tr.png', 'model_title_en.png'), 105 * mm,
                  t('Başlık bloğu (mukavva, otomatik A3, fiyat girilmiş örnek).', 'Title block (greyboard, automatic A3, priced).'),
                  crop=(0.2, 0.43, 1.0, 1.0)),
          table([[t('Satır', 'Row'), t('Anlamı', 'Meaning')],
                 [t('Doluluk', 'Fill'), t('Parçaların net alanı / levhanın tamamı.', 'The parts\' net area / the whole sheet.')],
                 [t('Fire (levha)', 'Scrap (sheet)'), t('Levhanın tamamına göre boşta kalan; parçalar bir köşedeyse yüksek görünür.',
                                                       'Unused part of the whole sheet; high when the parts take a corner.')],
                 [t('Fire (parça bölgesi)', 'Scrap (parts area)'),
                  t('Parçaların kapladığı dikdörtgenin içinde boşa giden. <b>Asıl bakılacak oran.</b>',
                    'Waste inside the rectangle the parts take. <b>The figure to watch.</b>')],
                 [t('Kalan levha', 'Sheet left over'), t('O dikdörtgenin dışında kalan, kullanılabilir kısım.', 'What is left outside it, reusable.')],
                 [t('Levha / parça payı / fire', 'Sheet / parts share / scrap'),
                  t('Levhanın fiyatı; parçaların alanına düşen kısmı; bölgedeki firenin fiyatı.',
                    'The sheet\'s price; the share of the parts\' area; the price of the scrap in the parts area.')],
                 [t('Lazer', 'Laser'), t('Kesim ücreti, çizgi uzunluğu, giriş sayısı, dakikayla çalışıyorsan süre.',
                                       'Laser charge, line length, pierces, and time when priced per minute.')],
                 [t('İş toplamı', 'Job total'), t('Levhanın tamamıyla; parantezde yalnız parçaların payıyla.',
                                                'With whole sheets; in brackets with the parts\' share only.')]],
                [44 * mm, W - 44 * mm]),
          p(t('Fiyat girmek', 'Entering prices'), H3),
          *bullets([t('Kalınlık bölmesinde <b>Fiyat hesapla</b>\'yı aç. Fiyat girilmezse maliyet hesaplanmaz.',
                      'Turn on <b>Calculate cost</b> in the thickness section. No prices, no cost.'),
                    t('<b>Fiyat birimi</b>: sac metalde kg veya m²; makette m². Levhayı listeden seçtiysen levha başına da olur.',
                      '<b>Price unit</b>: per kg or per m² for metal; per m² for model making. Per sheet too when you pick the sheet.'),
                    t('<b>Lazer ücreti</b>: "Metre + giriş" (sac atölyeleri) ya da "Dakika" (maket atölyeleri; hızlar tahminidir).',
                      '<b>Laser charge</b>: "Metres + pierces" (metal shops) or "Minutes" (model workshops; speeds are rough guesses).'),
                    t('Sac metalde büküm (abkant) ücreti ve her işte hazırlık ücreti.', 'Bending (press brake) for metal and a set-up fee per job.'),
                    t('Fiyatlar malzeme + kalınlık için hatırlanır. Hiçbir fiyat önceden yazılı gelmez.',
                      'Prices are remembered per material + thickness. None are filled in for you.')])]
    s += [PageBreak(), p(t('Sorun çıkarsa', 'Troubleshooting'), H2),
          table([[t('Ne oldu', 'What happened'), t('Ne yap', 'What to do')],
                 [t('Buton yok', 'No button'), t('UTILITIES &gt; ADD-INS &gt; Scripts and Add-Ins &gt; Add-Ins: SacAcinimDXF, Run; '
                                                 '"Run on Startup" işaretli olsun.',
                                                 'UTILITIES &gt; ADD-INS &gt; Scripts and Add-Ins &gt; Add-Ins: SacAcinimDXF, Run; '
                                                 'tick "Run on Startup".')],
                 [t('"Görünür sheet metal gövde bulunamadı"', '"No visible sheet metal bodies found"'),
                  t('Gövdeler sheet metal değil ya da gizli.', 'The bodies are not sheet metal, or hidden.')],
                 [t('"EKSİK AÇINIM"', '"INCOMPLETE FLAT PATTERN"'),
                  t('Fusion o parçanın açınımını tam çıkaramadı; parçayı ve DXF ölçüsünü kontrol et.',
                    'Fusion could not fully flatten that part; check the part and the DXF\'s size.')],
                 [t('"ATLANDI ... Flat Pattern"', '"SKIPPED ... Flat Pattern"'),
                  t('Browser\'da o component\'in Flat Pattern\'ını sil, tekrar çalıştır.', 'Delete that component\'s Flat Pattern in the Browser, run again.')],
                 [t('"KALINLIK DEĞİŞMEDİ"', '"THICKNESS NOT CHANGED"'),
                  t('Fusion modeli yeni kalınlıkla kuramadı; o parçalar model kalınlığıyla ayrı dosyaya çıkar.',
                    'Fusion could not rebuild the model at the new thickness; those parts come out at the model\'s thickness, in a separate file.')],
                 [t('Dizme çok uzun', 'Nesting takes too long'), t('Kalite: Hızlı, ya da İptal.', 'Quality: Fast, or Cancel.')],
                 [t('"Python bulunamadı"', '"No Python with ezdxf found"'), t('Kurulum dosyasını tekrar çalıştır.', 'Run the installer again.')],
                 [t('Başka bir hata', 'Anything else'), t('GitHub\'da issue aç: ekran görüntüsü + _log.txt.',
                                                        'Open an issue on GitHub with a screenshot and _log.txt.')]],
                [52 * mm, W - 52 * mm])]
    s += [p(t('Bilinen sınırlar ve sorumluluk', 'Known limits and responsibility'), H2),
          *bullets([t('Intel Mac\'lerde gerçek şekil dizimi yok; parçalar dikdörtgen dizilir.', 'Intel Macs: no true-shape nesting; parts are nested as rectangles.'),
                    t('Windows kurulumu henüz gerçek bir Windows\'ta denenmedi.', 'The Windows installer has not been tested on a real Windows PC yet.'),
                    t('"Kenarları birleştir" yalnız tam üst üste gelen düz kenarları birleştirir; genelde az kenar birleşir.',
                      '"Merge edges" only merges straight edges that lie exactly on top of each other; usually few do.'),
                    t('Karton sacla aynı bükülmez: maket ölçüsü büküm başına tahminen yarım milimetre şaşabilir (ölçülmedi).',
                      'Card does not bend like metal: a model can be off by roughly half a millimetre per bend (an estimate, not measured).'),
                    t('PVC / foreks lazerde kesilmez (zehirli klor gazı).', 'Never laser-cut PVC / Forex (toxic chlorine gas).')]),
          p(t('Bu yazılım MIT Lisansı ile "olduğu gibi", hiçbir garanti olmadan sunulur. Hatalar olabilir. Kesmeden önce '
              'her DXF\'in ölçüsünü kontrol et; kestiğin şeyden, malzemeden ve lazeri güvenli kullanmaktan sen sorumlusun.',
              'This software is provided "as is" under the MIT License, without warranty of any kind. It may contain bugs. '
              'Check every DXF\'s dimensions before cutting; you are responsible for what you cut, the material and using '
              'your laser safely.'), NOTE),
          p(t('Autodesk ve Fusion, Autodesk, Inc.\'in ABD\'de ve diğer ülkelerde tescilli markaları ya da markalarıdır. Bu bağımsız '
              'bir projedir; Autodesk, Inc. ile bağlantılı değildir, onun tarafından desteklenmez ya da onaylanmaz.',
              'Autodesk and Fusion are registered trademarks or trademarks of Autodesk, Inc., in the USA and other countries. '
              'This is an independent project, not affiliated with, sponsored or endorsed by Autodesk, Inc.'), SMALL),
          Spacer(1, 4), p(datetime.date.today().strftime('%d.%m.%Y'), SMALL)]
    return s


for LANG, name in (('en', 'USER_GUIDE.pdf'), ('tr', 'KULLANIM.pdf')):
    out = os.path.join(ROOT, 'docs', name)
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=t('Autodesk Fusion için Sac Açınım / Nesting — kullanım kılavuzu', 'Sheet Metal Nesting for Autodesk Fusion — user guide'),
                            author='barisegemenbas')
    doc.build(story(), onFirstPage=footer, onLaterPages=footer)
    print('written', out)
for f in os.listdir(PICS):
    if f.startswith('_crop_'): os.remove(os.path.join(PICS, f))
