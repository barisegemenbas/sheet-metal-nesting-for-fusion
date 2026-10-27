#!/bin/bash
# Sheet Metal Nesting for Autodesk Fusion — Mac installer. Double-click it; it does the rest.
# Copies the add-in into Fusion's add-ins folder, puts its own portable Python (python-build-standalone, no admin
# password needed) inside the add-in and installs the packages it needs there. Running it again updates the add-in
# and keeps the user's settings and prices.
set -u
cd "$(dirname "$0")" || exit 1
SRC="$PWD/SacAcinimDXF"
FUSION="$HOME/Library/Application Support/Autodesk"
PARENT="${SAC_TARGET:-$FUSION/Autodesk Fusion 360/API/AddIns}"  # SAC_TARGET: another folder, for testing only
DEST="$PARENT/SacAcinimDXF"
PY_TAG=20261009
PY_VER=3.13.16
case "$(uname -m)" in arm64) ARCH=aarch64 ;; *) ARCH=x86_64 ;; esac
URL="https://github.com/astral-sh/python-build-standalone/releases/download/$PY_TAG/cpython-$PY_VER+$PY_TAG-$ARCH-apple-darwin-install_only.tar.gz"
PACKAGES="ezdxf ironnest spyrrow shapely matplotlib pillow"

# Turkish when the Mac is set to Turkish, English otherwise
case "$(defaults read -g AppleLocale 2>/dev/null)" in tr*) TR=1 ;; *) TR=0 ;; esac
say() { if [ "$TR" = 1 ]; then echo "$1"; else echo "$2"; fi; }
finish() { echo; if [ "$TR" = 1 ]; then read -r -p "Kapatmak için Enter'a bas..." _; else read -r -p "Press Enter to close..." _; fi; exit "$1"; }
fail() { echo; say "HATA: $1" "ERROR: $2"; say "Bu pencerenin ekran görüntüsünü al ve GitHub'da bir issue aç." \
    "Take a screenshot of this window and open an issue on GitHub."; finish 1; }

say "== Autodesk Fusion için Sac Açınım / Nesting kurulumu ==" "== Sheet Metal Nesting for Autodesk Fusion — setup =="
echo
[ -f "$SRC/SacAcinimDXF.py" ] || fail "SacAcinimDXF klasörü bulunamadı. Zip'i açıp bu dosyayı açılan klasörün içinden çalıştır." \
    "SacAcinimDXF folder not found. Unzip the download and run this file from the unzipped folder."
[ -d "$FUSION" ] || [ -n "${SAC_TARGET:-}" ] || fail "Autodesk Fusion bulunamadı. Önce Fusion'ı kurup bir kez açıp kapat." \
    "Autodesk Fusion not found. Install Fusion and open it once first."

say "1/3 Eklenti kopyalanıyor..." "1/3 Copying the add-in..."
mkdir -p "$DEST" || fail "Eklenti klasörü oluşturulamadı: $DEST" "Could not create the add-in folder: $DEST"
rsync -a --exclude '_python' --exclude '_*.json' --exclude '.DS_Store' "$SRC/" "$DEST/" || fail "Kopyalama başarısız." "Copying failed."

PY="$DEST/_python/bin/python3"
if [ -x "$PY" ] && "$PY" -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" 2>/dev/null; then
    say "2/3 Python zaten kurulu." "2/3 Python already installed."
else
    say "2/3 Python indiriliyor (yaklaşık 25 MB)..." "2/3 Downloading Python (about 25 MB)..."
    TMP="$(mktemp -d)" || fail "Geçici klasör açılamadı." "Could not create a temporary folder."
    curl -fL --progress-bar -o "$TMP/python.tar.gz" "$URL" || fail "Python indirilemedi. İnternet bağlantısını kontrol edip tekrar dene." \
        "Could not download Python. Check the internet connection and try again."
    rm -rf "$DEST/_python"
    mkdir -p "$DEST/_python"
    tar -xzf "$TMP/python.tar.gz" -C "$DEST/_python" --strip-components 1 || fail "İndirilen Python açılamadı." "Could not unpack Python."
    rm -rf "$TMP"
    [ -x "$PY" ] || fail "Python kurulamadı." "Python could not be installed."
fi

say "3/3 Paketler kuruluyor (birkaç dakika sürebilir)..." "3/3 Installing packages (may take a few minutes)..."
LOG="$DEST/_install.log"
date > "$LOG"
"$PY" -m pip install --upgrade --disable-pip-version-check pip >>"$LOG" 2>&1
MISSING=""
for p in $PACKAGES; do
    printf "    %-12s " "$p"
    # ready-built packages only: building from source needs compilers a normal Mac does not have
    if "$PY" -m pip install --disable-pip-version-check --only-binary :all: --upgrade "$p" >>"$LOG" 2>&1; then
        say "tamam" "ok"
    else
        say "KURULAMADI" "FAILED"; MISSING="$MISSING $p"
    fi
done
"$PY" -c "import ezdxf" 2>/dev/null || fail "ezdxf kurulamadı; eklenti DXF yazamaz. Ayrıntı: $LOG" "ezdxf failed; the add-in cannot write DXFs. Details: $LOG"

echo
say "KURULUM TAMAM." "SETUP COMPLETE."
if [ -n "$MISSING" ]; then
    echo
    say "Kurulamayan paketler:$MISSING" "Packages that failed:$MISSING"
    case "$MISSING" in *ironnest*) say " - ironnest yok: parçalar dikdörtgen olarak dizilir (Intel Mac'te beklenen)." \
        " - no ironnest: parts are nested as rectangles (expected on Intel Macs)." ;; esac
    case "$MISSING" in *spyrrow*) say " - spyrrow yok: dizim biraz daha az sıkı olur." " - no spyrrow: nesting is a little less tight." ;; esac
    case "$MISSING" in *shapely*) say " - shapely yok: maket modu çalışmaz." " - no shapely: model-making mode does not work." ;; esac
    case "$MISSING" in *matplotlib*|*pillow*) say " - matplotlib/pillow yok: PNG resimleri çıkmaz." " - no matplotlib/pillow: no PNG pictures." ;; esac
fi
echo
say "Fusion açıksa kapatıp yeniden aç. SHEET METAL sekmesinde 'Sac Açınım DXF' butonu çıkar." \
    "Restart Fusion if it is open. The 'Sheet Metal Nesting' button appears on the SHEET METAL tab."
finish 0
