# -*- coding: utf-8 -*-
"""
Модуль: data/gui/service_card.py
Назначение: Графическая карточка сервиса с мультиязычным интерфейсом, параметрами,
            поддержкой мульти-модельного режима Gemini (выбор модели, размышлений, пинг,
            поиск в Google / Grounding и чтение сайтов по ссылкам),
            агентным поиском в сети для моделей OrcaRouter, адаптацией списков,
            чистыми надписями Windows 7 (без квадратиков) и логированием действий.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import json
import threading
import tkinter as tk
from tkinter import ttk

from data.core.config_manager import config
from data.core.api_config import api_config
from data.core.i18n import t
from data.presets.preset_manager import preset_manager
from data.gui.theme_manager import theme
from data.gui.dialogs import ToolTip
from data.core.logger import logger

GEMINI_ALLOWED_MODELS = [
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

GEMINI_THINKING_MODES = [
    "Низкий (LOW / Быстрый)",
    "Средний (MEDIUM)",
    "Высокий (HIGH)",
    "Авто (По умолчанию)"
]

HELP_TEXTS = {
    "temp": (
        "ТЕМПЕРАТУРА (temperature)\n\n"
        "Отвечает за строгость и точность перевода.\n\n"
        "* Меньше (0.0 - 0.2): перевод максимально строгий, точный и буквальный. "
        "Идеально для интерфейсов, кода и модов.\n"
        "* Больше (0.7 - 1.0): модель активнее подбирает синонимы, но может менять детали."
    ),
    "topp": (
        "ВЫБОРКА СЛОВ (top_p)\n\n"
        "Ограничивает пул слов для генерации.\n\n"
        "* Меньше (0.1 - 0.3): отсекает сомнительные варианты, оставляя самые подходящие.\n"
        "* Больше (0.8 - 1.0): разрешает редкие слова и разнообразные обороты."
    ),
    "tokens": (
        "МАКСИМУМ ТОКЕНОВ (max_tokens)\n\n"
        "Максимальная длина ответа модели (1 токен ~ 3-4 символа).\n\n"
        "Значения 2048-4096 гарантируют, что длинный абзац или диалог не оборвется на полуслове."
    ),
    "thinking": (
        "РАССУЖДЕНИЯ (Chain of Thought)\n\n"
        "Внутренний мыслительный процесс нейросети перед генерацией ответа.\n\n"
        "* Выключено (рекомендуется): мгновенный перевод (1-2 сек).\n"
        "* Включено: полезно для сложных логических конструкций, но увеличивает время ответа."
    ),
    "glossary": (
        "УМНЫЙ ГЛОССАРИЙ\n\n"
        "Автоматическая подстановка терминов из словаря.\n\n"
        "Нейросеть берет перевод из словаря и сама согласует падеж, род, число и окончания "
        "под грамматику всего предложения."
    ),
    "gemini_search": (
        "ПОИСК В СЕТИ И ЧТЕНИЕ ССЫЛОК (Agentic Tool Calling)\n\n"
        "Позволяет модели выходить в интернет во время перевода и генерации:\n\n"
        "* Поиск фактов: модель сама формулирует точный запрос и ищет свежую информацию, имена и факты через DuckDuckGo.\n\n"
        "* Чтение по ссылкам (URL Context): если в переводимом тексте или пресете указана веб-ссылка, "
        "скрипт извлечет текст страницы и передаст его в контекст модели для точного перевода.\n\n"
        "* Выключено: перевод выполняется на базе внутренних знаний модели.\n"
        "* Включено: для фактчекинга, поиска актуального лора и перевода по веб-ссылкам."
    )
}

class HelpPopup(tk.Toplevel):
    def __init__(self, anchor_widget, text):
        super().__init__(anchor_widget)
        self.wm_overrideredirect(True)
        bg = theme.get_color("popup_bg")
        border = theme.get_color("popup_border")
        fg = theme.get_color("popup_fg")
        hint_fg = theme.get_color("popup_hint")

        self.configure(bg=bg)
        frame = tk.Frame(
            self, bg=bg, padx=10, pady=8, relief=tk.SOLID, bd=1,
            highlightbackground=border, highlightthickness=1
        )
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(frame, text=text, justify=tk.LEFT, bg=bg, fg=fg, font=theme.font(-1), wraplength=260)
        lbl.pack(anchor="w")

        hint_text = t("help_close_hint", "* Кликните в любом месте, чтобы закрыть")
        hint = tk.Label(frame, text=hint_text, font=theme.font(-2, "italic"), fg=hint_fg, bg=bg)
        hint.pack(anchor="w", pady=(6, 0))

        self.update_idletasks()
        btn_x = anchor_widget.winfo_rootx()
        btn_y = anchor_widget.winfo_rooty()
        btn_h = anchor_widget.winfo_height()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        pos_x = max(10, min(btn_x - 30, screen_w - w - 20))
        pos_y = btn_y + btn_h + 4
        if pos_y + h > screen_h - 40:
            pos_y = btn_y - h - 4

        self.wm_geometry(f"+{pos_x}+{pos_y}")

        self.bind("<Button-1>", lambda e: self.destroy())
        lbl.bind("<Button-1>", lambda e: self.destroy())
        frame.bind("<Button-1>", lambda e: self.destroy())
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

class ServiceCard(tk.Frame):
    def __init__(self, parent, service, on_reorder_step_callback=None,
                 on_drag_end_callback=None, on_settings_callback=None,
                 on_delete_callback=None, on_edit_preset_callback=None,
                 on_add_preset_callback=None, **kwargs):

        bg_card = theme.get_color("bg_card")
        bd_color = theme.get_color("bg_card_border")
        super().__init__(
            parent, relief=tk.SOLID, bd=1, padx=6, pady=4, bg=bg_card,
            highlightbackground=bd_color, highlightthickness=1, **kwargs
        )

        self.service = service
        self.service_id = service.service_id
        self.on_reorder_step = on_reorder_step_callback
        self.on_drag_end = on_drag_end_callback
        self.on_settings_callback = on_settings_callback
        self.on_delete_callback = on_delete_callback
        self.on_edit_preset_callback = on_edit_preset_callback
        self.on_add_preset_callback = on_add_preset_callback

        self.icon_photo = None
        self._preset_buttons = {}
        self.status_tooltip = None
        self._active_help_popup = None
        self._is_dragging = False
        self._drag_start_y = 0

        self._build_ui()
        self.refresh_status()
        self.refresh_presets()

    def _load_icon_image(self, icon_path, target_size=18):
        if not icon_path or not os.path.exists(icon_path):
            return None
        try:
            img = tk.PhotoImage(file=icon_path)
            w = img.width()
            if w > target_size:
                scale = max(1, round(w / target_size))
                img = img.subsample(scale, scale)
            return img
        except Exception:
            return None

    def _show_help(self, anchor_widget, help_key):
        if self._active_help_popup and self._active_help_popup.winfo_exists():
            self._active_help_popup.destroy()

        text = t(f"help_{help_key}", HELP_TEXTS.get(help_key, ""))
        if text:
            self._active_help_popup = HelpPopup(anchor_widget, text)

    def _create_help_btn(self, parent, help_key):
        btn = tk.Label(
            parent, text="?", font=theme.font(-2, "bold"),
            fg=theme.get_color("help_btn_fg"), bg=theme.get_color("help_btn_bg"),
            relief=tk.FLAT, bd=0, padx=3, pady=0, cursor="hand2"
        )
        btn.bind("<Button-1>", lambda e, k=help_key, w=btn: self._show_help(w, k))
        return btn

    def _build_ui(self):
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        param_fg = theme.get_color("preset_btn_fg")
        param_font = theme.font(-1, "normal")

        self.top_frame = tk.Frame(self, bg=bg_card)
        self.top_frame.pack(fill=tk.X, expand=True)

        icon_path = self.service.get_icon_path()
        self.icon_photo = self._load_icon_image(icon_path, target_size=18)
        if self.icon_photo:
            self.icon_lbl = tk.Label(self.top_frame, image=self.icon_photo, bg=bg_card)
            self.icon_lbl.image = self.icon_photo
            self.icon_lbl.pack(side=tk.LEFT, padx=(1, 3))
        else:
            self.icon_lbl = tk.Label(self.top_frame, text="[AI]", font=theme.font(0, "bold"), fg=theme.get_color("accent"), bg=bg_card)
            self.icon_lbl.pack(side=tk.LEFT, padx=(1, 3))

        self.title_lbl = tk.Label(
            self.top_frame, text=self.service.name, font=theme.font(1, "bold"),
            fg=fg_pri, bg=bg_card, cursor="sb_v_double_arrow"
        )
        self.title_lbl.pack(side=tk.LEFT, padx=(2, 4))
        ToolTip(self.title_lbl, "Зажмите левой кнопкой мыши для перемещения карточки выше / ниже")

        self.status_lbl = tk.Label(
            self.top_frame, text="...", font=theme.font(0, "bold"),
            bg=bg_card, cursor="question_arrow"
        )
        self.status_lbl.pack(side=tk.LEFT, padx=(0, 4))
        self.status_tooltip = ToolTip(self.status_lbl, "")

        self.btn_settings = tk.Button(
            self.top_frame, text="⚙", font=theme.font(1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, activebackground=theme.get_color("btn_hover"),
            cursor="hand2", width=2, padx=0, pady=0, command=self._on_settings_click
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(2, 0))
        ToolTip(self.btn_settings, t("tip_service_settings", "Параметры сервиса"))

        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        # Режим для семейства Gemini
        if self.service_id == "gemini_family":
            gemini_bar = tk.Frame(self.top_frame, bg=bg_card)
            gemini_bar.pack(side=tk.RIGHT, padx=(0, 4))

            tk.Label(gemini_bar, text="Модель:", font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
            self.combo_model = ttk.Combobox(gemini_bar, values=GEMINI_ALLOWED_MODELS, state="readonly", width=22, font=param_font)
            cur_model = self.service.get_config_val("model", GEMINI_ALLOWED_MODELS[0])
            self.combo_model.set(cur_model if cur_model in GEMINI_ALLOWED_MODELS else GEMINI_ALLOWED_MODELS[0])
            self.combo_model.pack(side=tk.LEFT, padx=(0, 2))
            self.combo_model.bind("<<ComboboxSelected>>", self._on_gemini_model_changed)

            self.btn_ping = tk.Button(
                gemini_bar, text="Пинг", font=theme.font(-2, "bold"), relief=tk.FLAT,
                bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
                activebackground=theme.get_color("btn_hover"), cursor="hand2", padx=4, pady=0,
                command=self._on_gemini_ping_click
            )
            self.btn_ping.pack(side=tk.LEFT, padx=(0, 4))
            ToolTip(self.btn_ping, "Проверить доступность и задержку выбранной модели Gemini")

            tk.Label(gemini_bar, text="Размышления:", font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
            self.combo_thinking = ttk.Combobox(gemini_bar, values=GEMINI_THINKING_MODES, state="readonly", width=22, font=param_font)

            saved_thinking = self.service.get_config_val("thinking_mode", GEMINI_THINKING_MODES[0])
            matched_thinking = GEMINI_THINKING_MODES[0]
            for m in GEMINI_THINKING_MODES:
                if ("Низкий" in saved_thinking and "Низкий" in m) or \
                   ("Средний" in saved_thinking and "Средний" in m) or \
                   ("Высокий" in saved_thinking and "Высокий" in m) or \
                   ("Авто" in saved_thinking and "Авто" in m):
                    matched_thinking = m
                    break

            self.combo_thinking.set(matched_thinking)
            self.combo_thinking.pack(side=tk.LEFT, padx=(0, 3))
            self.combo_thinking.bind("<<ComboboxSelected>>", self._on_gemini_thinking_changed)

            tk.Label(gemini_bar, text="Поиск:", font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
            self._create_help_btn(gemini_bar, "gemini_search").pack(side=tk.LEFT, padx=(0, 1))
            self.var_web_search = tk.BooleanVar(value=(self.service.get_config_val("enable_web_search", "0") in ("1", "true", "yes")))
            chk_search = tk.Checkbutton(
                gemini_bar, variable=self.var_web_search, bg=bg_card, activebackground=bg_card,
                command=self._on_web_search_toggle, padx=0, pady=0
            )
            chk_search.pack(side=tk.LEFT, padx=(0, 3))

            lbl_gloss = t("param_glossary", "Словарь")
            tk.Label(gemini_bar, text=lbl_gloss, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
            self._create_help_btn(gemini_bar, "glossary").pack(side=tk.LEFT, padx=(0, 1))
            self.var_glossary = tk.BooleanVar(value=(self.service.get_config_val("enable_glossary", "1") in ("1", "true", "yes")))
            chk_glossary = tk.Checkbutton(
                gemini_bar, variable=self.var_glossary, bg=bg_card, activebackground=bg_card,
                command=self._on_glossary_toggle, padx=0, pady=0
            )
            chk_glossary.pack(side=tk.LEFT, padx=(0, 1))

        # Режим для моделей OrcaRouter и других LLM
        else:
            has_params = getattr(self.service, "supports_hyperparameters", True)
            has_glossary = getattr(self.service, "supports_glossary", True) and getattr(self.service, "is_ai_service", True)
            supports_search = self.service_id in ("deepseek_flash", "tencent_hy3", "z_ai_glm_5_3") or "orca" in self.service_id

            if has_params or has_glossary or supports_search:
                params_bar = tk.Frame(self.top_frame, bg=bg_card)
                params_bar.pack(side=tk.RIGHT, padx=(0, 4))

                if has_params:
                    lbl_temp = t("param_temp", "temperature")
                    tk.Label(params_bar, text=lbl_temp, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(3, 1))
                    self._create_help_btn(params_bar, "temp").pack(side=tk.LEFT, padx=(0, 2))
                    self.e_temp = tk.Entry(params_bar, font=param_font, width=4, justify="center", bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
                    self.e_temp.insert(0, str(self.service.get_config_val("temperature", "0.2")))
                    self.e_temp.pack(side=tk.LEFT, padx=(0, 4))
                    self.e_temp.bind("<FocusOut>", lambda e: self._save_param("temperature", self.e_temp.get()))
                    self.e_temp.bind("<Return>", lambda e: self._save_param("temperature", self.e_temp.get()))

                    lbl_topp = t("param_topp", "top_p")
                    tk.Label(params_bar, text=lbl_topp, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
                    self._create_help_btn(params_bar, "topp").pack(side=tk.LEFT, padx=(0, 2))
                    self.e_topp = tk.Entry(params_bar, font=param_font, width=4, justify="center", bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
                    self.e_topp.insert(0, str(self.service.get_config_val("top_p", "0.2")))
                    self.e_topp.pack(side=tk.LEFT, padx=(0, 4))
                    self.e_topp.bind("<FocusOut>", lambda e: self._save_param("top_p", self.e_topp.get()))
                    self.e_topp.bind("<Return>", lambda e: self._save_param("top_p", self.e_topp.get()))

                    lbl_tokens = t("param_tokens", "max_tokens")
                    tk.Label(params_bar, text=lbl_tokens, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
                    self._create_help_btn(params_bar, "tokens").pack(side=tk.LEFT, padx=(0, 2))
                    self.e_tokens = tk.Entry(params_bar, font=param_font, width=5, justify="center", bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
                    self.e_tokens.insert(0, str(self.service.get_config_val("max_tokens", "2048")))
                    self.e_tokens.pack(side=tk.LEFT, padx=(0, 4))
                    self.e_tokens.bind("<FocusOut>", lambda e: self._save_param("max_tokens", self.e_tokens.get()))
                    self.e_tokens.bind("<Return>", lambda e: self._save_param("max_tokens", self.e_tokens.get()))

                    lbl_think = t("param_thinking", "Рассуждения")
                    tk.Label(params_bar, text=lbl_think, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
                    self._create_help_btn(params_bar, "thinking").pack(side=tk.LEFT, padx=(0, 1))
                    self.var_thinking = tk.BooleanVar(value=(self.service.get_config_val("enable_thinking", "0") in ("1", "true", "yes")))
                    chk_thinking = tk.Checkbutton(
                        params_bar, variable=self.var_thinking, bg=bg_card, activebackground=bg_card,
                        command=self._on_thinking_toggle, padx=0, pady=0
                    )
                    chk_thinking.pack(side=tk.LEFT, padx=(0, 3))

                if supports_search:
                    tk.Label(params_bar, text="Поиск:", font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
                    self._create_help_btn(params_bar, "gemini_search").pack(side=tk.LEFT, padx=(0, 1))
                    self.var_web_search = tk.BooleanVar(value=(self.service.get_config_val("enable_web_search", "0") in ("1", "true", "yes")))
                    chk_search = tk.Checkbutton(
                        params_bar, variable=self.var_web_search, bg=bg_card, activebackground=bg_card,
                        command=self._on_web_search_toggle, padx=0, pady=0
                    )
                    chk_search.pack(side=tk.LEFT, padx=(0, 3))

                if has_glossary:
                    lbl_gloss = t("param_glossary", "Словарь")
                    tk.Label(params_bar, text=lbl_gloss, font=param_font, fg=param_fg, bg=bg_card).pack(side=tk.LEFT, padx=(2, 1))
                    self._create_help_btn(params_bar, "glossary").pack(side=tk.LEFT, padx=(0, 1))
                    self.var_glossary = tk.BooleanVar(value=(self.service.get_config_val("enable_glossary", "1") in ("1", "true", "yes")))
                    chk_glossary = tk.Checkbutton(
                        params_bar, variable=self.var_glossary, bg=bg_card, activebackground=bg_card,
                        command=self._on_glossary_toggle, padx=0, pady=0
                    )
                    chk_glossary.pack(side=tk.LEFT, padx=(0, 1))

        self.bottom_frame = tk.Frame(self, bg=bg_card)
        self.bottom_frame.pack(fill=tk.X, expand=True, pady=(4, 0))

        self.btn_delete = tk.Button(
            self.bottom_frame, text="X", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg="#ef4444", activebackground="#fee2e2", activeforeground="#b91c1c",
            cursor="hand2", width=2, padx=0, pady=0, command=self._on_delete_click
        )
        self.btn_delete.pack(side=tk.RIGHT, padx=(2, 0))
        ToolTip(self.btn_delete, t("tip_service_delete", "Удалить сервис и все его файлы"))

        self.presets_container = tk.Frame(self.bottom_frame, bg=bg_card)
        self.presets_container.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for drag_target in [self.title_lbl, self.icon_lbl]:
            drag_target.bind("<ButtonPress-1>", self._on_drag_start)
            drag_target.bind("<B1-Motion>", self._on_drag_motion)
            drag_target.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_gemini_model_changed(self, event=None):
        new_model = self.combo_model.get().strip()
        if new_model:
            self.service.set_config_val("model", new_model)
            logger.system(f"Сервис {self.service.name}: установлена модель '{new_model}'")

    def _on_gemini_thinking_changed(self, event=None):
        new_mode = self.combo_thinking.get().strip()
        if new_mode:
            self.service.set_config_val("thinking_mode", new_mode)
            logger.system(f"Сервис {self.service.name}: режим размышлений '{new_mode}'")

    def _on_web_search_toggle(self):
        val = "1" if self.var_web_search.get() else "0"
        self.service.set_config_val("enable_web_search", val)
        logger.system(f"Сервис {self.service.name}: веб-поиск {'включен' if val == '1' else 'выключен'}")

    def _on_gemini_ping_click(self):
        cur_model = self.service.get_config_val("model", GEMINI_ALLOWED_MODELS[0])
        self.btn_ping.config(state="disabled", text="...")

        def _worker():
            ok, msg, elapsed = self.service.ping_model(cur_model)
            def _ui():
                self.btn_ping.config(state="normal", text="Пинг")
                if ok:
                    self.status_lbl.config(text=f"* {msg}", fg=theme.get_color("status_ready"))
                else:
                    self.status_lbl.config(text=f"* {msg}", fg=theme.get_color("status_error"))
                if self.status_tooltip:
                    self.status_tooltip.set_text(f"Пинг модели {cur_model}: {msg}")
            self.after(0, _ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_drag_start(self, event):
        self._is_dragging = True
        self._drag_start_y = event.y_root
        accent_color = theme.get_color("accent")
        self.configure(relief=tk.SOLID, bd=2, highlightbackground=accent_color, highlightthickness=2)

    def _on_drag_motion(self, event):
        if not self._is_dragging:
            return
        delta_y = event.y_root - self._drag_start_y
        if abs(delta_y) > 35:
            direction = -1 if delta_y < 0 else 1
            if self.on_reorder_step:
                swapped = self.on_reorder_step(self.service_id, direction)
                if swapped:
                    self._drag_start_y = event.y_root

    def _on_drag_release(self, event):
        if self._is_dragging:
            self._is_dragging = False
            bd_color = theme.get_color("bg_card_border")
            self.configure(relief=tk.SOLID, bd=1, highlightbackground=bd_color, highlightthickness=1)
            if self.on_drag_end:
                self.on_drag_end(self.service_id)

    def _save_param(self, key, value):
        val = str(value).strip()
        if val:
            self.service.set_config_val(key, val)
            logger.system(f"Сервис {self.service.name}: параметр '{key}' изменен на '{val}'")

    def _on_thinking_toggle(self):
        val = "1" if self.var_thinking.get() else "0"
        self.service.set_config_val("enable_thinking", val)
        logger.system(f"Сервис {self.service.name}: рассуждения {'включены' if val == '1' else 'выключены'}")

    def _on_glossary_toggle(self):
        val = "1" if self.var_glossary.get() else "0"
        self.service.set_config_val("enable_glossary", val)
        logger.system(f"Сервис {self.service.name}: глоссарий {'включен' if val == '1' else 'выключен'}")

    def _on_delete_click(self):
        if self.on_delete_callback:
            self.on_delete_callback(self.service)

    def refresh_status(self):
        ok, reason = self.service.is_ready()
        if ok:
            self.status_lbl.config(text=f"* {t('status_ready', 'Готов')}", fg=theme.get_color("status_ready"))
        else:
            self.status_lbl.config(text=f"* {t('status_not_ready', 'Не готов')}", fg=theme.get_color("status_error"))

        if self.status_tooltip:
            self.status_tooltip.set_text(reason)

    def refresh_presets(self):
        for widget in self.presets_container.winfo_children():
            widget.destroy()
        self._preset_buttons.clear()

        available_presets = preset_manager.get_presets_for_service(self.service_id)
        active_preset = config.get_active_preset(self.service_id)

        for name in available_presets:
            is_active = (name == active_preset)
            btn_text = f"v {name}" if is_active else name
            bg_color = theme.get_color("preset_btn_active_bg") if is_active else theme.get_color("preset_btn_bg")
            fg_color = theme.get_color("preset_btn_active_fg") if is_active else theme.get_color("preset_btn_fg")

            btn = tk.Button(
                self.presets_container, text=btn_text, font=theme.font(-1, "bold" if is_active else "normal"),
                bg=bg_color, fg=fg_color, activebackground=theme.get_color("accent_hover"), activeforeground="#ffffff",
                relief=tk.FLAT, bd=0, padx=6, pady=2, cursor="hand2",
                command=lambda p=name: self._on_preset_select(p)
            )
            btn.pack(side=tk.LEFT, padx=(0, 3))
            ToolTip(btn, t("tip_select_preset", "Выбрать стиль: {name}", name=name))
            self._preset_buttons[name] = btn

        btn_add = tk.Button(
            self.presets_container, text="+", font=theme.font(0, "bold"),
            bg=theme.get_color("btn_bg"), fg=theme.get_color("status_ready"),
            activebackground=theme.get_color("btn_hover"),
            relief=tk.FLAT, bd=0, padx=6, pady=1, cursor="hand2",
            command=self._on_add_preset_click
        )
        btn_add.pack(side=tk.LEFT, padx=(3, 2))
        ToolTip(btn_add, t("tip_add_preset", "Создать новый пресет"))

        btn_edit = tk.Button(
            self.presets_container, text="*", font=theme.font(0, "bold"),
            bg=theme.get_color("btn_bg"), fg=theme.get_color("accent"),
            activebackground=theme.get_color("btn_hover"),
            relief=tk.FLAT, bd=0, padx=6, pady=1, cursor="hand2",
            command=self._on_edit_preset_click
        )
        btn_edit.pack(side=tk.LEFT, padx=2)
        ToolTip(btn_edit, t("tip_edit_preset", "Редактировать активный пресет"))

    def _on_preset_select(self, preset_name):
        config.set_active_preset(self.service_id, preset_name)
        logger.system(f"Сервис {self.service.name}: выбран пресет '{preset_name}'")
        self.refresh_presets()

    def _on_settings_click(self):
        if self.on_settings_callback:
            self.on_settings_callback(self.service, on_saved=self.refresh_status)

    def _on_add_preset_click(self):
        if self.on_add_preset_callback:
            self.on_add_preset_callback(self.service_id)

    def _on_edit_preset_click(self):
        if self.on_edit_preset_callback:
            active = config.get_active_preset(self.service_id)
            self.on_edit_preset_callback(self.service_id, active)