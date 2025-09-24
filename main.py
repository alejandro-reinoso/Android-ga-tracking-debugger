import queue
import tkinter as tk
from tkinter import messagebox
import webbrowser
from src.i18n import load_translations, set_language, _
from src.utils import resource_path
from src.log_parser import parse_logging_event_line, parse_user_property_line, parse_consent_line
from src.config_manager import load_config, save_config
from src.adb_manager import check_adb_installed, check_device_connected, LogcatManager, AdbError
from src.view import View

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
        self.view = View(self.root, self)
        self.refresh_ui_texts() # Actualizar textos al inicio


    def refresh_ui_texts(self):
        """
        Order to the view update all the text to the current language.
        """
        # Menu
        self.view.menubar.entryconfig(1, label=_("menu.languages"))
        self.view.menubar.entryconfig(3, label=_("menu.help"))

        # Submenu
        self.view.filemenu.entryconfig(0, label=_("menu.spanish"))
        self.view.filemenu.entryconfig(1, label=_("menu.english"))

        #helpmenu.entryconfig(0, label=_("menu.user_guide"))
        self.view.helpmenu.entryconfig(0, label=_("menu.support"))
        self.view.helpmenu.entryconfig(1, label=_("menu.feedback"))
        self.view.helpmenu.entryconfig(3, label=_("menu.check_updates"))
        self.view.helpmenu.entryconfig(5, label=_("menu.about_me"))

        # Action buttons
        self.view.start_button.config(text=_("menu.start_log"))
        self.view.stop_button.config(text=_("menu.stop_log"))
        self.view.clear_button.config(text=_("menu.clear_all"))

        # Titles
        self.view.events_title.config(text=_("events.title"))
        self.view.user_props_title.config(text=_("user_props.title"))
        self.view.consent_title.config(text=_("consent.title"))

        # Search
        self.view.search_label.config(text=_("search.label"))
        self.view.search_button.config(text=_("search.button"))
        self.view.first_button.config(text=_("search.first"))
        self.view.prev_button.config(text=_("search.previous"))
        self.view.next_button.config(text=_("search.next"))
        self.view.last_button.config(text=_("search.last"))
        self.view.jump_button.config(text=_("search.goto_button"))
        self.view.search_goto_label.config(text=_("search.goto_label"))

        self.view.consent_tree.heading("datetime", text=_("consent.datetime"))
        self.view.consent_tree.heading("ad_storage", text=_("consent.ad_storage"))
        self.view.consent_tree.heading("analytics_storage",
                            text=_("consent.analytics_storage"))
        self.view.consent_tree.heading("ad_user_data", text=_("consent.ad_user_data"))
        self.view.consent_tree.heading("ad_personalization",
                            text=_("consent.ad_personalization"))


    def on_language_change(self, new_lang):
        """
        Triggered when the language is changed from the dropdown. 
        Updates texts and saves to config.
        """
        set_language(new_lang)
        self.refresh_ui_texts()
        self.config_data["language"] = new_lang
        save_config(self.config_data)


    def handle_adb_error(self, error_type):
        """Function that will be called by the LogcatManager in case of error."""
        if error_type == AdbError.MULTIPLE_DEVICES:
            messagebox.showerror(_("error.several_devices_title"),
                                _("error.several_devices_description"))
        self.stop_logging() # Detenemos el log desde el hilo principal de la UI
    

    def check_log_queue(self):
        """Processes log lines from the queue and updates UI accordingly."""
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()

            # 1) Show in console
            self.view.update_console(line + "\n")

            # 2) “Logging event:”
            if "Logging event:" in line:
                ev = parse_logging_event_line(line)
                if ev:
                    self.events_data.append(ev)
                    self.insert_event_in_tree(ev)

            # 3) “Setting user property:” (excluding "storage consent"/"DMA consent")
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

        # We create and start the manager
        self.logcat_manager = LogcatManager(self.log_queue, self.handle_adb_error)
        self.logcat_manager.start()

        # We start the loop that processes the queue
        self.check_log_queue()
        self.view.update_console("\n--- Start log ---\n")


    def stop_logging(self):
        """Terminates the logcat process and stops logging thread."""
        if self.logcat_manager:
            self.logcat_manager.stop()
            self.logcat_manager = None
        self.view.update_console("\n--- Stop log ---\n")


    def clear_all(self):
        """Clears console, events, user properties, and consent data from the UI."""
        # Console
        self.view.text_area.delete("1.0", tk.END)
        # Events
        self.events_data.clear()
        for it in self.view.events_tree.get_children():
            self.view.events_tree.delete(it)
        # User props
        self.user_properties.clear()
        for it in self.view.user_props_tree.get_children():
            self.view.user_props_tree.delete(it)
        # Consent
        self.current_consent = {
            "ad_storage": None,
            "analytics_storage": None,
            "ad_user_data": None,
            "ad_personalization": None,
        }
        for it in self.view.consent_tree.get_children():
            self.view.consent_tree.delete(it)
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

        parent_id = self.view.events_tree.insert("", tk.END, text=f"{dt} - {name}")
        for k, v in params.items():
            self.view.events_tree.insert(parent_id, tk.END, text=f"{k} = {v}")

    def insert_consent_in_tree(self, cdict):
        """
        cdict => {datetime, ad_storage, analytics_storage, ad_user_data, ad_personalization}
        If there is already a row with the same datetime => we delete it and reinsert it
        """
        dt = cdict["datetime"]
        values = (
            dt,
            cdict.get("ad_storage", ""),
            cdict.get("analytics_storage", ""),
            cdict.get("ad_user_data", ""),
            cdict.get("ad_personalization", "")
        )
        if dt in self.consent_entries:
            self.view.consent_tree.delete(self.consent_entries[dt])
        
        new_item = self.view.consent_tree.insert("", tk.END, values=values)
        self.consent_entries[dt] = new_item

    
    def refresh_user_props_tree(self):
        """Refreshes the user properties display in the UI."""
        for item in self.view.user_props_tree.get_children():
            self.view.user_props_tree.delete(item)
        for prop_name, prop_val in self.user_properties.items():
            self.view.user_props_tree.insert("", tk.END, text=f"{prop_name} = {prop_val}")


    # -----------------------------------------------------
    # Search Functionality in Log Text Area
    # -----------------------------------------------------
    def search_logs(self):
        """Highlights all matches of the search term in the log output area."""
        self.view.text_area.tag_remove("search_highlight", "1.0", tk.END)
        self.view.text_area.tag_remove("search_current", "1.0", tk.END)
        self.search_matches.clear()
        self.current_match_index = -1

        term = self.view.search_entry.get().strip()
        if not term:
            self.update_match_label(0, 0)
            return

        start_pos = "1.0"
        while True:
            pos = self.view.text_area.search(term, start_pos, stopindex=tk.END)
            if not pos:
                break
            end_pos = f"{pos}+{len(term)}c"
            self.search_matches.append((pos, end_pos))
            self.view.text_area.tag_add("search_highlight", pos, end_pos)
            start_pos = end_pos

        self.view.text_area.tag_config("search_highlight",
                            background="yellow", foreground="black")

        total = len(self.search_matches)
        if total > 0:
            self.current_match_index = 0
            self.highlight_current_match()
        else:
            self.update_match_label(0, 0)


    def highlight_current_match(self):
        """Highlights the currently selected match in the text area."""
        self.view.text_area.tag_remove("search_current", "1.0", tk.END)
        total = len(self.search_matches)
        
        if not (0 <= self.current_match_index < total):
            self.update_match_label(0, total)
            return

        start_pos, end_pos = self.search_matches[self.current_match_index]
        self.view.text_area.tag_add("search_current", start_pos, end_pos)
        self.view.text_area.tag_config(
            "search_current", background="orange", foreground="black")
        self.view.text_area.see(start_pos)
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
            idx = int(self.view.index_entry.get()) - 1
        except ValueError:
            return
        idx = max(0, min(idx, len(self.search_matches) - 1))
        self.current_match_index = idx
        self.highlight_current_match()


    def update_match_label(self, current, total):
        """Updates the label showing the current match index out of total."""
        self.view.match_label.config(text=f"{current} / {total}")


if __name__ == "__main__":
    load_translations()
    
    root = tk.Tk()
    app = App(root)
    root.mainloop()