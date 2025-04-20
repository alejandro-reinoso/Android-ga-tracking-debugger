import os
import json
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, Menu
import re
import webbrowser
import requests
import gettext


# -----------------------------------------------------
# i18n - manejo de traducciones
# -----------------------------------------------------
TRANSLATIONS = {}
CURRENT_LANG = "en"  # Usaremos inglés como fallback predeterminado

def load_translations():
    """Carga las traducciones desde el archivo locales.json"""
    global TRANSLATIONS

    if not os.path.exists("locales.json"):
        print("No se encontró 'locales.json'; se usarán literales en duro.")
        TRANSLATIONS = {}
        return

    with open("locales.json", "r", encoding="utf-8") as f:
        TRANSLATIONS = json.load(f)

def set_language(lang):
    """Cambia el idioma actual (p. ej. 'es', 'en', etc.)."""
    global CURRENT_LANG
    CURRENT_LANG = lang

def _(key):
    """
    Devuelve el texto traducido según la clave y el idioma actual.
    Si no existe, retorna la propia clave como fallback.
    """
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)

# -----------------------------------------------------
# Actualizar textos según idioma
# -----------------------------------------------------
def refresh_ui_texts():
    # Textos menu superior
    menubar.entryconfig(1, label=_("menu.languages"))  # Actualiza el nombre del menú de idiomas
    menubar.entryconfig(2, label=_("menu.license"))    # Actualiza el nombre del menú de licencia
    menubar.entryconfig(3, label=_("menu.help"))       # Actualiza el nombre del menú de ayuda

    # Actualizar los textos de los submenús
    filemenu.entryconfig(0, label=_("menu.spanish"))  
    filemenu.entryconfig(1, label=_("menu.english"))  

    editmenu.entryconfig(0, label=_("menu.buy_licence"))  

    helpmenu.entryconfig(0, label=_("menu.user_guide"))  
    helpmenu.entryconfig(1, label=_("menu.support"))  
    helpmenu.entryconfig(2, label=_("menu.feedback"))  
    helpmenu.entryconfig(4, label=_("menu.check_updates"))  
    helpmenu.entryconfig(6, label=_("menu.about_me"))  

    # Botones superiores
    start_button.config(text=_("menu.start_log"))
    stop_button.config(text=_("menu.stop_log"))
    clear_button.config(text=_("menu.clear_all"))

    # Email, licencias
    email_label.config(text=_("license.email"))
    license_label.config(text=_("license.license"))
    btn_check_license.config(text=_("license.check"))
    btn_renew.config(text=_("license.renew_buy"))
    on_check_license()

    if not license_is_active:
        license_status_label.config(text=_("license.unverified"), fg="gray")

    events_title.config(text=_("events.title"))
    user_props_title.config(text=_("user_props.title"))
    consent_title.config(text=_("consent.title"))

    # Búsqueda
    search_label.config(text=_("search.label"))
    search_button.config(text=_("search.button"))
    first_button.config(text=_("search.first"))
    prev_button.config(text=_("search.previous"))
    next_button.config(text=_("search.next"))
    last_button.config(text=_("search.last"))
    jump_button.config(text=_("search.goto_button"))
    search_goto_label.config(text=_("search.goto_label"))


    consent_tree.heading("datetime", text=_("consent.datetime"))
    consent_tree.heading("ad_storage", text=_("consent.ad_storage"))
    consent_tree.heading("analytics_storage", text=_("consent.analytics_storage"))
    consent_tree.heading("ad_user_data", text=_("consent.ad_user_data"))
    consent_tree.heading("ad_personalization", text=_("consent.ad_personalization"))

def on_language_change(new_lang):
    """Cuando se cambia el idioma en el ComboBox, refresca textos y guarda en config.json."""
    set_language(new_lang)
    refresh_ui_texts()

    # Guardar en config.json
    config_data["language"] = new_lang
    save_config(config_data)

