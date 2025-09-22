import sys, os
import json
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, Menu
import re
import webbrowser
from src.i18n import load_translations, set_language, _
from src.utils import resource_path


# Solo definimos el flag una vez, es 0 en Linux/Mac
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# -----------------------------------------------------
# Update UI Texts According to Current Language
# -----------------------------------------------------

def refresh_ui_texts():
    """
    Refresh all UI texts based on current language selection.
    """
    # Menu
    menubar.entryconfig(1, label=_("menu.languages"))
    menubar.entryconfig(3, label=_("menu.help"))

    # Submenu
    filemenu.entryconfig(0, label=_("menu.spanish"))
    filemenu.entryconfig(1, label=_("menu.english"))

    #helpmenu.entryconfig(0, label=_("menu.user_guide"))
    helpmenu.entryconfig(0, label=_("menu.support"))
    helpmenu.entryconfig(1, label=_("menu.feedback"))
    helpmenu.entryconfig(3, label=_("menu.check_updates"))
    helpmenu.entryconfig(5, label=_("menu.about_me"))

    # Action buttons
    start_button.config(text=_("menu.start_log"))
    stop_button.config(text=_("menu.stop_log"))
    clear_button.config(text=_("menu.clear_all"))

    # Titles
    events_title.config(text=_("events.title"))
    user_props_title.config(text=_("user_props.title"))
    consent_title.config(text=_("consent.title"))

    # Search
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
    consent_tree.heading("analytics_storage",
                         text=_("consent.analytics_storage"))
    consent_tree.heading("ad_user_data", text=_("consent.ad_user_data"))
    consent_tree.heading("ad_personalization",
                         text=_("consent.ad_personalization"))


def on_language_change(new_lang):
    """Triggered when the language is changed from the dropdown. Updates texts and saves to config."""
    set_language(new_lang)
    refresh_ui_texts()
    config_data["language"] = new_lang
    save_config(config_data)

# -----------------------------------------------------
# Global Variables / Data Structures
# -----------------------------------------------------
CONFIG_FILE = resource_path("config.json")

logcat_process = None
stop_thread = False
log_queue = queue.Queue()

events_data = []
user_properties = {}
current_consent = {
    "ad_storage": None,
    "analytics_storage": None,
    "ad_user_data": None,
    "ad_personalization": None,
}

search_matches = []
current_match_index = -1

# For consent table: if another log with same datetime arrives, it will replace the old one
consent_entries = {}  # dict: datetime => item_id of the Treeview

