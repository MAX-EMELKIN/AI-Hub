# -*- coding: utf-8 -*-
# data/gui/glossary_window.py

import os, re, threading, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from data.core.i18n import t
from data.dictionary.glossary_engine import glossary_engine
from data.gui.dialogs import attach_entry_context_menu, attach_text_context_menu, ToolTip
from data.gui.theme_manager import theme
from data.services.base_service import LOADED_SERVICES
LANG_OPTIONS = [
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("ja", "日本語"),
    ("zh-CN", "中文"),
    ("ko", "한국어"),
    ("it", "Italiano"),
    ("pl", "Polski"),
    ("ru", "Русский")
]

class GlossaryEnrichmentDialog(tk.Toplevel):
    def __init__(self, parent, on_enriched_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_enriched = on_enriched_callback
        self._is_running = False
        self._cancel_flag = False

        bg_main = theme.get_color("bg_main")
        self.title(t("enrich_title", "✨ ИИ-обогащение всего словаря"))
        self.geometry("680x560")
        self.minsize(580, 460)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        self._generated_terms = {}
        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 680, 560
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")
        border = theme.get_color("bg_card_border")

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad, text=t("enrich_header", "✨ Генерация грамматических форм и множественного числа через ИИ"),
            font=theme.font(1, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(anchor="w", pady=(0, 8))

        opt_frame = tk.Frame(pad, bg=bg_card, padx=10, pady=8, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        opt_frame.pack(fill=tk.X, pady=(0, 8))

        r1 = tk.Frame(opt_frame, bg=bg_card)
        r1.pack(fill=tk.X, pady=3)
        tk.Label(r1, text=t("enrich_model_lbl", "Модель ИИ для генерации:"), font=theme.font(0, "bold"), fg=fg_pri, width=22, anchor="w", bg=bg_card).pack(side=tk.LEFT)

        self.srv_keys = [k for k in LOADED_SERVICES.keys() if k != "google_ai"]
        if not self.srv_keys:
            self.srv_keys = list(LOADED_SERVICES.keys())
        srv_display_names = [f"{LOADED_SERVICES[k].name} ({k})" for k in self.srv_keys] or ["DeepSeek Flash"]

        self.combo_srv = ttk.Combobox(r1, values=srv_display_names, state="readonly", width=28)
        self.combo_srv.set(srv_display_names[0])
        self.combo_srv.pack(side=tk.LEFT, fill=tk.X, expand=True)

        r2 = tk.Frame(opt_frame, bg=bg_card)
        r2.pack(fill=tk.X, pady=4)

        tk.Label(r2, text=t("enrich_src_lbl", "Язык оригинала:"), font=theme.font(0, "bold"), fg=fg_pri, width=14, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self.combo_src = ttk.Combobox(r2, values=[n for _, n in LANG_OPTIONS], state="readonly", width=18)
        self.combo_src.set("English")
        self.combo_src.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(r2, text=t("enrich_trg_lbl", "➔ Язык перевода:"), font=theme.font(0, "bold"), fg=fg_pri, width=15, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self.combo_trg = ttk.Combobox(r2, values=[n for _, n in LANG_OPTIONS], state="readonly", width=18)
        self.combo_trg.set("Русский")
        self.combo_trg.pack(side=tk.LEFT)

        r3 = tk.Frame(opt_frame, bg=bg_card)
        r3.pack(fill=tk.X, pady=4)
        self.var_plurals = tk.BooleanVar(value=True)
        tk.Checkbutton(r3, text=t("enrich_chk_plurals", "Множественное число и глагольные формы"), variable=self.var_plurals, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)).pack(side=tk.LEFT, padx=(0, 10))

        self.var_spelling = tk.BooleanVar(value=True)
        tk.Checkbutton(r3, text=t("enrich_chk_spelling", "Варианты через дефис / слитно и UK/US написание"), variable=self.var_spelling, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)).pack(side=tk.LEFT)

        prog_frame = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.pbar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.pbar.pack(fill=tk.X, pady=2)

        self.lbl_status = tk.Label(prog_frame, text=t("enrich_status_ready", "Готов к расширению словаря"), font=theme.font(-1), fg=theme.get_color("fg_muted"), bg=bg_card, anchor="w")
        self.lbl_status.pack(fill=tk.X)

        tk.Label(pad, text=t("enrich_preview_lbl", "Результаты генерации (Новые найденные формы):"), font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(anchor="w", pady=(0, 2))

        preview_frame = tk.Frame(pad, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.txt_preview = tk.Text(preview_frame, font=theme.font(0), bg=in_bg, fg=in_fg, wrap=tk.NONE, bd=0, padx=6, pady=6)
        sb_y = tk.Scrollbar(preview_frame, orient="vertical", command=self.txt_preview.yview)
        sb_x = tk.Scrollbar(preview_frame, orient="horizontal", command=self.txt_preview.xview)
        self.txt_preview.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_text_context_menu(self.txt_preview)

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_cancel = tk.Button(
            btn_bar, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self._on_close
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_apply = tk.Button(
            btn_bar, text=t("enrich_btn_apply", "💾 Применить к словарю"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("status_ready"), fg="#ffffff",
            state="disabled", cursor="hand2", padx=14, pady=3, command=self._apply_to_glossary
        )
        self.btn_apply.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_start = tk.Button(
            btn_bar, text=t("enrich_btn_start", "🚀 Начать обогащение"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=16, pady=3, command=self._start_enrichment
        )
        self.btn_start.pack(side=tk.LEFT)

    def _get_lang_code(self, display_name):
        for code, name in LANG_OPTIONS:
            if name == display_name: return code
        return "en"

    def _start_enrichment(self):
        terms = glossary_engine.get_all_terms()
        if not terms:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("enrich_warn_empty_dict", "Словарь пуст! Сначала добавьте базовые термины."), parent=self)
            return

        selected_idx = self.combo_srv.current()
        if selected_idx < 0 or selected_idx >= len(self.srv_keys):
            selected_idx = 0
        service_id = self.srv_keys[selected_idx]
        service = LOADED_SERVICES.get(service_id)

        src_lang = self._get_lang_code(self.combo_src.get())
        trg_lang = self._get_lang_code(self.combo_trg.get())

        self._is_running = True
        self._cancel_flag = False
        self.btn_start.config(state="disabled")
        self.btn_apply.config(state="disabled")
        self.pbar["value"] = 0
        self.txt_preview.delete("1.0", tk.END)
        self._generated_terms = {}

        threading.Thread(
            target=self._worker_thread,
            args=(service, terms, src_lang, trg_lang),
            daemon=True
        ).start()

    def _worker_thread(self, service, terms, src_lang, trg_lang):
        items = list(terms.items())
        total_items = len(items)
        batch_size = 10

        batches = [items[i:i + batch_size] for i in range(0, total_items, batch_size)]
        total_batches = len(batches)

        src_name = service.get_target_lang_name(src_lang)
        all_new_terms = {}
        current_lower = {k.strip().lower() for k in terms.keys()}

        system_instruction = (
            f"You are a high-speed morphological generator for game localization.\n"
            f"Task: Output ONLY real grammatical plural and inflected forms for terms in '{src_name}'.\n\n"
            f"STRICT FORBIDDEN RULES (DO NOT GENERATE):\n"
            f"1. NO casing changes: NEVER output lowercase or uppercase duplicates.\n"
            f"2. NO hyphenation changes: NEVER add '-' or merge words. Keep original spacing intact.\n"
            f"3. NO commentary, NO thoughts, NO preambles.\n\n"
            f"ALLOWED ONLY:\n"
            f"• Plural form with matching Russian plural (e.g. 'Stealth Boys = Стелс-бои', 'Stimpaks = Стимуляторы', 'Wolves = Волки').\n"
            f"• Output format: strictly 'Variant = Translation' (MAX 1-2 lines per term)."
        )

        junk_keywords = ["the user", "rule", "note", "format", "variant", "here is", "translation", "example", "singular", "plural"]

        for b_idx, batch in enumerate(batches):
            if self._cancel_flag: break

            batch_text = "\n".join(f"{k} = {v}" for k, v in batch)

            try:
                raw_response = service.query_llm_raw(
                    system_prompt=system_instruction,
                    user_content=batch_text,
                    max_tokens=400,
                    temperature=0.1
                )

                parsed = glossary_engine.parse_raw_text(raw_response)

                for gen_k, gen_v in parsed.items():
                    clean_k = gen_k.replace("[[__GLOSS:", "").replace("[[GLOSS:", "").replace("__]]", "").replace("]]", "").strip()
                    clean_v = gen_v.strip()

                    if not clean_k or len(clean_k.split()) > 4 or len(clean_k) > 35:
                        continue
                    if any(bad in clean_k.lower() for bad in junk_keywords):
                        continue
                    if not re.match(r'^[A-Za-z0-9\s\-_]+$', clean_k):
                        continue

                    k_low = clean_k.lower()
                    if k_low in current_lower:
                        continue

                    current_lower.add(k_low)
                    all_new_terms[clean_k] = clean_v
                    self._append_preview_line(f"{clean_k} = {clean_v}\n")

            except Exception as e:
                print(f"[Enrichment Batch Error]: {e}")

            pct = int(((b_idx + 1) / total_batches) * 100)
            self._update_progress(b_idx + 1, total_batches, pct, len(all_new_terms))
            time.sleep(0.2)

        self._generated_terms = all_new_terms
        self._finish_work(len(terms), len(all_new_terms))

    def _append_preview_line(self, line_text):
        self.after(0, lambda: (self.txt_preview.insert(tk.END, line_text), self.txt_preview.see(tk.END)))

    def _update_progress(self, curr, total, pct, new_count):
        def _ui():
            self.pbar["value"] = pct
            status_text = t(
                "enrich_status_progress",
                f"Обработано пачек: {curr} из {total} ({pct}%) | Найдено новых вариантов: +{new_count}",
                curr=curr, total=total, pct=pct, new_count=new_count
            )
            self.lbl_status.config(text=status_text)
        self.after(0, _ui)

    def _finish_work(self, orig_count, new_count):
        def _ui():
            self._is_running = False
            self.btn_start.config(state="normal")
            if new_count > 0:
                self.btn_apply.config(state="normal")
                done_text = t(
                    "enrich_status_done",
                    f"✅ Готово! Исходных терминов: {orig_count} | Найдено новых: +{new_count} | Всего станет: {orig_count + new_count}",
                    orig=orig_count, new_count=new_count, total=orig_count + new_count
                )
                self.lbl_status.config(text=done_text)
            else:
                self.lbl_status.config(text=t("enrich_status_empty", "Завершено. Все формы уже есть в словаре."))
        self.after(0, _ui)

    def _apply_to_glossary(self):
        if not self._generated_terms: return

        current_terms = glossary_engine.get_all_terms()
        current_terms.update(self._generated_terms)
        glossary_engine.save_all_terms(current_terms)

        if self.on_enriched:
            self.on_enriched()

        success_text = t(
            "enrich_success_msg",
            f"Словарь успешно обогащён!\n\nДобавлено новых вариантов: +{len(self._generated_terms)}\nВсего терминов в базе: {len(current_terms)}.",
            count=len(self._generated_terms), total=len(current_terms)
        )
        messagebox.showinfo("OK", success_text, parent=self)
        self.destroy()

    def _on_close(self):
        if self._is_running:
            self._cancel_flag = True
        self.destroy()

class BatchGlossaryImportDialog(tk.Toplevel):
    def __init__(self, parent, on_imported_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_imported = on_imported_callback

        bg_main = theme.get_color("bg_main")
        self.title(t("import_title", "Пакетный импорт терминов в словарь"))
        self.geometry("680x540")
        self.minsize(580, 440)
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
        w, h = 680, 540
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")
        border = theme.get_color("bg_card_border")

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad, text=t("import_header", "📥 Вставьте скопированный список или загрузите файл:"),
            font=theme.font(1, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(anchor="w", pady=(0, 6))

        act_bar = tk.Frame(pad, bg=bg_main)
        act_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            act_bar, text=t("import_btn_paste", "📋 Вставить из буфера"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
            cursor="hand2", padx=8, pady=2, command=self._paste_clipboard
        ).pack(side=tk.LEFT)

        tk.Button(
            act_bar, text=t("import_btn_load_file", "📁 Загрузить из файла"), font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri,
            cursor="hand2", padx=8, pady=2, command=self._load_file
        ).pack(side=tk.LEFT, padx=6)

        self.btn_pre_enrich = tk.Button(
            act_bar, text=t("import_btn_enrich_pre", "✨ Обогатить список через ИИ"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=8, pady=2, command=self._enrich_list_before_import
        )
        self.btn_pre_enrich.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_pre_enrich, t("import_tip_enrich_pre", "Сгенерировать множественные числа и формы для всех строк в поле перед сохранением"))

        tk.Button(
            act_bar, text=t("import_btn_clear", "Очистить"), font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri,
            cursor="hand2", padx=6, pady=2, command=lambda: self.text_area.delete("1.0", tk.END)
        ).pack(side=tk.RIGHT)

        text_frame = tk.Frame(pad, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        self.text_area = tk.Text(text_frame, font=theme.font(0), bg=in_bg, fg=in_fg, wrap=tk.NONE, bd=0, padx=6, pady=6)
        sb_y = tk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        sb_x = tk.Scrollbar(text_frame, orient="horizontal", command=self.text_area.xview)
        self.text_area.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_text_context_menu(self.text_area)

        info_frame = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        info_frame.pack(fill=tk.X, pady=(0, 8))

        default_info_text = (
            "💡 Поддерживаются любые разделители (=, ->, табуляция, пробелы между языками).\n"
            "Скрипт сам автоматически отделит латиницу / иероглифы от целевого перевода."
        )
        tk.Label(
            info_frame, text=t("import_info_text", default_info_text),
            font=theme.font(-2), fg=theme.get_color("fg_secondary"), bg=bg_card, justify="left"
        ).pack(side=tk.LEFT)

        self.var_merge = tk.BooleanVar(value=True)
        tk.Checkbutton(
            info_frame, text=t("import_chk_merge", "Добавить к существующим"), variable=self.var_merge,
            bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1, "bold")
        ).pack(side=tk.RIGHT, padx=4)

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_bar, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_bar, text=t("import_btn_do_import", "💾 Импортировать в словарь"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=16, pady=4, command=self._do_import
        ).pack(side=tk.RIGHT)

    def _paste_clipboard(self):
        try:
            from data.core.win_api import read_clipboard_text
            text = read_clipboard_text() or self.clipboard_get()
            if text:
                self.text_area.insert(tk.INSERT, text)
        except Exception: pass

    def _load_file(self):
        fn = filedialog.askopenfilename(
            filetypes=[("Text & Table files", "*.txt;*.tsv;*.csv;*.dic"), ("All files", "*.*")],
            parent=self
        )
        if fn and os.path.exists(fn):
            for enc in ["utf-8-sig", "utf-8", "cp1251", "utf-16"]:
                try:
                    with open(fn, "r", encoding=enc) as f:
                        data = f.read()
                        self.text_area.delete("1.0", tk.END)
                        self.text_area.insert("1.0", data)
                        return
                except Exception: pass

    def _enrich_list_before_import(self):
        raw = self.text_area.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("import_warn_empty", "Вставьте или загрузите список терминов!"), parent=self)
            return

        parsed = glossary_engine.parse_raw_text(raw)
        if not parsed:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("import_warn_parse_fail", "Не удалось распознать строки. Проверьте формат."), parent=self)
            return

        avail = [s for s in LOADED_SERVICES.values() if s.service_id != "google_ai"]
        if not avail:
            avail = list(LOADED_SERVICES.values())

        if not avail:
            messagebox.showerror(t("status_error", "Ошибка"), t("enrich_err_no_services", "Нет активных сервисов ИИ для генерации!"), parent=self)
            return

        service = avail[0]
        self.btn_pre_enrich.config(state="disabled", text="⏳ ...")

        def _worker():
            items = list(parsed.items())
            batch_size = 12
            batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

            system_instruction = (
                "You are an expert morphological lexicographer for video game localization.\n"
                "Task: Output ONLY real grammatical plural and inflected forms for given terms.\n\n"
                "STRICT FORBIDDEN RULES:\n"
                "1. NO casing changes: NEVER output lowercase or uppercase duplicates.\n"
                "2. NO hyphenation changes: NEVER add '-' or merge words. Keep original spacing.\n"
                "3. NO commentary, NO thoughts.\n\n"
                "ALLOWED ONLY:\n"
                "• Plural form with matching Russian plural (e.g. 'Stealth Boys = Стелс-бои', 'Stimpaks = Стимуляторы').\n"
                "• Output format: strictly 'Variant = Translation' (MAX 1-2 lines per term)."
            )

            all_combined = dict(parsed)
            new_added = 0
            current_lower = {k.strip().lower() for k in parsed.keys()}

            for batch in batches:
                batch_text = "\n".join(f"{k} = {v}" for k, v in batch)
                try:
                    raw_res = service.query_llm_raw(
                        system_prompt=system_instruction,
                        user_content=batch_text,
                        max_tokens=400,
                        temperature=0.1
                    )
                    gen_parsed = glossary_engine.parse_raw_text(raw_res)
                    for k, v in gen_parsed.items():
                        clean_k = k.replace("[[__GLOSS:", "").replace("[[GLOSS:", "").replace("__]]", "").replace("]]", "").strip()
                        clean_v = v.strip()
                        if not clean_k or len(clean_k.split()) > 4: continue
                        if clean_k.lower() not in current_lower:
                            all_combined[clean_k] = clean_v
                            current_lower.add(clean_k.lower())
                            new_added += 1
                except Exception as e:
                    print(f"[Pre-enrich Error]: {e}")
                time.sleep(0.2)

            def _done():
                self.btn_pre_enrich.config(state="normal", text=t("import_btn_enrich_pre", "✨ Обогатить список через ИИ"))
                formatted_lines = [f"{k} = {v}" for k, v in sorted(all_combined.items(), key=lambda x: str(x[0]).lower())]
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", "\n".join(formatted_lines))

                done_msg = t(
                    "import_pre_done_msg",
                    f"✅ Список успешно обогащён!\n\nБыло исходных терминов: {len(parsed)}\nДобавлено новых форм: +{new_added}\nВсего готово к импорту: {len(all_combined)}\n\nНажмите «💾 Импортировать в словарь» для сохранения.",
                    orig=len(parsed), new_count=new_added, total=len(all_combined)
                )
                messagebox.showinfo("OK", done_msg, parent=self)

            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _do_import(self):
        raw = self.text_area.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("import_warn_empty", "Вставьте или загрузите список терминов!"), parent=self)
            return

        parsed = glossary_engine.parse_raw_text(raw)
        if not parsed:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("import_warn_parse_fail", "Не удалось распознать термины. Проверьте формат строк."), parent=self)
            return

        current_terms = glossary_engine.get_all_terms() if self.var_merge.get() else {}
        current_terms.update(parsed)

        glossary_engine.save_all_terms(current_terms)

        if self.on_imported:
            self.on_imported()

        success_msg = t(
            "import_success_msg",
            f"Успешно импортировано {len(parsed)} терминов!\nВсего в словаре: {len(current_terms)}.",
            count=len(parsed), total=len(current_terms)
        )
        messagebox.showinfo("OK", success_msg, parent=self)
        self.destroy()

class GlossaryWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        theme.apply_ttk_theme(self)

        self._all_terms_cache = {}
        self._search_timer = None
        self._is_enriching = False

        bg_main = theme.get_color("bg_main")
        self.title(t("dict_title", "Словарь терминов (Глоссарий)"))
        self.geometry("740x520")
        self.minsize(640, 440)
        self.configure(bg=bg_main)
        self.transient(parent)

        self._build_ui()
        self._load_terms()

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")
        border = theme.get_color("bg_card_border")

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(pad, bg=bg_main)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        tk.Label(top_bar, text=t("dict_search", "🔍 Поиск:"), font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT, padx=(0, 4))
        self.e_search = tk.Entry(top_bar, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=18)
        self.e_search.pack(side=tk.LEFT, padx=(0, 6))
        self.e_search.bind("<KeyRelease>", self._on_search_changed)
        attach_entry_context_menu(self.e_search)

        self.lbl_count = tk.Label(top_bar, text=t("dict_total_count", "Всего: 0", count=0), font=theme.font(-1), fg=theme.get_color("fg_muted"), bg=bg_main)
        self.lbl_count.pack(side=tk.LEFT)

        btn_enrich_all = tk.Button(
            top_bar, text=t("dict_btn_enrich_all", "✨ Обогатить всю базу через ИИ"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=8, pady=2, command=self._open_enrichment_wizard
        )
        btn_enrich_all.pack(side=tk.RIGHT)
        ToolTip(btn_enrich_all, t("dict_tip_enrich_all", "Пакетная генерация форм для всех слов в словаре"))

        btn_batch = tk.Button(
            top_bar, text=t("dict_btn_batch_import", "📥 Пакетный импорт"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
            cursor="hand2", padx=8, pady=2, command=self._open_batch_import
        )
        btn_batch.pack(side=tk.RIGHT, padx=6)
        ToolTip(btn_batch, t("dict_tip_batch_import", "Вставить список из буфера или загрузить файл на тысячи слов"))

        tree_frame = tk.Frame(pad, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        columns = ("orig", "trans")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("orig", text=t("dict_col_orig", "Оригинальное слово / фраза"))
        self.tree.heading("trans", text=t("dict_col_trans", "Обязательный перевод"))
        self.tree.column("orig", width=280)
        self.tree.column("trans", width=280)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)

        in_frame = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)
        in_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(in_frame, text=t("dict_lbl_orig", "Оригинал:"), font=theme.font(0), fg=fg_pri, bg=bg_card).grid(row=0, column=0, sticky="w", padx=2)
        self.e_orig = tk.Entry(in_frame, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_orig.grid(row=0, column=1, padx=4, sticky="ew")
        attach_entry_context_menu(self.e_orig)

        tk.Label(in_frame, text=t("dict_lbl_trans", "Перевод:"), font=theme.font(0), fg=fg_pri, bg=bg_card).grid(row=0, column=2, sticky="w", padx=4)
        self.e_trans = tk.Entry(in_frame, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_trans.grid(row=0, column=3, padx=4, sticky="ew")
        attach_entry_context_menu(self.e_trans)

        in_frame.columnconfigure(1, weight=1)
        in_frame.columnconfigure(3, weight=1)

        btn_row = tk.Frame(pad, bg=bg_main)
        btn_row.pack(fill=tk.X)

        tk.Button(
            btn_row, text=t("dict_btn_add", "➕ Добавить / Обновить"), font=theme.font(0),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=theme.get_color("status_ready"),
            cursor="hand2", padx=10, pady=3, command=self._add_term
        ).pack(side=tk.LEFT)

        self.btn_enrich = tk.Button(
            btn_row, text=t("dict_btn_enrich_single", "✨ Обогатить термин"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
            cursor="hand2", padx=10, pady=3, command=self._enrich_selected_or_single
        )
        self.btn_enrich.pack(side=tk.LEFT, padx=6)
        ToolTip(self.btn_enrich, t("dict_tip_enrich_single", "Сгенерировать множественное число и формы для одного или всех выделенных терминов"))

        self.btn_delete = tk.Button(
            btn_row, text=t("dict_btn_delete", "🗑️ Удалить"), font=theme.font(0),
            relief=tk.FLAT, bg="#ffebee", fg="#c62828",
            cursor="hand2", padx=10, pady=3, command=self._delete_selected_terms
        )
        self.btn_delete.pack(side=tk.LEFT, padx=6)

        tk.Button(
            btn_row, text=t("btn_close", "Закрыть"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=14, pady=3, command=self.destroy
        ).pack(side=tk.RIGHT)

    def _open_enrichment_wizard(self):
        GlossaryEnrichmentDialog(self, on_enriched_callback=self._load_terms)

    def _open_batch_import(self):
        BatchGlossaryImportDialog(self, on_imported_callback=self._load_terms)

    def _load_terms(self):
        glossary_engine.reload()
        self._all_terms_cache = glossary_engine.get_all_terms()
        self._refresh_tree_view()

    def _on_search_changed(self, event):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(150, self._refresh_tree_view)

    def _refresh_tree_view(self):
        q = self.e_search.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        total_count = len(self._all_terms_cache)
        items_shown = 0
        max_display = 1500

        for k, v in sorted(self._all_terms_cache.items(), key=lambda x: str(x[0]).lower()):
            if not q or q in str(k).lower() or q in str(v).lower():
                self.tree.insert("", tk.END, values=(k, v))
                items_shown += 1
                if items_shown >= max_display:
                    break

        if q:
            self.lbl_count.config(text=t("dict_found_count", f"Найдено: {items_shown} из {total_count}", shown=items_shown, total=total_count))
        else:
            self.lbl_count.config(text=t("dict_total_count", f"Всего терминов: {total_count}", count=total_count))

    def _on_select_item(self, event):
        sel = self.tree.selection()
        if len(sel) == 1:
            item = self.tree.item(sel[0])
            vals = item["values"]
            self.e_orig.delete(0, tk.END)
            self.e_orig.insert(0, vals[0])
            self.e_trans.delete(0, tk.END)
            self.e_trans.insert(0, vals[1])
            self.btn_enrich.config(text=t("dict_btn_enrich_single", "✨ Обогатить термин"))
            self.btn_delete.config(text=t("dict_btn_delete", "🗑️ Удалить"))
        elif len(sel) > 1:
            self.btn_enrich.config(text=t("dict_btn_enrich_selected", f"✨ Обогатить выбранное ({len(sel)})", count=len(sel)))
            self.btn_delete.config(text=t("dict_btn_delete_selected", f"🗑️ Удалить ({len(sel)})", count=len(sel)))
        else:
            self.btn_enrich.config(text=t("dict_btn_enrich_single", "✨ Обогатить термин"))
            self.btn_delete.config(text=t("dict_btn_delete", "🗑️ Удалить"))

    def _add_term(self):
        k = self.e_orig.get().strip()
        v = self.e_trans.get().strip()
        if not k or not v:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("dict_warn_fill", "Заполните оба поля!"), parent=self)
            return
        terms = glossary_engine.get_all_terms()
        terms[k] = v
        glossary_engine.save_all_terms(terms)
        self._load_terms()
        self.e_orig.delete(0, tk.END)
        self.e_trans.delete(0, tk.END)

    def _enrich_selected_or_single(self):
        sel = self.tree.selection()
        target_pairs = []

        if len(sel) > 1:
            for s_item in sel:
                item_data = self.tree.item(s_item)
                vals = item_data["values"]
                if len(vals) >= 2:
                    target_pairs.append((str(vals[0]).strip(), str(vals[1]).strip()))
        else:
            k = self.e_orig.get().strip()
            v = self.e_trans.get().strip()
            if not k or not v:
                messagebox.showwarning(t("btn_settings", "Внимание"), t("dict_warn_fill", "Заполните поля или выделите строки в таблице!"), parent=self)
                return
            target_pairs.append((k, v))

        avail = [s for s in LOADED_SERVICES.values() if s.service_id != "google_ai"]
        if not avail:
            avail = list(LOADED_SERVICES.values())

        if not avail:
            messagebox.showerror(t("status_error", "Ошибка"), t("dict_warn_no_ai", "Нет активных сервисов ИИ для генерации!"), parent=self)
            return

        service = avail[0]
        total_terms = len(target_pairs)

        self.btn_enrich.config(state="disabled", text=f"⏳ ({total_terms})...")
        self.lbl_count.config(text=t("dict_enrich_generating", f"Генерация форм для {total_terms} терминов через {service.name}...", count=total_terms, name=service.name))

        def _worker():
            batch_size = 10
            batches = [target_pairs[i:i + batch_size] for i in range(0, total_terms, batch_size)]

            system_instruction = (
                "You are a high-speed morphological generator for game localization.\n"
                "Task: Output ONLY real grammatical plural and inflected forms for terms.\n\n"
                "STRICT FORBIDDEN RULES:\n"
                "1. NO casing changes: NEVER output lowercase or uppercase duplicates.\n"
                "2. NO hyphenation changes: NEVER add '-' or merge words. Keep original spacing intact.\n"
                "3. NO commentary, NO thoughts.\n\n"
                "ALLOWED ONLY:\n"
                "• Plural form with matching Russian plural (e.g. 'Stealth Boys = Стелс-бои', 'Stimpaks = Стимуляторы', 'Wolves = Волки').\n"
                "• Output format: strictly 'Variant = Translation' (MAX 1-2 lines per term)."
            )

            current_terms = glossary_engine.get_all_terms()
            current_lower = {k.strip().lower() for k in current_terms.keys()}
            new_added = 0
            added_list = []

            for batch in batches:
                batch_text = "\n".join(f"{k} = {v}" for k, v in batch)
                try:
                    raw_res = service.query_llm_raw(
                        system_prompt=system_instruction,
                        user_content=batch_text,
                        max_tokens=400,
                        temperature=0.1
                    )

                    parsed = glossary_engine.parse_raw_text(raw_res)

                    for gen_k, gen_v in parsed.items():
                        clean_k = gen_k.replace("[[__GLOSS:", "").replace("[[GLOSS:", "").replace("__]]", "").replace("]]", "").strip()
                        clean_v = gen_v.strip()

                        if not clean_k or len(clean_k.split()) > 4: continue
                        if clean_k.lower() in current_lower: continue

                        current_lower.add(clean_k.lower())
                        current_terms[clean_k] = clean_v
                        added_list.append(f"{clean_k} = {clean_v}")
                        new_added += 1

                except Exception as e:
                    print(f"[Multi-enrich Error]: {e}")
                time.sleep(0.2)

            glossary_engine.save_all_terms(current_terms)

            def _done():
                self._load_terms()
                self.btn_enrich.config(state="normal", text=t("dict_btn_enrich_single", "✨ Обогатить термин"))
                if new_added > 0:
                    self.lbl_count.config(text=f"✅ +{new_added}")
                    preview = "\n".join(f"• {x}" for x in added_list[:12])
                    if len(added_list) > 12:
                        preview += f"\n... ({len(added_list) - 12})"

                    done_msg = t(
                        "dict_enrich_done_msg",
                        f"Для {total_terms} терминов создано +{new_added} новых форм:\n\n{preview}",
                        count=total_terms, new_count=new_added, preview=preview
                    )
                    messagebox.showinfo("OK", done_msg, parent=self)
                else:
                    self.lbl_count.config(text=t("dict_enrich_none_msg", "Все формы для выбранных терминов уже есть в словаре."))
                    messagebox.showinfo("OK", t("dict_enrich_none_msg", "Все формы для выбранных терминов уже есть в словаре."), parent=self)

            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _delete_selected_terms(self):
        sel = self.tree.selection()
        if not sel: return

        count = len(sel)
        if count == 1:
            item = self.tree.item(sel[0])
            k = item["values"][0]
            del_msg = t("dict_delete_confirm_single", f"Удалить термин '{k}'?", name=k)
            if messagebox.askyesno(t("confirm_delete_title", "Подтверждение"), del_msg, parent=self):
                terms = glossary_engine.get_all_terms()
                if k in terms:
                    del terms[k]
                    glossary_engine.save_all_terms(terms)
                    self._load_terms()
                    self.e_orig.delete(0, tk.END)
                    self.e_trans.delete(0, tk.END)
        else:
            del_multi_msg = t("dict_delete_confirm_multi", f"Вы действительно хотите удалить {count} выделенных терминов?", count=count)
            if messagebox.askyesno(t("confirm_delete_title", "Подтверждение"), del_multi_msg, parent=self):
                terms = glossary_engine.get_all_terms()
                for s_item in sel:
                    item_data = self.tree.item(s_item)
                    k = item_data["values"][0]
                    if k in terms:
                        del terms[k]
                glossary_engine.save_all_terms(terms)
                self._load_terms()
                self.e_orig.delete(0, tk.END)
                self.e_trans.delete(0, tk.END)
