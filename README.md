# 🚀 SSH Terminal & Server Automation Manager

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**SSH Terminal & Server Automation Manager**, SSH bağlantılarınızı ve sunucu otomasyonlarınızı tek bir merkezden yönetmenizi sağlayan güçlü, renkli ve zengin özellikli bir konsol uygulamasıdır.

---

## 🌟 Öne Çıkan Özellikler

- **🔑 Çoklu Oturum ve Kimlik Yönetimi:**
  - Şifre (Password) veya SSH Özel Anahtar (Private Key & Passphrase) ile oturum yönetimi.
  - Sınırsız oturum ekleme, düzenleme, klonlama ve silme.

- **⚡ Otomatik Komut & Yönerge İcrası:**
  - Her oturum için önceden tanımlanmış komut dizileri (örn. `cd /var/www`, `git pull`, `docker compose up -d`).
  - Komutlar tamamlandıktan sonra otomatik olarak kesintisiz, interaktif SSH terminaline geçiş.

- **🎯 Akıllı SSH Bağlantı Ayrıştırıcı (Smart Parser):**
  - Standart bağlantı formatlarını otomatik tanır:  
    `ssh -p 2222 root@192.168.1.100` veya `user@example.com:2200`

- **🛡️ Güvenlik ve Şifreleme (Obfuscation):**
  - Hassas şifreler ve anahtar parolaları yerel oturum dosyasında düz metin (plain-text) olarak saklanmaz.

- **🖥️ Çift Tıklanabilir Başlatıcılar ve Masaüstü Kısayolları:**
  - Kaydedilen her sunucu için tek tıkla bağlanabileceğiniz `.bat` başlatıcıları ve Windows Masaüstü kısayolları (`.lnk`).

- **📦 Taşınabilir EXE ve Kurulum Sihirbazı:**
  - Python bağımlılığı olmadan her Windows bilgisayarda çalıştırılabilen tek dosya (`SSHTerminal.exe`) ve kurulum paketi (`SSHTerminal_Setup.exe`).

- **🔄 Yedekleme & Geri Yükleme (Export / Import):**
  - Kayıtlı oturumlarınızı kolayca JSON olarak yedekleme ve başka sistemlere aktarma.

---

## 📂 Proje Yapısı

```
.
├── server.py              # Ana SSH oturum ve otomasyon konsol uygulaması
├── installer.py           # Windows kurulum ve kısayol sihirbazı
├── build_release.bat      # Tek tıkla Portable EXE ve Setup derleme aracı
├── app.manifest           # Windows UTF-8 ve yüksek DPI uyumluluk bildirgesi
├── app_icon.ico           # Uygulama simgesi
├── version_info.txt       # Windows PE sürüm ve telif bilgileri
├── requirements.txt       # Python bağımlılıkları
├── .gitignore             # Git yoksayma kuralları
└── README.md              # Proje dokümantasyonu
```

---

## 🛠️ Kurulum

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/KULLANICI_ADI/REPO_ADI.git
cd REPO_ADI
```

### 2. Gerekli Paketleri Yükleyin
```bash
pip install -r requirements.txt
```

---

## 💻 Kullanım

### İnteraktif Ana Menü
Uygulamayı başlatmak için:
```bash
python server.py
```

### Doğrudan Kayıtlı Bir Oturuma Bağlanma
```bash
python server.py --connect "Sunucu_Adi"
```

---

## 🔨 EXE ve Kurulum Paketi Derleme

Projeyi Python gerektirmeyen bağımsız bir Windows `.exe` haline getirmek için:

1. `build_release.bat` dosyasına çift tıklayın veya terminalden çalıştırın:
```cmd
build_release.bat
```
2. Derleme tamamlandığında `dist/` klasörü altında aşağıdaki dosyalar üretilecektir:
   - **`dist/SSHTerminal.exe`**: Taşınabilir (portable), tek dosya uygulama.
   - **`dist/SSHTerminal_Setup.exe`**: Masaüstü ve Başlat Menüsü kısayollarını otomatik oluşturan kurulum sihirbazı.

---

## 🔒 Güvenlik Notu

- Yerel oturumlar `ssh_sessions.json` dosyasında saklanır ve bu dosya `.gitignore` listesine eklenmiştir.
- Gerçek sunucu giriş bilgilerinizi, şifrelerinizi ve özel anahtarlarınızı GitHub veya halka açık ortamlara yüklemeyiniz.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.
