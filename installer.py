# -*- coding: utf-8 -*-
"""
==============================================================================
SSH Terminal & Automation Manager - Windows Setup Installer
==============================================================================
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

# Renk Sabitleri
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

def print_installer_banner():
    banner = rf"""{C.CYAN}{C.BOLD}
=================================================================
       ___ ___ _  _   _____ ___ ___ __  __ ___ _  _   _   _     
      / __/ __| || | |_   _| __| _ \  \/  |_ _| \| | /_\ | |    
      \__ \__ \ __ |   | | | _||   / |\/| || || .` |/ _ \| |__  
      |___/___/_||_|   |_| |___|_|_\_|  |_|___|_|\_/_/ \_\____| 
                                                                
         >> SSH Terminal Manager - Kurulum Sihirbazi <<          
================================================================={C.RESET}"""
    print(banner)


def get_default_install_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        return Path(local_app_data) / "Programs" / "SSHTerminal"
    return Path.home() / "AppData" / "Local" / "Programs" / "SSHTerminal"


def create_shortcut(target_exe: Path, lnk_path: Path, work_dir: Path, icon_path: Path = None, description: str = ""):
    try:
        ps_script = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{str(lnk_path)}")
        $Shortcut.TargetPath = "{str(target_exe)}"
        $Shortcut.WorkingDirectory = "{str(work_dir)}"
        $Shortcut.Description = "{description}"
        '''
        if icon_path and icon_path.exists():
            ps_script += f'\n$Shortcut.IconLocation = "{str(icon_path)},0"\n'
        ps_script += '\n$Shortcut.Save()\n'

        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return lnk_path.exists()
    except Exception:
        return False


def create_uninstaller_script(install_dir: Path, desktop_lnk: Path, start_menu_dir: Path):
    uninstaller_bat = install_dir / "uninstall.bat"
    content = f"""@echo off
chcp 65001 >nul
title SSH Terminal Manager - Kaldirma Araci
cls
echo =================================================================
echo   SSH Terminal Manager Kaldirma Islemi
echo =================================================================
echo.
set /p CONFIRM="SSH Terminal Manager sisteminizden kaldirilsin mi? (e/H): "
if /i not "%CONFIRM%"=="e" (
    echo Kaldirma islemi iptal edildi.
    pause
    exit /b
)

echo.
echo Kısayollar ve dosyalar temizleniyor...

if exist "{str(desktop_lnk)}" del /f /q "{str(desktop_lnk)}" >nul 2>&1
if exist "{str(start_menu_dir)}" rd /s /q "{str(start_menu_dir)}" >nul 2>&1

echo.
echo [✓] SSH Terminal Manager basariyla sisteminizden kaldirildi!
echo (Bu klasoru guvenle silebilirsiniz: "{str(install_dir)}")
echo.
pause
"""
    try:
        with open(uninstaller_bat, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def main():
    if os.name == "nt":
        import ctypes
        try:
            kernel32 = ctypes.windll.kernel32
            hStdOut = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
            kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004 | 0x0002)
        except Exception:
            pass

    os.system("cls" if os.name == "nt" else "clear")
    print_installer_banner()
    print(f"\n{C.WHITE}SSH Terminal Manager Kurulumuna Hos Geldiniz!{C.RESET}")
    print(f"{C.DIM}Bu sihirbaz uygulamayi bilgisayariniza yukleyecek ve kisayollari olusturacaktir.{C.RESET}\n")

    # 1. Kurulum Dizini
    default_dir = get_default_install_dir()
    print(f"{C.CYAN}1. Kurulum Dizini:{C.RESET}")
    print(f"Varsayilan: {C.YELLOW}{default_dir}{C.RESET}")
    custom_dir = input(f"Baska bir dizin belirtmek ister misiniz? (Enter = Varsayilan): ").strip()
    install_dir = Path(custom_dir).resolve() if custom_dir else default_dir

    print(f"\nSecilen Dizin: {C.GREEN}{install_dir}{C.RESET}\n")

    # 2. Kisayol Secenekleri
    print(f"{C.CYAN}2. Kisayol Tercihleri:{C.RESET}")
    create_desktop = input("Masaustune kisayol olusturulsun mu? (E/h): ").strip().lower() != "h"
    create_start_menu = input("Baslat Menusune kisayol eklensin mi? (E/h): ").strip().lower() != "h"

    print(f"\n{C.YELLOW}[*] Kurulum baslatiliyor...{C.RESET}")

    # Dizini olustur
    install_dir.mkdir(parents=True, exist_ok=True)

    # Kaynak dosyalari bul ve kopyala
    current_dir = Path(__file__).resolve().parent
    
    # 1. SSHTerminal.exe veya server.py dosyasini ara
    src_exe = current_dir / "SSHTerminal.exe"
    if not src_exe.exists():
        src_exe = current_dir / "dist" / "SSHTerminal.exe"
    
    src_server_py = current_dir / "server.py"
    src_icon = current_dir / "app_icon.ico"

    dest_exe = install_dir / "SSHTerminal.exe"
    dest_server_py = install_dir / "server.py"
    dest_icon = install_dir / "app_icon.ico"

    if src_exe.exists():
        shutil.copy2(src_exe, dest_exe)
        print(f"{C.GREEN}[✓] SSHTerminal.exe kopyalandi.{C.RESET}")
    
    if src_server_py.exists():
        shutil.copy2(src_server_py, dest_server_py)

    if src_icon.exists():
        shutil.copy2(src_icon, dest_icon)

    # Kısayollar
    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.exists():
        desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    desktop_lnk = desktop_dir / "SSH Terminal Manager.lnk"

    app_data = os.environ.get("APPDATA", "")
    start_menu_programs = Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu_app_dir = start_menu_programs / "SSH Terminal Manager"

    target_app = dest_exe if dest_exe.exists() else dest_server_py

    if create_desktop:
        create_shortcut(target_app, desktop_lnk, install_dir, dest_icon if dest_icon.exists() else None, "SSH Terminal & Server Automation Manager")
        print(f"{C.GREEN}[✓] Masaustu kisayolu olusturuldu.{C.RESET}")

    if create_start_menu:
        start_menu_app_dir.mkdir(parents=True, exist_ok=True)
        start_menu_lnk = start_menu_app_dir / "SSH Terminal Manager.lnk"
        create_shortcut(target_app, start_menu_lnk, install_dir, dest_icon if dest_icon.exists() else None, "SSH Terminal & Server Automation Manager")
        print(f"{C.GREEN}[✓] Baslat Menusu kisayolu olusturuldu.{C.RESET}")

    # Uninstaller Olustur
    create_uninstaller_script(install_dir, desktop_lnk, start_menu_app_dir)
    print(f"{C.GREEN}[✓] Kaldirma araci (uninstall.bat) olusturuldu.{C.RESET}")

    print(f"\n{C.GREEN}{C.BOLD}================================================================={C.RESET}")
    print(f"{C.GREEN}{C.BOLD}[✓] KURULUM BASARIYLA TAMAMLANDI!{C.RESET}")
    print(f"{C.WHITE}    Kurulum Yeri: {C.CYAN}{install_dir}{C.RESET}")
    print(f"{C.GREEN}{C.BOLD}================================================================={C.RESET}\n")

    run_now = input("SSH Terminal Manager simdi calistirilsin mi? (E/h): ").strip().lower() != "h"
    if run_now:
        if dest_exe.exists():
            subprocess.Popen([str(dest_exe)], cwd=str(install_dir))
        elif dest_server_py.exists():
            subprocess.Popen([sys.executable, str(dest_server_py)], cwd=str(install_dir))


if __name__ == "__main__":
    main()
