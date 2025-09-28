# 📊 Interfaz de depuración GA Android

> 🇬🇧 For the English version, [click here](README.md)

Una herramienta de escritorio para inspeccionar logs de Firebase/Google Analytics desde dispositivos Android conectados, usando `adb logcat`.

## 🧰 Funcionalidades

- Interfaz intuitiva en **Tkinter**
- Visualización de:
  - Eventos (`Logging event`)
  - Propiedades del usuario (`Setting user property`)
  - Datos de consentimiento (`Setting storage consent`)
- Soporte multilenguaje (🇪🇸 Español, 🇺🇸 Inglés)
- Búsqueda y navegación por los logs
- Verificación de ADB y dispositivos conectados

---

## 📦 Requisitos

- Python 3.7 o superior
- ADB (Android Debug Bridge)
- Windows, Linux o macOS

---

## ⚙️ Instalación

### 1. Clonar o descargar el repositorio

```bash
git clone https://github.com/alejandro-reinoso/Android-ga-tracking-debugger.git
cd Android-ga-tracking-debugger
```

### 2. Instalar dependencias de Python

Este script sólo usa librerías estándar, no necesitas instalar nada más.

### 3. Instalar ADB

#### ✅ Opción rápida (recomendada)

Descargar **platform-tools** desde el sitio oficial:

📎 https://developer.android.com/tools/releases/platform-tools?hl=es-419

#### 🔧 Windows

1. Extrae el zip en una carpeta como `C:\platform-tools`
2. Agrega esa carpeta a tu variable `PATH`:
   - Panel de Control > Sistema > Configuración avanzada del sistema > Variables de entorno

#### 🔧 macOS / Linux

```bash
unzip platform-tools-latest-*.zip
sudo mv platform-tools /opt/
export PATH=$PATH:/opt/platform-tools
```

Verifica con:

```bash
adb version
```

---

## 🚀 Ejecutar

```bash
python main.py
```

El programa verificará:

- Si ADB está instalado
- Si hay un dispositivo o emulador conectado

---

## 🌐 Idiomas

Puedes cambiar entre español e inglés desde el menú `Languages`.

---

## 📂 Estructura del proyecto

El proyecto sigue una arquitectura Modelo-Vista-Controlador (MVC) para asegurar una clara separación de responsabilidades.

- main.py: Punto de entrada principal de la aplicación. Inicializa y ejecuta el Controlador.

- src/: Contiene el código fuente principal.

  - model.py: El Modelo, que gestiona el estado y la lógica de datos de la aplicación.

  - view.py: La Vista, que construye y gestiona la interfaz gráfica (GUI) con Tkinter.

  - adb_manager.py: Módulo dedicado a gestionar toda la comunicación con ADB.

  - log_parser.py: Se encarga de procesar las líneas de logcat.

  - config_manager.py: Gestiona la configuración del usuario.

  - i18n.py: Gestiona la internacionalización (traducciones).

- assets/: Contiene archivos estáticos como iconos e imágenes.

- locales.json: Almacena las cadenas de texto para el soporte multilenguaje.

- config.json: Guarda la configuración del usuario, como el idioma seleccionado.

---

## 👨‍💻 Autor

**Alejandro Reinoso**  
🔗 [LinkedIn](https://www.linkedin.com/in/alejandroreinosogomez/)  
📬 [Contacto](https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger)
