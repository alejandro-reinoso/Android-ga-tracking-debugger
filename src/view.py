# Android GA Tracking Debugger
# Copyright (c) 2025 Alejandro Reinoso
#
# This software is licensed under the Custom Shared-Profit License (CSPL) v1.0.
# See the LICENSE.txt file for details.

import tkinter as tk
from tkinter import scrolledtext, ttk, Menu
import webbrowser
from src.i18n import _


class View:
    def __init__(self, root, controller):
        self.controller = controller

        main_paned = tk.PanedWindow(
            root, orient=tk.VERTICAL, sashwidth=8, sashrelief="raised")
        main_paned.pack(fill=tk.BOTH, expand=True)

        # --- MENU: Languages, Help ---
        self.menubar = Menu(root)
        root.config(menu=self.menubar)

        self.filemenu = Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label=_("menu.spanish"),
                                  command=lambda: self.controller.on_language_change("es"))
        self.filemenu.add_command(label=_("menu.english"),
                                  command=lambda: self.controller.on_language_change("en"))

        self.helpmenu = Menu(self.menubar, tearoff=0)
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
            "menu.start_log"), command=self.controller.start_logging)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(buttons_frame, text=_(
            "menu.stop_log"), command=self.controller.stop_logging)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(buttons_frame, text=_(
            "menu.clear_all"), command=self.controller.clear_all)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # --- INTERMEDIATE FRAME -> subdiv (izq, der) ---
        middle_frame = tk.Frame(main_paned, bd=2, relief="groove")
        main_paned.add(middle_frame, minsize=150)

        left_frame = tk.Frame(middle_frame, bg="white")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # User Properties Tree
        self.user_props_title = tk.Label(
            left_frame, text=_("user_props.title"), bg="white")
        self.user_props_title.pack(anchor="w", pady=(0, 2))
        
        up_container = tk.Frame(left_frame)
        up_container.pack(fill=tk.BOTH, expand=True)
        up_scrollbar = ttk.Scrollbar(up_container, orient=tk.VERTICAL)
        self.user_props_tree = ttk.Treeview(up_container, yscrollcommand=up_scrollbar.set)
        up_scrollbar.config(command=self.user_props_tree.yview)
        up_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.user_props_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Consent Tree
        self.consent_title = tk.Label(
            left_frame, text=_("consent.title"), bg="white")
        self.consent_title.pack(anchor="w", pady=(5, 2))

        consent_container = tk.Frame(left_frame)
        consent_container.pack(fill=tk.BOTH, expand=True)
        consent_scrollbar = ttk.Scrollbar(consent_container, orient=tk.VERTICAL)
        self.consent_tree = ttk.Treeview(
            consent_container,
            columns=("datetime", "ad_storage", "analytics_storage",
                     "ad_user_data", "ad_personalization"),
            show="headings",
            yscrollcommand=consent_scrollbar.set
        )
        consent_scrollbar.config(command=self.consent_tree.yview)
        consent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.consent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.consent_tree.heading("datetime", text="DateTime")
        self.consent_tree.heading("ad_storage", text="ad_storage")
        self.consent_tree.heading(
            "analytics_storage", text="analytics_storage")
        self.consent_tree.heading("ad_user_data", text="ad_user_data")
        self.consent_tree.heading(
            "ad_personalization", text="ad_personalization")

        self.consent_tree.column("datetime", width=130)
        self.consent_tree.column("ad_storage", width=90)
        self.consent_tree.column("analytics_storage", width=120)
        self.consent_tree.column("ad_user_data", width=120)
        self.consent_tree.column("ad_personalization", width=130)

        right_frame = tk.Frame(middle_frame, bg="white")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Events Tree
        self.events_title = tk.Label(
            right_frame, text=_("events.title"), bg="white")
        self.events_title.pack(anchor="w")

        events_container = tk.Frame(right_frame)
        events_container.pack(fill=tk.BOTH, expand=True)
        events_scrollbar = ttk.Scrollbar(events_container, orient=tk.VERTICAL)

        self.events_tree = ttk.Treeview(events_container, yscrollcommand=events_scrollbar.set)

        events_scrollbar.config(command=self.events_tree.yview)
        events_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- LOWER FRAME -> console + search
        bottom_frame = tk.Frame(main_paned, bd=2, relief="sunken")
        main_paned.add(bottom_frame, minsize=50)

        frame_search = tk.Frame(bottom_frame)
        frame_search.pack(pady=5, fill=tk.X)

        self.search_label = tk.Label(frame_search, text=_("search.label"))
        self.search_label.pack(side=tk.LEFT)
        self.search_entry = tk.Entry(frame_search, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        self.search_button = tk.Button(frame_search, text=_(
            "search.button"), command=self.controller.search_logs)
        self.search_button.pack(side=tk.LEFT, padx=5)

        self.first_button = tk.Button(
            frame_search, text="|<<", command=self.controller.jump_to_first)
        self.first_button.pack(side=tk.LEFT, padx=2)

        self.prev_button = tk.Button(
            frame_search, text="<<", command=self.controller.prev_match)
        self.prev_button.pack(side=tk.LEFT, padx=2)

        self.match_label = tk.Label(frame_search, text="0 / 0")
        self.match_label.pack(side=tk.LEFT, padx=10)

        self.next_button = tk.Button(
            frame_search, text=">>", command=self.controller.next_match)
        self.next_button.pack(side=tk.LEFT, padx=2)

        self.last_button = tk.Button(
            frame_search, text=">>|", command=self.controller.jump_to_last)
        self.last_button.pack(side=tk.LEFT, padx=2)

        self.search_goto_label = tk.Label(
            frame_search, text=_("search.goto_label"))
        self.search_goto_label.pack(side=tk.LEFT, padx=5)
        self.index_entry = tk.Entry(frame_search, width=5)
        self.index_entry.pack(side=tk.LEFT)
        self.jump_button = tk.Button(frame_search, text=_(
            "search.goto_button"), command=self.controller.jump_to_index)
        self.jump_button.pack(side=tk.LEFT, padx=5)

        self.text_area = scrolledtext.ScrolledText(
            bottom_frame, width=100, height=10)
        self.text_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

    def update_console(self, text):
        '''
        Insert text in the console
        '''
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)  # automatic scroll

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

        self.events_tree.see(parent_id)

    def insert_consent_in_tree(self, cdict, consent_entries_from_model):
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
        if dt in consent_entries_from_model:
            self.consent_tree.delete(consent_entries_from_model[dt])

        new_item = self.consent_tree.insert("", tk.END, values=values)
        self.consent_tree.see(new_item)

        return new_item

    def refresh_user_props_tree(self, user_properties_from_model):
        """Refreshes the user properties display in the UI."""
        for item in self.user_props_tree.get_children():
            self.user_props_tree.delete(item)
        for prop_name, prop_val in user_properties_from_model.items():
            self.user_props_tree.insert(
                "", tk.END, text=f"{prop_name} = {prop_val}")
            
        # Scroll until the last item
        children = self.user_props_tree.get_children()
        if children:
            self.user_props_tree.see(children[-1])

    def clear_ui(self):
        """Clears all widgets that display session data."""
        self.text_area.delete("1.0", tk.END)
        for tree in [self.events_tree, self.user_props_tree, self.consent_tree]:
            for item in tree.get_children():
                tree.delete(item)
