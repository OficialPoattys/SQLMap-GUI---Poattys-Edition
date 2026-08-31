#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Zenmap-inspired Tkinter application for sqlmap.

The interface is intentionally split into four user concepts:

* Scan: target, profile, and the options most users need first;
* Options: every public sqlmap option grouped like the command line;
* Results: structured ``--report-json`` data;
* Output: the live terminal and interactive prompts.

No Tkinter import happens at module import time.  The package entry point
supplies Tk modules so the rest of sqlmap remains usable on headless systems.
"""

from __future__ import print_function

import io
import json
import os
import sys
import webbrowser

from lib.core.common import getSafeExString
from lib.core.common import saveConfig
from lib.core.data import paths
from lib.core.exception import SqlmapSystemException
from lib.core.settings import GIT_PAGE
from lib.core.settings import IS_WIN
from lib.core.settings import SITE
from lib.core.settings import VERSION_STRING
from lib.core.settings import WIKI_PAGE
from lib.gui.compat import list2cmdline
from lib.gui.compat import quote_arg
from lib.gui.compat import to_text
from lib.gui.models import DANGEROUS_OPTIONS
from lib.gui.models import OptionCatalog
from lib.gui.models import OptionModel
from lib.gui.models import ProfileStore
from lib.gui.models import profile_description
from lib.gui.runner import ScanRunner
from lib.gui.runner import create_report_file
from thirdparty.six.moves import configparser as _configparser


class SqlmapGui(object):
    """Main window and coordinator for the Tkinter front-end."""

    QUICK_OPTIONS = (
        "level", "risk", "technique", "testParameter", "tamper",
        "getBanner", "getCurrentUser", "getCurrentDb", "getDbs", "getTables",
        "getColumns", "dumpTable", "threads", "timeout", "delay",
    )

    TARGET_SOURCE_ORDER = (
        "url", "direct", "requestFile", "harFile", "logFile", "bulkFile", "googleDork", "openApiFile",
    )
    TARGET_SOURCE_OPTIONS = frozenset(TARGET_SOURCE_ORDER)

    TARGET_OPTIONS = TARGET_SOURCE_OPTIONS | frozenset(("openApiBase", "openApiTags"))

    def __init__(self, parser, tk, ttk, scrolledtext, messagebox, filedialog, font, simpledialog=None):
        self.parser = parser
        self.tk = tk
        self.ttk = ttk
        self.scrolledtext = scrolledtext
        self.messagebox = messagebox
        self.filedialog = filedialog
        self.font = font
        self.simpledialog = simpledialog

        self.catalog = OptionCatalog(parser)
        self.model = OptionModel(self.catalog)
        self.profiles = ProfileStore()
        self.runner = ScanRunner(paths.SQLMAP_ROOT_PATH)
        self.vars = {}
        self.controls = {}
        self.option_pages = {}
        self.option_page_builders = {}
        self.result_payloads = {}
        self.report = None
        self.report_path = None
        self._suspend = False
        self._poll_job = None
        self._force_stop_job = None
        self._target_history = []

        try:
            self.window = tk.Tk()
        except Exception as ex:
            raise SqlmapSystemException("unable to create GUI window ('%s')" % getSafeExString(ex))

        self._init_variables()
        self._init_fonts()
        self._init_style()
        self._build_layout()
        self._bind_shortcuts()
        self._refresh_command()
        self._select_profile("Detection only")
        self._poll_job = self.window.after(100, self._poll_runner)

    # ------------------------------------------------------------------
    # Initialization and layout

    def _init_variables(self):
        for dest in self.catalog.order:
            spec = self.catalog.by_dest[dest]
            if spec.kind == "bool":
                variable = self.tk.BooleanVar(value=bool(spec.default))
            else:
                variable = self.tk.StringVar(value=to_text(spec.default))
            self.vars[dest] = variable
            try:
                variable.trace("w", lambda *args, d=dest: self._value_changed(d))
            except Exception:
                pass

        self.profile_var = self.tk.StringVar(value="Detection only")
        self.command_var = self.tk.StringVar(value="sqlmap.py")
        self.status_var = self.tk.StringVar(value="Ready")
        self.hint_var = self.tk.StringVar(value="Choose a target and a profile, then review the command before running.")
        self.summary_var = self.tk.StringVar(value="No scan has been run in this window.")
        self.source_summary_var = self.tk.StringVar(value="No target source selected.")
        self.option_search_var = self.tk.StringVar(value="")

    def _init_fonts(self):
        default_family = self.font.nametofont("TkDefaultFont").actual("family")
        fixed_family = self.font.nametofont("TkFixedFont").actual("family")
        self.fonts = {
            "body": (default_family, 10),
            "small": (default_family, 9),
            "body_bold": (default_family, 10, "bold"),
            "title": (default_family, 18, "bold"),
            "section": (default_family, 12, "bold"),
            "mono": (fixed_family, 10),
        }

    def _init_style(self):
        p = self.palette = {
            "navy": "#18354a",
            "navy_dark": "#102535",
            "blue": "#176b92",
            "blue_light": "#dcecf3",
            "background": "#edf1f4",
            "surface": "#ffffff",
            "border": "#b8c3cc",
            "text": "#1d2933",
            "muted": "#5e6d78",
            "green": "#2f8f57",
            "red": "#b83d45",
            "orange": "#bd6d24",
            "selected": "#cfe6f0",
            "console": "#101b22",
            "console_text": "#d8e9df",
        }
        style = self.ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=self.fonts["body"], background=p["background"], foreground=p["text"])
        style.configure("TFrame", background=p["background"])
        style.configure("Surface.TFrame", background=p["surface"])
        style.configure("Header.TFrame", background=p["navy"])
        style.configure("Toolbar.TFrame", background=p["surface"])
        style.configure("TLabel", background=p["background"], foreground=p["text"])
        style.configure("Surface.TLabel", background=p["surface"], foreground=p["text"])
        style.configure("Muted.TLabel", background=p["background"], foreground=p["muted"], font=self.fonts["small"])
        style.configure("SurfaceMuted.TLabel", background=p["surface"], foreground=p["muted"], font=self.fonts["small"])
        style.configure("HeaderTitle.TLabel", background=p["navy"], foreground="#ffffff", font=self.fonts["title"])
        style.configure("HeaderSubtitle.TLabel", background=p["navy"], foreground="#c7e1ec", font=self.fonts["small"])
        style.configure("Section.TLabel", background=p["surface"], foreground=p["blue"], font=self.fonts["section"])
        style.configure("TButton", padding=(10, 5))
        style.configure("Accent.TButton", background=p["green"], foreground="#ffffff", font=self.fonts["body_bold"], padding=(14, 6))
        style.map("Accent.TButton", background=[("active", "#3aa967"), ("pressed", "#237441")])
        style.configure("Stop.TButton", background=p["red"], foreground="#ffffff", padding=(14, 6))
        style.configure("TNotebook", background=p["background"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7))
        style.map("TNotebook.Tab", background=[("selected", p["surface"])], foreground=[("selected", p["blue"])])
        style.configure("TEntry", fieldbackground="#ffffff", foreground=p["text"], padding=5)
        style.configure("TCombobox", fieldbackground="#ffffff", foreground=p["text"], padding=4)
        style.configure("TLabelframe", background=p["surface"], foreground=p["blue"])
        style.configure("TLabelframe.Label", background=p["surface"], foreground=p["blue"], font=self.fonts["body_bold"])
        style.configure("Treeview", rowheight=24, background="#ffffff", fieldbackground="#ffffff", foreground=p["text"])
        style.configure("Treeview.Heading", font=self.fonts["body_bold"])
        style.map("Treeview", background=[("selected", p["blue"])], foreground=[("selected", "#ffffff")])

        self.window.configure(background=p["background"])

    def _build_layout(self):
        tk, ttk, p = self.tk, self.ttk, self.palette
        self.window.title("sqlmap - graphical interface")
        self.window.minsize(1020, 700)
        self.window.geometry("1180x800")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)

        self._build_menu()
        self._build_header()
        self._build_target_bar()

        body = ttk.Panedwindow(self.window, orient=tk.HORIZONTAL)
        body.grid(row=2, column=0, sticky="nsew")
        body.add(self._build_sidebar(body), weight=0)
        body.add(self._build_notebook(body), weight=1)

        status = ttk.Frame(self.window, style="Toolbar.TFrame", padding=(12, 6))
        status.grid(row=3, column=0, sticky="ew")
        status.columnconfigure(1, weight=1)
        self.status_light = tk.Canvas(status, width=12, height=12, background=p["surface"], highlightthickness=0)
        self.status_light.grid(row=0, column=0, padx=(0, 7))
        ttk.Label(status, textvariable=self.status_var, style="SurfaceMuted.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(status, textvariable=self.hint_var, style="SurfaceMuted.TLabel", anchor="e").grid(row=0, column=2, sticky="e", padx=(12, 0))
        self._update_status_light()
        self._center_window()

    def _build_menu(self):
        p = self.palette
        menu_kw = {"bg": p["surface"], "fg": p["text"], "activebackground": p["blue"], "activeforeground": "#ffffff"}
        menubar = self.tk.Menu(self.window, borderwidth=0, **menu_kw)

        file_menu = self.tk.Menu(menubar, tearoff=0, **menu_kw)
        file_menu.add_command(label="New scan", command=self.new_scan)
        file_menu.add_command(label="Open sqlmap configuration...", command=self.load_config)
        file_menu.add_command(label="Export sqlmap configuration...", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Save current report...", command=self.save_report)
        file_menu.add_command(label="Save console output...", command=self.save_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menubar.add_cascade(label="File", menu=file_menu)

        scan_menu = self.tk.Menu(menubar, tearoff=0, **menu_kw)
        scan_menu.add_command(label="Start scan", command=self.start_scan)
        scan_menu.add_command(label="Stop scan", command=self.stop_scan)
        scan_menu.add_command(label="Clear output", command=self.clear_output)
        menubar.add_cascade(label="Scan", menu=scan_menu)

        profile_menu = self.tk.Menu(menubar, tearoff=0, **menu_kw)
        profile_menu.add_command(label="Save profile...", command=self.save_profile)
        profile_menu.add_command(label="Delete selected profile", command=self.delete_profile)
        menubar.add_cascade(label="Profile", menu=profile_menu)

        help_menu = self.tk.Menu(menubar, tearoff=0, **menu_kw)
        help_menu.add_command(label="Official site", command=lambda: webbrowser.open(SITE))
        help_menu.add_command(label="Wiki", command=lambda: webbrowser.open(WIKI_PAGE))
        help_menu.add_command(label="GitHub", command=lambda: webbrowser.open(GIT_PAGE))
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.window.configure(menu=menubar)

    def _build_header(self):
        ttk = self.ttk
        header = ttk.Frame(self.window, style="Header.TFrame", padding=(20, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="sqlmap", style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=VERSION_STRING.replace("sqlmap/", ""), style="HeaderSubtitle.TLabel").grid(row=1, column=0, sticky="w")
        self.run_button = ttk.Button(header, text="▶  Start scan", style="Accent.TButton", command=self.start_scan)
        self.run_button.grid(row=0, column=1, rowspan=2, padx=(15, 0))

    def _build_target_bar(self):
        tk, ttk, p = self.tk, self.ttk, self.palette
        outer = tk.Frame(self.window, background=p["border"], padx=1, pady=1)
        outer.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 8))
        card = ttk.Frame(outer, style="Surface.TFrame", padding=(12, 10))
        card.pack(fill=tk.X)
        card.columnconfigure(1, weight=1)
        card.columnconfigure(4, weight=0)

        ttk.Label(card, text="Target", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.target_entry = ttk.Entry(card, textvariable=self.vars.get("url"), width=50)
        self.target_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(card, text="Paste", command=self.paste_target).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(card, text="Clear", command=self.clear_target).grid(row=0, column=3, padx=(5, 0))

        ttk.Label(card, text="Profile", style="Section.TLabel").grid(row=0, column=4, sticky="w", padx=(18, 8))
        names = ["Custom"] + self.profiles.names()
        self.profile_combo = ttk.Combobox(card, textvariable=self.profile_var, values=names, state="readonly", width=22)
        self.profile_combo.grid(row=0, column=5, sticky="e")
        self.profile_combo.bind("<<ComboboxSelected>>", lambda event: self._select_profile(self.profile_var.get()))
        ttk.Button(card, text="Save profile", command=self.save_profile).grid(row=0, column=6, padx=(7, 0))

        ttk.Label(card, text="Command", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.command_entry = tk.Entry(card, textvariable=self.command_var, state="readonly", readonlybackground=p["navy_dark"],
                                      foreground="#9de0a9", background=p["navy_dark"], relief="flat", font=self.fonts["mono"])
        self.command_entry.grid(row=1, column=1, columnspan=6, sticky="ew", pady=(8, 0), ipady=5)

    def _build_sidebar(self, parent):
        tk, ttk, p = self.tk, self.ttk, self.palette
        sidebar = ttk.Frame(parent, style="Surface.TFrame", padding=(12, 12))
        sidebar.configure(width=225)
        sidebar.pack_propagate(False)
        sidebar.rowconfigure(2, weight=1)

        ttk.Label(sidebar, text="Profiles", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(sidebar, text="Reusable scan configurations", style="SurfaceMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 8))
        self.profile_list = tk.Listbox(sidebar, exportselection=False, relief="flat", borderwidth=1,
                                       background="#f7fafb", foreground=p["text"], selectbackground=p["blue"],
                                       selectforeground="#ffffff", highlightthickness=1,
                                       highlightbackground=p["border"], font=self.fonts["body"])
        self.profile_list.grid(row=2, column=0, sticky="nsew")
        self.profile_list.bind("<<ListboxSelect>>", self._profile_list_selected)
        for name in ["Custom"] + self.profiles.names():
            self.profile_list.insert(tk.END, name)
        self.profile_list.selection_set(1)

        self.profile_description = tk.StringVar(value=profile_description("Detection only"))
        ttk.Label(sidebar, textvariable=self.profile_description, style="SurfaceMuted.TLabel", wraplength=195, justify="left").grid(row=3, column=0, sticky="ew", pady=(10, 12))
        buttons = ttk.Frame(sidebar, style="Surface.TFrame")
        buttons.grid(row=4, column=0, sticky="ew")
        ttk.Button(buttons, text="Save...", command=self.save_profile).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(buttons, text="Delete", command=self.delete_profile).pack(side=tk.LEFT, padx=(6, 0))
        return sidebar

    def _build_notebook(self, parent):
        notebook = self.notebook = self.ttk.Notebook(parent)
        notebook.add(self._build_scan_tab(notebook), text="Scan")
        notebook.add(self._build_options_tab(notebook), text="Options")
        notebook.add(self._build_results_tab(notebook), text="Results")
        notebook.add(self._build_output_tab(notebook), text="Output")
        return notebook

    def _build_scan_tab(self, parent):
        tk, ttk, p = self.tk, self.ttk, self.palette
        tab = ttk.Frame(parent, style="Surface.TFrame", padding=(18, 15))
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=0)

        intro = tk.Frame(tab, background=p["blue_light"], highlightthickness=1, highlightbackground=p["border"])
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 13))
        ttk.Label(intro, text="Start a scan", style="Surface.TLabel").pack(anchor="w", padx=12, pady=(9, 1))
        ttk.Label(intro, text="Select a profile, review the generated command, and start only after confirming the target scope.", style="SurfaceMuted.TLabel").pack(anchor="w", padx=12, pady=(0, 9))

        quick = ttk.LabelFrame(tab, text="Common options", padding=(12, 9))
        quick.grid(row=1, column=0, sticky="ew")
        quick.columnconfigure(1, weight=1)
        quick.columnconfigure(3, weight=1)
        row = 0
        for index, dest in enumerate(self.QUICK_OPTIONS):
            spec = self.catalog.get(dest)
            if spec is None:
                continue
            column = 0 if index % 2 == 0 else 2
            value_column = column + 1
            if column == 0 and index > 0:
                row += 1
            self._build_control(quick, spec, row, column, value_column, compact=True)

        sources = ttk.LabelFrame(tab, text="Alternative target sources", padding=(12, 8))
        sources.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(sources, textvariable=self.source_summary_var, style="SurfaceMuted.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        source_buttons = (
            ("HTTP request...", "requestFile"),
            ("Burp/WebScarab log...", "logFile"),
            ("HAR export...", "harFile"),
            ("OpenAPI file...", "openApiFile"),
            ("Target list...", "bulkFile"),
        )
        for column, (label, dest) in enumerate(source_buttons):
            ttk.Button(sources, text=label, command=lambda d=dest: self._choose_target_file(d)).grid(row=1, column=column, padx=(0 if column == 0 else 6, 0), sticky="w")
        ttk.Button(sources, text="Clear sources", command=self.clear_target).grid(row=1, column=len(source_buttons), padx=(8, 0), sticky="w")

        actions = ttk.Frame(tab, style="Surface.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(15, 0))
        ttk.Button(actions, text="Open advanced options", command=lambda: self.notebook.select(1)).pack(side=tk.LEFT)
        ttk.Button(actions, text="Export configuration...", command=self.save_config).pack(side=tk.LEFT, padx=(7, 0))
        ttk.Button(actions, text="Start scan", style="Accent.TButton", command=self.start_scan).pack(side=tk.RIGHT)
        return tab

    def _build_options_tab(self, parent):
        tk, ttk, p = self.tk, self.ttk, self.palette
        tab = ttk.Frame(parent, style="Surface.TFrame", padding=(10, 10))
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        ttk.Label(tab, text="Advanced options", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=(0, 7))
        search = ttk.Entry(tab, textvariable=self.option_search_var)
        search.grid(row=0, column=1, sticky="e", padx=8, pady=(0, 7))
        search.configure(width=34)
        search.insert(0, "")
        search.bind("<Return>", self._activate_option_search)
        try:
            self.option_search_var.trace("w", lambda *args: self._option_search_changed())
        except Exception:
            pass

        left = ttk.Frame(tab, style="Surface.TFrame", padding=(4, 4))
        left.grid(row=1, column=0, sticky="nsw")
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Categories", style="SurfaceMuted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.category_list = tk.Listbox(left, width=25, exportselection=False, relief="flat", borderwidth=1,
                                        background="#f7fafb", foreground=p["text"], selectbackground=p["blue"],
                                        selectforeground="#ffffff", highlightthickness=1,
                                        highlightbackground=p["border"], font=self.fonts["body"])
        self.category_list.grid(row=1, column=0, sticky="ns")
        self.category_list.bind("<<ListboxSelect>>", self._category_selected)
        for title, _, _ in self.catalog.groups:
            self.category_list.insert(tk.END, title)

        separator = tk.Frame(tab, background=p["border"], width=1)
        separator.grid(row=1, column=0, sticky="nse", padx=(8, 9))

        outer = ttk.Frame(tab, style="Surface.TFrame")
        outer.grid(row=1, column=1, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(outer, background=p["surface"], highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, style="Surface.TFrame", padding=(8, 4, 18, 16))
        inner.columnconfigure(1, weight=1)
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.option_canvas = canvas
        self.option_inner = inner

        if self.catalog.groups:
            self.category_list.selection_set(0)
            self._show_category(0)
        return tab

    def _build_results_tab(self, parent):
        tk, ttk, p = self.tk, self.ttk, self.palette
        tab = ttk.Frame(parent, style="Surface.TFrame", padding=(12, 12))
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        top = ttk.Frame(tab, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Structured results", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.summary_var, style="SurfaceMuted.TLabel", wraplength=780, justify="left").grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Button(top, text="Save report...", command=self.save_report).grid(row=0, column=1, rowspan=2, sticky="e")

        tree_frame = ttk.Frame(tab, style="Surface.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.results_tree = ttk.Treeview(tree_frame, columns=("value",), show="tree headings", selectmode="browse")
        self.results_tree.heading("#0", text="Result")
        self.results_tree.heading("value", text="Value")
        self.results_tree.column("#0", width=290, stretch=False)
        self.results_tree.column("value", width=680, stretch=True)
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=tree_scroll.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.results_tree.bind("<<TreeviewSelect>>", self._result_selected)

        details = ttk.LabelFrame(tab, text="Selected value", padding=(7, 5))
        details.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(0, weight=1)
        self.result_details = self.scrolledtext.ScrolledText(details, height=7, wrap=tk.NONE, state="disabled",
                                                              background="#f7fafb", foreground=p["text"],
                                                              font=self.fonts["mono"])
        self.result_details.grid(row=0, column=0, sticky="ew")
        return tab

    def _build_output_tab(self, parent):
        tk, ttk, p = self.tk, self.ttk, self.palette
        tab = ttk.Frame(parent, style="Surface.TFrame", padding=(10, 10))
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(tab, style="Surface.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(toolbar, text="Live output", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Clear", command=self.clear_output).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Save output...", command=self.save_output).pack(side=tk.RIGHT, padx=(0, 7))

        self.output_text = self.scrolledtext.ScrolledText(tab, wrap=tk.NONE, state="disabled", undo=False,
                                                          background=p["console"], foreground=p["console_text"],
                                                          insertbackground="#ffffff", selectbackground=p["blue"],
                                                          font=self.fonts["mono"], padx=10, pady=8)
        self.output_text.grid(row=1, column=0, sticky="nsew")
        self.output_text.tag_configure("system", foreground="#9bb5a4")
        self.output_text.tag_configure("error", foreground="#ff9a9f")

        input_bar = ttk.Frame(tab, style="Surface.TFrame", padding=(0, 8, 0, 0))
        input_bar.grid(row=2, column=0, sticky="ew")
        input_bar.columnconfigure(1, weight=1)
        ttk.Label(input_bar, text="Input", style="SurfaceMuted.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.input_var = tk.StringVar(value="")
        self.input_entry = ttk.Entry(input_bar, textvariable=self.input_var)
        self.input_entry.grid(row=0, column=1, sticky="ew")
        self.input_entry.bind("<Return>", self.send_input)
        ttk.Button(input_bar, text="Send", command=self.send_input).grid(row=0, column=2, padx=(7, 0))
        return tab

    # ------------------------------------------------------------------
    # Dynamic option editor

    def _build_control(self, parent, spec, row, label_column, value_column, compact=False):
        tk, ttk = self.tk, self.ttk
        if spec.kind == "bool":
            widget = ttk.Checkbutton(parent, text=spec.flag, variable=self.vars[spec.dest], command=lambda d=spec.dest: self._value_changed(d))
            widget.grid(row=row, column=label_column, columnspan=2, sticky="w", padx=(3, 12), pady=4)
            self.controls.setdefault(spec.dest, []).append(widget)
            self._attach_help(widget, spec)
            return widget

        label = ttk.Label(parent, text=spec.flag, style="Surface.TLabel")
        label.grid(row=row, column=label_column, sticky="w", padx=(3, 12), pady=(4, 0 if compact else 1))
        field = ttk.Frame(parent, style="Surface.TFrame")
        field.grid(row=row, column=value_column, sticky="ew", pady=(2, 4))
        field.columnconfigure(0, weight=1)

        if spec.choices:
            widget = ttk.Combobox(field, textvariable=self.vars[spec.dest], values=[to_text(_) for _ in spec.choices], state="readonly")
        else:
            show = "*" if spec.secret and spec.dest not in ("headers",) else None
            widget = ttk.Entry(field, textvariable=self.vars[spec.dest], show=show) if show else ttk.Entry(field, textvariable=self.vars[spec.dest])
            if spec.kind in ("int", "float"):
                command = self.window.register(lambda proposed, kind=spec.kind: self._valid_number(proposed, kind))
                widget.configure(validate="key", validatecommand=(command, "%P"))
        widget.grid(row=0, column=0, sticky="ew")
        self.controls.setdefault(spec.dest, []).append(widget)
        self._attach_help(widget, spec)

        if spec.file_value:
            if spec.dest == "outputDir":
                action = self._choose_directory
            else:
                action = self._choose_file
            ttk.Button(field, text="...", width=3, command=lambda d=spec.dest, a=action: a(d)).grid(row=0, column=1, padx=(5, 0))

        if not compact:
            help_label = ttk.Label(parent, text=self._help_text(spec), style="SurfaceMuted.TLabel", wraplength=720, justify="left")
            help_label.grid(row=row + 1, column=label_column, columnspan=2, sticky="w", padx=(3, 12), pady=(0, 6))
        return widget

    def _show_category(self, index):
        if index < 0 or index >= len(self.catalog.groups):
            return
        title, description, specs = self.catalog.groups[index]
        for child in self.option_inner.winfo_children():
            child.destroy()
        self.controls = {}
        self.option_inner.columnconfigure(1, weight=1)
        self.ttk.Label(self.option_inner, text=title, style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(4, 1))
        self.ttk.Label(self.option_inner, text=description or "Options from the sqlmap command line.", style="SurfaceMuted.TLabel", wraplength=740, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        row = 2
        for spec in specs:
            self._build_control(self.option_inner, spec, row, 0, 1, compact=False)
            row += 2 if spec.kind != "bool" else 1
        self.option_canvas.yview_moveto(0)
        self.option_inner.update_idletasks()

    def _category_selected(self, event=None):
        selection = self.category_list.curselection()
        if selection:
            self._show_category(int(selection[0]))

    def _option_search_changed(self):
        query = self.option_search_var.get().strip()
        if not query:
            return
        matches = self.catalog.search(query)
        if matches:
            first = matches[0]
            for index, (title, _, _) in enumerate(self.catalog.groups):
                if title == first.section:
                    self.category_list.selection_clear(0, self.tk.END)
                    self.category_list.selection_set(index)
                    self.category_list.see(index)
                    self._show_category(index)
                    break

    def _activate_option_search(self, event=None):
        matches = self.catalog.search(self.option_search_var.get())
        if not matches:
            return "break"
        spec = matches[0]
        self.notebook.select(1)
        self._focus_option(spec.dest)
        return "break"

    def _focus_option(self, dest):
        for index, (title, _, specs) in enumerate(self.catalog.groups):
            if any(spec.dest == dest for spec in specs):
                self.category_list.selection_clear(0, self.tk.END)
                self.category_list.selection_set(index)
                self.category_list.see(index)
                self._show_category(index)
                self.window.after_idle(lambda d=dest: self._focus_control(d))
                return

    def _focus_control(self, dest):
        widgets = self.controls.get(dest, [])
        if not widgets:
            return
        try:
            widgets[0].focus_set()
            self.option_canvas.yview_moveto(0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Profiles and configuration

    def _profile_list_selected(self, event=None):
        selection = self.profile_list.curselection()
        if not selection:
            return
        name = self.profile_list.get(selection[0])
        if name != self.profile_var.get():
            self._select_profile(name)

    def _select_profile(self, name):
        if not name:
            return
        self._suspend = True
        try:
            targets = dict((dest, self.model.get(dest)) for dest in self.TARGET_OPTIONS if self.catalog.get(dest))
            if name == "Custom":
                pass
            else:
                self.model.reset()
                self.model.apply(self.profiles.values(name))
                for dest, value in targets.items():
                    self.model.set(dest, value)
            self.profile_var.set(name)
            if name != "Custom":
                self.model.changed = False
            self._sync_variables()
            self.profile_description.set(profile_description(name))
            for index in range(self.profile_list.size()):
                if self.profile_list.get(index) == name:
                    self.profile_list.selection_clear(0, self.tk.END)
                    self.profile_list.selection_set(index)
                    self.profile_list.see(index)
                    break
        finally:
            self._suspend = False
        self._refresh_command()
        self.hint_var.set("Profile '%s' selected" % name)

    def _sync_variables(self):
        for dest, spec in self.catalog.by_dest.items():
            try:
                self.vars[dest].set(self.model.get(dest))
            except Exception:
                pass

    def save_profile(self):
        if self.simpledialog is None:
            return
        name = self.simpledialog.askstring("Save profile", "Profile name:", parent=self.window)
        if not name:
            return
        name = name.strip()
        if not name or name.lower() == "custom":
            self.messagebox.showwarning("Invalid profile", "Choose a different profile name.")
            return
        try:
            # Secrets are intentionally not written to profile files.  They can
            # still be entered for the current run and exported explicitly.
            values = self.model.snapshot(include_secrets=False)
            self.profiles.save(name, values)
            self._refresh_profile_lists()
            self._select_profile(name)
            self.hint_var.set("Profile saved without secret fields")
        except Exception as ex:
            self.messagebox.showerror("Save profile failed", getSafeExString(ex))

    def delete_profile(self):
        name = self.profile_var.get()
        if name not in self.profiles.custom:
            self.hint_var.set("Built-in profiles cannot be deleted")
            return
        if not self.messagebox.askyesno("Delete profile", "Delete profile '%s'?" % name):
            return
        self.profiles.delete(name)
        self._refresh_profile_lists()
        self._select_profile("Custom")

    def _refresh_profile_lists(self):
        names = ["Custom"] + self.profiles.names()
        self.profile_combo.configure(values=names)
        self.profile_list.delete(0, self.tk.END)
        for name in names:
            self.profile_list.insert(self.tk.END, name)

    def save_config(self):
        path = self.filedialog.asksaveasfilename(
            parent=self.window, title="Export sqlmap configuration", defaultextension=".conf",
            filetypes=[("sqlmap configuration", "*.conf"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            config = self.model.collect_config()
            # The CLI normalizes repeated -H/--header values into the
            # serializable `headers` option. Preserve that behavior here.
            header = config.pop("header", None)
            if header:
                existing = config.get("headers") or ""
                config["headers"] = (existing + "\n" + header).strip() if existing else header
            saveConfig(config, path)
            self.hint_var.set("Configuration exported to %s" % os.path.basename(path))
        except Exception as ex:
            self.messagebox.showerror("Export failed", getSafeExString(ex))

    def load_config(self):
        path = self.filedialog.askopenfilename(
            parent=self.window, title="Open sqlmap configuration",
            filetypes=[("sqlmap configuration", "*.conf *.ini"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            parser = _configparser.ConfigParser()
            parser.optionxform = str
            parser.read(path)
            values = {}
            for section in parser.sections():
                for name, value in parser.items(section):
                    dest = name
                    if dest not in self.catalog.by_dest and dest == "headers" and "header" in self.catalog.by_dest:
                        dest = "header"
                    if dest not in self.catalog.by_dest:
                        continue
                    spec = self.catalog.by_dest[dest]
                    if spec.kind == "bool":
                        values[dest] = value.strip().lower() in ("1", "true", "yes", "on")
                    elif spec.kind == "int":
                        values[dest] = int(value) if value.strip() else ""
                    elif spec.kind == "float":
                        values[dest] = float(value) if value.strip() else ""
                    else:
                        values[dest] = value
            self._suspend = True
            self.model.apply(values)
            self._sync_variables()
            self._suspend = False
            self.profile_var.set("Custom")
            self._refresh_command()
            self.hint_var.set("Loaded configuration from %s" % os.path.basename(path))
        except Exception as ex:
            self._suspend = False
            self.messagebox.showerror("Load failed", getSafeExString(ex))

    def new_scan(self):
        if self.runner.is_running():
            self.hint_var.set("Stop the current scan before starting a new configuration")
            return
        self._suspend = True
        self.model.reset()
        self._sync_variables()
        self._suspend = False
        self._select_profile("Detection only")
        self.clear_output()
        self._clear_results()
        self.report = None
        self.hint_var.set("New scan configuration created")

    # ------------------------------------------------------------------
    # Scan lifecycle

    def start_scan(self):
        if self.runner.is_running():
            self.notebook.select(3)
            self.hint_var.set("A scan is already running")
            return

        if not self._has_target():
            self.messagebox.showwarning("Target required", "Provide a URL, request file, bulk file, log, OpenAPI document, or direct database target.")
            self.notebook.select(0)
            return

        dangerous = [
            spec.flag for dest, spec in self.catalog.by_dest.items()
            if dest in DANGEROUS_OPTIONS and self._is_set(spec)
        ]
        if dangerous:
            message = "This configuration enables high-impact options:\n\n%s\n\nContinue only if you are authorized to test this target." % "\n".join(dangerous)
            if not self.messagebox.askyesno("Confirm high-impact scan", message):
                return

        report_path = create_report_file()
        args = self._build_arguments()
        frozen = bool(getattr(sys, "frozen", False))
        script = os.path.join(paths.SQLMAP_ROOT_PATH, "sqlmap.py")
        if not frozen and not os.path.isfile(script):
            self.messagebox.showerror("Unable to start", "Could not locate sqlmap.py at:\n%s" % script)
            self._remove_report(report_path)
            return

        # In a source checkout the interpreter launches sqlmap.py. In a future
        # frozen build the executable is already the sqlmap entry point, so do
        # not append a script path that would not exist beside the executable.
        command = [sys.executable or "python"]
        if not frozen:
            command.append(script)
        command += args
        # Structured reporting is an implementation detail of the GUI. It
        # avoids parsing human-readable console lines and is shared with the API.
        command += ["--report-json", report_path, "--disable-coloring"]
        try:
            self.runner.start(command, report_path=report_path)
        except Exception as ex:
            self._remove_report(report_path)
            self.messagebox.showerror("Unable to start sqlmap", getSafeExString(ex))
            return

        self.report = None
        self.report_path = report_path
        self.clear_output()
        self._append_output("$ %s\n\n" % self._format_command(command), "system")
        self.notebook.select(3)
        self.status_var.set("Running")
        self.hint_var.set("sqlmap is running; output will appear here")
        self._update_status_light()
        self._update_run_button()

    def stop_scan(self):
        if not self.runner.is_running():
            self.hint_var.set("No scan is running")
            return
        if self.messagebox.askyesno("Stop scan", "Stop the running sqlmap process?"):
            self.runner.stop()
            self.status_var.set("Stopping")
            self.hint_var.set("Stopping sqlmap...")
            try:
                if self._force_stop_job is not None:
                    self.window.after_cancel(self._force_stop_job)
                self._force_stop_job = self.window.after(3000, self._force_stop_if_needed)
            except Exception:
                self._force_stop_job = None

    def _force_stop_if_needed(self):
        self._force_stop_job = None
        if self.runner.is_running():
            self.runner.stop(force=True)
            self.hint_var.set("sqlmap did not stop cleanly; process group terminated")

    def _poll_runner(self):
        for event in self.runner.drain():
            kind = event[0]
            if kind == "started":
                self._append_output("[sqlmap process started]\n", "system")
            elif kind == "output":
                self._append_output(event[1])
            elif kind == "error":
                self._append_output("[%s]" % event[1], "error")
            elif kind == "finished":
                self._scan_finished(event[1], event[2])
        self._update_run_button()
        self._update_status_light()
        try:
            self._poll_job = self.window.after(100, self._poll_runner)
        except Exception:
            self._poll_job = None

    def _scan_finished(self, returncode, report_path):
        if self._force_stop_job is not None:
            try:
                self.window.after_cancel(self._force_stop_job)
            except Exception:
                pass
            self._force_stop_job = None
        if returncode == 0:
            self.status_var.set("Finished successfully")
        else:
            self.status_var.set("Finished with exit code %s" % returncode)
        self.hint_var.set("Scan finished; review Results and Output")
        self._append_output("\n--- process finished (exit code %s) ---\n" % returncode, "system")
        if report_path:
            try:
                with io.open(report_path, "r", encoding="utf-8") as handle:
                    self.report = json.load(handle)
                self._render_report(self.report)
            except (IOError, OSError, ValueError) as ex:
                self._append_output("[report unavailable: %s]\n" % getSafeExString(ex), "error")
            finally:
                self._remove_report(report_path)
        self.notebook.select(2)
        self._update_run_button()

    def _build_arguments(self):
        args = []
        for dest in self.catalog.order:
            spec = self.catalog.by_dest[dest]
            value = self.model.get(dest)
            if spec.kind == "bool":
                if bool(value) and not spec.is_default(value):
                    args.append(spec.flag)
                continue
            if value in (None, "") or spec.is_default(value):
                continue
            if dest == "header" and "\n" in to_text(value):
                for header in to_text(value).splitlines():
                    if header.strip():
                        args.extend((spec.flag, header.strip()))
            else:
                args.extend((spec.flag, to_text(value)))
        return args

    def _format_command(self, command):
        if IS_WIN:
            return list2cmdline(command)
        return " ".join(quote_arg(value, False) for value in command)

    # ------------------------------------------------------------------
    # Output, results, and file helpers

    def _append_output(self, value, tag=None):
        try:
            at_bottom = self.output_text.yview()[1] >= 0.985
            self.output_text.configure(state="normal")
            if tag:
                self.output_text.insert(self.tk.END, to_text(value), tag)
            else:
                self.output_text.insert(self.tk.END, to_text(value))
            line_count = int(float(self.output_text.index("end-1c").split(".")[0]))
            if line_count > 20000:
                self.output_text.delete("1.0", "%d.0" % (line_count - 20000))
            self.output_text.configure(state="disabled")
            if at_bottom:
                self.output_text.see(self.tk.END)
        except Exception:
            pass

    def clear_output(self):
        if not hasattr(self, "output_text"):
            return
        try:
            self.output_text.configure(state="normal")
            self.output_text.delete("1.0", self.tk.END)
            self.output_text.configure(state="disabled")
        except Exception:
            pass

    def send_input(self, event=None):
        value = self.input_var.get()
        if not value or not self.runner.is_running():
            return "break"
        if self.runner.send_input(value):
            self._append_output("> %s\n" % value, "system")
            self.input_var.set("")
        return "break"

    def save_output(self):
        path = self.filedialog.asksaveasfilename(parent=self.window, title="Save console output", defaultextension=".log", filetypes=[("Log file", "*.log"), ("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(to_text(self.output_text.get("1.0", "end-1c")))
            self.hint_var.set("Console output saved to %s" % os.path.basename(path))
        except Exception as ex:
            self.messagebox.showerror("Save output failed", getSafeExString(ex))

    def _render_report(self, report):
        self._clear_results()
        if not isinstance(report, dict):
            return
        data = report.get("data") or []
        errors = report.get("error") or []
        meta = report.get("meta") or {}
        types = [item.get("type_name") for item in data if isinstance(item, dict) and item.get("type_name")]
        summary = "%d structured result section(s)" % len(data)
        if types:
            summary += ": " + ", ".join(types)
        if errors:
            summary += " | %d error(s)" % len(errors)
        if meta.get("sqlmap_version"):
            summary += " | " + to_text(meta.get("sqlmap_version"))
        self.summary_var.set(summary)

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            title = item.get("type_name") or ("Type %s" % item.get("type"))
            root = self.results_tree.insert("", self.tk.END, text=title, values=(to_text(item.get("status", "")),), open=True)
            self.result_payloads[root] = item.get("value")
            self._insert_value(root, item.get("value"))
        if errors:
            error_root = self.results_tree.insert("", self.tk.END, text="Errors", values=("%d message(s)" % len(errors),), open=True)
            self.result_payloads[error_root] = errors
            self._insert_value(error_root, errors)

    def _insert_value(self, parent, value, depth=0):
        if depth > 8:
            child = self.results_tree.insert(parent, self.tk.END, text="...", values=("depth limit",))
            self.result_payloads[child] = value
            return
        if isinstance(value, dict):
            for key in sorted(value.keys(), key=lambda x: to_text(x)):
                child = self.results_tree.insert(parent, self.tk.END, text=to_text(key), values=(self._short_value(value[key]),), open=False)
                self.result_payloads[child] = value[key]
                if isinstance(value[key], (dict, list, tuple)):
                    self._insert_value(child, value[key], depth + 1)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                child = self.results_tree.insert(parent, self.tk.END, text="[%d]" % index, values=(self._short_value(item),), open=False)
                self.result_payloads[child] = item
                if isinstance(item, (dict, list, tuple)):
                    self._insert_value(child, item, depth + 1)

    def _result_selected(self, event=None):
        selection = self.results_tree.selection()
        if not selection:
            return
        value = self.result_payloads.get(selection[0])
        try:
            rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            rendered = to_text(value)
        if not isinstance(rendered, str):
            rendered = to_text(rendered)
        self.result_details.configure(state="normal")
        self.result_details.delete("1.0", self.tk.END)
        self.result_details.insert("1.0", rendered)
        self.result_details.configure(state="disabled")

    def _clear_results(self):
        if not hasattr(self, "results_tree"):
            return
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.result_payloads = {}
        self.summary_var.set("No scan has been run in this window.")
        try:
            self.result_details.configure(state="normal")
            self.result_details.delete("1.0", self.tk.END)
            self.result_details.configure(state="disabled")
        except Exception:
            pass

    def save_report(self):
        if self.report is None:
            self.hint_var.set("There is no structured report to save")
            return
        path = self.filedialog.asksaveasfilename(parent=self.window, title="Save JSON report", defaultextension=".json", filetypes=[("JSON report", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with io.open(path, "w", encoding="utf-8") as handle:
                json.dump(self.report, handle, indent=2, ensure_ascii=False)
            self.hint_var.set("Report saved to %s" % os.path.basename(path))
        except Exception as ex:
            self.messagebox.showerror("Save report failed", getSafeExString(ex))

    # ------------------------------------------------------------------
    # Small helpers and window management

    def _value_changed(self, dest):
        if self._suspend:
            return
        spec = self.catalog.get(dest)
        if spec is None:
            return
        try:
            value = self.vars[dest].get()
        except Exception:
            return
        self.model.set(dest, value)
        if dest in self.TARGET_SOURCE_OPTIONS and value not in (None, "", False):
            self._suspend = True
            try:
                self._clear_target_sources_except(dest)
            finally:
                self._suspend = False
        if self.profile_var.get() not in ("Custom", ""):
            self.profile_var.set("Custom")
            self.profile_description.set(profile_description("Custom"))
        self._refresh_command()
        self._update_status_light()

    def _refresh_command(self):
        if not hasattr(self, "command_var"):
            return
        args = self._build_arguments()
        preview = ["sqlmap.py"] + args
        self.command_var.set(self._format_command(preview))
        if hasattr(self, "source_summary_var"):
            labels = {
                "url": "URL",
                "direct": "direct database connection",
                "requestFile": "HTTP request file",
                "logFile": "Burp/WebScarab log",
                "harFile": "HAR export",
                "bulkFile": "target list",
                "googleDork": "Google dork",
                "openApiFile": "OpenAPI/Swagger document",
            }
            selected = [(labels.get(dest, dest), self.model.get(dest)) for dest in self.TARGET_SOURCE_ORDER if self.model.get(dest) not in (None, "", False)]
            if selected:
                self.source_summary_var.set("Active target source: %s" % selected[0][0])
            else:
                self.source_summary_var.set("No target source selected.")

    def _is_set(self, spec):
        return not spec.is_default(self.model.get(spec.dest))

    def _has_target(self):
        return any(self.model.get(dest) not in (None, "", False) for dest in self.TARGET_SOURCE_ORDER if self.catalog.get(dest))

    def _valid_number(self, proposed, kind):
        if proposed in ("", "+", "-", ".", "+.", "-."):
            return True
        try:
            int(proposed) if kind == "int" else float(proposed)
            return True
        except (TypeError, ValueError):
            return False

    def _help_text(self, spec):
        text = spec.help or "No additional description is available."
        suffix = " Default: %s." % spec.display_default()
        if spec.dangerous:
            suffix += " High-impact option; review the target scope before using it."
        if spec.secret:
            suffix += " Secret values are not saved in profiles."
        return text + suffix

    def _attach_help(self, widget, spec):
        try:
            widget._sqlmap_help = self._help_text(spec)
        except Exception:
            pass

    def _choose_file(self, dest):
        path = self.filedialog.askopenfilename(parent=self.window, title="Choose file")
        if path:
            self._set_value(dest, path)

    def _choose_directory(self, dest):
        path = self.filedialog.askdirectory(parent=self.window, title="Choose directory")
        if path:
            self._set_value(dest, path)

    def _choose_target_file(self, dest):
        path = self.filedialog.askopenfilename(parent=self.window, title="Choose target source")
        if path:
            self._set_target_source(dest, path)

    def _set_target_source(self, dest, value):
        if dest not in self.TARGET_SOURCE_OPTIONS or dest not in self.vars:
            return
        self._suspend = True
        try:
            for source in self.TARGET_SOURCE_ORDER:
                if source not in self.vars:
                    continue
                selected = value if source == dest else ""
                self.model.set(source, selected)
                self.vars[source].set(selected)
        finally:
            self._suspend = False
        self._refresh_command()

    def _clear_target_sources_except(self, dest):
        for source in self.TARGET_SOURCE_ORDER:
            if source == dest or source not in self.vars:
                continue
            self.model.set(source, "")
            self.vars[source].set("")

    def _set_value(self, dest, value):
        if dest not in self.vars:
            return
        self._suspend = True
        try:
            self.model.set(dest, value)
            self.vars[dest].set(value)
        finally:
            self._suspend = False
        self._refresh_command()

    def paste_target(self):
        try:
            self._set_target_source("url", to_text(self.window.clipboard_get()).strip())
            self.target_entry.focus_set()
        except Exception:
            self.hint_var.set("Clipboard does not contain text")

    def clear_target(self):
        self._set_target_source("url", "")
        try:
            self.target_entry.focus_set()
        except Exception:
            pass

    def _update_run_button(self):
        if not hasattr(self, "run_button"):
            return
        if self.runner.is_running():
            self.run_button.configure(text="■  Stop scan", style="Stop.TButton", command=self.stop_scan)
        else:
            self.run_button.configure(text="▶  Start scan", style="Accent.TButton", command=self.start_scan)

    def _update_status_light(self):
        if not hasattr(self, "status_light"):
            return
        try:
            self.status_light.delete("all")
            color = self.palette["green"] if self.runner.is_running() else self.palette["blue"] if self.model.changed else self.palette["border"]
            self.status_light.create_oval(2, 2, 10, 10, fill=color, outline="")
        except Exception:
            pass

    def _center_window(self):
        self.window.update_idletasks()
        width = max(1020, self.window.winfo_width())
        height = max(700, self.window.winfo_height())
        x = max(0, self.window.winfo_screenwidth() // 2 - width // 2)
        y = max(0, self.window.winfo_screenheight() // 2 - height // 2)
        self.window.geometry("%dx%d+%d+%d" % (width, height, x, y))

    def _bind_shortcuts(self):
        self.window.bind("<Control-r>", lambda event: self.start_scan())
        self.window.bind("<Control-s>", lambda event: self.save_config())
        self.window.bind("<Control-o>", lambda event: self.load_config())
        self.window.bind("<Control-l>", lambda event: self._focus_target())
        self.window.bind("<Escape>", lambda event: self.stop_scan() if self.runner.is_running() else None)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def _focus_target(self):
        try:
            self.target_entry.focus_set()
            self.target_entry.select_range(0, self.tk.END)
        except Exception:
            pass
        return "break"

    def about(self):
        self.messagebox.showinfo("About sqlmap GUI", "%s\n\nZenmap-inspired Tkinter interface\n\n%s" % (VERSION_STRING, SITE), parent=self.window)

    def _remove_report(self, path):
        if path:
            try:
                os.remove(path)
            except (IOError, OSError):
                pass

    def close(self):
        if self.runner.is_running():
            if not self.messagebox.askyesno("Exit", "A scan is running. Stop it and exit?", parent=self.window):
                return
            self.runner.stop(force=True)
        if self._poll_job is not None:
            try:
                self.window.after_cancel(self._poll_job)
            except Exception:
                pass
        if self._force_stop_job is not None:
            try:
                self.window.after_cancel(self._force_stop_job)
            except Exception:
                pass
        self._remove_report(self.report_path)
        try:
            self.window.destroy()
        except Exception:
            pass


__all__ = ["SqlmapGui"]
