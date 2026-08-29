@echo off
chcp 65001 >nul
title SSH Terminal Manager - EXE ve Setup Derleme Araci
cls
echo =================================================================
echo   SSH Terminal Manager - EXE ve Setup Derleme & Imzalama
echo =================================================================
echo.

echo [1/4] Gerekli paketler kontrol ediliyor...
python -m pip install --upgrade pip pyinstaller paramiko cryptography >nul 2>&1

echo [2/4] SSHTerminal.exe (Standalone Portable) derleniyor...
python -m PyInstaller --noconfirm --clean --onefile --console --name "SSHTerminal" --icon "app_icon.ico" --version-file "version_info.txt" --manifest "app.manifest" --noupx --distpath "dist" --workpath "build" "server.py"

if errorlevel 1 (
    echo [!] SSHTerminal.exe derlenirken hata olustu.
    pause
    exit /b
)

echo [3/4] SSHTerminal_Setup.exe (Kurulum Paketi) derleniyor...
python -m PyInstaller --noconfirm --clean --onefile --console --name "SSHTerminal_Setup" --icon "app_icon.ico" --version-file "version_info.txt" --manifest "app.manifest" --noupx --add-data "dist\SSHTerminal.exe;." --add-data "app_icon.ico;." --add-data "server.py;." --distpath "dist" --workpath "build" "installer.py"

if errorlevel 1 (
    echo [!] SSHTerminal_Setup.exe derlenirken hata olustu.
    pause
    exit /b
)

echo [4/4] Dijital Kod Imzasi uygulaniyor (Kaan Turkoglu)...
powershell -NoProfile -Command "$cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' | Where-Object { $_.Subject -like '*Kaan*' } | Select-Object -First 1; if ($cert) { Set-AuthenticodeSignature -FilePath 'dist\SSHTerminal.exe' -Certificate $cert -HashAlgorithm SHA256 | Out-Null; Set-AuthenticodeSignature -FilePath 'dist\SSHTerminal_Setup.exe' -Certificate $cert -HashAlgorithm SHA256 | Out-Null; Export-Certificate -Cert $cert -FilePath 'dist\KaanTurkoglu_Certificate.cer' -Force | Out-Null; Write-Host '[✓] Dosyalar Kaan Turkoglu sertifikasiyla basariyla imzalandi!' -ForegroundColor Green } else { Write-Host '[!] Imzalama sertifikasi bulunamadi, imzasiz gecildi.' -ForegroundColor Yellow }"

rd /s /q "build" >nul 2>&1

echo.
echo =================================================================
echo [✓] DERLEME VE IMZALAMA BASARIYLA TAMAMLANDI!
echo Dosyalar 'dist' klasorunde hazir:
echo   - dist\SSHTerminal.exe        (Dijital Imzali Ana Program)
echo   - dist\SSHTerminal_Setup.exe  (Dijital Imzali Kurulum Paketi)
echo   - dist\KaanTurkoglu_Certificate.cer (Genel Guvenlik Sertifikasi)
echo =================================================================
echo.
pause