# -----------------------------------------------------
# Configuration Logic
# -----------------------------------------------------
def load_config():
    """Reads the 'config.json' file and returns its data as a dictionary. 
    Returns empty dict if missing or corrupted."""
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
    """Saves the given config dictionary into 'config.json'."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# -----------------------------------------------------
# ADB Reading Thread
# -----------------------------------------------------
def reader_thread():
    """Reads lines from logcat stdout and pushes them into a queue while ADB is running."""
    global stop_thread, logcat_process
    while not stop_thread and logcat_process and logcat_process.poll() is None:
        line = logcat_process.stdout.readline()
        if not line:
            break
        line = line.rstrip('\n')
        log_queue.put(line)


def stderr_reader_thread():
    """Reads lines from logcat stderr and detects issues like multiple connected devices."""
    global logcat_process, stop_thread
    while not stop_thread and logcat_process and logcat_process.poll() is None:
        line_err = logcat_process.stderr.readline()
        if not line_err:
            break
        line_err = line_err.strip()

        # React if "more than one device/emulator" appears
        if "more than one device/emulator" in line_err.lower():
            messagebox.showerror(_("error.several_devices_title"),
                _("error.several_devices_description")
            )
            # Stop logging on error:
            stop_logging()
            return


def check_log_queue():
    """Processes log lines from the queue and updates UI accordingly."""
    while not log_queue.empty():
        line = log_queue.get_nowait()

        # 1) Show in console
        text_area.insert(tk.END, line + "\n")
        text_area.see(tk.END)

        # 2) “Logging event:”
        if "Logging event:" in line:
            ev = parse_logging_event_line(line)
            if ev:
                events_data.append(ev)
                insert_event_in_tree(ev)

        # 3) “Setting user property:” (excluding "storage consent"/"DMA consent")
        # if "Setting user property:" in line and "storage consent" not in line and "DMA consent" not in line:
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
                # We update the current status
                current_consent.update(c)
                # Insert into consent table (replacing if dt matches)
                insert_consent_in_tree(c)

    root.after(100, check_log_queue)


def check_adb_installed():
    """
    Checks whether ADB is installed by attempting to run 'adb version'.
    Returns: True if it can be executed, False otherwise.
    """
    try:
        subprocess.check_output(["adb", "version"], 
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def show_adb_install_dialog():
    """
    Displays a dialog with links to download or guide for ADB installation.
    """
    dialog = tk.Toplevel()
    dialog.title("ADB not found")

    msg_label = tk.Label(
        dialog,
        text=_("error.adb_not_found")
    )
    msg_label.pack(pady=10, padx=10)

    # Button to open official Google link
    google_button = tk.Button(
        dialog,
        text=_("download_adb"),
        command=lambda: webbrowser.open(
            "https://developer.android.com/tools/releases/platform-tools?hl=es-419")
    )
    google_button.pack(pady=5)

    close_button = tk.Button(
        dialog,
        text=_("close"),
        command=dialog.destroy
    )
    close_button.pack(pady=10)


# -----------------------------------------------------
# Check Connected Devices
# -----------------------------------------------------

def check_device_connected():
    """
    Runs 'adb devices' and determines if at least one device or emulator is connected.
    """
    try:
        result = subprocess.check_output(
            ["adb", "devices"], stderr=subprocess.STDOUT, universal_newlines=True,
                   creationflags=CREATE_NO_WINDOW)
        lines = result.strip().split('\n')

        # The first line is usually: "List of devices attached"
        # Starting from the second, each line represents a device (id + state).
        if len(lines) > 1:
            # We filter out empty lines or those that begin with "* daemon"
            device_lines = [
                l for l in lines[1:]
                if l.strip() != '' and not l.startswith('* daemon')
            ]

            for dev in device_lines:
                parts = dev.split()
                # parts[0] = device ID, parts[1] = state
                if len(parts) >= 2:
                    state = parts[1].lower()
                    if state == "device":
                        return True
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        # If ADB is not installed or fails
        return False


def show_no_device_dialog():
    """
    Shows a dialog notifying the user that no device or emulator is connected.
    """
    dialog = tk.Toplevel()
    dialog.title(_("error.device_not_found"))

    msg_label = tk.Label(
        dialog,
        text=_("error.no_connected_device")
        
    )
    msg_label.pack(pady=10, padx=10)

    close_button = tk.Button(dialog, text=_("close"), command=dialog.destroy)
    close_button.pack(pady=10)

    # Avoid using the main window while it is open.
    dialog.grab_set()
    dialog.focus_set()


# -----------------------------------------------------
# Start/Stop Logging and Clear All
# -----------------------------------------------------
def start_logging():
    """Initializes ADB logging, starts reading threads, and prepares UI."""
    global stop_thread, logcat_process

    # We check if ADB is installed
    if not check_adb_installed():
        show_adb_install_dialog()
        return

    # We check if there is at least one device/emulator
    if not check_device_connected():
        show_no_device_dialog()
        return

    stop_thread = False
    subprocess.run(["adb", "shell", "setprop", "log.tag.FA", "VERBOSE"],
                   creationflags=CREATE_NO_WINDOW)
    subprocess.run(["adb", "shell", "setprop", "log.tag.FA-SVC", "VERBOSE"],
                   creationflags=CREATE_NO_WINDOW)
    subprocess.run(["adb", "logcat", "-c"],
                   creationflags=CREATE_NO_WINDOW)  # Opcional (limpia buffer)

    logcat_process = subprocess.Popen(
        ["adb", "logcat", "-v", "time", "-s", "FA", "FA-SVC"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        creationflags=CREATE_NO_WINDOW
    )

    # STDOUT reader thread
    t_stdout = threading.Thread(target=reader_thread, daemon=True)
    t_stdout .start()

    # STDERR reader thread
    t_stderr = threading.Thread(target=stderr_reader_thread, daemon=True)
    t_stderr.start()

    # Start queue check loop
    check_log_queue()

    text_area.insert(tk.END, "\n--- Start log ---\n")


def stop_logging():
    """Terminates the logcat process and stops logging thread."""
    global logcat_process, stop_thread
    stop_thread = True
    if logcat_process and logcat_process.poll() is None:
        logcat_process.terminate()
        logcat_process = None
    text_area.insert(tk.END, "\n--- Stop log ---\n")
    text_area.see(tk.END)


def clear_all():
    """Clears console, events, user properties, and consent data from the UI."""
    global current_consent, consent_entries

    # Console
    text_area.delete("1.0", tk.END)
    # Events
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
# Log Line Parsers
# -----------------------------------------------------


def parse_logging_event_line(line):
    """Parses a logging event line for event name, datetime and parameters."""
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
            k, v = pair.split('=', 1)
            params_dict[k.strip()] = v.strip()

    return {
        "datetime": datetime_str,
        "name": event_name,
        "params": params_dict
    }


def parse_user_property_line(line):
    """Parses a line for user property settings."""
    pat = r"Setting user property:\s+([^,]+),\s+(.*)"
    m = re.search(pat, line)
    if not m:
        # pat_fe = r"Setting user property(FE):\s+([^,]+),\s+(.*)"
        pat_fe = r"Setting user property\s*\(FE\):\s+([^,]+),\s+(.*)"
        m = re.search(pat_fe, line)
        if not m:
            return None

    return {
        "name": m.group(1).strip(),
        "value": m.group(2).strip()
    }


def parse_consent_line(line):
    """Parses a line containing consent data into a dictionary format."""
    datetime_str = line[:18].strip()
    found = re.findall(r'(\w+)=(\w+)', line)
    cdict = {
        "datetime": datetime_str,
        "ad_storage": None,
        "analytics_storage": None,
        "ad_user_data": None,
        "ad_personalization": None,
    }
    for (k, v) in found:
        if k in cdict:  # ad_storage, analytics_storage, ad_user_data, ad_personalization
            cdict[k] = v

    if (cdict["ad_storage"] is None
        and cdict["analytics_storage"] is None
            and cdict["ad_user_data"] is None):
        return None
    return cdict


def fill_missing_consent_fields(c):
    """Fill in consent fields with 'current_consent' if they don't appear, 
       ad_user_data => if there isn't a previous one => ad_storage."""
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
    """We use 'non_personalized_ads(_npa)' => 1 => denied, 0 => granted. 
       If not available, use the previous value or ad_storage"""
    # TODO: improve this function.
    # print("revisar non_personalized_ads")
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
# Insert Data Into UI Treeviews
# -----------------------------------------------------


