# -*- coding: utf-8 -*-
# data/gui/service_settings_dialog.py

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from data.core.i18n import t
from data.core.logger import logger
from data.gui.dialog_helpers import attach_entry_context_menu, attach_text_context_menu
from data.gui.theme_manager import theme
DOH_PRESET_KEYS = [
    "Text",
    "Control D (Uncensored)",
    "Cloudflare (1.1.1.1)",
    "Google (8.8.8.8)",
    "Text"
]

GEMINI_MODELS_LIST = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro"
]

class TestResultDialog(tk.Toplevel):
    def __init__(self, parent, result_text):
        super().__init__(parent)
        self.parent = parent

        bg_main = theme.get_color("bg_main")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        self.title("Text")
        self.geometry("540x380")
        self.minsize(400, 300)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        x = px + max(0, (pw - 540) // 2)
        y = py + max(0, (ph - 380) // 2)
        self.geometry(f"+{x}+{y}")

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad, text="Text",
            font=theme.font(1, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(anchor="w", pady=(0, 6))

        t_border = tk.Frame(pad, relief=tk.SOLID, bd=1, bg=in_bg)
        t_border.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        text_area = tk.Text(t_border, font=theme.font(0), bg=in_bg, fg=in_fg, wrap=tk.WORD, bd=0, padx=6, pady=6)
        sb = tk.Scrollbar(t_border, command=text_area.yview)
        text_area.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_area.insert("1.0", result_text)
        attach_text_context_menu(text_area)

        tk.Button(
            pad, text="Text", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, cursor="hand2", padx=16, pady=4,
            command=self.destroy
        ).pack(anchor="e")

class ServiceSettingsDialog(tk.Toplevel):
    def __init__(self, parent, service, on_saved_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.service = service
        self.on_saved = on_saved_callback
        self.entries = {}

        bg_main = theme.get_color("bg_main")
        self.title(t("params_dialog_title", f"Text", name=service.name))

        self.has_search_prompt = any(
            f.get("key") == "search_prompt"
            for f in (self.service.get_config_fields() if hasattr(self.service, "get_config_fields") else [])
        )

        if self.service.service_id == "gemini_family":
            self.geometry("560x650")
        else:
            w = 540
            h = 510 if self.has_search_prompt else 380
            self.geometry(f"{w}x{h}")

        self.resizable(False, False)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150

        if self.service.service_id == "gemini_family":
            w, h = 560, 650
        else:
            w = 540
            h = 510 if self.has_search_prompt else 380

        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad_frame = tk.Frame(self, bg=bg_main, padx=16, pady=14)
        pad_frame.pack(fill=tk.BOTH, expand=True)

        header_str = t("params_dialog_header", f"Text", name=self.service.name)
        tk.Label(pad_frame, text=header_str, font=theme.font(2, "bold"), fg=theme.get_color("accent"), bg=bg_main).pack(anchor="w", pady=(0, 10))

        if self.service.service_id == "gemini_family":
            r_api = tk.Frame(pad_frame, bg=bg_main)
            r_api.pack(fill=tk.X, pady=3)
            tk.Label(r_api, text="Text", font=theme.font(0, "bold"), fg=fg_pri, width=24, anchor="w", bg=bg_main).pack(side=tk.LEFT)
            self.e_api_gemini = tk.Entry(r_api, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_api_gemini.insert(0, str(self.service.get_config_val("api_key", "")))
            self.e_api_gemini.pack(side=tk.LEFT, fill=tk.X, expand=True)
            attach_entry_context_menu(self.e_api_gemini)

            r_mod = tk.Frame(pad_frame, bg=bg_main)
            r_mod.pack(fill=tk.X, pady=3)
            tk.Label(r_mod, text="Text", font=theme.font(0, "bold"), fg=fg_pri, width=24, anchor="w", bg=bg_main).pack(side=tk.LEFT)
            self.combo_gem_def_model = ttk.Combobox(r_mod, values=GEMINI_MODELS_LIST, state="readonly")
            cur_m = self.service.get_config_val("model", GEMINI_MODELS_LIST[0])
            self.combo_gem_def_model.set(cur_m if cur_m in GEMINI_MODELS_LIST else GEMINI_MODELS_LIST[0])
            self.combo_gem_def_model.pack(side=tk.LEFT, fill=tk.X, expand=True)

            conn_frame = tk.LabelFrame(pad_frame, text="Text", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=10, pady=8)
            conn_frame.pack(fill=tk.X, pady=(10, 4))

            self.conn_mode_var = tk.StringVar(value=self.service.get_config_val("connection_mode", "doh"))

            rb_doh = tk.Radiobutton(
                conn_frame, text="Text",
                variable=self.conn_mode_var, value="doh", bg=bg_card, fg=fg_pri,
                selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_doh.pack(anchor="w")

            self.doh_subframe = tk.Frame(conn_frame, bg=bg_card)
            self.doh_subframe.pack(fill=tk.X, padx=20, pady=3)

            doh_top = tk.Frame(self.doh_subframe, bg=bg_card)
            doh_top.pack(fill=tk.X)
            tk.Label(doh_top, text="Text", bg=bg_card, fg=fg_pri, font=theme.font(-1)).pack(side=tk.LEFT)

            self.combo_doh = ttk.Combobox(doh_top, values=DOH_PRESET_KEYS, state="readonly", width=30)
            cur_doh = self.service.get_config_val("doh_preset", DOH_PRESET_KEYS[0])
            self.combo_doh.set(cur_doh if cur_doh in DOH_PRESET_KEYS else DOH_PRESET_KEYS[0])
            self.combo_doh.pack(side=tk.LEFT, padx=6)
            self.combo_doh.bind("<<ComboboxSelected>>", self._toggle_doh_custom_ui)

            self.doh_custom_frame = tk.Frame(self.doh_subframe, bg=bg_card)
            tk.Label(self.doh_custom_frame, text="Text", bg=bg_card, fg=fg_pri, font=theme.font(-1)).pack(side=tk.LEFT)
            self.e_doh_custom = tk.Entry(self.doh_custom_frame, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_doh_custom.insert(0, self.service.get_config_val("doh_custom_url", "https://xbox-dns.ru/dns-query"))
            self.e_doh_custom.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            attach_entry_context_menu(self.e_doh_custom)

            rb_proxy = tk.Radiobutton(
                conn_frame, text="Text",
                variable=self.conn_mode_var, value="proxy", bg=bg_card, fg=fg_pri,
                selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_proxy.pack(anchor="w", pady=(6, 0))

            self.e_proxy = tk.Entry(conn_frame, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_proxy.insert(0, self.service.get_config_val("proxy", ""))
            self.e_proxy.pack(fill=tk.X, padx=20, pady=2)
            attach_entry_context_menu(self.e_proxy)

            rb_direct = tk.Radiobutton(
                conn_frame, text="Text",
                variable=self.conn_mode_var, value="direct", bg=bg_card, fg=fg_pri,
                selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_direct.pack(anchor="w", pady=(6, 0))

            self._toggle_conn_ui()
            self._toggle_doh_custom_ui()

            search_frame = tk.LabelFrame(pad_frame, text="Text", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=10, pady=6)
            search_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 4))

            t_border = tk.Frame(search_frame, relief=tk.SOLID, bd=1, bg=in_bg)
            t_border.pack(fill=tk.BOTH, expand=True)
            self.t_search_prompt = tk.Text(t_border, font=theme.font(-1), bg=in_bg, fg=in_fg, wrap=tk.WORD, height=4, bd=0)
            sb = tk.Scrollbar(t_border, command=self.t_search_prompt.yview)
            self.t_search_prompt.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.t_search_prompt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            self.t_search_prompt.insert("1.0", str(self.service.get_config_val("search_prompt", "")))
            attach_text_context_menu(self.t_search_prompt)

        else:
            fields = self.service.get_config_fields()
            for f in fields:
                k = f["key"]
                lbl = f["label"]
                req = f.get("required", False)

                if k == "search_prompt":
                    row = tk.Frame(pad_frame, bg=bg_main)
                    row.pack(fill=tk.BOTH, expand=True, pady=4)

                    req_mark = " *" if req else ""
                    tk.Label(row, text=lbl + req_mark, font=theme.font(0, "bold" if req else "normal"), fg=fg_pri, anchor="w", bg=bg_main).pack(side=tk.TOP, anchor="w", pady=(0, 2))

                    t_border = tk.Frame(row, relief=tk.SOLID, bd=1, bg=in_bg)
                    t_border.pack(fill=tk.BOTH, expand=True)
                    entry = tk.Text(t_border, font=theme.font(-1), bg=in_bg, fg=in_fg, wrap=tk.WORD, height=4, bd=0)
                    sb = tk.Scrollbar(t_border, command=entry.yview)
                    entry.configure(yscrollcommand=sb.set)
                    sb.pack(side=tk.RIGHT, fill=tk.Y)
                    entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

                    val = self.service.get_config_val(k)
                    entry.insert("1.0", str(val))
                    attach_text_context_menu(entry)
                    self.entries[k] = entry
                else:
                    row = tk.Frame(pad_frame, bg=bg_main)
                    row.pack(fill=tk.X, pady=4)

                    req_mark = " *" if req else ""
                    tk.Label(row, text=lbl + req_mark, font=theme.font(0, "bold" if req else "normal"), fg=fg_pri, width=18, anchor="w", bg=bg_main).pack(side=tk.LEFT)

                    entry = tk.Entry(row, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
                    val = self.service.get_config_val(k)
                    entry.insert(0, str(val))
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    attach_entry_context_menu(entry)
                    self.entries[k] = entry

        help_box = tk.Label(
            pad_frame, text=t("params_dialog_note", "Text"),
            font=theme.font(-1, "italic"), fg=theme.get_color("fg_muted"), bg=bg_main, justify="left"
        )
        help_box.pack(anchor="w", pady=(10, 0))

        btn_row = tk.Frame(pad_frame, bg=bg_main)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        self.btn_test = tk.Button(
            btn_row, text="Text", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
            cursor="hand2", padx=12, command=self._on_test_api
        )
        self.btn_test.pack(side=tk.LEFT)

        tk.Button(btn_row, text=t("btn_cancel", "Text"), font=theme.font(0), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_row, text=t("params_btn_save", "Text"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=14, command=lambda: self._on_save(close_window=True)
        ).pack(side=tk.RIGHT)

    def _toggle_conn_ui(self):
        mode = self.conn_mode_var.get()
        if mode == "doh":
            self.combo_doh.config(state="readonly")
            self.e_proxy.config(state="disabled")
            self._toggle_doh_custom_ui()
        elif mode == "proxy":
            self.combo_doh.config(state="disabled")
            self.e_proxy.config(state="normal")
            self.doh_custom_frame.pack_forget()
        else:
            self.combo_doh.config(state="disabled")
            self.e_proxy.config(state="disabled")
            self.doh_custom_frame.pack_forget()

    def _toggle_doh_custom_ui(self, event=None):
        if self.conn_mode_var.get() == "doh" and self.combo_doh.get() == "Text":
            self.doh_custom_frame.pack(fill="x", pady=(4, 0))
        else:
            self.doh_custom_frame.pack_forget()

    def _save_data(self):
        if self.service.service_id == "gemini_family":
            self.service.set_config_val("api_key", self.e_api_gemini.get().strip())
            self.service.set_config_val("model", self.combo_gem_def_model.get().strip())
            self.service.set_config_val("connection_mode", self.conn_mode_var.get())
            self.service.set_config_val("doh_preset", self.combo_doh.get().strip())
            self.service.set_config_val("doh_custom_url", self.e_doh_custom.get().strip())
            self.service.set_config_val("proxy", self.e_proxy.get().strip())
            self.service.set_config_val("search_prompt", self.t_search_prompt.get("1.0", tk.END).strip())
        else:
            for k, entry in self.entries.items():
                if isinstance(entry, tk.Text):
                    val = entry.get("1.0", tk.END).strip()
                else:
                    val = entry.get().strip()
                self.service.set_config_val(k, val)

        logger.system(f"Text")

    def _on_save(self, close_window=True):
        self._save_data()

        if self.on_saved:
            self.on_saved()

        if close_window:
            success_msg = t("params_saved_msg", f"Text", name=self.service.name)
            messagebox.showinfo("OK", success_msg, parent=self)
            self.destroy()

    def _on_test_api(self):
        self._save_data()
        if self.on_saved:
            self.on_saved()

        self.btn_test.config(state="disabled", text="Text")

        def _worker():
            test_text = "Connection established successfully! System is ready to use."
            try:
                res = self.service.translate(test_text, src_lang="en", trg_lang="ru")
            except Exception as e:
                res = f"Text"

            def _on_done():
                if self.winfo_exists():
                    self.btn_test.config(state="normal", text="Text")
                    TestResultDialog(self, res)

            self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()