# -----------------------------------------------------
# Variables / Estructuras globales
# -----------------------------------------------------
CONFIG_FILE = "config.json"

logcat_process = None
stop_thread = False
log_queue = queue.Queue()

events_data = []         # Para “Logging event:”
user_properties = {}     # {propName: propValue}
current_consent = {      # Estado actual (se actualiza cada vez que parseamos “Setting storage consent” / “DMA consent”)
    "ad_storage": None,
    "analytics_storage": None,
    "ad_user_data": None,
    "ad_personalization": None,
}

search_matches = []
current_match_index = -1

# Para la tabla de consentimiento, si llega otro log con la misma fecha/hora, se reemplaza
consent_entries = {}  # dict fecha/hora => item_id del Treeview

# -----------------------------------------------------
# LÓGICA DE LICENCIA
# -----------------------------------------------------
license_is_active = False

import requests

def check_license(email, license_code):
    """
    Verifica la licencia con la API REST de WordPress.
    Realiza una solicitud GET a la API y devuelve True si la licencia es válida.
    """
    url = "https://alejandroreinoso.com/wp-json/license/v1/check/"
    params = {"email": email, "license_key": license_code}

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if response.status_code == 200 and data.get("message") == "Licencia válida":
            return True
        else:
            print(f"Error: {data.get('message', 'No se pudo verificar la licencia')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        return False

def load_config():
    """Lee el archivo config.json y devuelve un dict con los datos; 
       si no existe o está corrupto, devuelve {}."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except:
            return {}
    else:
        return {}

def save_config(config):
    """Guarda el dict 'config' en config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def on_check_license():
    """
    Cuando el usuario pulse "Verificar Licencia" se llama a check_license(...) 
    y se actualiza el label de estado, habilitando o no el botón "Iniciar Log".
    """
    global license_is_active
    email = email_entry.get().strip()
    code = license_entry.get().strip()
    if not email or not code:
        license_status_label.config(text=_("license.missing_data"), fg="red")
        license_is_active = False
        start_button.config(state=tk.DISABLED)
        return

    # Llamamos a la función que consulta la licencia
    active = check_license(email, code)
    if active:
        license_is_active = True
        license_status_label.config(text=_("license.active"), fg="green")
        start_button.config(state=tk.NORMAL)  # Permite iniciar log

        # Almacenar en config.json
        config_data["email"] = email
        config_data["license_code"] = code
        save_config(config_data)
    else:
        license_is_active = False
        license_status_label.config(text=_("license.inactive"), fg="red")
        start_button.config(state=tk.DISABLED)

def on_buy_renew_click():
    """
    Abre el navegador apuntando a tu web (p.ej. link de compra de licencias).
    """
    webbrowser.open("https://alejandroreinoso.com/renovar-o-comprar")

# -----------------------------------------------------
# HILO de lectura ADB
# -----------------------------------------------------
def reader_thread():
    global stop_thread, logcat_process
    while not stop_thread and logcat_process and logcat_process.poll() is None:
        line = logcat_process.stdout.readline()
        if not line:
            break
        line = line.rstrip('\n')
        log_queue.put(line)

def stderr_reader_thread():
    global logcat_process, stop_thread
    while not stop_thread and logcat_process and logcat_process.poll() is None:
        line_err = logcat_process.stderr.readline()
        if not line_err:
            break
        line_err = line_err.strip()

        # Reaccionar si aparece "more than one device/emulator"
        if "more than one device/emulator" in line_err.lower():
            # Avisamos en la interfaz (o con messagebox)
            messagebox.showerror(
                "ADB: varios dispositivos",
                "Se ha detectado más de un dispositivo/emulador conectado.\n"
                "Por favor, mantén conectado solo el que deseas depurar."
            )
            # Detengo el log en caso de error:
            stop_logging()
            return


def check_log_queue():
    while not log_queue.empty():
        line = log_queue.get_nowait()

        # 1) Mostrar en la consola
        text_area.insert(tk.END, line + "\n")
        text_area.see(tk.END)

        # 2) “Logging event:”
        if "Logging event:" in line:
            ev = parse_logging_event_line(line)
            if ev:
                events_data.append(ev)
                insert_event_in_tree(ev)

        # 3) “Setting user property:” (excluyendo "storage consent"/"DMA consent")
        #if "Setting user property:" in line and "storage consent" not in line and "DMA consent" not in line:
        if "Setting user property:" in line or "Setting user property(FE):" in line:
            up = parse_user_property_line(line)
            if up:
                user_properties[up["name"]] = up["value"]
                refresh_user_props_tree()

        # 4) “Setting storage consent” / “Setting DMA consent”
        if ("Setting storage consent" in line) or ("Setting DMA consent" in line) or ("non_personalized_ads" in line):
            c = parse_consent_line(line)
            if c:
                fill_missing_consent_fields(c)
                deduce_ad_personalization(c)
                # Actualizamos el estado actual
                current_consent.update(c)
                # Insertar en la tabla de consentimiento (reemplazando si dt coincide)
                insert_consent_in_tree(c)

    root.after(100, check_log_queue)

def check_adb_installed():
    """
    Verifica si ADB está instalado intentando ejecutar 'adb version'.
    Retorna True si puede ejecutarlo, False en caso contrario.
    """
    try:
        # Intentamos obtener la versión; si no existe 'adb', lanzará FileNotFoundError
        subprocess.check_output(["adb", "version"], stderr=subprocess.STDOUT)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    
def show_adb_install_dialog():
    """
    Muestra una ventana emergente (Toplevel) con botones que llevan a:
    - Descargar ADB desde la página oficial de Google
    - Tu guía de instalación
    """
    dialog = tk.Toplevel()
    dialog.title("ADB no encontrado")

    msg_label = tk.Label(
        dialog, 
        text=(
            "No se ha encontrado ADB en tu sistema.\n"
            "Debes instalarlo para poder usar esta herramienta.\n"
            "Revisa los siguientes enlaces de instalación:"
        )
    )
    msg_label.pack(pady=10, padx=10)

    # Botón para abrir link oficial de Google
    google_button = tk.Button(
        dialog, 
        text="Descargar ADB (Google)", 
        command=lambda: webbrowser.open("https://developer.android.com/tools/releases/platform-tools?hl=es-419")
    )
    google_button.pack(pady=5)

    # Botón para abrir tu guía de instalación
    reinoso_button = tk.Button(
        dialog, 
        text="Guía de instalación (alejandroreinoso.com)", 
        command=lambda: webbrowser.open("https://alejandroreinoso.com")
    )
    reinoso_button.pack(pady=5)

    close_button = tk.Button(
        dialog, 
        text="Cerrar", 
        command=dialog.destroy
    )
    close_button.pack(pady=10)


# -----------------------------------------------------
# Revisar dispositivos conectados
# -----------------------------------------------------

def check_device_connected():
    """
    Ejecuta 'adb devices' y verifica si hay al menos un dispositivo/emulador conectado.
    Retorna True si encuentra alguno, False en caso contrario.
    """
    try:
        result = subprocess.check_output(["adb", "devices"], stderr=subprocess.STDOUT, universal_newlines=True)
        lines = result.strip().split('\n')

        # La primera línea suele ser: "List of devices attached"
        # A partir de la segunda, cada línea representa un dispositivo (id + estado).
        if len(lines) > 1:
            # Filtramos líneas vacías o las que empiezan con "* daemon"
            device_lines = [
                l for l in lines[1:] 
                if l.strip() != '' and not l.startswith('* daemon')
            ]
            # Cada línea con un dispositivo válido normalmente es algo como:
            # "emulator-5554    device" o "0123456789ABCDEF    device"
            # o "0123456789ABCDEF    unauthorized" ...
            # Aquí podrías afinar qué estados aceptas (device, emulator, etc.)
            for dev in device_lines:
                parts = dev.split()
                # parts[0] = ID del dispositivo, parts[1] = estado
                if len(parts) >= 2:
                    state = parts[1].lower()
                    # Consideramos "device" o "emulator" como conectados válidos
                    if state == "device":
                        return True
        # Si llegamos hasta aquí, no hay dispositivos válidos
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Si ADB no está instalado o falla
        return False

def show_no_device_dialog():
    """
    Muestra una ventana emergente avisando que no se detectó ningún dispositivo/emulador.
    """
    dialog = tk.Toplevel()
    dialog.title("Dispositivo no encontrado")

    msg_label = tk.Label(
        dialog, 
        text=(
            "No se ha encontrado ningún dispositivo o emulador conectado.\n"
            "Conecta un dispositivo físico o inicia un emulador antes de continuar."
        )
    )
    msg_label.pack(pady=10, padx=10)

    close_button = tk.Button(dialog, text="Cerrar", command=dialog.destroy)
    close_button.pack(pady=10)

    # Evitar usar la ventana principal mientras esté abierta esta
    dialog.grab_set()
    dialog.focus_set()

# -----------------------------------------------------
# Funciones “Iniciar/Detener” y “Limpiar”
# -----------------------------------------------------
def start_logging():
    global stop_thread, logcat_process
    # Verificamos que licencia esté activa
    if not license_is_active:
        # No hacemos nada, o mensaje
        text_area.insert(tk.END, "No se puede iniciar Log. Licencia inactiva.\n")
        text_area.see(tk.END)
        return
    
    # Verificamos si ADB está instalado
    if not check_adb_installed():
        # Mostramos la ventana de ayuda para instalar ADB
        show_adb_install_dialog()
        return
    
    # Verificamos si hay al menos un dispositivo/emulador
    if not check_device_connected():
        show_no_device_dialog()
        return

    stop_thread = False
    subprocess.run(["adb", "shell", "setprop", "log.tag.FA", "VERBOSE"])
    subprocess.run(["adb", "shell", "setprop", "log.tag.FA-SVC", "VERBOSE"])
    subprocess.run(["adb", "logcat", "-c"])  # Opcional (limpia buffer)

    logcat_process = subprocess.Popen(
        ["adb", "logcat", "-v", "time", "-s", "FA", "FA-SVC"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )

    # Hilo lector de STDOUT
    t_stdout  = threading.Thread(target=reader_thread, daemon=True)
    t_stdout .start()

    # Hilo lector de STDERR
    t_stderr = threading.Thread(target=stderr_reader_thread, daemon=True)
    t_stderr.start()

    # Iniciar loop de check cola
    check_log_queue()

def stop_logging():
    global logcat_process, stop_thread
    stop_thread = True
    if logcat_process and logcat_process.poll() is None:
        logcat_process.terminate()
        logcat_process = None
    text_area.insert(tk.END, "\n--- Logging detenido ---\n")
    text_area.see(tk.END)

def clear_all():
    global current_consent, consent_entries

    # Consola
    text_area.delete("1.0", tk.END)
    # Eventos
    events_data.clear()
    for it in events_tree.get_children():
        events_tree.delete(it)
    # User props
    user_properties.clear()
    for it in user_props_tree.get_children():
        user_props_tree.delete(it)
    # Consent
    current_consent = {
        "ad_storage": None,
        "analytics_storage": None,
        "ad_user_data": None,
        "ad_personalization": None,
    }
    for it in consent_tree.get_children():
        consent_tree.delete(it)
    consent_entries.clear()

# -----------------------------------------------------
# PARSEOS
# -----------------------------------------------------
def parse_logging_event_line(line):
    datetime_str = line[:18].strip()
    name_match = re.search(r"name=([^,]+)", line)
    params_match = re.search(r"params=Bundle\[\{(.*)\}\]", line)
    if not name_match or not params_match:
        return None
    event_name = name_match.group(1).strip()
    params_str = params_match.group(1).strip()

    params_dict = {}
    raw_pairs = params_str.split(',')
    for pair in raw_pairs:
        pair = pair.strip()
        if '=' in pair:
            k,v = pair.split('=',1)
            params_dict[k.strip()] = v.strip()

    return {
        "datetime": datetime_str,
        "name": event_name,
        "params": params_dict
    }

def parse_user_property_line(line):
    pat = r"Setting user property:\s+([^,]+),\s+(.*)"
    m = re.search(pat, line)
    if not m:
        #pat_fe = r"Setting user property(FE):\s+([^,]+),\s+(.*)"
        pat_fe = r"Setting user property\s*\(FE\):\s+([^,]+),\s+(.*)"
        m = re.search(pat_fe, line)
        if not m:
            return None
    
    return {
        "name": m.group(1).strip(),
        "value": m.group(2).strip()
    }

def parse_consent_line(line):
    datetime_str = line[:18].strip()
    found = re.findall(r'(\w+)=(\w+)', line)
    cdict = {
        "datetime": datetime_str,
        "ad_storage": None,
        "analytics_storage": None,
        "ad_user_data": None,
        "ad_personalization": None,
    }
    for (k,v) in found:
        if k in cdict:  # ad_storage, analytics_storage, ad_user_data, ad_personalization
            cdict[k] = v
    # Si no hay nada, return None
    if (cdict["ad_storage"] is None
        and cdict["analytics_storage"] is None
        and cdict["ad_user_data"] is None):
        return None
    return cdict

# -----------------------------------------------------
# COMPLETAR LOGICA DE CONSENT
# -----------------------------------------------------
def fill_missing_consent_fields(c):
    """Rellena campos de c con el 'current_consent' si no aparecen, 
       ad_user_data => si no hay anterior => ad_storage."""
    if c["ad_storage"] is None:
        c["ad_storage"] = current_consent["ad_storage"]
    if c["analytics_storage"] is None:
        c["analytics_storage"] = current_consent["analytics_storage"]
    if c["ad_user_data"] is None:
        if current_consent["ad_user_data"] is not None:
            c["ad_user_data"] = current_consent["ad_user_data"]
        else:
            c["ad_user_data"] = c["ad_storage"]

def deduce_ad_personalization(c):
    """Usamos 'non_personalized_ads(_npa)' => 1 => denied, 0 => granted. 
       Si no hay => valor anterior, si no => ad_storage."""
    # Buscar la key para 'non_personalized_ads'
    print("revisar non_personalized_ads")
    npa_key = None
    for k in user_properties:
        if "non_personalized_ads" in k:
            npa_key = k
            break
    if npa_key:
        val = user_properties[npa_key].strip()
        if val == '1':
            c["ad_personalization"] = "denied"
        elif val == '0':
            c["ad_personalization"] = "granted"
        else:
            # fallback
            if current_consent["ad_personalization"] is not None:
                c["ad_personalization"] = current_consent["ad_personalization"]
            else:
                c["ad_personalization"] = c["ad_storage"]
    else:
        # no npa key => fallback
        if current_consent["ad_personalization"] is not None:
            c["ad_personalization"] = current_consent["ad_personalization"]
        else:
            c["ad_personalization"] = c["ad_storage"]

# -----------------------------------------------------
# INSERCION EN LOS TREEVIEWS
# -----------------------------------------------------
def insert_event_in_tree(ev):
    dt = ev["datetime"]
    name = ev["name"]
    params = ev["params"]

    parent_id = events_tree.insert("", tk.END, text=f"{dt} - {name}")
    for k,v in params.items():
        events_tree.insert(parent_id, tk.END, text=f"{k} = {v}")

def insert_consent_in_tree(cdict):
    """
    cdict => {datetime, ad_storage, analytics_storage, ad_user_data, ad_personalization}
    Si ya hay un row con la misma datetime => lo eliminamos y reinsertamos
    """
    dt = cdict["datetime"]
    ad_storage = cdict["ad_storage"] or ""
    analytics_storage = cdict["analytics_storage"] or ""
    ad_user_data = cdict["ad_user_data"] or ""
    ad_personalization = cdict["ad_personalization"] or ""

    # Si ya existe un row con esa dt, lo borramos
    if dt in consent_entries:
        old_item = consent_entries[dt]
        consent_tree.delete(old_item)

    # Insertar row
    new_item = consent_tree.insert(
        "",
        tk.END,
        values=(dt, ad_storage, analytics_storage, ad_user_data, ad_personalization)
    )
    # Guardar en consent_entries
    consent_entries[dt] = new_item

def refresh_user_props_tree():
    for item in user_props_tree.get_children():
        user_props_tree.delete(item)
    for prop_name, prop_val in user_properties.items():
        user_props_tree.insert("", tk.END, text=f"{prop_name} = {prop_val}")

# -----------------------------------------------------
# Búsqueda en el text_area
# -----------------------------------------------------
def search_logs():
    global search_matches, current_match_index
    text_area.tag_remove("search_highlight", "1.0", tk.END)
    text_area.tag_remove("search_current", "1.0", tk.END)
    search_matches.clear()
    current_match_index = -1

    term = search_entry.get().strip()
    if not term:
        update_match_label(0, 0)
        return

    start_pos = "1.0"
    while True:
        pos = text_area.search(term, start_pos, stopindex=tk.END)
        if not pos:
            break
        end_pos = f"{pos}+{len(term)}c"
        search_matches.append((pos, end_pos))
        text_area.tag_add("search_highlight", pos, end_pos)
        start_pos = end_pos

    text_area.tag_config("search_highlight", background="yellow", foreground="black")

    total = len(search_matches)
    if total > 0:
        current_match_index = 0
        highlight_current_match()
    else:
        update_match_label(0, 0)

def highlight_current_match():
    global current_match_index, search_matches
    text_area.tag_remove("search_current", "1.0", tk.END)
    total = len(search_matches)
    if total == 0 or current_match_index < 0 or current_match_index >= total:
        update_match_label(0, total)
        return

    start_pos, end_pos = search_matches[current_match_index]
    text_area.tag_add("search_current", start_pos, end_pos)
    text_area.tag_config("search_current", background="orange", foreground="black")
    text_area.see(start_pos)
    update_match_label(current_match_index + 1, total)

def next_match():
    global current_match_index, search_matches
    if search_matches and current_match_index < len(search_matches) - 1:
        current_match_index += 1
        highlight_current_match()

def prev_match():
    global current_match_index, search_matches
    if search_matches and current_match_index > 0:
        current_match_index -= 1
        highlight_current_match()

def jump_to_first():
    global current_match_index
    if search_matches:
        current_match_index = 0
        highlight_current_match()

def jump_to_last():
    global current_match_index, search_matches
    if search_matches:
        current_match_index = len(search_matches) - 1
        highlight_current_match()

def jump_to_index():
    global current_match_index, search_matches
    if not search_matches:
        return
    try:
        idx = int(index_entry.get()) - 1
    except ValueError:
        return
    idx = max(0, min(idx, len(search_matches) - 1))
    current_match_index = idx
    highlight_current_match()

def update_match_label(current, total):
    match_label.config(text=f"{current} / {total}")

# -----------------------------------------------------
# Construcción de la Interfaz
# -----------------------------------------------------
# 1) Cargar traducciones
load_translations()

# 2) Cargar config
config_data = load_config()
# Si en config_data hay "language", lo asignamos, sino "en"
default_lang_code = config_data.get("language", "en")
set_language(default_lang_code)

root = tk.Tk()
root.title("Debug Google Analytics (Alejandro Reinoso)")
root.iconbitmap("logo-alejandro-reinoso.ico")

# Valor por defecto licensia
license_is_active = False

main_paned = tk.PanedWindow(root, orient=tk.VERTICAL, sashwidth=8, sashrelief="raised")
main_paned.pack(fill=tk.BOTH, expand=True)

# --- MENU: Idiomas, Licencia, aYUDA ---
menubar = Menu(root)
root.config(menu=menubar)

filemenu = Menu(menubar, tearoff=0)
filemenu.add_command(label=_("menu.spanish"), command=lambda: on_language_change("es"))
filemenu.add_command(label=_("menu.english"), command=lambda: on_language_change("en"))

editmenu = Menu(menubar, tearoff=0)
editmenu.add_command(label=_("menu.buy_licence"), command=on_buy_renew_click)
#editmenu.add_command(label="Indicar licencia")

helpmenu = Menu(menubar, tearoff=0)
helpmenu.add_command(label=_("menu.user_guide"))
helpmenu.add_command(label=_("menu.support"))
helpmenu.add_command(label=_("menu.feedback"))
helpmenu.add_separator()
helpmenu.add_command(label=_("menu.check_updates"))
#helpmenu.add_command(label="Comprobar actualizaciones automáticamente")
helpmenu.add_separator()
helpmenu.add_command(label=_("menu.about_me"))

menubar.add_cascade(label=_("menu.languages"), menu=filemenu)
menubar.add_cascade(label=_("menu.license"), menu=editmenu)
menubar.add_cascade(label=_("menu.help"), menu=helpmenu)

# --- FRAME SUPERIOR: email, license, estado de licencia ---
top_frame = tk.Frame(main_paned, bd=2, relief="groove")
main_paned.add(top_frame, minsize=50)

# Frame IZQUIERDA: para “Iniciar Log”, “Detener Log”, “Limpiar Todo”
buttons_frame = tk.Frame(top_frame)
buttons_frame.pack(side=tk.LEFT, padx=10, pady=10)

start_button = tk.Button(buttons_frame, text=_("menu.start_log"), command=start_logging, state=tk.DISABLED)
start_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(buttons_frame, text=_("menu.stop_log"), command=stop_logging)
stop_button.pack(side=tk.LEFT, padx=5)

clear_button = tk.Button(buttons_frame, text=_("menu.clear_all"), command=clear_all)
clear_button.pack(side=tk.LEFT, padx=5)

# Frame DERECHA: para Email, Licencia, Estado y Botones “Verificar” / “Renovar/Comprar”
license_frame = tk.Frame(top_frame)
license_frame.pack(side=tk.RIGHT, padx=10, pady=10)

# Fila 1: Email + Licencia Activa + Botón “Renovar”
email_label = tk.Label(license_frame, text="Email:")
email_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")

email_entry = tk.Entry(license_frame, width=30)
email_entry.grid(row=0, column=1, padx=5, pady=5)

license_status_label = tk.Label(license_frame, text=_("license.unverified"), fg="gray")
license_status_label.grid(row=0, column=2, padx=10, pady=5, sticky="w")

btn_renew = tk.Button(license_frame, text=_("license.renew_buy"), command=on_buy_renew_click)
btn_renew.grid(row=0, column=3, padx=5, pady=5)

# Fila 2: Licencia + Botón “Verificar Licencia”
license_label = tk.Label(license_frame, text=_("license.license"))
license_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")

license_entry = tk.Entry(license_frame, width=30)
license_entry.grid(row=1, column=1, padx=5, pady=5)

btn_check_license = tk.Button(license_frame, text=_("license.check"), command=on_check_license)
btn_check_license.grid(row=1, column=2, padx=10, pady=5, sticky="w")

# Restaurar valores previos (si existen en config)
if "email" in config_data:
    email_entry.insert(0, config_data["email"])
if "license_code" in config_data:
    license_entry.insert(0, config_data["license_code"])

if "email" in config_data and "license_code" in config_data:
    on_check_license()

# --- FRAME INTERMEDIO -> subdiv (izq, der) ---
middle_frame = tk.Frame(main_paned, bd=2, relief="groove")
main_paned.add(middle_frame, minsize=150)

left_frame = tk.Frame(middle_frame, bg="white")
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

user_props_title = tk.Label(left_frame, text=_("user_props.title"), bg="white")
user_props_title.pack(anchor="w")
user_props_tree = ttk.Treeview(left_frame)
user_props_tree.pack(fill=tk.BOTH, expand=True)

consent_title = tk.Label(left_frame, text=_("consent.title"), bg="white")
consent_title.pack(anchor="w")
consent_tree = ttk.Treeview(
    left_frame, 
    columns=("datetime","ad_storage","analytics_storage","ad_user_data","ad_personalization"), 
    show="headings"
)
consent_tree.pack(fill=tk.BOTH, expand=True)
consent_tree.heading("datetime", text="DateTime")
consent_tree.heading("ad_storage", text="ad_storage")
consent_tree.heading("analytics_storage", text="analytics_storage")
consent_tree.heading("ad_user_data", text="ad_user_data")
consent_tree.heading("ad_personalization", text="ad_personalization")

consent_tree.column("datetime", width=130)
consent_tree.column("ad_storage", width=90)
consent_tree.column("analytics_storage", width=120)
consent_tree.column("ad_user_data", width=120)
consent_tree.column("ad_personalization", width=130)

right_frame = tk.Frame(middle_frame, bg="white")
right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

events_title = tk.Label(right_frame, text=_("events.title"), bg="white")
events_title.pack(anchor="w")
events_tree = ttk.Treeview(right_frame)
events_tree.pack(fill=tk.BOTH, expand=True)

# --- FRAME INFERIOR -> consola + búsqueda
bottom_frame = tk.Frame(main_paned, bd=2, relief="sunken")
main_paned.add(bottom_frame, minsize=50)

frame_search = tk.Frame(bottom_frame)
frame_search.pack(pady=5, fill=tk.X)

search_label = tk.Label(frame_search, text=_("search.label"))
search_label.pack(side=tk.LEFT)
search_entry = tk.Entry(frame_search, width=30)
search_entry.pack(side=tk.LEFT, padx=5)

search_button = tk.Button(frame_search, text=_("search.button"), command=search_logs)
search_button.pack(side=tk.LEFT, padx=5)

first_button = tk.Button(frame_search, text="|<<", command=jump_to_first)
first_button.pack(side=tk.LEFT, padx=2)

prev_button = tk.Button(frame_search, text="<<", command=prev_match)
prev_button.pack(side=tk.LEFT, padx=2)

match_label = tk.Label(frame_search, text="0 / 0")
match_label.pack(side=tk.LEFT, padx=10)

next_button = tk.Button(frame_search, text=">>", command=next_match)
next_button.pack(side=tk.LEFT, padx=2)

last_button = tk.Button(frame_search, text=">>|", command=jump_to_last)
last_button.pack(side=tk.LEFT, padx=2)

search_goto_label = tk.Label(frame_search, text=_("search.goto_label"))
search_goto_label.pack(side=tk.LEFT, padx=5)
index_entry = tk.Entry(frame_search, width=5)
index_entry.pack(side=tk.LEFT)
jump_button = tk.Button(frame_search, text=_("search.goto_button"), command=jump_to_index)
jump_button.pack(side=tk.LEFT, padx=5)

text_area = scrolledtext.ScrolledText(bottom_frame, width=100, height=10)
text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

# Forzamos el refresh de textos según el idioma default_lang_code
refresh_ui_texts()

root.mainloop()