def insert_event_in_tree(ev):
    """Inserts an event into the events tree view in the UI."""
    dt = ev["datetime"]
    name = ev["name"]
    params = ev["params"]

    parent_id = events_tree.insert("", tk.END, text=f"{dt} - {name}")
    for k, v in params.items():
        events_tree.insert(parent_id, tk.END, text=f"{k} = {v}")


def insert_consent_in_tree(cdict):
    """
    cdict => {datetime, ad_storage, analytics_storage, ad_user_data, ad_personalization}
    If there is already a row with the same datetime => we delete it and reinsert it
    """
    dt = cdict["datetime"]
    ad_storage = cdict["ad_storage"] or ""
    analytics_storage = cdict["analytics_storage"] or ""
    ad_user_data = cdict["ad_user_data"] or ""
    ad_personalization = cdict["ad_personalization"] or ""

    if dt in consent_entries:
        old_item = consent_entries[dt]
        consent_tree.delete(old_item)

    new_item = consent_tree.insert(
        "",
        tk.END,
        values=(dt, ad_storage, analytics_storage,
                ad_user_data, ad_personalization)
    )

    consent_entries[dt] = new_item


def refresh_user_props_tree():
    """Refreshes the user properties display in the UI."""
    for item in user_props_tree.get_children():
        user_props_tree.delete(item)
    for prop_name, prop_val in user_properties.items():
        user_props_tree.insert("", tk.END, text=f"{prop_name} = {prop_val}")

# -----------------------------------------------------
# Search Functionality in Log Text Area
# -----------------------------------------------------


def search_logs():
    """Highlights all matches of the search term in the log output area."""
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

    text_area.tag_config("search_highlight",
                         background="yellow", foreground="black")

    total = len(search_matches)
    if total > 0:
        current_match_index = 0
        highlight_current_match()
    else:
        update_match_label(0, 0)


def highlight_current_match():
    """Highlights the currently selected match in the text area."""
    global current_match_index, search_matches
    text_area.tag_remove("search_current", "1.0", tk.END)
    total = len(search_matches)
    if total == 0 or current_match_index < 0 or current_match_index >= total:
        update_match_label(0, total)
        return

    start_pos, end_pos = search_matches[current_match_index]
    text_area.tag_add("search_current", start_pos, end_pos)
    text_area.tag_config(
        "search_current", background="orange", foreground="black")
    text_area.see(start_pos)
    update_match_label(current_match_index + 1, total)


