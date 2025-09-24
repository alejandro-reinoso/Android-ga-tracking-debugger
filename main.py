import queue
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, Menu
import webbrowser
from src.i18n import load_translations, set_language, _
from src.utils import resource_path
from src.log_parser import parse_logging_event_line, parse_user_property_line, parse_consent_line
from src.config_manager import load_config, save_config
from src.adb_manager import check_adb_installed, check_device_connected, LogcatManager, AdbError


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Analytics Tracking Debugger Android (Alejandro Reinoso)")
        self.root.iconbitmap(resource_path("./assets/logo-alejandro-reinoso.ico"))

        # --- Estado de la Aplicación ---
        self.log_queue = queue.Queue()
        self.logcat_manager = None
        self.events_data = []
        self.user_properties = {}
        self.current_consent = {
            "ad_storage": None, "analytics_storage": None,
            "ad_user_data": None, "ad_personalization": None
        }
        self.consent_entries = {}
        self.search_matches = []
        self.current_match_index = -1

        # --- Cargar configuración e i18n ---
        self.config_data = load_config()
        default_lang_code = self.config_data.get("language", "en")
        set_language(default_lang_code)

        # --- Construir la UI ---
        self._create_widgets()
        self.refresh_ui_texts() # Actualizar textos al inicio

    def _create_widgets(self):
        # Aquí irá todo el código que crea los botones, frames, treeviews, etc.
        main_paned = tk.PanedWindow(
            self.root, orient=tk.VERTICAL, sashwidth=8, sashrelief="raised")
        main_paned.pack(fill=tk.BOTH, expand=True)

        # --- MENU: Languages, Help ---
        self.menubar = Menu(self.root)
        self.root.config(menu=self.menubar)

        self.filemenu = Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label=_("menu.spanish"),
                            command=lambda: self.on_language_change("es"))
        self.filemenu.add_command(label=_("menu.english"),
                            command=lambda: self.on_language_change("en"))

        self.helpmenu = Menu(self.menubar, tearoff=0)
        #helpmenu.add_command(label=_("menu.user_guide"))
        self.helpmenu.add_command(label=_("menu.support"),
                            command=lambda: webbrowser.open("https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger&utm_medium=ga_android_debugger&utm_term=support"))
        self.helpmenu.add_command(label=_("menu.feedback"),
                            command=lambda: webbrowser.open("https://alejandroreinoso.com/contacto/?utm_source=ga_android_debugger&utm_medium=ga_android_debugger&utm_term=feedback"))
        self.helpmenu.add_separator()
        self.helpmenu.add_command(label=_("menu.about_me"),
                            command=lambda: webbrowser.open("https://www.linkedin.com/in/alejandroreinosogomez/"))

        self.menubar.add_cascade(label=_("menu.languages"), menu=self.filemenu)
        self.menubar.add_cascade(label=_("menu.help"), menu=self.helpmenu)


        # LEFT FRAME: for “Start Log”, “Stop Log”, “Clear All”
        top_frame = tk.Frame(main_paned, bd=2, relief="groove")
        main_paned.add(top_frame, minsize=50)
        buttons_frame = tk.Frame(top_frame)
        buttons_frame.pack(side=tk.LEFT, padx=10, pady=10)

        self.start_button = tk.Button(buttons_frame, text=_(
            "menu.start_log"), command=self.start_logging)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(buttons_frame, text=_(
            "menu.stop_log"), command=self.stop_logging)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(buttons_frame, text=_(
            "menu.clear_all"), command=self.clear_all)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # --- INTERMEDIATE FRAME -> subdiv (izq, der) ---
        middle_frame = tk.Frame(main_paned, bd=2, relief="groove")
        main_paned.add(middle_frame, minsize=150)

        left_frame = tk.Frame(middle_frame, bg="white")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.user_props_title = tk.Label(left_frame, text=_("user_props.title"), bg="white")
        self.user_props_title.pack(anchor="w")
        self.user_props_tree = ttk.Treeview(left_frame)
        self.user_props_tree.pack(fill=tk.BOTH, expand=True)

        self.consent_title = tk.Label(left_frame, text=_("consent.title"), bg="white")
        self.consent_title.pack(anchor="w")
        self.consent_tree = ttk.Treeview(
            left_frame,
            columns=("datetime", "ad_storage", "analytics_storage",
                    "ad_user_data", "ad_personalization"),
            show="headings"
        )
        self.consent_tree.pack(fill=tk.BOTH, expand=True)
        self.consent_tree.heading("datetime", text="DateTime")
        self.consent_tree.heading("ad_storage", text="ad_storage")
        self.consent_tree.heading("analytics_storage", text="analytics_storage")
        self.consent_tree.heading("ad_user_data", text="ad_user_data")
        self.consent_tree.heading("ad_personalization", text="ad_personalization")

        self.consent_tree.column("datetime", width=130)
        self.consent_tree.column("ad_storage", width=90)
        self.consent_tree.column("analytics_storage", width=120)
        self.consent_tree.column("ad_user_data", width=120)
        self.consent_tree.column("ad_personalization", width=130)

        right_frame = tk.Frame(middle_frame, bg="white")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.events_title = tk.Label(right_frame, text=_("events.title"), bg="white")
        self.events_title.pack(anchor="w")
        self.events_tree = ttk.Treeview(right_frame)
        self.events_tree.pack(fill=tk.BOTH, expand=True)

        # --- LOWER FRAME -> consola + búsqueda
        bottom_frame = tk.Frame(main_paned, bd=2, relief="sunken")
        main_paned.add(bottom_frame, minsize=50)

        frame_search = tk.Frame(bottom_frame)
        frame_search.pack(pady=5, fill=tk.X)

        self.search_label = tk.Label(frame_search, text=_("search.label"))
        self.search_label.pack(side=tk.LEFT)
        self.search_entry = tk.Entry(frame_search, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        self.search_button = tk.Button(frame_search, text=_(
            "search.button"), command=self.search_logs)
        self.search_button.pack(side=tk.LEFT, padx=5)

        self.first_button = tk.Button(frame_search, text="|<<", command=self.jump_to_first)
        self.first_button.pack(side=tk.LEFT, padx=2)

        self.prev_button = tk.Button(frame_search, text="<<", command=self.prev_match)
        self.prev_button.pack(side=tk.LEFT, padx=2)

        self.match_label = tk.Label(frame_search, text="0 / 0")
        self.match_label.pack(side=tk.LEFT, padx=10)

        self.next_button = tk.Button(frame_search, text=">>", command=self.next_match)
        self.next_button.pack(side=tk.LEFT, padx=2)

        self.last_button = tk.Button(frame_search, text=">>|", command=self.jump_to_last)
        self.last_button.pack(side=tk.LEFT, padx=2)

        self.search_goto_label = tk.Label(frame_search, text=_("search.goto_label"))
        self.search_goto_label.pack(side=tk.LEFT, padx=5)
        self.index_entry = tk.Entry(frame_search, width=5)
        self.index_entry.pack(side=tk.LEFT)
        self.jump_button = tk.Button(frame_search, text=_(
            "search.goto_button"), command=self.jump_to_index)
        self.jump_button.pack(side=tk.LEFT, padx=5)

        self.text_area = scrolledtext.ScrolledText(bottom_frame, width=100, height=10)
        self.text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

    def refresh_ui_texts(self):
        """
        Refresh all UI texts based on current language selection.
        """
        # Menu
        self.menubar.entryconfig(1, label=_("menu.languages"))
        self.menubar.entryconfig(3, label=_("menu.help"))

        # Submenu
        self.filemenu.entryconfig(0, label=_("menu.spanish"))
        self.filemenu.entryconfig(1, label=_("menu.english"))

        #helpmenu.entryconfig(0, label=_("menu.user_guide"))
        self.helpmenu.entryconfig(0, label=_("menu.support"))
        self.helpmenu.entryconfig(1, label=_("menu.feedback"))
        self.helpmenu.entryconfig(3, label=_("menu.check_updates"))
        self.helpmenu.entryconfig(5, label=_("menu.about_me"))

        # Action buttons
        self.start_button.config(text=_("menu.start_log"))
        self.stop_button.config(text=_("menu.stop_log"))
        self.clear_button.config(text=_("menu.clear_all"))

        # Titles
        self.events_title.config(text=_("events.title"))
        self.user_props_title.config(text=_("user_props.title"))
        self.consent_title.config(text=_("consent.title"))

        # Search
        self.search_label.config(text=_("search.label"))
        self.search_button.config(text=_("search.button"))
        self.first_button.config(text=_("search.first"))
        self.prev_button.config(text=_("search.previous"))
        self.next_button.config(text=_("search.next"))
        self.last_button.config(text=_("search.last"))
        self.jump_button.config(text=_("search.goto_button"))
        self.search_goto_label.config(text=_("search.goto_label"))

        self.consent_tree.heading("datetime", text=_("consent.datetime"))
        self.consent_tree.heading("ad_storage", text=_("consent.ad_storage"))
        self.consent_tree.heading("analytics_storage",
                            text=_("consent.analytics_storage"))
        self.consent_tree.heading("ad_user_data", text=_("consent.ad_user_data"))
        self.consent_tree.heading("ad_personalization",
                            text=_("consent.ad_personalization"))


    def on_language_change(self, new_lang):
        """Triggered when the language is changed from the dropdown. Updates texts and saves to config."""
        set_language(new_lang)
        self.refresh_ui_texts()
        self.config_data["language"] = new_lang
        save_config(self.config_data)


    def handle_adb_error(self, error_type):
        """Función que será llamada por el LogcatManager en caso de error."""
        if error_type == AdbError.MULTIPLE_DEVICES:
            messagebox.showerror(_("error.several_devices_title"),
                                _("error.several_devices_description"))
        self.stop_logging() # Detenemos el log desde el hilo principal de la UI
    

    def check_log_queue(self):
        """Processes log lines from the queue and updates UI accordingly."""
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()

            # 1) Show in console
            self.text_area.insert(tk.END, line + "\n")
            self.text_area.see(tk.END)

            # 2) “Logging event:”
            if "Logging event:" in line:
                ev = parse_logging_event_line(line)
                if ev:
                    self.events_data.append(ev)
                    self.insert_event_in_tree(ev)

            # 3) “Setting user property:” (excluding "storage consent"/"DMA consent")
            # if "Setting user property:" in line and "storage consent" not in line and "DMA consent" not in line:
            if "Setting user property:" in line or "Setting user property(FE):" in line:
                up = parse_user_property_line(line)
                if up:
                    self.user_properties[up["name"]] = up["value"]
                    self.refresh_user_props_tree()

            # 4) “Setting storage consent” / “Setting DMA consent”
            if ("Setting storage consent" in line) or ("Setting DMA consent" in line) or ("non_personalized_ads" in line):
                c = parse_consent_line(line)
                if c:
                    self.fill_missing_consent_fields(c)
                    self.deduce_ad_personalization(c)
                    # We update the current status
                    self.current_consent.update(c)
                    # Insert into consent table (replacing if dt matches)
                    self.insert_consent_in_tree(c)

        self.root.after(100, self.check_log_queue)


    def show_adb_install_dialog(self):
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


    def show_no_device_dialog(self):
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
    def start_logging(self):
        """Initializes ADB logging, starts reading threads, and prepares UI."""
        # We check if ADB is installed
        if not check_adb_installed():
            self.show_adb_install_dialog()
            return

        # We check if there is at least one device/emulator
        if not check_device_connected():
            self.show_no_device_dialog()
            return

        # Creamos e iniciamos el manager
        self.logcat_manager = LogcatManager(self.log_queue, self.handle_adb_error)
        self.logcat_manager.start()

        # Iniciamos el bucle que procesa la cola
        self.check_log_queue()
        self.text_area.insert(tk.END, "\n--- Start log ---\n")


    def stop_logging(self):
        """Terminates the logcat process and stops logging thread."""
        if self.logcat_manager:
            self.logcat_manager.stop()
            self.logcat_manager = None
        self.text_area.insert(tk.END, "\n--- Stop log ---\n")
        self.text_area.see(tk.END)


    def clear_all(self):
        """Clears console, events, user properties, and consent data from the UI."""
        # Console
        self.text_area.delete("1.0", tk.END)
        # Events
        self.events_data.clear()
        for it in self.events_tree.get_children():
            self.events_tree.delete(it)
        # User props
        self.user_properties.clear()
        for it in self.user_props_tree.get_children():
            self.user_props_tree.delete(it)
        # Consent
        self.current_consent = {
            "ad_storage": None,
            "analytics_storage": None,
            "ad_user_data": None,
            "ad_personalization": None,
        }
        for it in self.consent_tree.get_children():
            self.consent_tree.delete(it)
        self.consent_entries.clear()


    def fill_missing_consent_fields(self, c):
        """Fill in consent fields with 'current_consent' if they don't appear, 
        ad_user_data => if there isn't a previous one => ad_storage."""
        if c["ad_storage"] is None:
            c["ad_storage"] = self.current_consent["ad_storage"]
        if c["analytics_storage"] is None:
            c["analytics_storage"] = self.current_consent["analytics_storage"]
        if c["ad_user_data"] is None:
            if self.current_consent["ad_user_data"] is not None:
                c["ad_user_data"] = self.current_consent["ad_user_data"]
            else:
                c["ad_user_data"] = c["ad_storage"]


    def deduce_ad_personalization(self, c):
        """We use 'non_personalized_ads(_npa)' => 1 => denied, 0 => granted. 
        If not available, use the previous value or ad_storage"""
        # TODO: improve this function.
        # print("revisar non_personalized_ads")
        npa_key = None
        for k in self.user_properties:
            if "non_personalized_ads" in k:
                npa_key = k
                break
        if npa_key:
            val = self.user_properties[npa_key].strip()
            if val == '1':
                c["ad_personalization"] = "denied"
            elif val == '0':
                c["ad_personalization"] = "granted"
            else:
                # fallback
                if self.current_consent["ad_personalization"] is not None:
                    c["ad_personalization"] = self.current_consent["ad_personalization"]
                else:
                    c["ad_personalization"] = c["ad_storage"]
        else:
            # no npa key => fallback
            if self.current_consent["ad_personalization"] is not None:
                c["ad_personalization"] = self.current_consent["ad_personalization"]
            else:
                c["ad_personalization"] = c["ad_storage"]


    # -----------------------------------------------------
    # Insert Data Into UI Treeviews
    # -----------------------------------------------------


    def insert_event_in_tree(self, ev):
        """Inserts an event into the events tree view in the UI."""
        dt = ev["datetime"]
        name = ev["name"]
        params = ev["params"]

        parent_id = self.events_tree.insert("", tk.END, text=f"{dt} - {name}")
        for k, v in params.items():
            self.events_tree.insert(parent_id, tk.END, text=f"{k} = {v}")

    def insert_consent_in_tree(self, cdict):
        """
        cdict => {datetime, ad_storage, analytics_storage, ad_user_data, ad_personalization}
        If there is already a row with the same datetime => we delete it and reinsert it
        """
        dt = cdict["datetime"]
        ad_storage = cdict["ad_storage"] or ""
        analytics_storage = cdict["analytics_storage"] or ""
        ad_user_data = cdict["ad_user_data"] or ""
        ad_personalization = cdict["ad_personalization"] or ""

        if dt in self.consent_entries:
            old_item = self.consent_entries[dt]
            self.consent_tree.delete(old_item)

        new_item = self.consent_tree.insert(
            "",
            tk.END,
            values=(dt, ad_storage, analytics_storage,
                    ad_user_data, ad_personalization)
        )

        self.consent_entries[dt] = new_item

    
    def refresh_user_props_tree(self):
        """Refreshes the user properties display in the UI."""
        for item in self.user_props_tree.get_children():
            self.user_props_tree.delete(item)
        for prop_name, prop_val in self.user_properties.items():
            self.user_props_tree.insert("", tk.END, text=f"{prop_name} = {prop_val}")


    # -----------------------------------------------------
    # Search Functionality in Log Text Area
    # -----------------------------------------------------
    def search_logs(self):
        """Highlights all matches of the search term in the log output area."""
        self.text_area.tag_remove("search_highlight", "1.0", tk.END)
        self.text_area.tag_remove("search_current", "1.0", tk.END)
        self.search_matches.clear()
        self.current_match_index = -1

        term = self.search_entry.get().strip()
        if not term:
            self.update_match_label(0, 0)
            return

        start_pos = "1.0"
        while True:
            pos = self.text_area.search(term, start_pos, stopindex=tk.END)
            if not pos:
                break
            end_pos = f"{pos}+{len(term)}c"
            self.search_matches.append((pos, end_pos))
            self.text_area.tag_add("search_highlight", pos, end_pos)
            start_pos = end_pos

        self.text_area.tag_config("search_highlight",
                            background="yellow", foreground="black")

        total = len(self.search_matches)
        if total > 0:
            self.current_match_index = 0
            self.highlight_current_match()
        else:
            self.update_match_label(0, 0)


    def highlight_current_match(self):
        """Highlights the currently selected match in the text area."""
        self.text_area.tag_remove("search_current", "1.0", tk.END)
        total = len(self.search_matches)
        
        #if total == 0 or self.current_match_index < 0 or self.current_match_index >= total:
        if not (0 <= self.current_match_index < total):
            self.update_match_label(0, total)
            return

        start_pos, end_pos = self.search_matches[self.current_match_index]
        self.text_area.tag_add("search_current", start_pos, end_pos)
        self.text_area.tag_config(
            "search_current", background="orange", foreground="black")
        self.text_area.see(start_pos)
        self.update_match_label(self.current_match_index + 1, total)


    def next_match(self):
        """Moves selection to the next search match."""
        if self.search_matches and self.current_match_index < len(self.search_matches) - 1:
            self.current_match_index += 1
            self.highlight_current_match()


    def prev_match(self):
        """Moves selection to the previous search match."""
        if self.search_matches and self.current_match_index > 0:
            self.current_match_index -= 1
            self.highlight_current_match()


    def jump_to_first(self):
        """Jumps to the first search match."""
        if self.search_matches:
            self.current_match_index = 0
            self.highlight_current_match()


    def jump_to_last(self):
        """Jumps to the last search match."""
        if self.search_matches:
            self.current_match_index = len(self.search_matches) - 1
            self.highlight_current_match()


    def jump_to_index(self):
        """Jumps to a specific search match index provided by the user."""
        if not self.search_matches:
            return
        try:
            idx = int(self.index_entry.get()) - 1
        except ValueError:
            return
        idx = max(0, min(idx, len(self.search_matches) - 1))
        self.current_match_index = idx
        self.highlight_current_match()


    def update_match_label(self, current, total):
        """Updates the label showing the current match index out of total."""
        self.match_label.config(text=f"{current} / {total}")


if __name__ == "__main__":
    load_translations()
    
    root = tk.Tk()
    app = App(root)
    root.mainloop()