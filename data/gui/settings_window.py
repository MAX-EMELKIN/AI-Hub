# -*- coding: utf-8 -*-
# data/gui/settings_window.py

import os, time, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from data.core.config_manager import config
from data.core.hotkey_manager import hotkey_manager
from data.core.i18n import t, i18n
from data.core.logger import logger
from data.gui.dialogs import attach_entry_context_menu
from data.gui.theme_manager import theme
from data.ocr.ocr_engine import ocr_engine
from data.tts.tts_engine import tts_engine
from data.gui.dialog_helpers import ToolTip

SEARCH_ENGINE_DISPLAY = [
    ("google", "Text"),
    ("duckduckgo", "Text"),
    ("brave", "Text"),
    ("tavily", "Text"),
    ("serper", "Serper (Google Search API)"),
    ("searxng", "Text")
]

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, on_settings_updated=None):
        super().__init__(parent)
        self.parent = parent
        self.on_settings_updated = on_settings_updated

        theme.apply_ttk_theme(self)

        bg_main = theme.get_color("bg_main")
        self.title(t("settings_title", "Text"))
        self.geometry("760x650")
        self.minsize(700, 520)
        self.configure(bg=bg_main)
        self.transient(parent)

        self._last_ctrl_time = 0
        self._last_alt_time = 0

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 760, 650
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        nb = ttk.Notebook(pad)
        nb.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 1. note note
        tab_gen = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_gen, text="Text")

        self.var_autolaunch = tk.BooleanVar(value=config.get_bool("GENERAL", "AutoLaunchQTranslate", True))
        tk.Checkbutton(
            tab_gen, text=t("settings_chk_autolaunch", "Text"),
            variable=self.var_autolaunch, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0)
        ).pack(anchor="w", pady=4)

        self.var_minimized = tk.BooleanVar(value=config.get_bool("GENERAL", "StartMinimized", True))
        tk.Checkbutton(
            tab_gen, text=t("settings_chk_minimized", "Text"),
            variable=self.var_minimized, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0)
        ).pack(anchor="w", pady=4)

        r_theme = tk.Frame(tab_gen, bg=bg_card)
        r_theme.pack(fill=tk.X, pady=6)
        tk.Label(r_theme, text=t("settings_lbl_theme", "Text"), bg=bg_card, fg=fg_pri, font=theme.font(0, "bold"), width=18, anchor="w").pack(side=tk.LEFT)

        self.theme_options = theme.get_theme_display_options()
        theme_names = [name for _, name in self.theme_options]
        self.combo_theme = ttk.Combobox(r_theme, values=theme_names, state="readonly", width=16)

        cur_th = theme.current_theme_key
        cur_th_name = next((name for k, name in self.theme_options if k == cur_th), theme_names[0])
        self.combo_theme.set(cur_th_name)
        self.combo_theme.pack(side=tk.LEFT, padx=6)

        r_font = tk.Frame(tab_gen, bg=bg_card)
        r_font.pack(fill=tk.X, pady=6)
        tk.Label(r_font, text=t("settings_lbl_fontsize", "Text"), bg=bg_card, fg=fg_pri, font=theme.font(0, "bold"), width=18, anchor="w").pack(side=tk.LEFT)

        self.font_options = theme.get_font_display_options()
        font_names = [name for _, name in self.font_options]
        self.combo_font = ttk.Combobox(r_font, values=font_names, state="readonly", width=18)

        cur_fs = theme.current_font_scale
        cur_fs_name = next((name for k, name in self.font_options if k == cur_fs), font_names[1])
        self.combo_font.set(cur_fs_name)
        self.combo_font.pack(side=tk.LEFT, padx=6)

        r_lang = tk.Frame(tab_gen, bg=bg_card)
        r_lang.pack(fill=tk.X, pady=6)
        tk.Label(r_lang, text=t("settings_lbl_lang", "Text"), bg=bg_card, fg=fg_pri, font=theme.font(0), width=18, anchor="w").pack(side=tk.LEFT)

        self.lang_options = i18n.get_available_languages()
        lang_display_names = [name for _, name in self.lang_options]
        self.combo_lang = ttk.Combobox(r_lang, values=lang_display_names, state="readonly", width=18)

        cur_lang = config.get_str("GENERAL", "UILanguage", "auto").lower()
        cur_lang_name = next((name for k, name in self.lang_options if k == cur_lang), lang_display_names[0])
        self.combo_lang.set(cur_lang_name)
        self.combo_lang.pack(side=tk.LEFT, padx=6)

        r_port = tk.Frame(tab_gen, bg=bg_card)
        r_port.pack(fill=tk.X, pady=6)
        tk.Label(r_port, text=t("settings_lbl_port", "Text"), bg=bg_card, fg=fg_pri, font=theme.font(0), width=18, anchor="w").pack(side=tk.LEFT)
        self.e_port = tk.Entry(r_port, width=8, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_port.insert(0, str(config.get_int("GENERAL", "ServerPort", 8080)))
        self.e_port.pack(side=tk.LEFT, padx=6)
        attach_entry_context_menu(self.e_port)

        r_editor = tk.Frame(tab_gen, bg=bg_card)
        r_editor.pack(fill=tk.X, pady=6)
        tk.Label(r_editor, text=t("settings_lbl_editor", "Text"), bg=bg_card, fg=fg_pri, font=theme.font(0), width=18, anchor="w").pack(side=tk.LEFT)
        self.e_editor = tk.Entry(r_editor, width=28, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_editor.insert(0, config.get_str("GENERAL", "CodeEditor", "auto"))
        self.e_editor.pack(side=tk.LEFT, padx=6)
        attach_entry_context_menu(self.e_editor)

        tk.Button(
            r_editor, text=t("settings_btn_browse", "Text"), font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._browse_editor
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            r_editor, text=t("settings_btn_reset_editor", "Text"), font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=lambda: self._set_editor_value("auto")
        ).pack(side=tk.LEFT, padx=2)

        # 2. note note
        tab_search = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_search, text="Text")

        tk.Label(tab_search, text="Text", font=theme.font(0, "bold"), fg=theme.get_color("accent"), bg=bg_card).pack(anchor="w", pady=(0, 6))

        r_engine = tk.Frame(tab_search, bg=bg_card)
        r_engine.pack(fill=tk.X, pady=4)
        tk.Label(r_engine, text="Text", font=theme.font(0), bg=bg_card, fg=fg_pri, width=20, anchor="w").pack(side=tk.LEFT)

        engine_titles = [title for _, title in SEARCH_ENGINE_DISPLAY]
        self.combo_engine = ttk.Combobox(r_engine, values=engine_titles, state="readonly", width=38)

        cur_engine = config.get_str("SEARCH", "engine", "google").lower()
        cur_engine_title = next((title for eid, title in SEARCH_ENGINE_DISPLAY if eid == cur_engine), engine_titles[0])
        self.combo_engine.set(cur_engine_title)
        self.combo_engine.pack(side=tk.LEFT, padx=6)

        f_keys = tk.LabelFrame(tab_search, text="Text", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_keys.pack(fill=tk.X, pady=(6, 6))

        r_brave = tk.Frame(f_keys, bg=bg_card)
        r_brave.pack(fill=tk.X, pady=2)
        tk.Label(r_brave, text="Brave API Key:", font=theme.font(-1), bg=bg_card, fg=fg_pri, width=14, anchor="w").pack(side=tk.LEFT)
        self.e_brave_key = tk.Entry(r_brave, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_brave_key.insert(0, config.get_str("SEARCH", "brave_key", ""))
        self.e_brave_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.e_brave_key)
        tk.Button(r_brave, text="Text", font=theme.font(-2), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=lambda: os.startfile("https://brave.com/search/api/")).pack(side=tk.RIGHT)

        r_tavily = tk.Frame(f_keys, bg=bg_card)
        r_tavily.pack(fill=tk.X, pady=2)
        tk.Label(r_tavily, text="Tavily API Key:", font=theme.font(-1), bg=bg_card, fg=fg_pri, width=14, anchor="w").pack(side=tk.LEFT)
        self.e_tavily_key = tk.Entry(r_tavily, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_tavily_key.insert(0, config.get_str("SEARCH", "tavily_key", ""))
        self.e_tavily_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.e_tavily_key)
        tk.Button(r_tavily, text="Text", font=theme.font(-2), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=lambda: os.startfile("https://tavily.com")).pack(side=tk.RIGHT)

        r_serper = tk.Frame(f_keys, bg=bg_card)
        r_serper.pack(fill=tk.X, pady=2)
        tk.Label(r_serper, text="Serper API Key:", font=theme.font(-1), bg=bg_card, fg=fg_pri, width=14, anchor="w").pack(side=tk.LEFT)
        self.e_serper_key = tk.Entry(r_serper, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_serper_key.insert(0, config.get_str("SEARCH", "serper_key", ""))
        self.e_serper_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.e_serper_key)
        tk.Button(r_serper, text="Text", font=theme.font(-2), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=lambda: os.startfile("https://serper.dev")).pack(side=tk.RIGHT)

        r_sx = tk.Frame(f_keys, bg=bg_card)
        r_sx.pack(fill=tk.X, pady=2)
        tk.Label(r_sx, text="SearXNG URL:", font=theme.font(-1), bg=bg_card, fg=fg_pri, width=14, anchor="w").pack(side=tk.LEFT)
        self.e_searxng_url = tk.Entry(r_sx, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_searxng_url.insert(0, config.get_str("SEARCH", "searxng_url", "https://search.sapti.me/search"))
        self.e_searxng_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.e_searxng_url)
        ToolTip(self.e_searxng_url, "Text")

        f_test = tk.LabelFrame(tab_search, text="Text", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_test.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        r_tbar = tk.Frame(f_test, bg=bg_card)
        r_tbar.pack(fill=tk.X, pady=(0, 4))
        tk.Label(r_tbar, text="Text", font=theme.font(-1), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.e_test_query = tk.Entry(r_tbar, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=28)
        self.e_test_query.insert(0, "QTranslate AI Hub")
        self.e_test_query.pack(side=tk.LEFT, padx=4)
        attach_entry_context_menu(self.e_test_query)

        btn_test_s = tk.Button(r_tbar, text="Text", font=theme.font(-1, "bold"), relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=8, command=self._test_search)
        btn_test_s.pack(side=tk.LEFT, padx=4)

        self.txt_search_res = tk.Text(f_test, height=5, font=theme.font(-2), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, wrap=tk.WORD)
        self.txt_search_res.pack(fill=tk.BOTH, expand=True)
        attach_entry_context_menu(self.txt_search_res)

        # 3. note note
        tab_keys = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_keys, text="Text")

        tk.Label(tab_keys, text=t("settings_hk_header", "Text"), font=theme.font(0, "bold"), fg=theme.get_color("accent"), bg=bg_card).pack(anchor="w", pady=(0, 6))

        r_hk_ocr = tk.Frame(tab_keys, bg=bg_card)
        r_hk_ocr.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_ocr, text="Text", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_ocr = tk.Entry(r_hk_ocr, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_ocr.insert(0, config.get_str("HOTKEYS", "OCR", ""))
        self.e_hk_ocr.pack(side=tk.RIGHT)
        self.e_hk_ocr.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_ocr))

        r_hk_win = tk.Frame(tab_keys, bg=bg_card)
        r_hk_win.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_win, text="Text", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_win = tk.Entry(r_hk_win, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_win.insert(0, config.get_str("HOTKEYS", "ToggleWindow", ""))
        self.e_hk_win.pack(side=tk.RIGHT)
        self.e_hk_win.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_win))

        r_hk_tts = tk.Frame(tab_keys, bg=bg_card)
        r_hk_tts.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_tts, text="Text", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_tts = tk.Entry(r_hk_tts, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_tts.insert(0, config.get_str("HOTKEYS", "TTS", ""))
        self.e_hk_tts.pack(side=tk.RIGHT)
        self.e_hk_tts.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_tts))

        r_qtr = tk.Frame(tab_keys, bg=bg_card)
        r_qtr.pack(fill=tk.X, pady=(10, 3))
        tk.Label(r_qtr, text="Text", bg=bg_card, fg=theme.get_color("status_ready"), font=theme.font(0, "bold"), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_qtr = tk.Entry(r_qtr, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("status_ready"))
        self.e_hk_qtr.insert(0, config.get_str("QTRANSLATE", "SummonHotkey", "double_ctrl"))
        self.e_hk_qtr.pack(side=tk.RIGHT)
        self.e_hk_qtr.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_qtr))

        tk.Label(
            tab_keys, text="Text",
            font=theme.font(-2, "italic"), fg=theme.get_color("fg_muted"), bg=bg_card
        ).pack(anchor="w", pady=(8, 0))

        # 4. note note
        tab_media = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_media, text="Text")

        tk.Label(tab_media, text=t("settings_ocr_model_lbl", "Text"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri).pack(anchor="w", pady=(0, 2))
        self.combo_ocr = ttk.Combobox(tab_media, values=ocr_engine.get_available_models(), state="readonly", width=14)
        self.combo_ocr.set(ocr_engine.get_active_model())
        self.combo_ocr.pack(anchor="w", pady=(0, 10))

        tk.Label(tab_media, text=t("settings_tts_speed_lbl", "Text"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri).pack(anchor="w", pady=(0, 2))
        self.scale_speed = tk.Scale(
            tab_media, from_=0.7, to=1.4, resolution=0.05, orient="horizontal",
            bg=bg_card, fg=fg_pri, troughcolor=in_bg, activebackground=theme.get_color("accent"),
            highlightthickness=0
        )
        self.scale_speed.set(config.get_float("TTS", "Speed", 1.0))
        self.scale_speed.pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            tab_media, text="Text", font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._test_tts
        ).pack(anchor="w")

        # 5. note note
        tab_logs = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_logs, text="Text")

        f_con = tk.LabelFrame(tab_logs, text="Text", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_con.pack(fill=tk.X, pady=(0, 8))

        self.var_show_console = tk.BooleanVar(value=config.get_bool("LOGGING", "showconsole", False))
        tk.Checkbutton(
            f_con, text="Text",
            variable=self.var_show_console, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0, "bold"),
            command=self._toggle_console_live
        ).pack(anchor="w")

        r_log_files = tk.Frame(f_con, bg=bg_card)
        r_log_files.pack(fill=tk.X, pady=(4, 0))

        self.var_log_to_file = tk.BooleanVar(value=config.get_bool("LOGGING", "logtofile", True))
        tk.Checkbutton(
            r_log_files, text="Text",
            variable=self.var_log_to_file, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(side=tk.LEFT)

        self.var_clear_on_startup = tk.BooleanVar(value=config.get_bool("LOGGING", "clearonstartup", True))
        tk.Checkbutton(
            r_log_files, text="Text",
            variable=self.var_clear_on_startup, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Button(
            f_con, text="Text", font=theme.font(-2), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._open_log_folder
        ).pack(anchor="e", pady=(4, 0))

        f_cats = tk.LabelFrame(tab_logs, text="Text", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_cats.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.var_log_api_summary = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_summary", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_api_summary, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_api_payload = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_payload", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_api_payload, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_api_raw = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_raw_response", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_api_raw, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_tools = tk.BooleanVar(value=config.get_bool("LOGGING", "log_tools", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_tools, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_glossary = tk.BooleanVar(value=config.get_bool("LOGGING", "log_glossary", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_glossary, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_filtering = tk.BooleanVar(value=config.get_bool("LOGGING", "log_filtering", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_filtering, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_qtranslate = tk.BooleanVar(value=config.get_bool("LOGGING", "log_qtranslate", True))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_qtranslate, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_browser = tk.BooleanVar(value=config.get_bool("LOGGING", "log_browser", False))
        tk.Checkbutton(
            f_cats, text="Text",
            variable=self.var_log_browser, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        # note note
        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X)
        tk.Button(btn_bar, text=t("btn_cancel", "Text"), font=theme.font(0), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_bar, text=t("btn_save", "Text"), font=theme.font(0, "bold"), relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=16, command=self._save).pack(side=tk.RIGHT)

    def _browse_editor(self):
        chosen = filedialog.askopenfilename(
            parent=self,
            title=t("dlg_select_editor", "Text"),
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if chosen:
            self.e_editor.delete(0, tk.END)
            self.e_editor.insert(0, os.path.normpath(chosen))

    def _set_editor_value(self, val):
        self.e_editor.delete(0, tk.END)
        self.e_editor.insert(0, val)

    def _test_search(self):
        q = self.e_test_query.get().strip()
        if not q:
            return

        chosen_title = self.combo_engine.get()
        engine_id = next((eid for eid, title in SEARCH_ENGINE_DISPLAY if title == chosen_title), "google")

        self.txt_search_res.delete("1.0", tk.END)
        self.txt_search_res.insert("1.0", f"Text")

        def _worker():
            try:
                from data.core.web_search import search_web
                res = search_web(q, engine=engine_id, max_results=2)
                def _update():
                    self.txt_search_res.delete("1.0", tk.END)
                    self.txt_search_res.insert("1.0", res)
                self.after(0, _update)
            except Exception as e:
                self.after(0, lambda: self.txt_search_res.insert(tk.END, f"Text"))

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_console_live(self):
        show = self.var_show_console.get()
        logger.show_console(show)

    def _open_log_folder(self):
        try:
            os.startfile(logger.log_dir)
        except Exception:
            pass

    def _record_key(self, event, entry_widget):
        keysym = event.keysym
        now = time.time()

        if keysym in ("Delete", "BackSpace"):
            entry_widget.delete(0, tk.END)
            return "break"

        if keysym in ("Control_L", "Control_R"):
            if now - self._last_ctrl_time < 0.35:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, "double_ctrl")
                self._last_ctrl_time = 0
                return "break"
            self._last_ctrl_time = now
            return "break"

        if keysym in ("Alt_L", "Alt_R"):
            if now - self._last_alt_time < 0.35:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, "double_alt")
                self._last_alt_time = 0
                return "break"
            self._last_alt_time = now
            return "break"

        mods = []
        state = event.state
        if state & 0x0004: mods.append("Ctrl")
        if state & 0x20000 or state & 0x0008: mods.append("Alt")
        if state & 0x0001: mods.append("Shift")

        key_name = keysym
        if keysym.startswith("F") and keysym[1:].isdigit():
            key_name = keysym.upper()
        elif len(keysym) == 1:
            key_name = keysym.upper()
        elif keysym in ("Return", "KP_Enter"):
            key_name = "Enter"
        elif keysym == "Escape":
            key_name = "Esc"
        elif keysym in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
            return "break"

        res = "+".join(mods + [key_name]) if (mods and key_name not in mods) else key_name
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, res)
        return "break"

    def _test_tts(self):
        phrase = t("settings_tts_test_phrase", "Text")
        tts_engine.speak_text(phrase, speed=self.scale_speed.get(), lang=i18n.current_lang)

    def _save(self):
        config.set_value("GENERAL", "AutoLaunchQTranslate", "1" if self.var_autolaunch.get() else "0")
        config.set_value("GENERAL", "StartMinimized", "1" if self.var_minimized.get() else "0")
        config.set_value("GENERAL", "ServerPort", self.e_port.get().strip() or "8080")
        config.set_value("GENERAL", "CodeEditor", self.e_editor.get().strip() or "auto")

        chosen_theme_display = self.combo_theme.get()
        chosen_theme_key = next((k for k, name in self.theme_options if name == chosen_theme_display), "light")
        theme.set_theme(chosen_theme_key)

        chosen_font_display = self.combo_font.get()
        chosen_font_scale = next((k for k, name in self.font_options if name == chosen_font_display), "normal")
        theme.set_font_size(chosen_font_scale)

        chosen_lang_display = self.combo_lang.get()
        chosen_lang_code = next((k for k, name in self.lang_options if name == chosen_lang_display), "auto")
        i18n.set_language(chosen_lang_code)

        chosen_engine_title = self.combo_engine.get()
        chosen_engine_id = next((eid for eid, title in SEARCH_ENGINE_DISPLAY if title == chosen_engine_title), "google")
        config.set_value("SEARCH", "engine", chosen_engine_id)
        config.set_value("SEARCH", "searxng_url", self.e_searxng_url.get().strip() or "https://search.sapti.me/search")
        config.set_value("SEARCH", "brave_key", self.e_brave_key.get().strip())
        config.set_value("SEARCH", "tavily_key", self.e_tavily_key.get().strip())
        config.set_value("SEARCH", "serper_key", self.e_serper_key.get().strip())

        config.set_value("HOTKEYS", "OCR", self.e_hk_ocr.get().strip())
        config.set_value("HOTKEYS", "ToggleWindow", self.e_hk_win.get().strip())
        config.set_value("HOTKEYS", "TTS", self.e_hk_tts.get().strip())
        config.set_value("QTRANSLATE", "SummonHotkey", self.e_hk_qtr.get().strip() or "double_ctrl")

        ocr_engine.set_active_model(self.combo_ocr.get())
        config.set_value("TTS", "Speed", str(self.scale_speed.get()))

        config.set_value("LOGGING", "showconsole", "1" if self.var_show_console.get() else "0")
        config.set_value("LOGGING", "logtofile", "1" if self.var_log_to_file.get() else "0")
        config.set_value("LOGGING", "clearonstartup", "1" if self.var_clear_on_startup.get() else "0")

        config.set_value("LOGGING", "log_api_summary", "1" if self.var_log_api_summary.get() else "0")
        config.set_value("LOGGING", "log_api_payload", "1" if self.var_log_api_payload.get() else "0")
        config.set_value("LOGGING", "log_api_raw_response", "1" if self.var_log_api_raw.get() else "0")
        config.set_value("LOGGING", "log_tools", "1" if self.var_log_tools.get() else "0")
        config.set_value("LOGGING", "log_glossary", "1" if self.var_log_glossary.get() else "0")
        config.set_value("LOGGING", "log_filtering", "1" if self.var_log_filtering.get() else "0")
        config.set_value("LOGGING", "log_qtranslate", "1" if self.var_log_qtranslate.get() else "0")
        config.set_value("LOGGING", "log_browser", "1" if self.var_log_browser.get() else "0")

        logger.show_console(self.var_show_console.get())
        hotkey_manager.reload_from_config()

        if self.on_settings_updated:
            self.on_settings_updated()

        messagebox.showinfo("OK", t("settings_saved_msg", "Text"), parent=self)
        self.destroy()
