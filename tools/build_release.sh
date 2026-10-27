#!/bin/bash
# Builds dist/fusion-sheet-metal-nesting-v<version>.zip: the add-in, both installers and the docs, ready to attach to
# a GitHub release. Run on a Mac from the repository: bash tools/build_release.sh
set -eu
cd "$(dirname "$0")/.."
VER=$(python3 -c "import json; print(json.load(open('SacAcinimDXF/SacAcinimDXF.manifest'))['version'])")
NAME="fusion-sheet-metal-nesting-v$VER"
STAGE="build/$NAME"
rm -rf build
mkdir -p "$STAGE" dist
rsync -a --exclude '_*' --exclude '__pycache__' --exclude '.DS_Store' SacAcinimDXF "$STAGE/"
cp installer/Install-Mac.command "$STAGE/"
chmod +x "$STAGE/Install-Mac.command"
perl -pe 's/\r?\n/\r\n/' installer/Install-Windows.bat > "$STAGE/Install-Windows.bat"  # CRLF for cmd.exe
cp docs/INSTALL.txt docs/KURULUM.txt docs/USER_GUIDE.pdf docs/KULLANIM.pdf LICENSE "$STAGE/"
rm -f "dist/$NAME.zip"
# ditto keeps Install-Mac.command executable; no ._ metadata files that would litter Windows
ditto -c -k --norsrc --noextattr --keepParent "$STAGE" "dist/$NAME.zip"
rm -rf build
echo "dist/$NAME.zip ($(du -h "dist/$NAME.zip" | cut -f1))"
