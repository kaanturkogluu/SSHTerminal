@echo off
chcp 65001 >nul
title SSH Terminal Manager - EXE ve Setup Derleme Araci
cls
echo =================================================================
echo   SSH Terminal Manager - EXE ve Setup Derleme Araci
echo =================================================================
echo.

echo [1/3] Gerekli paketler kontrol ediliyor...
python -m pip install --upgrade pip pyinstaller paramiko cryptography >nul 2>&1

echo [2/3] SSHTerminal.exe (Standalone Portable) derleniyor...
python -m PyInstaller --noconfirm --clean --onefile --console --name "SSHTerminal" --icon "app_icon.ico" --version-file "version_info.txt" --manifest "app.manifest" --noupx --distpath "dist" --workpath "build" "server.py"

if errorlevel 1 (
    echo [!] SSHTerminal.exe derlenirken hata olustu.
    pause
    exit /b
)

echo [3/3] SSHTerminal_Setup.exe (Kurulum Paketi) derleniyor...
python -m PyInstaller --noconfirm --clean --onefile --console --name "SSHTerminal_Setup" --icon "app_icon.ico" --version-file "version_info.txt" --manifest "app.manifest" --noupx --add-data "dist\SSHTerminal.exe;." --add-data "app_icon.ico;." --add-data "server.py;." --distpath "dist" --workpath "build" "installer.py"

if errorlevel 1 (
    echo [!] SSHTerminal_Setup.exe derlenirken hata olustu.
    pause
    exit /b
)

echo.
echo =================================================================
echo [✓] DERLEME BASARIYLA TAMAMLANDI!
echo Dosyalar 'dist' klasorunde olusturuldu:
echo   - dist\SSHTerminal.exe
echo   - dist\SSHTerminal_Setup.exe
echo =================================================================
echo.
pause