def next_match():
    """Moves selection to the next search match."""
    global current_match_index, search_matches
    if search_matches and current_match_index < len(search_matches) - 1:
        current_match_index += 1
        highlight_current_match()


def prev_match():
    """Moves selection to the previous search match."""
    global current_match_index, search_matches
    if search_matches and current_match_index > 0:
        current_match_index -= 1
        highlight_current_match()


def jump_to_first():
    """Jumps to the first search match."""
    global current_match_index
    if search_matches:
        current_match_index = 0
        highlight_current_match()


def jump_to_last():
    """Jumps to the last search match."""
    global current_match_index, search_matches
    if search_matches:
        current_match_index = len(search_matches) - 1
        highlight_current_match()


def jump_to_index():
    """Jumps to a specific search match index provided by the user."""
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
    """Updates the label showing the current match index out of total."""
    match_label.config(text=f"{current} / {total}")


# -----------------------------------------------------
# UI Construction and Layout
# -----------------------------------------------------
# 1) Load translations
load_translations()

# 2) Load config
config_data = load_config()
default_lang_code = config_data.get("language", "en")
set_language(default_lang_code)

root = tk.Tk()
root.title("Analytics Tracking Debugger Android (Alejandro Reinoso)")
root.iconbitmap(resource_path("./assets/logo-alejandro-reinoso.ico"))

main_paned = tk.PanedWindow(
    root, orient=tk.VERTICAL, sashwidth=8, sashrelief="raised")
main_paned.pack(fill=tk.BOTH, expand=True)

# --- MENU: Languages, Help ---
menubar = Menu(root)
root.config(menu=menubar)

filemenu = Menu(menubar, tearoff=0)
filemenu.add_command(label=_("menu.spanish"),
                     command=lambda: on_language_change("es"))
filemenu.add_command(label=_("menu.english"),
                     command=lambda: on_language_change("en"))

helpmenu = Menu(menubar, tearoff=0)
#helpmenu.add_command(label=_("menu.user_guide"))
helpmenu.add_command(label=_("menu.support"),
                     command=lambda: webbrowser.open("https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger&utm_medium=ga_android_debugger&utm_term=support"))
helpmenu.add_command(label=_("menu.feedback"),
                     command=lambda: webbrowser.open("https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger&utm_medium=ga_android_debugger&utm_term=feedback"))
helpmenu.add_separator()
helpmenu.add_command(label=_("menu.about_me"),
                     command=lambda: webbrowser.open("https://www.linkedin.com/in/alejandroreinosogomez/"))

menubar.add_cascade(label=_("menu.languages"), menu=filemenu)
menubar.add_cascade(label=_("menu.help"), menu=helpmenu)


# LEFT FRAME: for “Start Log”, “Stop Log”, “Clear All”
top_frame = tk.Frame(main_paned, bd=2, relief="groove")
main_paned.add(top_frame, minsize=50)
buttons_frame = tk.Frame(top_frame)
buttons_frame.pack(side=tk.LEFT, padx=10, pady=10)

start_button = tk.Button(buttons_frame, text=_(
    "menu.start_log"), command=start_logging)
start_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(buttons_frame, text=_(
    "menu.stop_log"), command=stop_logging)
stop_button.pack(side=tk.LEFT, padx=5)

clear_button = tk.Button(buttons_frame, text=_(
    "menu.clear_all"), command=clear_all)
clear_button.pack(side=tk.LEFT, padx=5)

# --- INTERMEDIATE FRAME -> subdiv (izq, der) ---
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
    columns=("datetime", "ad_storage", "analytics_storage",
             "ad_user_data", "ad_personalization"),
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

# --- LOWER FRAME -> consola + búsqueda
bottom_frame = tk.Frame(main_paned, bd=2, relief="sunken")
main_paned.add(bottom_frame, minsize=50)

frame_search = tk.Frame(bottom_frame)
frame_search.pack(pady=5, fill=tk.X)

search_label = tk.Label(frame_search, text=_("search.label"))
search_label.pack(side=tk.LEFT)
search_entry = tk.Entry(frame_search, width=30)
search_entry.pack(side=tk.LEFT, padx=5)

search_button = tk.Button(frame_search, text=_(
    "search.button"), command=search_logs)
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
jump_button = tk.Button(frame_search, text=_(
    "search.goto_button"), command=jump_to_index)
jump_button.pack(side=tk.LEFT, padx=5)

text_area = scrolledtext.ScrolledText(bottom_frame, width=100, height=10)
text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

# We force the refresh of texts according to the default_lang_code language
refresh_ui_texts()

root.mainloop()
