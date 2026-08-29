# -*- coding: utf-8 -*-
"""
==============================================================================
SSH Oturum Yoneticisi ve Otomasyon Araci (server.py) - Production Edition
==============================================================================
"""

import sys
import os
import re
import json
import time
import base64
import shutil
import socket
import getpass
import threading
import argparse
import subprocess
from pathlib import Path

# Paramiko kontrolu
try:
    import paramiko
except ImportError:
    print("\n[!] 'paramiko' kutuphanesi yuklu degil.")
    print("Yuklemek icin asagidaki komutu calistirin:")
    print("pip install paramiko\n")
    sys.exit(1)

# Windows Konsol Renk ve VT100 Destegi
if os.name == "nt":
    import msvcrt
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        hStdOut = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
        kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004 | 0x0002)
    except Exception:
        pass
else:
    import select
    import termios
    import tty

# Renk Sabitleri
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    UNDER   = "\033[4m"
    
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

# EXE modunda calisirken gercek calisma dizinini bul
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

SESSIONS_FILE = BASE_DIR / "ssh_sessions.json"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    banner = rf"""{C.CYAN}{C.BOLD}
=================================================================
       ___ ___ _  _   _____ ___ ___ __  __ ___ _  _   _   _     
      / __/ __| || | |_   _| __| _ \  \/  |_ _| \| | /_\ | |    
      \__ \__ \ __ |   | | | _||   / |\/| || || .` |/ _ \| |__  
      |___/___/_||_|   |_| |___|_|_\_|  |_|___|_|\_/_/ \_\____| 
                                                                
         >> SSH Oturum & Otomasyon Yonetim Konsolu <<            
================================================================={C.RESET}"""
    print(banner)


# ==============================================================================
# SIFRELEME VE GUVENLIK YARDIMCILARI (OBFUSCATION / SECURITY)
# ==============================================================================

def encode_secret(text: str) -> str:
    """Hassas bilgileri dosyada duz metin saklamamak icin encode eder."""
    if not text:
        return ""
    try:
        raw = text.encode("utf-8")
        masked = bytes([b ^ 0x5A for b in raw])
        return "enc::" + base64.b64encode(masked).decode("ascii")
    except Exception:
        return text


def decode_secret(text: str) -> str:
    """Encode edilmis bilgiyi cozer."""
    if not text:
        return ""
    if isinstance(text, str) and text.startswith("enc::"):
        try:
            b64_str = text[5:]
            masked = base64.b64decode(b64_str)
            raw = bytes([b ^ 0x5A for b in masked])
            return raw.decode("utf-8")
        except Exception:
            return text
    return text


# ==============================================================================
# GUVENLI VE DOGRULAMALI KULLANICI GIRIS FONKSIYONLARI (INPUT VALIDATION)
# ==============================================================================

def safe_input(prompt: str = "") -> str:
    """Kullanicidan guvenli giris alir; Ctrl+C veya EOF durumlarinda programi korur."""
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        print(f"\n{C.YELLOW}[*] Islem kullanici tarafindan iptal edildi.{C.RESET}\n")
        return ""


def prompt_choice(prompt_text: str, valid_choices: list[str], default: str = None) -> str:
    """Kullanicidan sadece gecerli seceneklerden birini alir."""
    valid_lower = [c.lower() for c in valid_choices]
    while True:
        raw = safe_input(prompt_text).strip()
        if not raw and default is not None:
            return default
        if raw.lower() in valid_lower:
            idx = valid_lower.index(raw.lower())
            return valid_choices[idx]
        
        choices_str = "/".join(valid_choices)
        if default is not None:
            choices_str += f" (Varsayilan: {default})"
        print(f"{C.RED}[!] Gecersiz secim: '{raw}'. Lutfen gecerli bir secenek giriniz: [{choices_str}]{C.RESET}")


def prompt_yes_no(prompt_text: str, default: bool = True) -> bool:
    """Evet/Hayir sorularini kesin olarak dogrular."""
    def_str = "E/h" if default else "e/H"
    full_prompt = f"{prompt_text} ({def_str}): " if not prompt_text.endswith(" ") else prompt_text
    while True:
        raw = safe_input(full_prompt).strip().lower()
        if not raw:
            return default
        if raw in ("e", "evet", "y", "yes"):
            return True
        if raw in ("h", "hayir", "n", "no"):
            return False
        print(f"{C.RED}[!] Gecersiz cevap: '{raw}'. Lutfen 'e' (Evet) veya 'h' (Hayir) yaziniz.{C.RESET}")


def prompt_port(prompt_text: str = "SSH Portu [Varsayilan: 22]: ", default: int = 22) -> int:
    """Port numarasini 1-65535 araliginda bir tam sayi olarak dogrular."""
    while True:
        raw = safe_input(prompt_text).strip()
        if not raw:
            return default
        if raw.isdigit():
            port_num = int(raw)
            if 1 <= port_num <= 65535:
                return port_num
            else:
                print(f"{C.RED}[!] Gecersiz port numarasi: {port_num}. Port 1 ile 65535 arasinda olmalidir.{C.RESET}")
        else:
            print(f"{C.RED}[!] Gecersiz port girisi: '{raw}'. Lutfen sayisal bir port numarasi yazin (Ornek: 22 veya 2222).{C.RESET}")


def prompt_non_empty(prompt_text: str, field_name: str = "Bu alan") -> str:
    """Bos birakilamayacak alanlar icin kullanicidan girdi alir."""
    while True:
        val = safe_input(prompt_text).strip()
        if val:
            return val
        print(f"{C.RED}[!] {field_name} bos birakilamaz! Lutfen gecerli bir deger giriniz.{C.RESET}")


def prompt_int_range(prompt_text: str, min_val: int, max_val: int, allow_zero_cancel: bool = True) -> int:
    """Belirli bir sayisal araliktaki secimleri dogrular."""
    while True:
        raw = safe_input(prompt_text).strip()
        if allow_zero_cancel and raw == "0":
            return 0
        if raw.isdigit():
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            else:
                print(f"{C.RED}[!] Gecersiz numara: {val}. Lutfen {min_val} ile {max_val} arasinda bir secim yapin.{C.RESET}")
        else:
            print(f"{C.RED}[!] Gecersiz giris: '{raw}'. Lutfen bir sayi giriniz.{C.RESET}")


def get_secure_password(prompt: str = "SSH Sifresi: ") -> str:
    """Kullanicidan guvenli sekilde sifre alir."""
    try:
        pw = getpass.getpass(prompt)
        if not pw:
            pw = safe_input(f"{prompt} (Acik giris): ")
        return pw
    except Exception:
        return safe_input(prompt)


# ==============================================================================
# IP / HOST DOGRULAMA VE AG ERISIM TESTLERI
# ==============================================================================

