# -*- coding: utf-8 -*-
# data/gui/service_settings_dialog.py

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.i18n import t
from data.core.logger import logger
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import attach_entry_context_menu, attach_text_context_menu

DOH_PRESET_KEYS = [
    "Comss.one (SmartDNS)",
    "Control D (Uncensored)",
    "Cloudflare (1.1.1.1)",
    "Google (8.8.8.8)"
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
        self.title(t("test_result_title"))
        self.geometry("540x350")
        self.minsize(400, 250)
        self.transient(parent)
        self.grab_set()

        bg_main = theme.get_color("bg_main")
        self.configure(bg=bg_main)

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        t_border = tk.Frame(
            pad, bg=theme.get_color("input_bg"), relief=tk.SOLID, bd=1,
            highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
        )
        t_border.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        text_area = tk.Text(
            t_border, bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"),
            font=theme.font(0), wrap=tk.WORD, padx=8, pady=8, relief=tk.FLAT
        )
        sb = tk.Scrollbar(t_border, command=text_area.yview)
        text_area.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_area.insert("1.0", str(result_text))
        text_area.config(state=tk.DISABLED)
        attach_text_context_menu(text_area)

        btn_close = tk.Button(
            pad, text=t("btn_close"), font=theme.font(0, "bold"),
            bg=theme.get_color("btn_bg"), fg=theme.get_color("fg_primary"),
            relief=tk.FLAT, cursor="hand2", padx=16, pady=4, command=self.destroy
        )
        btn_close.pack(anchor="e")

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx() if parent else 150
        py = parent.winfo_rooty() if parent else 150
        w, h = 540, 350
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

class ServiceSettingsDialog(tk.Toplevel):
    def __init__(self, parent, service, on_saved_callback=None):
        super().__init__(parent)
        self.service = service
        self.on_saved = on_saved_callback
        self.entries = {}

        self.title(t("params_dialog_title", name=service.name))
        self.transient(parent)
        self.grab_set()

        has_search_prompt = any(f.get("key") == "search_prompt" for f in self.service.get_config_fields())

        bg_main = theme.get_color("bg_main")
        self.configure(bg=bg_main)

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx() if parent else 150
        py = parent.winfo_rooty() if parent else 150

        if self.service.service_id == "gemini_family":
            w, h = 560, 650 if has_search_prompt else 510
        else:
            w, h = 540, 510 if has_search_prompt else 380

        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")

        header = tk.Frame(
            self, bg=theme.get_color("bg_header"), padx=12, pady=10, relief=tk.SOLID, bd=1,
            highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
        )
        header.pack(fill=tk.X)

        tk.Label(
            header, text=t("params_dialog_header", name=self.service.name),
            font=theme.font(2, "bold"), fg=theme.get_color("accent"), bg=theme.get_color("bg_header")
        ).pack(anchor="w")

        pad_frame = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad_frame.pack(fill=tk.BOTH, expand=True)

        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        if self.service.service_id == "gemini_family":
            tk.Label(pad_frame, text=t("lbl_api_key"), font=theme.font(0, "bold"), bg=bg_main, fg=fg_pri).pack(anchor="w", pady=(0, 2))
            self.e_api_gemini = tk.Entry(pad_frame, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_api_gemini.pack(fill=tk.X, pady=(0, 8))
            attach_entry_context_menu(self.e_api_gemini)
            self.e_api_gemini.insert(0, str(self.service.get_config_val("api_key", "")))

            tk.Label(pad_frame, text=t("lbl_model"), font=theme.font(0, "bold"), bg=bg_main, fg=fg_pri).pack(anchor="w", pady=(0, 2))
            self.combo_gem_def_model = ttk.Combobox(pad_frame, values=GEMINI_MODELS_LIST, state="readonly", font=theme.font(0))
            cur_m = self.service.get_config_val("model", GEMINI_MODELS_LIST[0])
            self.combo_gem_def_model.set(cur_m if cur_m in GEMINI_MODELS_LIST else GEMINI_MODELS_LIST[0])
            self.combo_gem_def_model.pack(fill=tk.X, pady=(0, 10))

            tk.Label(pad_frame, text=t("lbl_connection_mode"), font=theme.font(0, "bold"), bg=bg_main, fg=fg_pri).pack(anchor="w", pady=(0, 2))
            conn_frame = tk.Frame(pad_frame, bg=bg_card, relief=tk.SOLID, bd=1, padx=10, pady=8)
            conn_frame.pack(fill=tk.X, pady=(0, 8))

            self.conn_mode_var = tk.StringVar(value=self.service.get_config_val("connection_mode", "doh"))

            rb_direct = tk.Radiobutton(
                conn_frame, text=t("conn_direct"), variable=self.conn_mode_var, value="direct",
                bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_direct.pack(anchor="w")

            rb_proxy = tk.Radiobutton(
                conn_frame, text=t("conn_proxy"), variable=self.conn_mode_var, value="proxy",
                bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_proxy.pack(anchor="w", pady=(4, 0))

            rb_doh = tk.Radiobutton(
                conn_frame, text=t("conn_doh"), variable=self.conn_mode_var, value="doh",
                bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._toggle_conn_ui
            )
            rb_doh.pack(anchor="w", pady=(4, 0))

            self.doh_subframe = tk.Frame(conn_frame, bg=bg_card)
            self.doh_subframe.pack(fill=tk.X, pady=(6, 0))

            tk.Label(self.doh_subframe, text=t("lbl_doh_preset"), bg=bg_card, fg=fg_pri, font=theme.font(-1)).pack(side=tk.LEFT)
            self.combo_doh = ttk.Combobox(self.doh_subframe, values=DOH_PRESET_KEYS + [t("lbl_doh_custom_opt")], state="readonly", width=34)
            cur_doh = self.service.get_config_val("doh_preset", DOH_PRESET_KEYS[0])
            self.combo_doh.set(cur_doh if cur_doh in DOH_PRESET_KEYS else DOH_PRESET_KEYS[0])
            self.combo_doh.pack(side=tk.LEFT, padx=6)
            self.combo_doh.bind("<<ComboboxSelected>>", self._toggle_doh_custom_ui)

            self.doh_custom_frame = tk.Frame(conn_frame, bg=bg_card)
            tk.Label(self.doh_custom_frame, text=t("lbl_doh_custom"), bg=bg_card, fg=fg_pri, font=theme.font(-1)).pack(side=tk.LEFT)
            self.e_doh_custom = tk.Entry(self.doh_custom_frame, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_doh_custom.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
            attach_entry_context_menu(self.e_doh_custom)
            de_var = self.service.get_config_val("doh_custom_url", "https://dns.comss.one/dns-query")
            self.e_doh_custom.insert(0, str(de_var))

            self.proxy_frame = tk.Frame(pad_frame, bg=bg_main)
            self.proxy_frame.pack(fill=tk.X, pady=(0, 8))

            tk.Label(self.proxy_frame, text=t("lbl_proxy_url"), font=theme.font(0, "bold"), bg=bg_main, fg=fg_pri).pack(anchor="w", pady=(0, 2))
            self.e_proxy = tk.Entry(self.proxy_frame, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
            self.e_proxy.pack(fill=tk.X)
            attach_entry_context_menu(self.e_proxy)
            self.e_proxy.insert(0, str(self.service.get_config_val("proxy", "")))

            self.search_prompt_frame = tk.Frame(pad_frame, bg=bg_main)
            self.search_prompt_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            tk.Label(self.search_prompt_frame, text=t("lbl_search_prompt"), font=theme.font(0, "bold"), bg=bg_main, fg=fg_pri).pack(anchor="w", pady=(0, 2))

            t_border = tk.Frame(
                self.search_prompt_frame, bg=in_bg, relief=tk.SOLID, bd=1,
                highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
            )
            t_border.pack(fill=tk.BOTH, expand=True)

            self.t_search_prompt = tk.Text(
                t_border, font=theme.font(-1), bg=in_bg, fg=in_fg, wrap=tk.WORD, height=4, bd=0, relief=tk.FLAT
            )
            sb = tk.Scrollbar(t_border, command=self.t_search_prompt.yview)
            self.t_search_prompt.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.t_search_prompt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
            attach_text_context_menu(self.t_search_prompt)

            s_prompt = self.service.get_config_val("search_prompt", "")
            self.t_search_prompt.insert("1.0", str(s_prompt))

            self._toggle_conn_ui()
            self._toggle_doh_custom_ui()

        else:
            fields = self.service.get_config_fields()
            for f in fields:
                req = f.get("required", False)
                row = tk.Frame(pad_frame, bg=bg_main)
                row.pack(fill=tk.X, pady=4)

                field_lbl = t(f"field_{f['key']}")
                lbl = f"{field_lbl} *" if req else field_lbl
                tk.Label(
                    row, text=lbl, font=theme.font(0, "bold" if req else "normal"),
                    fg=fg_pri, anchor="w", bg=bg_main
                ).pack(side=tk.TOP, anchor="w", pady=(0, 2))

                val = str(self.service.get_config_val(f["key"], ""))
                if f.get("key") == "search_prompt":
                    t_border = tk.Frame(
                        row, bg=in_bg, relief=tk.SOLID, bd=1,
                        highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
                    )
                    t_border.pack(fill=tk.BOTH, expand=True)

                    entry = tk.Text(t_border, font=theme.font(-1), bg=in_bg, fg=in_fg, wrap=tk.WORD, height=4, bd=0, relief=tk.FLAT)
                    sb = tk.Scrollbar(t_border, command=entry.yview)
                    entry.configure(yscrollcommand=sb.set)
                    sb.pack(side=tk.RIGHT, fill=tk.Y)
                    entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
                    entry.insert("1.0", str(val))
                    attach_text_context_menu(entry)
                else:
                    entry = tk.Entry(row, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
                    entry.pack(fill=tk.X)
                    entry.insert(0, str(val))
                    attach_entry_context_menu(entry)

                self.entries[f["key"]] = entry

        btn_row = tk.Frame(self, bg=bg_main)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 12))

        self.btn_test = tk.Button(
            btn_row, text=t("btn_test_conn"), font=theme.font(0),
            bg=theme.get_color("btn_bg"), fg=fg_pri, activebackground=theme.get_color("btn_hover"),
            relief=tk.FLAT, cursor="hand2", padx=10, pady=4, command=self._on_test_api
        )
        self.btn_test.pack(side=tk.LEFT)

        btn_save = tk.Button(
            btn_row, text=t("params_btn_save"), font=theme.font(0, "bold"),
            bg=theme.get_color("accent"), fg="#ffffff", activebackground=theme.get_color("accent_hover"),
            relief=tk.FLAT, cursor="hand2", padx=14, pady=4, command=lambda: self._save_data(close_window=True)
        )
        btn_save.pack(side=tk.RIGHT)

        btn_cancel = tk.Button(
            btn_row, text=t("btn_cancel"), font=theme.font(0),
            bg=theme.get_color("btn_bg"), fg=fg_pri, activebackground=theme.get_color("btn_hover"),
            relief=tk.FLAT, cursor="hand2", padx=12, pady=4, command=self.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, padx=6)

    def _toggle_conn_ui(self):
        mode = self.conn_mode_var.get()
        if mode == "doh":
            self.doh_subframe.pack(fill=tk.X, pady=(6, 0))
            self.proxy_frame.pack_forget()
        elif mode == "proxy":
            self.doh_subframe.pack_forget()
            self.doh_custom_frame.pack_forget()
            self.proxy_frame.pack(fill=tk.X, pady=(0, 8))
        else:
            self.doh_subframe.pack_forget()
            self.doh_custom_frame.pack_forget()
            self.proxy_frame.pack_forget()

    def _toggle_doh_custom_ui(self, event=None):
        if self.conn_mode_var.get() != "doh":
            self.doh_custom_frame.pack_forget()
            return

        cur = self.combo_doh.get()
        if cur not in DOH_PRESET_KEYS:
            self.doh_custom_frame.pack(fill=tk.X, pady=(4, 0))
        else:
            self.doh_custom_frame.pack_forget()

    def _save_data(self, close_window=True):
        if self.service.service_id == "gemini_family":
            self.service.set_config_val("api_key", self.e_api_gemini.get().strip())
            self.service.set_config_val("model", self.combo_gem_def_model.get().strip())
            self.service.set_config_val("connection_mode", self.conn_mode_var.get())

            doh_preset = self.combo_doh.get().strip()
            if doh_preset in DOH_PRESET_KEYS:
                self.service.set_config_val("doh_preset", doh_preset)
            else:
                self.service.set_config_val("doh_preset", "custom")
                self.service.set_config_val("doh_custom_url", self.e_doh_custom.get().strip())

            self.service.set_config_val("proxy", self.e_proxy.get().strip())
            self.service.set_config_val("search_prompt", self.t_search_prompt.get("1.0", tk.END).strip())

        else:
            for key, entry in self.entries.items():
                if isinstance(entry, tk.Text):
                    val = entry.get("1.0", tk.END).strip()
                else:
                    val = entry.get().strip()
                self.service.set_config_val(key, val)

        logger.system(f"Parameters saved for {self.service.name}")
        if self.on_saved:
            self.on_saved()

        if close_window:
            success_msg = t("params_saved_msg", name=self.service.name)
            messagebox.showinfo(t("common.info"), success_msg, parent=self)
            self.destroy()

    def _on_test_api(self):
        self._save_data(close_window=False)
        self.btn_test.config(state="disabled", text="...")

        def _worker():
            try:
                res = self.service.translate("Connection test message.", src_lang="auto", trg_lang="ru", preset=None)
                def _ui():
                    self.btn_test.config(state="normal", text=t("btn_test_conn"))
                    TestResultDialog(self, res)
                self.after(0, _ui)
            except Exception as ex:
                def _err():
                    self.btn_test.config(state="normal", text=t("btn_test_conn"))
                    TestResultDialog(self, f"{t('common.error')}:\n{ex}")
                self.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()