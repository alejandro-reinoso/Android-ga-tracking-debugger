# 📊 Android GA Debugger GUI

> 🇪🇸 Looking for the Spanish version? [Click here](README.es.md)

A desktop tool that lets you inspect Firebase/Google Analytics logs from connected Android devices using `adb logcat`.

## 🧰 Main Features

- Intuitive **Tkinter** GUI
- Visualizes:
  - Events (`Logging event`)
  - User properties (`Setting user property`)
  - Consent data (`Setting storage consent`)
- Multi-language support (🇪🇸 Spanish, 🇺🇸 English)
- Log search and navigation
- ADB and device connection checks

---

## 📦 Requirements

- Python 3.7+
- ADB (Android Debug Bridge)
- OS: Windows, Linux, or macOS

---

## ⚙️ Installation

### 1. Clone or download this repo

```bash
git clone https://github.com/youruser/ga-debugger.git
cd ga-debugger
```

### 2. Install Python dependencies

No external packages required – uses only standard Python libraries.

### 3. Install ADB

#### ✅ Quick way (recommended)

Download **platform-tools** from the official site:

📎 https://developer.android.com/tools/releases/platform-tools

#### 🔧 Windows

1. Unzip into a folder like `C:\platform-tools`
2. Add it to your system `PATH`:
   - Control Panel > System > Advanced system settings > Environment Variables
   - Edit `PATH` and add `C:\platform-tools`

#### 🔧 macOS / Linux

```bash
# Extract the zip
unzip platform-tools-latest-*.zip

# Move it globally (optional)
sudo mv platform-tools /opt/

# Add to PATH (in ~/.bashrc, ~/.zshrc, etc.)
export PATH=$PATH:/opt/platform-tools
```

Then check:

```bash
adb version
```

---

## 🚀 Run the App

```bash
python analytics-debuger.py
```

It will auto-check:

- If ADB is installed
- If an Android device/emulator is connected

---

## 🌐 Languages

You can switch between English and Spanish in the `Languages` menu.

---

## 📂 Project Structure

- `analytics-debuger.py`: main application
- `locales.json`: translation file (optional)
- `config.json`: auto-generated config file

---

## 👨‍💻 Author

**Alejandro Reinoso**  
🔗 [LinkedIn](https://www.linkedin.com/in/alejandroreinosogomez/)  
📬 [Contact](https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger)