def validate_ip_or_host(host: str) -> tuple[bool, str]:
    """IP veya Host formatinin gecerliligini kontrol eder."""
    if not host or not isinstance(host, str):
        return False, "Host / IP adresi bos olamaz."
    host = host.strip()
    
    ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    if re.match(ipv4_pattern, host):
        return True, "Gecerli IPv4 Adresi"
    
    domain_pattern = r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$'
    if re.match(domain_pattern, host):
        return True, "Gecerli Hostname / Domain"
    
    return False, "Gecersiz IP veya Domain formati! (Ornek: 123.45.67.89 veya example.com)"


def test_network_reachability(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    """Sunucu IP ve Portuna hizli bir TCP socket testi yaparak ulasilabilirligi dener."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True, f"{host}:{port} portuna erisim basarili. Sunucu acik ve yanit veriyor."
    except socket.gaierror:
        return False, f"'{host}' host adi cozumlenemedi (DNS Hatasi / Gecersiz adres)."
    except socket.timeout:
        return False, f"Sunucuya baglanti zaman asimina ugradi ({timeout} sn). IP yanlis veya Firewall/Port engeli olabilir."
    except ConnectionRefusedError:
        return False, f"Baglanti reddedildi. {port} portu kapali veya SSH servisi baska portta calisiyor."
    except Exception as e:
        return False, f"Ag erisim hatasi: {e}"


# ==============================================================================
# SSH BAGLANTI DIZESI AYRISTIRICI (SMART PARSER)
# ==============================================================================

def parse_ssh_string(ssh_str: str) -> dict:
    """Kullanicinin girdigi tek satir SSH komutlarini ayristirir."""
    raw = ssh_str.strip()
    port = 22
    username = "root"
    host = ""

    port_match = re.search(r'-[pP]\s*(\d+)', raw)
    if port_match:
        port = int(port_match.group(1))
        raw = re.sub(r'-[pP]\s*\d+', '', raw).strip()

    raw = re.sub(r'^ssh\s+', '', raw, flags=re.IGNORECASE).strip()

    if ':' in raw and not port_match:
        parts = raw.rsplit(':', 1)
        if parts[1].isdigit():
            port = int(parts[1])
            raw = parts[0]

    if '@' in raw:
        user_part, host_part = raw.split('@', 1)
        username = user_part.strip() if user_part.strip() else "root"
        host = host_part.strip()
    else:
        host = raw.strip()

    return {
        "host": host,
        "port": port,
        "username": username
    }


# ==============================================================================
# OTURUM VERITABANI VE LAUNCHER DOSYALARI
# ==============================================================================

def load_sessions() -> dict:
    """Kayitli oturumlari yukler ve hassas verileri de-obfuscate eder."""
    if not SESSIONS_FILE.exists():
        return {}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for s_name, s_val in data.items():
                if "password" in s_val:
                    s_val["password"] = decode_secret(s_val["password"])
                if "key_passphrase" in s_val:
                    s_val["key_passphrase"] = decode_secret(s_val["key_passphrase"])
            return data
    except Exception as e:
        print(f"{C.RED}[!] Oturum dosyasi okunamadi: {e}{C.RESET}")
        return {}


def save_sessions(sessions: dict):
    """Oturumlari guvenli sekilde kaydeder."""
    try:
        to_save = {}
        for s_name, s_val in sessions.items():
            entry = dict(s_val)
            if "password" in entry and entry["password"]:
                entry["password"] = encode_secret(entry["password"])
            if "key_passphrase" in entry and entry["key_passphrase"]:
                entry["key_passphrase"] = encode_secret(entry["key_passphrase"])
            to_save[s_name] = entry

        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"{C.RED}[!] Oturumlar kaydedilirken hata: {e}{C.RESET}")


def sanitize_filename(name: str) -> str:
    """Gecersiz dosya karakterlerini temizler."""
    return re.sub(r'[\\/*?:"<>| ]', '_', name.strip())


def generate_launchers(session_name: str):
    """
    Oturum kaydedildiginde ayni klasor icinde .bat ve .py launcher dosyalari uretir.
    .bat dosyasi oncelikle ayni dizindeki SSHTerminal.exe'yi kontrol eder (Python olmayan bilgisayarlar icin).
    """
    safe_name = sanitize_filename(session_name)
    
    # 1. Windows Batch (.bat) Dosyasi (SSHTerminal.exe Oncelikli, Python Zorunlulugu Yok)
    bat_file = BASE_DIR / f"{safe_name}.bat"
    bat_content = f"""@echo off
chcp 65001 >nul
title SSH Oturumu: {session_name}
cls

if exist "%~dp0SSHTerminal.exe" (
    "%~dp0SSHTerminal.exe" --connect "{session_name}"
    goto END
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%~dp0server.py" --connect "{session_name}"
    goto END
)
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 "%~dp0server.py" --connect "{session_name}"
    goto END
)
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    python3 "%~dp0server.py" --connect "{session_name}"
    goto END
)
echo [!] SSHTerminal.exe veya Python bulunamadi!
:END
if errorlevel 1 (
    echo.
    echo Baglanti sonlandi veya hata olustu.
    pause
)
"""
    try:
        with open(bat_file, "w", encoding="utf-8") as f:
            f.write(bat_content)
    except Exception as e:
        print(f"{C.YELLOW}[!] .bat dosyasi olusturulamadi: {e}{C.RESET}")

    # 2. Python Standalone Runner (.py) Dosyasi
    py_file = BASE_DIR / f"{safe_name}.py"
    py_content = f"""# -*- coding: utf-8 -*-
\"\"\"
SSH Otomatik Baslatici: {session_name}
\"\"\"
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    exe_file = base / "SSHTerminal.exe"
    if exe_file.exists():
        sys.exit(subprocess.call([str(exe_file), "--connect", "{session_name}"]))
    
    server_script = base / "server.py"
    if server_script.exists():
        sys.exit(subprocess.call([sys.executable, str(server_script), "--connect", "{session_name}"]))
    
    print("[!] Calistirilabilir dosya bulunamadi.")
    sys.exit(1)
