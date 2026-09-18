# -*- coding: utf-8 -*-
# data/gui/batch_window.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from data.batch.pipeline import batch_pipeline
from data.core.config_manager import config
from data.core.i18n import t
from data.gui.dialogs import attach_entry_context_menu
from data.gui.theme_manager import theme
from data.services.base_service import LOADED_SERVICES
class BatchWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        theme.apply_ttk_theme(self)

        bg_main = theme.get_color("bg_main")
        self.title(t("batch_title", "Пакетный перевод файлов"))
        self.geometry("640x480")
        self.minsize(540, 380)
        self.configure(bg=bg_main)
        self.transient(parent)
        self._build_ui()

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        f_box = tk.LabelFrame(pad, text=t("batch_box_files", "Файлы"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=8)
        f_box.pack(fill=tk.X, pady=(0, 10))

        r1 = tk.Frame(f_box, bg=bg_card)
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text=t("batch_src_file", "Исходный файл:"), width=14, anchor="w", bg=bg_card, fg=fg_pri, font=theme.font(0)).pack(side=tk.LEFT)
        self.in_entry = tk.Entry(r1, font=theme.font(0), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1)
        self.in_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.in_entry)
        tk.Button(r1, text=t("btn_browse", "Обзор..."), font=theme.font(-1), bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._browse_input).pack(side=tk.RIGHT)

        r2 = tk.Frame(f_box, bg=bg_card)
        r2.pack(fill=tk.X, pady=2)
        tk.Label(r2, text=t("batch_out_file", "Сохранить как:"), width=14, anchor="w", bg=bg_card, fg=fg_pri, font=theme.font(0)).pack(side=tk.LEFT)
        self.out_entry = tk.Entry(r2, font=theme.font(0), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(self.out_entry)
        tk.Button(r2, text=t("btn_browse", "Обзор..."), font=theme.font(-1), bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._browse_output).pack(side=tk.RIGHT)

        opt_box = tk.LabelFrame(pad, text=t("batch_box_params", "Параметры"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=8)
        opt_box.pack(fill=tk.X, pady=(0, 10))

        r3 = tk.Frame(opt_box, bg=bg_card)
        r3.pack(fill=tk.X, pady=2)

        tk.Label(r3, text=t("batch_service", "Сервис:"), bg=bg_card, fg=fg_pri, font=theme.font(0)).pack(side=tk.LEFT)

        self.srv_keys = list(LOADED_SERVICES.keys())
        self.srv_display_map = {f"{LOADED_SERVICES[k].name} ({k})": k for k in self.srv_keys}
        display_values = list(self.srv_display_map.keys()) or ["Bing Translator (bing)"]

        self.srv_combo = ttk.Combobox(r3, values=display_values, width=28, state="readonly")

        default_sel = display_values[0]
        for name, k in self.srv_display_map.items():
            if k == "bing":
                default_sel = name
                break
        self.srv_combo.set(default_sel)
        self.srv_combo.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(r3, text=t("batch_lang", "Язык:"), bg=bg_card, fg=fg_pri, font=theme.font(0)).pack(side=tk.LEFT)
        self.lang_combo = ttk.Combobox(r3, values=["ru", "en", "de", "es", "fr", "zh-CN", "ja", "it", "pl", "cs", "tr"], width=8, state="readonly")
        self.lang_combo.set("ru")
        self.lang_combo.pack(side=tk.LEFT, padx=(4, 12))

        self.prot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(r3, text=t("batch_chk_protect", "Защита кода и тегов"), variable=self.prot_var, bg=bg_card, fg=fg_pri, selectcolor=theme.get_color("input_bg"), font=theme.font(0)).pack(side=tk.LEFT)

        prog_box = tk.LabelFrame(pad, text=t("batch_box_progress", "Прогресс"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=8)
        prog_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.pbar = ttk.Progressbar(prog_box, orient="horizontal", mode="determinate")
        self.pbar.pack(fill=tk.X, pady=4)

        self.lbl_status = tk.Label(prog_box, text=t("batch_status_ready", "Готов к запуску"), font=theme.font(-1), fg=theme.get_color("fg_muted"), bg=bg_card, anchor="w")
        self.lbl_status.pack(fill=tk.X)

        self.preview_lbl = tk.Label(prog_box, text="", font=theme.font(-1, "italic"), fg=fg_pri, bg=bg_card, anchor="w")
        self.preview_lbl.pack(fill=tk.X, pady=(2, 0))

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X)

        self.btn_start = tk.Button(
            btn_bar, text=t("batch_btn_start", "▶ Начать перевод"), font=theme.font(0, "bold"),
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), relief=tk.FLAT,
            padx=12, pady=4, cursor="hand2", command=self._start
        )
        self.btn_start.pack(side=tk.LEFT)

        self.btn_pause = tk.Button(
            btn_bar, text=t("batch_btn_pause", "⏸ Пауза"), font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=10, state="disabled", command=self._toggle_pause
        )
        self.btn_pause.pack(side=tk.LEFT, padx=6)

        self.btn_cancel = tk.Button(
            btn_bar, text=t("batch_btn_cancel", "⏹ Отмена"), font=theme.font(0), relief=tk.FLAT,
            bg="#ffebee", fg="#c62828", padx=10, state="disabled", command=self._cancel
        )
        self.btn_cancel.pack(side=tk.LEFT)

    def _browse_input(self):
        fn = filedialog.askopenfilename(filetypes=[("Text files", "*.txt;*.sub;*.srt;*.log;*.json;*.xml"), ("All files", "*.*")], parent=self)
        if fn:
            self.in_entry.delete(0, tk.END)
            self.in_entry.insert(0, fn)
            base, ext = os.path.splitext(fn)
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, f"{base}_translated{ext}")

    def _browse_output(self):
        fn = filedialog.asksaveasfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")], defaultextension=".txt", parent=self)
        if fn:
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, fn)

    def _start(self):
        in_f = self.in_entry.get().strip()
        out_f = self.out_entry.get().strip()
        if not in_f or not os.path.exists(in_f):
            messagebox.showwarning(t("btn_settings", "Внимание"), t("batch_warn_select_file", "Выберите существующий исходный файл!"), parent=self)
            return

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal", text=t("batch_btn_pause", "⏸ Пауза"))
        self.btn_cancel.config(state="normal")
        self.pbar["value"] = 0

        config.set_value("BATCH", "ProtectCode", "1" if self.prot_var.get() else "0")

        selected_display = self.srv_combo.get()
        actual_service_id = self.srv_display_map.get(selected_display, "bing")

        def on_prog(curr, total, pct, prev):
            self.after(0, lambda: self._update_ui_progress(curr, total, pct, prev))

        def on_done(path):
            self.after(0, lambda: self._on_finish(path))

        def on_err(err):
            self.after(0, lambda: self._on_error(err))

        batch_pipeline.start_file_translation(
            input_file=in_f,
            output_file=out_f,
            service_id=actual_service_id,
            trg_lang=self.lang_combo.get(),
            on_progress=on_prog,
            on_complete=on_done,
            on_error=on_err
        )

    def _update_ui_progress(self, curr, total, pct, prev):
        self.pbar["value"] = pct
        status_str = t("batch_status_translating", f"Переведено блоков: {curr} из {total} ({pct}%)", curr=curr, total=total, pct=pct)
        self.lbl_status.config(text=status_str)
        preview_str = t("batch_preview_prefix", f"Превью: {prev}", prev=prev)
        self.preview_lbl.config(text=preview_str)

    def _toggle_pause(self):
        pause_label = t("batch_btn_pause", "⏸ Пауза")
        resume_label = t("batch_btn_resume", "▶ Продолжить")
        if self.btn_pause["text"] == pause_label:
            batch_pipeline.pause()
            self.btn_pause.config(text=resume_label)
            self.lbl_status.config(text=t("batch_status_paused", "Перевод приостановлен (Пауза)"))
        else:
            batch_pipeline.resume()
            self.btn_pause.config(text=pause_label)

    def _cancel(self):
        batch_pipeline.cancel()
        self.lbl_status.config(text=t("batch_status_cancelled", "Отмена процесса..."))

    def _on_finish(self, out_path):
        self.pbar["value"] = 100
        self.lbl_status.config(text=t("batch_status_done", "✅ Перевод успешно завершен!"))
        self.btn_start.config(state="normal")
        self.btn_pause.config(state="disabled")
        self.btn_cancel.config(state="disabled")

        done_msg = t("batch_done_msg", f"Файл успешно переведен:\n\n{out_path}", path=out_path)
        messagebox.showinfo("OK", done_msg, parent=self)

    def _on_error(self, err_msg):
        err_str = t("batch_status_error", f"❌ Ошибка: {err_msg}", err=err_msg)
        self.lbl_status.config(text=err_str)
        self.btn_start.config(state="normal")
        self.btn_pause.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        messagebox.showerror(t("status_error", "Ошибка"), err_msg, parent=self)
