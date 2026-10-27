@echo off
rem Fusion Sheet Metal Nesting - Windows installer. Double-click it; it does the rest.
rem Copies the add-in into Fusion's add-ins folder, puts its own portable Python (python-build-standalone, no admin
rem rights needed) inside the add-in and installs the packages it needs there. Running it again updates the add-in
rem and keeps the user's settings and prices. Messages are in English and plain-ASCII Turkish: old consoles garble
rem Turkish letters.
setlocal
cd /d "%~dp0"
set "SRC=%~dp0SacAcinimDXF"
if defined SAC_TARGET (set "PARENT=%SAC_TARGET%") else (set "PARENT=%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns")
set "DEST=%PARENT%\SacAcinimDXF"
set "URL=https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.13.16+20261009-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PY=%DEST%\_python\python.exe"
set "LOG=%DEST%\_install.log"

echo == Fusion Sheet Metal Nesting setup / kurulum ==
echo.
if not exist "%SRC%\SacAcinimDXF.py" goto :no_source
if not defined SAC_TARGET if not exist "%APPDATA%\Autodesk" goto :no_fusion

echo 1/3 Copying the add-in / Eklenti kopyalaniyor...
if not exist "%DEST%" mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /E /XD _python /XF _ayarlar.json _fiyatlar.json _yuz_hafiza.json /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :copy_failed

if exist "%PY%" (
    echo 2/3 Python already installed / Python zaten kurulu.
) else (
    echo 2/3 Downloading Python, about 48 MB / Python indiriliyor...
    curl -fL --progress-bar -o "%TEMP%\sac_python.tar.gz" "%URL%" || goto :no_download
    if not exist "%DEST%\_python" mkdir "%DEST%\_python"
    tar -xzf "%TEMP%\sac_python.tar.gz" -C "%DEST%\_python" --strip-components 1 || goto :no_unpack
    del "%TEMP%\sac_python.tar.gz"
)
if not exist "%PY%" goto :no_unpack

echo 3/3 Installing packages, may take a few minutes / Paketler kuruluyor...
echo %DATE% %TIME% > "%LOG%"
"%PY%" -m pip install --upgrade --disable-pip-version-check pip >>"%LOG%" 2>&1
set "MISSING="
for %%p in (ezdxf ironnest spyrrow shapely matplotlib pillow) do (
    "%PY%" -m pip install --disable-pip-version-check --only-binary :all: --upgrade %%p >>"%LOG%" 2>&1 && (echo     %%p ok) || (echo     %%p FAILED & call set "MISSING=%%MISSING%% %%p")
)
"%PY%" -c "import ezdxf" >nul 2>&1 || goto :no_ezdxf

echo.
echo SETUP COMPLETE / KURULUM TAMAM.
if defined MISSING (
    echo.
    echo Packages that failed / Kurulamayan paketler:%MISSING%
    echo  no ironnest: parts are nested as rectangles; no shapely: model-making mode does not work;
    echo  no matplotlib/pillow: no PNG pictures.
)
echo.
echo Restart Fusion if it is open. The button appears on the SHEET METAL tab.
echo Fusion aciksa kapatip yeniden ac. Buton SHEET METAL sekmesinde cikar.
goto :done

:no_source
echo ERROR: SacAcinimDXF folder not found. Right-click the zip, "Extract All", then run this file from the extracted folder.
echo HATA: SacAcinimDXF klasoru bulunamadi. Zip'e sag tikla, "Tumunu ayikla" de, bu dosyayi acilan klasorden calistir.
goto :error
:no_fusion
echo ERROR: Autodesk Fusion not found. Install Fusion and open it once first.
echo HATA: Autodesk Fusion bulunamadi. Once Fusion'i kurup bir kez acip kapat.
goto :error
:copy_failed
echo ERROR: could not copy the add-in to %DEST%
echo HATA: Eklenti kopyalanamadi: %DEST%
goto :error
:no_download
echo ERROR: could not download Python. Check the internet connection and try again.
echo HATA: Python indirilemedi. Internet baglantisini kontrol edip tekrar dene.
goto :error
:no_unpack
echo ERROR: could not unpack Python. / HATA: Indirilen Python acilamadi.
goto :error
:no_ezdxf
echo ERROR: ezdxf failed; the add-in cannot write DXFs. Details: %LOG%
echo HATA: ezdxf kurulamadi; eklenti DXF yazamaz. Ayrinti: %LOG%
goto :error

:error
echo Take a screenshot of this window and open an issue on GitHub.
echo Bu pencerenin ekran goruntusunu al ve GitHub'da bir issue ac.
echo.
pause
exit /b 1
:done
echo.
pause
exit /b 0
