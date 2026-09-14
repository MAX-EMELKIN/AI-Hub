# -*- coding: utf-8 -*-
"""
Модуль: data/gui/settings_window.py
Назначение: Окно настроек программы с полной мультиязычной локализацией,
            управлением темами, горячими клавишами, OCR, TTS и подробной вкладкой
            настройки категорий отладки и интерактивной консоли Windows.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64)
"""

import os
import time
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.config_manager import config
from data.core.i18n import t, i18n
from data.core.hotkey_manager import hotkey_manager
from data.ocr.ocr_engine import ocr_engine
from data.tts.tts_engine import tts_engine
from data.gui.theme_manager import theme
from data.gui.dialogs import attach_entry_context_menu
from data.core.logger import logger

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, on_settings_updated=None):
        super().__init__(parent)
        self.parent = parent
        self.on_settings_updated = on_settings_updated

        theme.apply_ttk_theme(self)

        bg_main = theme.get_color("bg_main")
        self.title(t("settings_title", "Настройки программы"))
        self.geometry("660x560")
        self.minsize(580, 480)
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
        w, h = 660, 560
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

        # --- ВКЛАДКА 1: ОСНОВНЫЕ И ОФОРМЛЕНИЕ ---
        tab_gen = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_gen, text=t("settings_tab_general", "Основные и Оформление"))

        self.var_autolaunch = tk.BooleanVar(value=config.get_bool("GENERAL", "AutoLaunchQTranslate", True))
        tk.Checkbutton(
            tab_gen, text=t("settings_chk_autolaunch", "Автозапуск QTranslate.exe вместе с хабом"),
            variable=self.var_autolaunch, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0)
        ).pack(anchor="w", pady=4)

        self.var_minimized = tk.BooleanVar(value=config.get_bool("GENERAL", "StartMinimized", True))
        tk.Checkbutton(
            tab_gen, text=t("settings_chk_minimized", "Запускать свернутым в трей"),
            variable=self.var_minimized, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0)
        ).pack(anchor="w", pady=4)

        # Выбор Темы
        r_theme = tk.Frame(tab_gen, bg=bg_card)
        r_theme.pack(fill=tk.X, pady=6)
        tk.Label(r_theme, text=t("settings_lbl_theme", "Тема оформления:"), bg=bg_card, fg=fg_pri, font=theme.font(0, "bold"), width=18, anchor="w").pack(side=tk.LEFT)
        
        self.theme_options = theme.get_theme_display_options()
        theme_names = [name for _, name in self.theme_options]
        self.combo_theme = ttk.Combobox(r_theme, values=theme_names, state="readonly", width=16)
        
        cur_th = theme.current_theme_key
        cur_th_name = next((name for k, name in self.theme_options if k == cur_th), theme_names[0])
        self.combo_theme.set(cur_th_name)
        self.combo_theme.pack(side=tk.LEFT, padx=6)

        # Выбор размера шрифта
        r_font = tk.Frame(tab_gen, bg=bg_card)
        r_font.pack(fill=tk.X, pady=6)
        tk.Label(r_font, text=t("settings_lbl_fontsize", "Размер шрифта GUI:"), bg=bg_card, fg=fg_pri, font=theme.font(0, "bold"), width=18, anchor="w").pack(side=tk.LEFT)
        
        self.font_options = theme.get_font_display_options()
        font_names = [name for _, name in self.font_options]
        self.combo_font = ttk.Combobox(r_font, values=font_names, state="readonly", width=18)
        
        cur_fs = theme.current_font_scale
        cur_fs_name = next((name for k, name in self.font_options if k == cur_fs), font_names[1])
        self.combo_font.set(cur_fs_name)
        self.combo_font.pack(side=tk.LEFT, padx=6)

        # Язык интерфейса
        r_lang = tk.Frame(tab_gen, bg=bg_card)
        r_lang.pack(fill=tk.X, pady=6)
        tk.Label(r_lang, text=t("settings_lbl_lang", "Язык интерфейса:"), bg=bg_card, fg=fg_pri, font=theme.font(0), width=18, anchor="w").pack(side=tk.LEFT)
        
        self.lang_options = i18n.get_available_languages()
        lang_display_names = [name for _, name in self.lang_options]
        self.combo_lang = ttk.Combobox(r_lang, values=lang_display_names, state="readonly", width=18)
        
        cur_lang = config.get_str("GENERAL", "UILanguage", "auto").lower()
        cur_lang_name = next((name for k, name in self.lang_options if k == cur_lang), lang_display_names[0])
        self.combo_lang.set(cur_lang_name)
        self.combo_lang.pack(side=tk.LEFT, padx=6)

        # HTTP Порт
        r_port = tk.Frame(tab_gen, bg=bg_card)
        r_port.pack(fill=tk.X, pady=6)
        tk.Label(r_port, text=t("settings_lbl_port", "HTTP Порт сервера:"), bg=bg_card, fg=fg_pri, font=theme.font(0), width=18, anchor="w").pack(side=tk.LEFT)
        self.e_port = tk.Entry(r_port, width=8, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_port.insert(0, str(config.get_int("GENERAL", "ServerPort", 8080)))
        self.e_port.pack(side=tk.LEFT, padx=6)
        attach_entry_context_menu(self.e_port)

        # --- ВКЛАДКА 2: ГОРЯЧИЕ КЛАВИШИ ---
        tab_keys = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_keys, text=t("settings_tab_hotkeys", "Горячие клавиши"))

        tk.Label(tab_keys, text=t("settings_hk_header", "Глобальные клавиши AI Hub:"), font=theme.font(0, "bold"), fg=theme.get_color("accent"), bg=bg_card).pack(anchor="w", pady=(0, 6))

        r_hk_ocr = tk.Frame(tab_keys, bg=bg_card)
        r_hk_ocr.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_ocr, text="Снимок OCR:", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_ocr = tk.Entry(r_hk_ocr, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_ocr.insert(0, config.get_str("HOTKEYS", "OCR", ""))
        self.e_hk_ocr.pack(side=tk.RIGHT)
        self.e_hk_ocr.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_ocr))

        r_hk_win = tk.Frame(tab_keys, bg=bg_card)
        r_hk_win.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_win, text="Показать / Скрыть Hub:", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_win = tk.Entry(r_hk_win, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_win.insert(0, config.get_str("HOTKEYS", "ToggleWindow", ""))
        self.e_hk_win.pack(side=tk.RIGHT)
        self.e_hk_win.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_win))

        r_hk_tts = tk.Frame(tab_keys, bg=bg_card)
        r_hk_tts.pack(fill=tk.X, pady=3)
        tk.Label(r_hk_tts, text="Озвучить буфер (TTS):", bg=bg_card, fg=fg_pri, font=theme.font(0), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_tts = tk.Entry(r_hk_tts, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("accent"))
        self.e_hk_tts.insert(0, config.get_str("HOTKEYS", "TTS", ""))
        self.e_hk_tts.pack(side=tk.RIGHT)
        self.e_hk_tts.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_tts))

        r_qtr = tk.Frame(tab_keys, bg=bg_card)
        r_qtr.pack(fill=tk.X, pady=(10, 3))
        tk.Label(r_qtr, text="Клавиша вызова QTranslate:", bg=bg_card, fg=theme.get_color("status_ready"), font=theme.font(0, "bold"), width=28, anchor="w").pack(side=tk.LEFT)
        self.e_hk_qtr = tk.Entry(r_qtr, font=theme.font(0, "bold"), width=16, justify="center", fg=theme.get_color("status_ready"))
        self.e_hk_qtr.insert(0, config.get_str("QTRANSLATE", "SummonHotkey", "double_ctrl"))
        self.e_hk_qtr.pack(side=tk.RIGHT)
        self.e_hk_qtr.bind("<KeyPress>", lambda e: self._record_key(e, self.e_hk_qtr))

        tk.Label(
            tab_keys, text="* Кликните в поле и нажмите клавишу. Нажмите Delete/Backspace чтобы очистить.",
            font=theme.font(-2, "italic"), fg=theme.get_color("fg_muted"), bg=bg_card
        ).pack(anchor="w", pady=(8, 0))

        # --- ВКЛАДКА 3: OCR & ОЗВУЧКА ---
        tab_media = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_media, text=t("settings_tab_media", "OCR и Озвучка"))

        tk.Label(tab_media, text=t("settings_ocr_model_lbl", "Модель офлайн OCR:"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri).pack(anchor="w", pady=(0, 2))
        self.combo_ocr = ttk.Combobox(tab_media, values=ocr_engine.get_available_models(), state="readonly", width=14)
        self.combo_ocr.set(ocr_engine.get_active_model())
        self.combo_ocr.pack(anchor="w", pady=(0, 10))

        tk.Label(tab_media, text=t("settings_tts_speed_lbl", "Скорость нейро-озвучки (TTS):"), font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri).pack(anchor="w", pady=(0, 2))
        self.scale_speed = tk.Scale(
            tab_media, from_=0.7, to=1.4, resolution=0.05, orient="horizontal",
            bg=bg_card, fg=fg_pri, troughcolor=in_bg, activebackground=theme.get_color("accent"),
            highlightthickness=0
        )
        self.scale_speed.set(config.get_float("TTS", "Speed", 1.0))
        self.scale_speed.pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            tab_media, text="Проверить озвучку", font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._test_tts
        ).pack(anchor="w")

        # --- ВКЛАДКА 4: ОТЛАДКА И КОНСОЛЬ ---
        tab_logs = tk.Frame(nb, bg=bg_card, padx=14, pady=12)
        nb.add(tab_logs, text="Отладка и Логи")

        # Блок управления консолью
        f_con = tk.LabelFrame(tab_logs, text=" Вывод логов ", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_con.pack(fill=tk.X, pady=(0, 8))

        self.var_show_console = tk.BooleanVar(value=config.get_bool("LOGGING", "showconsole", False))
        tk.Checkbutton(
            f_con, text="Показывать интерактивное окно консоли Windows",
            variable=self.var_show_console, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0, "bold"),
            command=self._toggle_console_live
        ).pack(anchor="w")

        r_log_files = tk.Frame(f_con, bg=bg_card)
        r_log_files.pack(fill=tk.X, pady=(4, 0))

        self.var_log_to_file = tk.BooleanVar(value=config.get_bool("LOGGING", "logtofile", True))
        tk.Checkbutton(
            r_log_files, text="Записывать лог в файл hub_debug.log",
            variable=self.var_log_to_file, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(side=tk.LEFT)

        self.var_clear_on_startup = tk.BooleanVar(value=config.get_bool("LOGGING", "clearonstartup", True))
        tk.Checkbutton(
            r_log_files, text="Очищать лог при перезапуске",
            variable=self.var_clear_on_startup, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Button(
            f_con, text="Открыть папку с логами", font=theme.font(-2), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, command=self._open_log_folder
        ).pack(anchor="e", pady=(4, 0))

        # Блок категорий логирования
        f_cats = tk.LabelFrame(tab_logs, text=" Разделы логирования ", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        f_cats.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.var_log_api_summary = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_summary", True))
        tk.Checkbutton(
            f_cats, text="[СЕТЬ] Краткий статус запросов (модель, время, статус HTTP)",
            variable=self.var_log_api_summary, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_api_payload = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_payload", True))
        tk.Checkbutton(
            f_cats, text="[СЕТЬ] Полное тело исходящего запроса (промпт, параметры)",
            variable=self.var_log_api_payload, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_api_raw = tk.BooleanVar(value=config.get_bool("LOGGING", "log_api_raw_response", True))
        tk.Checkbutton(
            f_cats, text="[СЕТЬ] Сырой ответ сервера (сырой JSON)",
            variable=self.var_log_api_raw, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_tools = tk.BooleanVar(value=config.get_bool("LOGGING", "log_tools", True))
        tk.Checkbutton(
            f_cats, text="[ПОИСК] Вызовы инструментов (DuckDuckGo, чтение ссылок)",
            variable=self.var_log_tools, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_glossary = tk.BooleanVar(value=config.get_bool("LOGGING", "log_glossary", True))
        tk.Checkbutton(
            f_cats, text="[ТЕКСТ] События умного глоссария (подстановка терминов)",
            variable=self.var_log_glossary, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_filtering = tk.BooleanVar(value=config.get_bool("LOGGING", "log_filtering", True))
        tk.Checkbutton(
            f_cats, text="[ТЕКСТ] Фильтрация ответа (удаление мыслей, кавычек и мусора)",
            variable=self.var_log_filtering, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_qtranslate = tk.BooleanVar(value=config.get_bool("LOGGING", "log_qtranslate", True))
        tk.Checkbutton(
            f_cats, text="[СИСТЕМА] Входящие вызовы от кнопок QTranslate",
            variable=self.var_log_qtranslate, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        self.var_log_browser = tk.BooleanVar(value=config.get_bool("LOGGING", "log_browser", False))
        tk.Checkbutton(
            f_cats, text="[СИСТЕМА] События браузера Supermium (CDP)",
            variable=self.var_log_browser, bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(-1)
        ).pack(anchor="w")

        # Нижние кнопки
        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X)
        tk.Button(btn_bar, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_bar, text=t("btn_save", "Сохранить"), font=theme.font(0, "bold"), relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=16, command=self._save).pack(side=tk.RIGHT)

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
        phrase = t("settings_tts_test_phrase", "Тестовая проверка скорости нейро-озвучки.")
        tts_engine.speak_text(phrase, speed=self.scale_speed.get(), lang=i18n.current_lang)

    def _save(self):
        config.set_value("GENERAL", "AutoLaunchQTranslate", "1" if self.var_autolaunch.get() else "0")
        config.set_value("GENERAL", "StartMinimized", "1" if self.var_minimized.get() else "0")
        config.set_value("GENERAL", "ServerPort", self.e_port.get().strip() or "8080")

        # Сохранение темы
        chosen_theme_display = self.combo_theme.get()
        chosen_theme_key = next((k for k, name in self.theme_options if name == chosen_theme_display), "light")
        theme.set_theme(chosen_theme_key)

        # Сохранение масштаба шрифта
        chosen_font_display = self.combo_font.get()
        chosen_font_scale = next((k for k, name in self.font_options if name == chosen_font_display), "normal")
        theme.set_font_size(chosen_font_scale)

        # Сохранение языка интерфейса
        chosen_lang_display = self.combo_lang.get()
        chosen_lang_code = next((k for k, name in self.lang_options if name == chosen_lang_display), "auto")
        i18n.set_language(chosen_lang_code)

        config.set_value("HOTKEYS", "OCR", self.e_hk_ocr.get().strip())
        config.set_value("HOTKEYS", "ToggleWindow", self.e_hk_win.get().strip())
        config.set_value("HOTKEYS", "TTS", self.e_hk_tts.get().strip())
        config.set_value("QTRANSLATE", "SummonHotkey", self.e_hk_qtr.get().strip() or "double_ctrl")

        ocr_engine.set_active_model(self.combo_ocr.get())
        config.set_value("TTS", "Speed", str(self.scale_speed.get()))

        # Сохранение параметров логирования
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

        messagebox.showinfo("OK", t("settings_saved_msg", "Настройки успешно сохранены!"), parent=self)
        self.destroy()