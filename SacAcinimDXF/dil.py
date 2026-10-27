# Interface language. The code is written with Turkish text; L() gives the English text when LANG is 'en'
# (anything missing stays Turkish). Dropdown items keep their Turkish name inside the code: they are shown with
# L() and read back with back(). To add a language, add a dictionary like EN and pick it in L().
LANG = 'tr'


def L(text):
    return EN.get(text, text) if LANG == 'en' else text


def back(shown):
    # the Turkish name of a translated dropdown item
    return _REV.get(shown, shown) if LANG == 'en' else shown


def pct(v, fmt='%.1f'):
    # %12,5 in Turkish (sign first), 12.5% in English
    return fmt % v + '%' if LANG == 'en' else '%' + (fmt % v).replace('.', ',')


def num(v, fmt='%g'):
    # 1,5 in Turkish, 1.5 in English
    s = fmt % v
    return s if LANG == 'en' else s.replace('.', ',')


EN = {
    # add-in, dialog
    'Sac Açınım DXF': 'Sheet Metal Nesting',
    'Görünür tüm sheet metal gövdeleri flat pattern yapıp DXF + nesting çıkarır.':
        'Flattens every visible sheet metal body and writes DXFs plus a nested layout.',
    'SacAcinimDXF yüklenemedi:\n': 'SacAcinimDXF could not load:\n',
    'Hata:\n': 'Error:\n',
    'Dil / Language': 'Dil / Language',
    'Dil değişikliği pencere kapatılıp yeniden açılınca uygulanır.':
        'The new language applies when you close and reopen this dialog.',
    'Ne için?': 'Made for',
    'Sac metal (lazer / abkant)': 'Sheet metal (laser / press brake)',
    'Maket (lazer: karton, pleksi, ahşap…)': 'Model making (laser: card, acrylic, wood…)',
    'Sac metal: kesim + büküm çizgileri. Maket: karton, pleksi, ahşap için çizik / menteşe / işaret çizgileri.':
        'Sheet metal: cut and bend lines. Model making: score / living-hinge / mark lines for card, acrylic, wood.',
    'Görünür sheet metal gövde bulunamadı.': 'No visible sheet metal bodies found.',
    '%d. %s — %d parça%s': '%d. %s — %d parts%s',
    ' (%d adet)': ' (%d pcs)',
    'kalınlık ölçülemedi': 'thickness unknown',
    'Dahil et': 'Include',
    'Kapalıysa bu kalınlıktaki parçalar çıkarılmaz.': 'Off: parts of this thickness are left out.',
    'Malzeme': 'Material',
    'Malzeme seçince ölçü, kalınlık ve (makette) kerf, büküm, çizik aralığı kendiliğinden dolar.':
        'Picking a material fills in sizes, thicknesses and (model making) kerf, bend handling and score spacing.',
    'Sac ölçüsü': 'Sheet size',
    'Standart levha ya da "Özel ölçü" ile elle.': 'A standard sheet, or type your own with "Custom size".',
    '   En': '   Width',
    '   Boy': '   Height',
    'Kalınlığı değiştir': 'Change thickness',
    'Kapalı: modeldeki kalınlık. Açık: açınım seçilen kalınlıkla yeniden hesaplanır (asıl tasarım değişmez).':
        'Off: the model\'s thickness. On: the flat pattern is recomputed at the chosen thickness (your design is not changed).',
    'Kalınlık': 'Thickness',
    '   Kalınlık (mm)': '   Thickness (mm)',
    'Kerf': 'Kerf',
    'Lazerin yaktığı genişlik. Çizik aralığı bunun en az 2 katı olur; kerf tikleri açıksa çizgilere yarısı eklenir.':
        'The width the beam burns. Score spacing is at least twice this; with the kerf ticks on, half of it is added to the lines.',
    'Büküm': 'Bends',
    'Çizik: büküm şeridini paralel çiziklerle doldurur. Menteşe: ahşapta kesik yarıklar. Isıyla: pleksi için yalnız işaret. Geniş bükümde şerit dolar, dar bükümde ortaya tek çizgi.':
        'Score: fills the bend strip with parallel score lines. Hinge: slits for wood. Heat: marks only, for acrylic. '
        'A wide bend gets its strip filled, a sharp one a single line in the middle.',
    'Çizik aralığı': 'Score spacing',
    'İki çizik (ahşapta iki menteşe sırası) arası. Büküm sertse küçült, kırılgansa büyüt.':
        'Distance between two score lines (hinge rows for wood). Bend too stiff: smaller; too weak: larger.',
    'Fiyat hesapla': 'Calculate cost',
    'Levha fiyatı ve lazer ücretiyle maliyet çıkarır. Girdiğin fiyatlar bu malzeme ve kalınlık için hatırlanır.':
        'Works out the cost from the sheet price and laser charges. Prices you type are remembered for this material and thickness.',
    '   Fiyat birimi': '   Price unit',
    'TL/kg: sacın kilo fiyatı (levhanın ağırlığı en × boy × kalınlık × yoğunluktan). TL/m²: malzemenin metrekare fiyatı; levha ölçüsü ne olursa olsun alanıyla hesaplanır. TL/levha: seçtiğin levhanın tanesinin fiyatı (Otomatik ölçüde yok).':
        'per kg: the sheet\'s price per kilo (weight from width × height × thickness × density). per m²: the material\'s '
        'price per square metre, any sheet size by its area. per sheet: the price of one chosen sheet (not with Automatic size).',
    '   Fiyat (TL)': '   Price',
    '   Lazer ücreti': '   Laser charge',
    'Sac atölyeleri genelde kesilen metre + giriş sayısıyla, maket atölyeleri makine dakikasıyla ücretlendirir.':
        'Metal shops usually charge per metre cut plus per pierce; model-making workshops per machine minute.',
    'Dizme': 'Nesting',
    'Yöntem': 'Method',
    'Gerçek şekil: parçaların kendi şekliyle, en az fire. Dikdörtgen: çevreleyen kutularla, anında.':
        'True shape: by the parts\' own outlines, least scrap. Rectangle: by their bounding boxes, instant.',
    'Dizilim': 'Layout',
    'En az fire: en küçük alan. Kompakt kare: sol altta kareye yakın. Şerit: sol kenar boyunca.':
        'Least scrap: smallest area. Compact square: near-square at the bottom left. Strip: along the left edge.',
    'Döndürme': 'Rotation',
    'Otomatik: her parçayı en verimli açıyla döndürür.': 'Automatic: turns every part to its most efficient angle.',
    'Kalite': 'Quality',
    'Uzun sürdükçe daha sıkı dizer.': 'The longer it runs, the tighter it packs.',
    'Küçük parçaları deliklere yerleştir': 'Put small parts into holes',
    'Büyük parçaların içindeki deliklere sığan küçük parçaları koyar.': 'Places small parts inside holes of larger ones.',
    'Boşluk ve kerf': 'Spacing and kerf',
    'Boşluk = sac kalınlığı (en az 3 mm)': 'Gap = sheet thickness (at least 3 mm)',
    'Her kalınlık kendi boşluğunu alır. Kapatınca elle girilir.': 'Each thickness gets its own gap. Turn off to type one.',
    'Parça arası boşluk': 'Gap between parts',
    'Sac kenar payı': 'Sheet edge margin',
    'Parçalarla sacın kenarı arası.': 'Between the parts and the sheet edge.',
    'Kerf (kesim genişliği)': 'Kerf (cut width)',
    'Parça arası boşluğa eklenir; DXF ölçüleri değişmez (kerfi kesim programı düzeltir).':
        'Added to the gap between parts; DXF sizes stay as drawn (the cutting software compensates the kerf).',
    'Ortak kesime hazırla (parça arası = kerf)': 'Prepare for common-line cutting (gap = kerf)',
    'Parçalar kerf kadar yakın dizilir; ortak kenarı kesim programı tek seferde keser.':
        'Parts are nested one kerf apart; the cutting software cuts the shared edge once.',
    'Kenarları birleştir (ortak kenar tek kesim)': 'Merge edges (shared edge cut once)',
    'Parçalar boşluksuz dizilir, üst üste gelen düz kenarlar tek çizgiye iner.':
        'Parts are nested with no gap; straight edges that lie on top of each other become one line.',
    'Dış çizgiye yarım kerf ekle': 'Add half kerf to outer lines',
    'Deliklere yarım kerf ekle': 'Add half kerf to holes',
    'Lazer programın kerfi düzeltiyorsa kapalı bırak.': 'Leave off if your laser software compensates the kerf.',
    'Çıktılar': 'Outputs',
    'Çizgi görünümü': 'Line look',
    'Kapalıysa bu çizgiler çıktıya girmez.': 'Off: these lines are left out of the output.',
    '   rengi': '   colour',
    '   çizgisi': '   line type',
    'Sac Açınım DXF  sürüm %s': 'Sheet Metal Nesting  version %s',
    'En az bir çıktı seçilmeli (Çıktılar bölmesi).': 'Pick at least one output (Outputs section).',
    'En az bir kalınlık dahil edilmeli.': 'Include at least one thickness.',
    # outputs
    'Parça başına DXF': 'DXF per part',
    'Her parça kendi DXF dosyasında.': 'Each part in its own DXF file.',
    'Nesting DXF': 'Nesting DXF',
    'Bütün parçalar sacın üstünde dizili, büküm çizgileriyle.': 'All parts nested on the sheet, with bend lines.',
    'Kesim DXF': 'Cut DXF',
    'Aynı dizilim, yalnız lazerin çizgileri (kesim, çizik): makineye giden dosya.':
        'The same layout with the laser\'s lines only (cut, score): the file for the machine.',
    'Nesting resmi (PNG)': 'Nesting picture (PNG)',
    'Dizilimin resmi, parça adları ve başlık bloğuyla.': 'A picture of the layout with part names and a title block.',
    'Kesim resmi (PNG)': 'Cut picture (PNG)',
    "Kesim DXF'inin resmi.": 'A picture of the cut DXF.',
    'Yakın resim': 'Close-up picture',
    'Parçalar sacın küçük bir köşesindeyse o köşenin büyük resmi.': 'When the parts take a small corner of the sheet: that corner, larger.',
    'Maliyet tablosu (CSV)': 'Cost table (CSV)',
    'Fiyat girildiyse parça parça maliyet; Excel açar.': 'Cost part by part when prices are given; opens in Excel.',
    'Çizgi açıklaması (DXF)': 'Line legend (DXF)',
    "Hangi renk çizginin ne olduğu, DXF'te parçaların dışına yazılır.": 'What each line colour means, written in the DXF clear of the parts.',
    'Parça listesi (_parcalar.json)': 'Part list (_parcalar.json)',
    'Parçaların ölçüleri, kalınlıkları ve bükümleri.': 'The parts\' sizes, thicknesses and bends.',
    # dropdown items
    'Gerçek şekil (sac tasarrufu)': 'True shape (saves material)',
    'Dikdörtgen (hızlı)': 'Rectangle (fast)',
    'En az fire (en küçük alan)': 'Least scrap (smallest area)',
    'Kompakt kare (sol alt)': 'Compact square (bottom left)',
    'Şerit (sol kenar)': 'Strip (left edge)',
    'Otomatik (en verimli)': 'Automatic (most efficient)',
    '90° (4 yön)': '90° (4 ways)',
    '45° (8 yön)': '45° (8 ways)',
    'Dengeli (~1-3 dk)': 'Balanced (~1-3 min)',
    'Hızlı (~30 sn)': 'Fast (~30 s)',
    'En iyi (~10 dk, ana ürün)': 'Best (~10 min, final job)',
    'Çizik (bükümü doldurur)': 'Score (fills the bend)',
    'Esnek menteşe (kesik yarıklar)': 'Living hinge (cut slits)',
    'Isıyla bük (yalnız işaret)': 'Heat bend (marks only)',
    'Büküm çizme': 'No bend lines',
    'Metre + giriş (sac atölyesi)': 'Metres + pierces (metal shop)',
    'Dakika (maket atölyesi)': 'Minutes (model workshop)',
    'Kesim (TL/m)': 'Cutting (per m)',
    'Kesilen her metre çizgi için.': 'For every metre of line cut.',
    'Giriş (TL/adet)': 'Pierce (each)',
    'Lazerin her kesime başlayışı (her kontur, her delik) için.': 'Each time the laser starts a cut (every outline, every hole).',
    'Makine (TL/dk)': 'Machine (per min)',
    'Atölyenin dakika ücreti.': 'The workshop\'s charge per minute.',
    'Kesim hızı (mm/sn)': 'Cutting speed (mm/s)',
    'Çizik hızı (mm/sn)': 'Scoring speed (mm/s)',
    'Tahmini başlangıç değeri; atölyenin makinesine göre düzelt.': 'A rough starting value; set it to the workshop\'s machine.',
    'Büküm (TL/büküm)': 'Bending (per bend)',
    'Abkant: her büküm için.': 'Press brake: for every bend.',
    'Hazırlık (TL/iş)': 'Set-up (per job)',
    'İş başına bir kez: hazırlık, en düşük ücret vb.': 'Once per job: set-up, minimum charge and so on.',
    'TL/kg': 'per kg', 'TL/m²': 'per m²', 'TL/levha': 'per sheet',
    'Otomatik (tek levhaya sığan en küçük)': 'Automatic (smallest single sheet that fits)',
    'Özel ölçü (elle gir)': 'Custom size (type it)',
    'Özel kalınlık (elle gir)': 'Custom thickness (type it)',
    'Dış kesim': 'Outer cut', 'İç kesim (delik)': 'Inner cut (hole)', 'Büküm çizgisi': 'Bend line',
    'Büküm sınırı': 'Bend extent', 'Çizik (düşük güç, kesmez)': 'Score (low power, no cut)',
    'Esnek menteşe yarığı (kesim)': 'Living-hinge slit (cut)', 'Isıyla büküm işareti (kesmez)': 'Heat-bend mark (no cut)',
    'Kırmızı': 'Red', 'Sarı': 'Yellow', 'Yeşil': 'Green', 'Camgöbeği': 'Cyan', 'Mavi': 'Blue', 'Mor': 'Magenta',
    'Beyaz/Siyah': 'White/Black', 'Gri': 'Grey', 'Turuncu': 'Orange',
    'Düz': 'Continuous', 'Kesikli': 'Dashed', 'Kesik-nokta': 'Dash-dot', 'Eksen': 'Centre',
    # materials
    'DKP (soğuk hadde)': 'Cold-rolled steel (DKP)', 'HRP / Siyah sac (sıcak hadde)': 'Hot-rolled steel (HRP)',
    'Galvaniz': 'Galvanised steel', 'Paslanmaz': 'Stainless steel', 'Alüminyum': 'Aluminium',
    'Diğer (tüm ölçüler)': 'Other (all sizes)',
    'Mukavva (gri maket kartonu)': 'Greyboard (model card)', 'Kağıt / Bristol': 'Paper / Bristol board',
    'PP levha (polipropilen)': 'PP sheet (polypropylene)', 'Oluklu karton': 'Corrugated board',
    'Kapa / köpük maket kartonu (içi köpük, dışı parlak)': 'Foam board (foam core, glossy faces)',
    'Balsa': 'Balsa', 'Kontrplak / MDF': 'Plywood / MDF', 'Pleksi (akrilik)': 'Acrylic (Plexiglas)',
    'Strafor (EPS/XPS)': 'Styrofoam (EPS/XPS)', 'Diğer maket malzemesi': 'Other model material',
    'Köpük erir: çizik gücünü önce artık parçada dene': 'The foam melts: test the score power on scrap first',
    'Strafor lazerde erir ve tutuşabilir; sıcak telle kesin': 'Styrofoam melts and can catch fire under a laser; cut it with a hot wire',
    # run (sac_core)
    'Aktif bir tasarım yok.': 'No active design.',
    'Dahil edilen kalınlıkta parça yok.': 'No parts in the included thicknesses.',
    'Sac_Acinim_DXF': 'SheetMetal_Nesting_DXF',
    '\nSistem Python bulunamadı (ezdxf gerekli): DXF yazılamadı/dizilemedi.':
        '\nNo Python with ezdxf found: DXFs were not written or nested. Run the installer again.',
    'İptal (hızlı dikdörtgen dizilim)': 'Cancel (fast rectangle nesting)',
    'DXF yazılıyor ve diziliyor...': 'Writing DXFs and nesting...',
    '%s dizim sürüyor: %d dk %02d sn': '%s nesting: %d min %02d s',
    'Gerçek şekil': 'True shape', 'Dikdörtgen': 'Rectangle',
    'Dikdörtgen dizim...': 'Rectangle nesting...',
    'Gerçek şekil iptal edildi, dikdörtgen yöntem kullanıldı.\n': 'True-shape nesting cancelled; rectangle nesting used.\n',
    '\nDXF/nesting hatası, _log.txt dosyasına bak.': '\nDXF / nesting error, see _log.txt.',
    '\n\nEKSİK AÇINIM, kontrol et: ': '\n\nINCOMPLETE FLAT PATTERN, check: ',
    '\n\nATLANDI (componentte önceden kalmış Flat Pattern silinemedi): %s\nBrowser → Flat Pattern → sağ tık → Delete, sonra tekrar çalıştırın.':
        '\n\nSKIPPED (an old Flat Pattern in the component could not be removed): %s\n'
        'Browser → Flat Pattern → right-click → Delete, then run again.',
    '\n\nKALINLIK DEĞİŞMEDİ: Fusion modeli yeni kalınlıkla yeniden oluşturamadı (ayrıntı _log.txt). Bu parçalar modeldeki kalınlıkla açıldı, ayrı dosyada: ':
        '\n\nTHICKNESS NOT CHANGED: Fusion could not rebuild the model at the new thickness (see _log.txt). '
        'These parts were flattened at the model\'s thickness, in a separate file: ',
    '\n\nKalınlık için kopyalarda bastırılan adımlar (ilgili parçayı etkilemeyen Combine): ':
        '\n\nSteps suppressed in the copies for the thickness change (Combines not affecting the part): ',
    '. Asıl tasarım değişmedi.': '. Your design was not changed.',
    '\n\nDahil edilmeyen: %d parça': '\n\nLeft out: %d parts',
    '%d parça DXF olarak aktarıldı%s.%s%s\n\nKlasör:\n%s\n\nSac Açınım DXF sürüm %s':
        '%d parts written as DXF%s.%s%s\n\nFolder:\n%s\n\nSheet Metal Nesting version %s',
    ', %d hata (%s)': ', %d failed (%s)',
    '_KALINLIK_DEGISMEDI': '_THICKNESS_UNCHANGED',
    # nesting (nest_dxf)
    'AÇIKLAMA': 'LEGEND',
    '00_KESIM_': '00_CUT_', '00_MALIYET_': '00_COST_',
    '90° adım': '90° steps', '%s° adım': '%s° steps', ' serbest açı': ' free angle',
    'SAC AÇINIM — NESTING': 'SHEET METAL — NESTING', 'MAKET — NESTING': 'MODEL — NESTING',
    'KESİM HATLARI': 'CUT LINES', 'KESİM + ÇİZİK': 'CUT + SCORE',
    'Belge': 'Document', 'Sac': 'Sheet', 'Levha ölçüsü': 'Sheet size', 'Sac no': 'Sheet no.', 'Levha no': 'Sheet no.',
    'Parça': 'Parts', '%d adet, %.3f m²': '%d pcs, %.3f m²', 'Doluluk': 'Fill', 'Fire (levha)': 'Scrap (sheet)',
    'Fire (parça bölgesi)': 'Scrap (parts area)', 'Kalan levha': 'Sheet left over', 'Parça arası': 'Part spacing',
    'birleşik kenar, %.0f mm tek kesim': 'merged edges, %.0f mm cut once', '%g mm, yarısı eklendi: %s': '%g mm, half added to: %s',
    'dış çizgi': 'outer lines', 'delikler': 'holes', 'yok (lazer programı)': 'none (laser software)',
    ', aralık %g mm': ', spacing %g mm', 'kerf kadar (ortak kesim)': 'one kerf (common-line)', '%g mm + kerf': '%g mm + kerf',
    'Kenar payı': 'Edge margin', 'Tarih': 'Date', 'Levha': 'Sheet', '  parça payı / fire': '  parts share / scrap',
    'Lazer': 'Laser', '%.2f TL  (%.2f m, %d giriş%s)': '%.2f  (%.2f m, %d pierces%s)', ', %.1f dk': ', %.1f min',
    'İş toplamı': 'Job total', '%.2f TL  (parça payıyla %.2f)': '%.2f  (parts share only %.2f)',
    '%.2f TL (%s)': '%.2f (%s)', '%.2f / %.2f TL': '%.2f / %.2f', '%.2f TL': '%.2f', 'UYARI': 'WARNING',
    '%g × %g (otomatik, %d aday denendi)': '%g × %g (automatic, %d tried)',
    'Otomatik': 'Automatic', 'Hızlı': 'Fast', 'Dengeli': 'Balanced', 'En iyi': 'Best', 'Kompakt kare': 'Compact square', 'En az fire': 'Least scrap',
    'Kompakt dikdörtgen': 'Compact rectangle', 'Şerit': 'Strip',
    'Çizik': 'Score', 'Esnek menteşe': 'Living hinge', 'Isıyla (işaret)': 'Heat (marks)', 'Çizilmedi': 'Not drawn',
    'Parça;Adet;Alan (m²);Malzeme payı (TL);Kesim (m);Çizik (m);Giriş;Lazer (TL);Büküm adedi;Büküm (TL);Bir adet (TL);Toplam (TL)':
        'Part;Qty;Area (m²);Material share;Cut (m);Score (m);Pierces;Laser;Bends;Bending;One piece;Total',
    'Levhaların tamamı (TL);': 'Whole sheets;', 'Parçaların levha payı (TL);': 'Parts\' share of the sheets;',
    'Lazer (TL);': 'Laser;', 'Büküm (TL);': 'Bending;', 'Hazırlık (TL);': 'Set-up;',
    'TOPLAM, levhaların tamamıyla (TL);': 'TOTAL, with whole sheets;',
    'TOPLAM, yalnız parçaların payıyla (TL);': 'TOTAL, parts share only;',
    # result summary lines (nest_dxf -> message)
    'Otomatik levha: %g × %g (%d aday denendi)': 'Automatic sheet: %g × %g (%d tried)',
    '%d. levha: parçalar %.3f m², fire %%%.1f (parça bölgesi %.0f × %.0f mm içinde %%%.1f), kalan %%%.0f':
        'Sheet %d: parts %.3f m², scrap %.1f%% (parts area %.0f × %.0f mm: %.1f%%), %.0f%% left over',
    '%d parça %d levhaya dizildi (%s).': '%d parts nested on %d sheet(s) (%s).',
    'Levhaya sığmayan (levhadan büyük): %s': 'Too big for the sheet: %s',
    'Birleşen kenar: %.0f mm (tek kesim).': 'Merged edges: %.0f mm (cut once).',
    'Maliyet: %.2f (levhaların tamamıyla) / %.2f (yalnız parçaların payıyla)%s':
        'Cost: %.2f (whole sheets) / %.2f (parts share only)%s',
    ', hazırlık %.2f dahil': ', set-up %.2f included',
    'Fiyat girilmedi: maliyet hesaplanmadı.': 'No prices given: cost not calculated.',
    'Gerçek şekil dizim olmadı, dikdörtgen kullanıldı.': 'True-shape nesting failed; rectangle nesting used.',
    'Dosyalar: %s': 'Files: %s',
}
_REV = {v: k for k, v in EN.items()}