"""
    try:
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(py_content)
    except Exception as e:
        print(f"{C.YELLOW}[!] .py dosyasi olusturulamadi: {e}{C.RESET}")

    return bat_file, py_file


def delete_launchers(session_name: str):
    """Oturum silindiginde olusturulan dosyalari temizler."""
    safe_name = sanitize_filename(session_name)
    bat_file = BASE_DIR / f"{safe_name}.bat"
    py_file = BASE_DIR / f"{safe_name}.py"
    
    if bat_file.exists():
        try:
            bat_file.unlink()
        except Exception:
            pass
    if py_file.exists():
        try:
            py_file.unlink()
        except Exception:
            pass


def create_desktop_shortcut(session_name: str) -> bool:
    """Windows Masaustune .lnk formatinda cift tiklanabilir kisayol olusturur."""
    if os.name != "nt":
        return False
    try:
        desktop_dir = Path.home() / "Desktop"
        if not desktop_dir.exists():
            desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        
        safe_name = sanitize_filename(session_name)
        bat_file = BASE_DIR / f"{safe_name}.bat"
        lnk_file = desktop_dir / f"SSH - {session_name}.lnk"
        
        ps_script = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{str(lnk_file)}")
        $Shortcut.TargetPath = "{str(bat_file)}"
        $Shortcut.WorkingDirectory = "{str(BASE_DIR)}"
        $Shortcut.Save()
        '''
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return lnk_file.exists()
    except Exception:
        return False


# ==============================================================================
# INTERAKTIF TERMINAL (DINAMIK PTY BOYUTLANDIRMA & GUVENLI I/O)
# ==============================================================================

def interactive_shell(channel):
    """
    Paramiko PTY uzerinden gercek zamanli, cift yonlu interaktif terminal oturumu.
    """
    stop_event = threading.Event()
    last_term_size = shutil.get_terminal_size(fallback=(100, 30))

    def resize_listener():
        nonlocal last_term_size
        while not stop_event.is_set() and not channel.closed:
            try:
                curr_size = shutil.get_terminal_size(fallback=(100, 30))
                if curr_size != last_term_size:
                    last_term_size = curr_size
                    channel.resize_pty(width=curr_size.columns, height=curr_size.lines)
                time.sleep(0.5)
            except Exception:
                break

    resize_thread = threading.Thread(target=resize_listener, daemon=True)
    resize_thread.start()

    def recv_thread():
        while not stop_event.is_set() and not channel.closed:
            try:
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
                else:
                    time.sleep(0.01)
            except Exception:
                break
        stop_event.set()

    t = threading.Thread(target=recv_thread, daemon=True)
    t.start()

    if os.name == "nt":
        try:
            while not stop_event.is_set() and not channel.closed:
                if msvcrt.kbhit():
                    char = msvcrt.getwch()
                    
                    if char in ('\x00', '\xe0'):
                        scancode = msvcrt.getwch()
                        key_map = {
                            'H': '\x1b[A',  # Yukari Ok
                            'P': '\x1b[B',  # Asagi Ok
                            'M': '\x1b[C',  # Sag Ok
                            'K': '\x1b[D',  # Sol Ok
                            'G': '\x1b[H',  # Home
                            'O': '\x1b[F',  # End
                            'S': '\x1b[3~', # Delete
                            'R': '\x1b[2~', # Insert
                            'I': '\x1b[5~', # Page Up
                            'Q': '\x1b[6~', # Page Down
                        }
                        seq = key_map.get(scancode, '')
                        if seq:
                            channel.send(seq.encode('utf-8'))
                    elif char == '\r':
                        channel.send(b'\r')
                    elif char == '\x08':
                        channel.send(b'\x08')
                    elif char == '\x03':
                        channel.send(b'\x03')
                    elif char == '\x04':
                        channel.send(b'\x04')
                    elif char == '\x1a':
                        channel.send(b'\x1a')
                    elif char == '\t':
                        channel.send(b'\t')
                    elif char == '\x1b':
                        channel.send(b'\x1b')
                    else:
                        channel.send(char.encode('utf-8'))
                else:
                    time.sleep(0.01)
        except Exception:
            pass
    else:
        old_tty = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            while not stop_event.is_set() and not channel.closed:
                r, _, _ = select.select([channel, sys.stdin], [], [], 0.05)
                if sys.stdin in r:
                    user_input = os.read(sys.stdin.fileno(), 1024)
                    if not user_input:
                        break
                    channel.send(user_input)
        except Exception:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

    stop_event.set()
    print(f"\n{C.YELLOW}[*] Oturum sonlandirildi.{C.RESET}\n")


# ==============================================================================
# YONERGELERIN (KOMUTLARIN) AKILLI VE CANLI AKISLI ICRA MOTORU
# ==============================================================================

def execute_commands_safely(channel, commands: list):
    if not commands:
        return

    print(f"\n{C.YELLOW}{C.BOLD}{'='*65}{C.RESET}")
    print(f"{C.YELLOW}{C.BOLD}[*] OTOMATIK YONERGELER ICRA EDILIYOR ({len(commands)} Adim)...{C.RESET}")
    print(f"{C.YELLOW}{C.BOLD}{'='*65}{C.RESET}\n")

    ERROR_PATTERNS = [
        r"No such file or directory",
        r"command not found",
        r"Permission denied",
        r"fatal:",
        r"Syntax error",
        r"Parse error",
        r"Could not open input file",
        r"is not recognized as",
        r"Access denied"
    ]

    cmd_index = 0
    while cmd_index < len(commands):
        cmd = commands[cmd_index]
        step_no = cmd_index + 1
        total_steps = len(commands)

        print(f"{C.MAGENTA}{C.BOLD}[Adim {step_no}/{total_steps}]{C.RESET} {C.CYAN}> {cmd}{C.RESET}")

        full_payload = f"{cmd}\n"
        channel.send(full_payload.encode("utf-8"))

        start_time = time.time()
        output_buffer = ""
        has_error = False
        error_reason = ""

        silence_start = time.time()
        while True:
            had_data = False
            while channel.recv_ready():
                try:
                    chunk = channel.recv(4096).decode("utf-8", errors="replace")
                    output_buffer += chunk
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    had_data = True
                    silence_start = time.time()
                except Exception:
                    break
            
            if had_data:
                for pat in ERROR_PATTERNS:
                    match = re.search(pat, output_buffer, re.IGNORECASE)
                    if match:
                        has_error = True
                        error_reason = match.group(0)
                        break

            if time.time() - silence_start > 0.8 and (time.time() - start_time >= 1.0 or had_data):
                break

            time.sleep(0.05)

        if has_error:
            print(f"\n\n{C.RED}{C.BOLD}{'!'*65}{C.RESET}")
            print(f"{C.RED}{C.BOLD}[!] ADIM {step_no} SIRASINDA HATA TESPIT EDILDI!{C.RESET}")
            print(f"    {C.WHITE}Calistirilan Komut:{C.RESET} {C.YELLOW}{cmd}{C.RESET}")
            print(f"    {C.WHITE}Sunucu Yaniti / Hata:{C.RESET} {C.RED}{error_reason}{C.RESET}")
            print(f"{C.RED}{C.BOLD}{'!'*65}{C.RESET}\n")

            print(f"{C.BOLD}Ne yapmak istersiniz?{C.RESET}")
            print(f"  {C.GREEN}[1] Bu hatayi gormezden gel ve siradaki komuta gec{C.RESET}")
            print(f"  {C.YELLOW}[2] Bu komutu duzelterek simdi tekrar calistir{C.RESET}")
            print(f"  {C.CYAN}[3] Kalan komutlari atla ve dogrudan Manuel Terminale gec{C.RESET}")
            print(f"  {C.RED}[4] Baglantiyi sonlandir ve cik{C.RESET}\n")

            choice = prompt_choice(f"{C.BOLD}Seciminiz [1/2/3/4] (Varsayilan: 1): {C.RESET}", ["1", "2", "3", "4"], default="1")

            if choice == "2":
                new_cmd = prompt_non_empty(f"\n{C.BOLD}Duzeltilmis yeni komutu girin: {C.RESET}", "Komut")
                commands[cmd_index] = new_cmd
                print(f"{C.CYAN}[*] Komut guncellendi, tekrar deneniyor...{C.RESET}\n")
                continue
            elif choice == "3":
                print(f"\n{C.YELLOW}[*] Otomasyon durduruldu. Manuel terminale devrediliyor...{C.RESET}\n")
                break
            elif choice == "4":
                print(f"\n{C.RED}[*] Oturum kullanici tarafindan iptal edildi.{C.RESET}\n")
                channel.close()
                return

        cmd_index += 1

    print(f"\n{C.GREEN}{C.BOLD}[V] Tum yonergeler tamamlandi!{C.RESET}")


# ==============================================================================
# SSH BAGLANTI YONETIMI
# ==============================================================================

def connect_to_session(session_name: str, session_data: dict = None):
    if session_data is None:
        sessions = load_sessions()
        if session_name not in sessions:
            print(f"\n{C.RED}[!] '{session_name}' adinda bir oturum bulunamadi!{C.RESET}")
            safe_input("\nDevam etmek icin Enter'a basin...")
            return
        session_data = sessions[session_name]

    host = session_data.get("host")
    port = session_data.get("port", 22)
    username = session_data.get("username", "root")
    auth_type = session_data.get("auth_type", "password")
    password = session_data.get("password", "")
    key_path = session_data.get("key_path", "")
    key_passphrase = session_data.get("key_passphrase", "")
    commands = session_data.get("commands", [])

    auth_desc = f"SSH Key ({Path(key_path).name})" if auth_type == "key" else "Sifre"

    print(f"\n{C.CYAN}{'='*65}{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}[+] SSH Baglantisi Baslatiliyor...{C.RESET}")
    print(f"    {C.WHITE}Oturum:{C.RESET}       {C.BOLD}{session_name}{C.RESET}")
    print(f"    {C.WHITE}Hedef Sunucu:{C.RESET} {C.CYAN}{username}@{host}:{port}{C.RESET}")
    print(f"    {C.WHITE}Kimlik Tipi:{C.RESET}  {C.YELLOW}{auth_desc}{C.RESET}")
    print(f"{C.CYAN}{'='*65}{C.RESET}\n")

    # ASAMA 1: AG TESTI
    print(f"{C.YELLOW}[ASAMA 1/3] Sunucu Ag ve Port Erisimi Test Ediliyor...{C.RESET}")
    is_reachable, reach_msg = test_network_reachability(host, port, timeout=3.5)
    
    if not is_reachable:
        print(f"\n{C.RED}{C.BOLD}[!] ASAMA 1 HATASI: Sunucuya Ag Uzerinden Ulasilamadi!{C.RESET}")
        print(f"    {C.WHITE}Detay:{C.RESET} {C.RED}{reach_msg}{C.RESET}")
        print(f"    {C.YELLOW}Olasiliklar:{C.RESET}")
        print(f"      1. Sunucu IP adresi ({host}) yanlis olabilir.")
        print(f"      2. SSH Portu ({port}) yanlis veya sunucu tarafinda kapali olabilir.")
        print(f"      3. Sunucu guvenlik duvari (Firewall) baglantinizi engelliyor olabilir.")
        
        cont = prompt_yes_no("\nYine de SSH baglantisi denenmeye devam edilsin mi?", default=False)
        if not cont:
            return
    else:
        print(f"{C.GREEN}[V] Asama 1 Basarili: {reach_msg}{C.RESET}\n")

    # ASAMA 2: AUTH TESTI
    print(f"{C.YELLOW}[ASAMA 2/3] SSH Oturumu Aciliyor ve Kimlik Dogrulaniyor...{C.RESET}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 15,
            "allow_agent": False,
            "look_for_keys": False
        }

        if auth_type == "key" and key_path:
            p_key = Path(key_path).expanduser().resolve()
            if not p_key.exists():
                print(f"{C.RED}[!] HATA: SSH Key dosyasi bulunamadi: {p_key}{C.RESET}")
                safe_input("Devam etmek icin Enter'a basin...")
                return
            
            connect_kwargs["key_filename"] = str(p_key)
            if key_passphrase:
                connect_kwargs["passphrase"] = key_passphrase
        else:
            connect_kwargs["password"] = password

        client.connect(**connect_kwargs)
        
        transport = client.get_transport()
        if transport:
            transport.set_keepalive(30)
            
        print(f"{C.GREEN}[V] Asama 2 Basarili: SSH Kimlik Dogrulamasi Gecti! (Keep-Alive Aktif){C.RESET}\n")

    except paramiko.AuthenticationException:
        print(f"\n{C.RED}{C.BOLD}[!] ASAMA 2 HATASI: Kimlik Dogrulama Reddedildi!{C.RESET}")
        print(f"    {C.WHITE}Sunucu Yaniti:{C.RESET} {C.RED}Authentication Failed (Kullanici adi, Sifre veya Key Yanlis){C.RESET}")
        print(f"    {C.WHITE}Denenen Kullanici:{C.RESET} {C.YELLOW}{username}{C.RESET}")
        print(f"    {C.YELLOW}Lutfen bilgilerinizi kontrol edip oturumu duzenleyin (Ana Menu -> 4).{C.RESET}\n")
        safe_input("Ana menuye donmek icin Enter'a basin...")
        return

    except socket.timeout:
        print(f"\n{C.RED}{C.BOLD}[!] ASAMA 2 HATASI: Sunucu Yanit Zaman Asimi!{C.RESET}")
        print(f"    {C.WHITE}Detay:{C.RESET} Sunucu SSH el sikismasina zamaninda yanit vermedi.\n")
        safe_input("Ana menuye donmek icin Enter'a basin...")
        return

    except paramiko.SSHException as ssh_err:
        print(f"\n{C.RED}{C.BOLD}[!] ASAMA 2 HATASI: SSH Protokol Hatasi!{C.RESET}")
        print(f"    {C.WHITE}Sunucu Yaniti:{C.RESET} {C.RED}{ssh_err}{C.RESET}\n")
        safe_input("Ana menuye donmek icin Enter'a basin...")
        return

    except Exception as general_err:
        print(f"\n{C.RED}{C.BOLD}[!] ASAMA 2 HATASI: Beklenmeyen Baglanti Hatasi!{C.RESET}")
        print(f"    {C.WHITE}Hata Detayi:{C.RESET} {C.RED}{general_err}{C.RESET}\n")
        safe_input("Ana menuye donmek icin Enter'a basin...")
        return

    # ASAMA 3: PTY
    print(f"{C.YELLOW}[ASAMA 3/3] Terminal Kanali (PTY) Olusturuluyor...{C.RESET}")
    try:
        cols, rows = shutil.get_terminal_size(fallback=(100, 30))
        channel = client.invoke_shell(term="xterm-256color", width=cols, height=rows)
        channel.settimeout(0.0)

        time.sleep(1.0)
        while channel.recv_ready():
            try:
                data = channel.recv(4096)
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
            except Exception:
                break

        execute_commands_safely(channel, commands)

        if not channel.closed:
            print(f"\n{C.GREEN}{C.BOLD}{'='*65}{C.RESET}")
            print(f"{C.GREEN}{C.BOLD}[*] MANUEL TERMINAL MODUNA GECILDI{C.RESET}")
            print(f"{C.WHITE}    Sunucuyu normal sekilde kullanabilirsiniz.{C.RESET}")
            print(f"{C.WHITE}    Cikis yapmak icin: {C.YELLOW}exit{C.WHITE} yazabilir veya pencereyi kapatabilirsiniz.{C.RESET}")
            print(f"{C.GREEN}{C.BOLD}{'='*65}{C.RESET}\n")

            interactive_shell(channel)

        channel.close()
        client.close()

    except Exception as e:
        print(f"\n{C.RED}[!] Terminal Hatasi: {e}{C.RESET}")
        safe_input("Devam etmek icin Enter'a basin...")


# ==============================================================================
# YENI OTURUM OLUSTURMA
# ==============================================================================

def create_session_menu():
    clear_screen()
    print_banner()
    print(f"{C.BOLD}{C.CYAN}--- YENI SSH OTURUMU & OTOMASYON OLUSTUR ---{C.RESET}\n")

    print(f"{C.YELLOW}[ADIM 1 / 5] Oturum Adi Belirleyin{C.RESET}")
    while True:
        session_name = prompt_non_empty(f"{C.BOLD}Oturum Adi (Ornek: sunucu1, prod_server): {C.RESET}", "Oturum adi")
        safe_name = sanitize_filename(session_name)
        if not safe_name:
            print(f"{C.RED}[!] Oturum adi gecersiz karakterler iceriyor. Lutfen gecerli bir isim giriniz.{C.RESET}")
            continue
        break

    print(f"\n{C.YELLOW}[ADIM 2 / 5] Sunucu Baglanti Bilgileri{C.RESET}")
    print(f"Giris yontemini secin:")
    print(f"  {C.GREEN}[1] Sirayla Adim Adim Giris (Port -> Kullanici Adi -> IP -> Sifre/Key) [Onerilen]{C.RESET}")
    print(f"  {C.CYAN}[2] Tek Satirda SSH Komutu Yapistir (Ornek: ssh -p 22 user123@123.45.67.89){C.RESET}")
    
    entry_mode = prompt_choice(f"\n{C.BOLD}Seciminiz [1/2] (Varsayilan: 1): {C.RESET}", ["1", "2"], default="1")

    host = ""
    port = 22
    username = "root"
    auth_type = "password"
    password = ""
    key_path = ""
    key_passphrase = ""

    while True:
        if entry_mode == "2":
            print(f"\n{C.WHITE}SSH Baglanti komutunu veya adresini yapistirin:{C.RESET}")
            print(f"{C.DIM}Ornekler: ssh -p 22 user123@123.45.67.89{C.RESET}\n")
            ssh_input = prompt_non_empty(f"{C.BOLD}SSH Komutu / Adresi: {C.RESET}", "SSH komutu")
            
            parsed = parse_ssh_string(ssh_input)
            host = parsed["host"]
            port = parsed["port"]
            username = parsed["username"]

            if not host:
                host = prompt_non_empty("Sunucu IP / Host Adresi: ", "Host adresi")

            print(f"\nTespit edilen -> {C.CYAN}Port: {port}{C.RESET} | {C.CYAN}Kullanici: {username}{C.RESET} | {C.CYAN}IP/Host: {host}{C.RESET}")
            confirm = prompt_yes_no("Bu bilgiler dogru mu?", default=True)
            if not confirm:
                entry_mode = "1"
                continue
        else:
            print(f"\n{C.BOLD}{C.WHITE}Lutfen bilgileri sirayla giriniz:{C.RESET}\n")
            port = prompt_port(f"{C.CYAN}[1] SSH Portu [Varsayilan: 22]: {C.RESET}", default=22)
            user_input = safe_input(f"{C.CYAN}[2] Kullanici Adi [Varsayilan: root]: {C.RESET}").strip()
            username = user_input if user_input else "root"

            while True:
                host_input = prompt_non_empty(f"{C.CYAN}[3] Sunucu IP / Host: {C.RESET}", "Sunucu IP adresi")
                if "ssh" in host_input or "@" in host_input or "-p" in host_input:
                    parsed_inner = parse_ssh_string(host_input)
                    host = parsed_inner["host"]
                    if parsed_inner["port"] != 22:
                        port = parsed_inner["port"]
                    if parsed_inner["username"] != "root":
                        username = parsed_inner["username"]
                    print(f"{C.GREEN}[i] Girilen komuttan bilgiler ayiklandi: {username}@{host}:{port}{C.RESET}")
                else:
                    host = host_input

                is_valid_fmt, fmt_msg = validate_ip_or_host(host)
                if not is_valid_fmt:
                    print(f"{C.RED}[!] Format Hatasi: {fmt_msg}{C.RESET}")
                    re_try = prompt_yes_no("Yine de bu host adresiyle devam edilsin mi?", default=False)
                    if not re_try:
                        continue
                break

        print(f"\n{C.YELLOW}[*] Sunucu erisilebilirligi test ediliyor ({host}:{port})...{C.RESET}")
        reach_ok, reach_msg = test_network_reachability(host, port, timeout=3.0)
        
        if reach_ok:
            print(f"{C.GREEN}{C.BOLD}[✓] Ag Testi Basarili:{C.RESET} {C.GREEN}{reach_msg}{C.RESET}")
            break
        else:
            print(f"{C.RED}{C.BOLD}[!] Ag Testi Uyarisi:{C.RESET} {C.RED}{reach_msg}{C.RESET}")
            fix_choice = prompt_yes_no("Bilgileri tekrar duzeltmek ister misiniz?", default=True)
            if not fix_choice:
                break
            else:
                entry_mode = "1"

    # Kimlik Dogrulama
    print(f"\n{C.YELLOW}[ADIM 3 / 5] Kimlik Dogrulama Yontemi{C.RESET}")
    print("  [1] SSH Sifresi ile Baglan (Standart)")
    print("  [2] SSH Private Key Dosyasi ile Baglan (.pem, id_rsa, id_ed25519)")
    auth_choice = prompt_choice(f"\nSeciminiz [1/2] (Varsayilan: 1): ", ["1", "2"], default="1")

    if auth_choice == "2":
        auth_type = "key"
        while True:
            key_path = prompt_non_empty("Private Key Dosya Yolu: ", "Key dosya yolu")
            p_test = Path(key_path).expanduser().resolve()
            if not p_test.exists():
                print(f"{C.RED}[!] Dosya bulunamadi: {p_test}{C.RESET}")
                cont_anyway = prompt_yes_no("Yine de bu dosya yolu kaydedilsin mi?", default=False)
                if cont_anyway:
                    break
            else:
                print(f"{C.GREEN}[✓] Key dosyasi dogrulandi ({p_test.stat().st_size} byte){C.RESET}")
                break
        
        has_passphrase = prompt_yes_no("\nBu key icin bir parola (passphrase) var mi?", default=False)
        if has_passphrase:
            key_passphrase = get_secure_password("Key Parolasi (Passphrase): ")
    else:
        auth_type = "password"
        password = get_secure_password("SSH Sifreniz: ")

    # Yonergeler
    print(f"\n{C.YELLOW}[ADIM 4 / 5] Baslangic Yonergeleri (Otomatik Komutlar){C.RESET}")
    print(f"{C.DIM}(Komut girisini tamamlamak icin bos Enter'a basin){C.RESET}\n")

    commands = []
    cmd_index = 1
    while True:
        cmd = safe_input(f"{C.BOLD}{cmd_index}. Komut: {C.RESET}").strip()
        if not cmd:
            break
        commands.append(cmd)
        cmd_index += 1

    # Ozet ve Kayit
    print(f"\n{C.YELLOW}[ADIM 5 / 5] Oturum Ozeti ve Kayit Onayi{C.RESET}")
    print(f"{C.CYAN}{'='*60}{C.RESET}")
    print(f"  {C.BOLD}Oturum Adi:{C.RESET}     {C.GREEN}{session_name}{C.RESET}")
    print(f"  {C.BOLD}SSH Portu:{C.RESET}      {C.WHITE}{port}{C.RESET}")
    print(f"  {C.BOLD}Kullanici Adi:{C.RESET}  {C.WHITE}{username}{C.RESET}")
    print(f"  {C.BOLD}Sunucu IP:{C.RESET}      {C.WHITE}{host}{C.RESET}")
    print(f"  {C.BOLD}Kimlik Tipi:{C.RESET}    {C.WHITE}{'SSH Key (' + Path(key_path).name + ')' if auth_type == 'key' else 'Sifre'}{C.RESET}")
    print(f"  {C.BOLD}Yonergeler:{C.RESET}     {C.WHITE}{len(commands)} adet komut{C.RESET}")
    print(f"{C.CYAN}{'='*60}{C.RESET}\n")

    confirm_save = prompt_yes_no("Bu oturum kaydedilsin mi?", default=True)
    if not confirm_save:
        print(f"{C.YELLOW}[*] Kayit iptal edildi.{C.RESET}")
        time.sleep(1.5)
        return

    sessions = load_sessions()
    sessions[session_name] = {
        "host": host,
        "port": port,
        "username": username,
        "auth_type": auth_type,
        "password": password,
        "key_path": key_path,
        "key_passphrase": key_passphrase,
        "commands": commands
    }
    save_sessions(sessions)

    bat_file, py_file = generate_launchers(session_name)

    print(f"\n{C.GREEN}{C.BOLD}[V] '{session_name}' OTURUMU BASARIYLA KAYDEDILDI!{C.RESET}")
    print(f"  -> {C.BOLD}{bat_file.name}{C.RESET} (Cift tiklanabilir baslatici olusturuldu)")

    if os.name == "nt":
        ask_desktop = prompt_yes_no("\nWindows Masaustune cift tiklanabilir kisayol olusturulsun mu?", default=True)
        if ask_desktop:
            desk_ok = create_desktop_shortcut(session_name)
            if desk_ok:
                print(f"{C.GREEN}[✓] Masaustune kisayol olusturuldu: 'SSH - {session_name}.lnk'{C.RESET}")

    ask_connect = prompt_yes_no("\nSimdi bu sunucuya baglanmak ister misiniz?", default=True)
    if ask_connect:
        connect_to_session(session_name, sessions[session_name])
    else:
        safe_input("\nAna menuye donmek icin Enter'a basin...")


# ==============================================================================
# DIGER MENULER (LISTELE, DUZENLE, SIL, YEDEKLE)
# ==============================================================================

def list_sessions_menu():
    clear_screen()
    print_banner()
    sessions = load_sessions()
    
    if not sessions:
        print(f"\n{C.YELLOW}[i] Henuz kayitli bir oturum bulunmuyor.{C.RESET}\n")
        safe_input("Ana menuye donmek icin Enter'a basin...")
        return

    print(f"{C.BOLD}{C.CYAN}--- KAYITLI SSH OTURUMLARI ({len(sessions)}) ---{C.RESET}\n")
    
    for idx, (name, s) in enumerate(sessions.items(), start=1):
        safe_name = sanitize_filename(name)
        auth_t = s.get("auth_type", "password")
        auth_str = f"SSH Key ({Path(s.get('key_path', '')).name})" if auth_t == "key" else "Sifre"
        
        print(f"{C.BOLD}{C.GREEN}[{idx}] {name}{C.RESET}")
        print(f"    {C.WHITE}Adres:{C.RESET}         {C.CYAN}{s.get('username')}@{s.get('host')}:{s.get('port')}{C.RESET}")
        print(f"    {C.WHITE}Kimlik Tipi:{C.RESET}   {C.MAGENTA}{auth_str}{C.RESET}")
        print(f"    {C.WHITE}Baslatici:{C.RESET}     {C.YELLOW}{safe_name}.bat{C.RESET}")
        
        cmds = s.get("commands", [])
        if cmds:
            print(f"    {C.WHITE}Yonergeler ({len(cmds)} adet):{C.RESET}")
            for c_idx, c in enumerate(cmds, start=1):
                print(f"       {C.DIM}{c_idx}.{C.RESET} {c}")
        print(f"{C.DIM}{'-'*50}{C.RESET}")

    safe_input("\nAna menuye donmek icin Enter'a basin...")


def select_and_connect_menu():
    clear_screen()
    print_banner()
    sessions = load_sessions()
    
    if not sessions:
        print(f"\n{C.YELLOW}[i] Kayitli oturum yok. Once bir oturum olusturun.{C.RESET}\n")
        safe_input("Devam etmek icin Enter'a basin...")
        return

    session_keys = list(sessions.keys())
    print(f"{C.BOLD}{C.CYAN}--- BAGLANILACAK OTURUMU SECIN ---{C.RESET}\n")
    for idx, name in enumerate(session_keys, start=1):
        s = sessions[name]
        print(f"  {C.BOLD}{C.GREEN}[{idx}]{C.RESET} {C.BOLD}{name}{C.RESET} ({s.get('username')}@{s.get('host')}:{s.get('port')})")

    print(f"  {C.RED}[0] Iptal / Geri Don{C.RESET}\n")
    
    choice_idx = prompt_int_range(f"{C.BOLD}Seciminiz (Numara): {C.RESET}", 1, len(session_keys), allow_zero_cancel=True)
    if choice_idx == 0:
        return
    
    target_name = session_keys[choice_idx - 1]
    connect_to_session(target_name, sessions[target_name])


def edit_session_menu():
    clear_screen()
    print_banner()
    sessions = load_sessions()
    
    if not sessions:
        print(f"\n{C.YELLOW}[i] Duzenlenecek oturum bulunmuyor.{C.RESET}\n")
        safe_input("Devam etmek icin Enter'a basin...")
        return

    session_keys = list(sessions.keys())
    print(f"{C.BOLD}{C.CYAN}--- DUZENLENECEK OTURUMU SECIN ---{C.RESET}\n")
    for idx, name in enumerate(session_keys, start=1):
        print(f"  {C.BOLD}{C.GREEN}[{idx}]{C.RESET} {name}")
    print(f"  {C.RED}[0] Geri Don{C.RESET}\n")

    choice_idx = prompt_int_range(f"{C.BOLD}Seciminiz: {C.RESET}", 1, len(session_keys), allow_zero_cancel=True)
    if choice_idx == 0:
        return
    
    target_name = session_keys[choice_idx - 1]
    s = sessions[target_name]

    print(f"\n{C.BOLD}Oturum: {target_name}{C.RESET}")
    print(f"  [1] Port degistir (Mevcut: {s.get('port')})")
    print(f"  [2] Kullanici Adi degistir (Mevcut: {s.get('username')})")
    print(f"  [3] Sunucu IP/Host degistir (Mevcut: {s.get('host')})")
    print(f"  [4] Kimlik Dogrulama (Sifre / Key) degistir")
    print(f"  [5] Yonergeleri (Komutlari) yeniden gir")
    print(f"  [6] Baslatici (.bat ve .py) dosyalarini yeniden olustur")
    print(f"  [7] Ag erisim testi yap ({s.get('host')}:{s.get('port')})")
    print(f"  [8] Bu oturumu kopyala / klonla (Duplicate)")
    print(f"  [9] Windows Masaustune Kisayol Olustur (.lnk)")
    print(f"  [0] Vazgec")

    sub_ch = prompt_choice("\nIslem [0-9]: ", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="0")
    if sub_ch == "0":
        return
    elif sub_ch == "1":
        s["port"] = prompt_port(f"Yeni Port [{s.get('port')}]: ", default=s.get('port', 22))
    elif sub_ch == "2":
        new_u = safe_input(f"Yeni Kullanici Adi [{s.get('username')}]: ").strip()
        if new_u:
            s["username"] = new_u
    elif sub_ch == "3":
        new_h = safe_input(f"Yeni Host [{s.get('host')}]: ").strip()
        if new_h:
            s["host"] = new_h
    elif sub_ch == "4":
        print("\nKimlik Dogrulama Yontemi:")
        print("  [1] Sifre")
        print("  [2] SSH Private Key")
        a_ch = prompt_choice("Secim [1/2]: ", ["1", "2"], default="1")
        if a_ch == "2":
            s["auth_type"] = "key"
            s["key_path"] = prompt_non_empty("Private Key Dosya Yolu: ", "Key dosyasi")
            has_p = prompt_yes_no("Passphrase var mi?", default=False)
            s["key_passphrase"] = get_secure_password("Passphrase: ") if has_p else ""
            s["password"] = ""
        else:
            s["auth_type"] = "password"
            s["password"] = get_secure_password("Yeni Sifre: ")
            s["key_path"] = ""
            s["key_passphrase"] = ""
    elif sub_ch == "5":
        print(f"\n{C.YELLOW}Yeni komutlari girin (Bitirmek icin bos Enter):{C.RESET}")
        new_cmds = []
        c_i = 1
        while True:
            c = safe_input(f"{c_i}. Komut: ").strip()
            if not c:
                break
            new_cmds.append(c)
            c_i += 1
        s["commands"] = new_cmds
    elif sub_ch == "6":
        generate_launchers(target_name)
        print(f"{C.GREEN}[V] Baslatici dosyalari yenilendi.{C.RESET}")
        time.sleep(1.5)
    elif sub_ch == "7":
        print(f"\n{C.YELLOW}[*] Ag testi yapiliyor...{C.RESET}")
        ok, msg = test_network_reachability(s.get('host'), s.get('port', 22), timeout=3.5)
        if ok:
            print(f"{C.GREEN}[✓] {msg}{C.RESET}")
        else:
            print(f"{C.RED}[!] {msg}{C.RESET}")
        safe_input("\nDevam etmek icin Enter'a basin...")
        return
    elif sub_ch == "8":
        clone_name = prompt_non_empty("Klonlanacak yeni oturum adi: ", "Oturum adi")
        sessions[clone_name] = dict(s)
        save_sessions(sessions)
        generate_launchers(clone_name)
        print(f"{C.GREEN}[V] '{clone_name}' adinda yeni oturum klonlandi ve baslaticilari uretildi!{C.RESET}")
        time.sleep(1.5)
        return
    elif sub_ch == "9":
        desk_ok = create_desktop_shortcut(target_name)
        if desk_ok:
            print(f"{C.GREEN}[✓] Masaustune kisayol olusturuldu: 'SSH - {target_name}.lnk'{C.RESET}")
        else:
            print(f"{C.RED}[!] Kisayol olusturulamadi.{C.RESET}")
        safe_input("\nDevam etmek icin Enter'a basin...")
        return

    sessions[target_name] = s
    save_sessions(sessions)
    generate_launchers(target_name)
    print(f"{C.GREEN}[V] Degisiklikler kaydedildi!{C.RESET}")
    time.sleep(1.5)


def delete_session_menu():
    clear_screen()
    print_banner()
    sessions = load_sessions()
    
    if not sessions:
        print(f"\n{C.YELLOW}[i] Silinecek oturum yok.{C.RESET}\n")
        safe_input("Devam etmek icin Enter'a basin...")
        return

    session_keys = list(sessions.keys())
    print(f"{C.BOLD}{C.RED}--- OTURUM SILME ---{C.RESET}\n")
    for idx, name in enumerate(session_keys, start=1):
        print(f"  [{idx}] {name}")
    print(f"  [0] Vazgec\n")

    choice_idx = prompt_int_range(f"{C.BOLD}Silinecek Oturum No: {C.RESET}", 1, len(session_keys), allow_zero_cancel=True)
    if choice_idx == 0:
        return
    
    target_name = session_keys[choice_idx - 1]
    confirm = prompt_yes_no(f"'{target_name}' oturumunu ve calistirici dosyalarini silmek istiyor musunuz?", default=False)
    if confirm:
        del sessions[target_name]
        save_sessions(sessions)
        delete_launchers(target_name)
        print(f"\n{C.GREEN}[V] '{target_name}' oturumu ve bagli dosyalari silindi.{C.RESET}")
        time.sleep(1.5)


def backup_restore_menu():
    clear_screen()
    print_banner()
    print(f"{C.BOLD}{C.CYAN}--- OTURUM YEDEGI YONETIMI (EXPORT / IMPORT) ---{C.RESET}\n")
    print("  [1] Tum Oturumlari JSON Dosyasina Yedekle (Export)")
    print("  [2] JSON Dosyasindan Oturumlari Geri Yukle (Import)")
    print("  [0] Geri Don\n")

    choice = prompt_choice("Seciminiz [0/1/2]: ", ["0", "1", "2"], default="0")
    if choice == "0":
        return

    if choice == "1":
        sessions = load_sessions()
        if not sessions:
            print(f"\n{C.YELLOW}[!] Yedeklenecek kayitli oturum bulunmuyor.{C.RESET}")
            safe_input("\nDevam etmek icin Enter'a basin...")
            return

        backup_file = BASE_DIR / f"ssh_backup_{int(time.time())}.json"
        try:
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=4, ensure_ascii=False)
            print(f"\n{C.GREEN}[✓] Yedek basariyla olusturuldu:{C.RESET} {C.BOLD}{backup_file.name}{C.RESET}")
        except Exception as e:
            print(f"\n{C.RED}[!] Yedek olusturulamadi: {e}{C.RESET}")
        safe_input("\nDevam etmek icin Enter'a basin...")

    elif choice == "2":
        import_path_str = prompt_non_empty("\nIce aktarilacak JSON dosya yolu: ", "Dosya yolu")
        p_imp = Path(import_path_str).expanduser().resolve()
        if not p_imp.exists():
            print(f"{C.RED}[!] Dosya bulunamadi: {p_imp}{C.RESET}")
            safe_input("\nDevam etmek icin Enter'a basin...")
            return

        try:
            with open(p_imp, "r", encoding="utf-8") as f:
                imported_data = json.load(f)
            
            curr_sessions = load_sessions()
            added_count = 0
            for name, s_val in imported_data.items():
                curr_sessions[name] = s_val
                generate_launchers(name)
                added_count += 1

            save_sessions(curr_sessions)
            print(f"\n{C.GREEN}[✓] {added_count} adet oturum basariyla ice aktarildi ve baslaticilari uretildi!{C.RESET}")
        except Exception as e:
            print(f"\n{C.RED}[!] Ice aktarma hatasi: {e}{C.RESET}")
        safe_input("\nDevam etmek icin Enter'a basin...")


def quick_connect_menu():
    clear_screen()
    print_banner()
    print(f"{C.BOLD}{C.CYAN}--- HIZLI SSH BAGLANTISI (KAYITSIZ) ---{C.RESET}\n")
    
    print("Giris yontemi:")
    print("  [1] Sirayla Adim Adim (Port -> Kullanici Adi -> IP -> Sifre)")
    print("  [2] Tek Satirda SSH Komutu (ssh -p 22 user123@123.45.67.89)")
    
    q_choice = prompt_choice(f"\n{C.BOLD}Seciminiz [1/2] (Varsayilan: 1): {C.RESET}", ["1", "2"], default="1")
    
    if q_choice == "2":
        ssh_input = prompt_non_empty("\nSSH Komutu / Adresi: ", "SSH komutu")
        parsed = parse_ssh_string(ssh_input)
        password = get_secure_password("Sifre: ")
        temp_data = {
            "host": parsed["host"],
            "port": parsed["port"],
            "username": parsed["username"],
            "auth_type": "password",
            "password": password,
            "commands": []
        }
    else:
        port = prompt_port("\nPort [Varsayilan: 22]: ", default=22)
        u_inp = safe_input("Kullanici Adi [Varsayilan: root]: ").strip()
        username = u_inp if u_inp else "root"
        host = prompt_non_empty("Sunucu IP / Host: ", "Sunucu IP adresi")
        password = get_secure_password("Sifre: ")
        temp_data = {
            "host": host,
            "port": port,
            "username": username,
            "auth_type": "password",
            "password": password,
            "commands": []
        }
    
    connect_to_session("Hizli Baglanti", temp_data)


def main():
    parser = argparse.ArgumentParser(description="SSH Oturum Yoneticisi ve Otomasyon Araci (Production Edition)")
    parser.add_argument("--connect", "-c", type=str, help="Belirtilen kayitli oturuma dogrudan baglan")
    args = parser.parse_args()

    if args.connect:
        connect_to_session(args.connect)
        return

    while True:
        clear_screen()
        print_banner()
        print(f"{C.BOLD}{C.WHITE}ANA MENU:{C.RESET}")
        print(f"  {C.GREEN}[1] Yeni SSH Oturumu ve Yonerge Olustur (Sifre / Key){C.RESET}")
        print(f"  {C.CYAN}[2] Kayitli Oturumlari Listele{C.RESET}")
        print(f"  {C.YELLOW}[3] Oturuma Baglan (Komutlari Calistir & Terminale Gec){C.RESET}")
        print(f"  {C.BLUE}[4] Oturum Duzenle / Yonergeleri Guncelle / Klonla{C.RESET}")
        print(f"  {C.RED}[5] Oturum Sil{C.RESET}")
        print(f"  {C.MAGENTA}[6] Hizli Baglanti (Kaydetmeden Baglan){C.RESET}")
        print(f"  {C.WHITE}[7] Oturum Yedekleme & Geri Yukleme (Export / Import){C.RESET}")
        print(f"  {C.DIM}[0] Cikis{C.RESET}\n")

        choice = prompt_choice(f"{C.BOLD}Seciminiz [0-7]: {C.RESET}", ["0", "1", "2", "3", "4", "5", "6", "7"])

        if choice == "1":
            create_session_menu()
        elif choice == "2":
            list_sessions_menu()
        elif choice == "3":
            select_and_connect_menu()
        elif choice == "4":
            edit_session_menu()
        elif choice == "5":
            delete_session_menu()
        elif choice == "6":
            quick_connect_menu()
        elif choice == "7":
            backup_restore_menu()
        elif choice == "0":
            print(f"\n{C.GREEN}[*] Program kapatildi. Iyi calismalar!{C.RESET}\n")
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{C.YELLOW}[*] Program kapatildi.{C.RESET}\n")
        sys.exit(0)
