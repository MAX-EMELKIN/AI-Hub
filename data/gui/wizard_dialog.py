# -*- coding: utf-8 -*-
"""
Модуль: data/gui/wizard_dialog.py
Назначение: Мастер добавления сервиса из шаблона (AddServiceWizardDialog) с динамическим
            подтягиванием списка доступных провайдеров из data/core/templates/ (Boltch,
            OpenRouter, Cloudflare, OpenAI-совместимые API) и контекстной справкой.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import sys
import re
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.i18n import t
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import HelpPopup, attach_entry_context_menu
from data.core.service_generator import get_next_available_qt_id, get_available_providers, create_service_from_template
from data.core.logger import logger

WIZARD_HELP_FALLBACK = {
    "provider": (
        "ПОСТАВЩИК API\n\n"
        "Выберите платформу или агрегатор, через который будет работать модель:\n\n"
        "* Boltch.cloud (Free Pool):\n"
        "Бесплатные ротационные модели без карт и баланса (free:kimi-k2.6, free:deepseek-v4-pro и др.).\n\n"
        "* OpenRouter.ai (Free & Paid):\n"
        "Крупнейший агрегатор с бесплатными моделями (:free) и поддержкой SOCKS5.\n\n"
        "* Cloudflare Workers AI:\n"
        "Модели Cloudflare (ID всегда начинается с @cf/..).\n\n"
        "* OpenAI-совместимый API:\n"
        "Прямые официальные API (DeepSeek, Qwen DashScope, Groq, Mistral, локальные LM Studio/Ollama)."
    ),
    "name": (
        "НАЗВАНИЕ СЕРВИСА\n\n"
        "Человекопонятное имя для вас.\n\n"
        "* Сюда можно написать любое удобное название, например:\n"
        "«Kimi K2.6», «DeepSeek Pro», «Быстрый переводчик».\n\n"
        "* Это имя будет написано на кнопке в QTranslate и в шапке карточки модели в Хабе."
    ),
    "id": (
        "ПАПКА / ID СЕРВИСА\n\n"
        "Уникальное кодовое имя на английском языке.\n\n"
        "* Заполняется автоматически по названию сервиса.\n\n"
        "* Используется для имени папки на диске и системного роута.\n\n"
        "* Менять вручную необязательно."
    ),
    "model": (
        "ИДЕНТИФИКАТОР МОДЕЛИ (Model ID)\n\n"
        "Это точный системный адрес нейросети на сервере API.\n\n"
        "В ЧЕМ РАЗНИЦА:\n"
        "* Имя — это просто текст («Kimi K2.6»).\n"
        "* ID — это системное имя в API (например: «free:kimi-k2.6», «deepseek-flash», «qwen-turbo»).\n\n"
        "* Скопируйте строго без пробелов!"
    ),
    "qt_id": (
        "УНИКАЛЬНЫЙ ID В QTRANSLATE\n\n"
        "Системный номер кнопки в QTranslate.\n\n"
        "* Хаб автоматически находит следующий свободный номер (например: 711, 712).\n\n"
        "* Два сервиса не могут иметь одинаковый номер, иначе они будут конфликтовать!"
    )
}

class AddServiceWizardDialog(tk.Toplevel):
    def __init__(self, parent, on_created_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_created = on_created_callback
        self._active_help_popup = None

        bg_main = theme.get_color("bg_main")
        self.title(t("wizard_title", "Мастер добавления сервиса из шаблона"))
        self.geometry("600x560")
        self.minsize(560, 500)
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
        w, h = 600, 560
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _show_help(self, anchor_widget, help_key):
        if self._active_help_popup and self._active_help_popup.winfo_exists():
            self._active_help_popup.destroy()

        text = t(f"wizard_help_{help_key}", WIZARD_HELP_FALLBACK.get(help_key, ""))
        if text:
            self._active_help_popup = HelpPopup(anchor_widget, text)

    def _create_help_btn(self, parent, help_key):
        btn = tk.Label(
            parent, text="?", font=theme.font(-1, "bold"),
            fg=theme.get_color("help_btn_fg"), bg=theme.get_color("help_btn_bg"),
            relief=tk.FLAT, bd=0, padx=4, pady=0, cursor="hand2"
        )
        btn.bind("<Button-1>", lambda e, k=help_key, w=btn: self._show_help(w, k))
        return btn

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")
        border = theme.get_color("bg_card_border")

        pad = tk.Frame(self, bg=bg_main, padx=16, pady=14)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad, text=t("wizard_header", "Создание нового сервиса перевода"),
            font=theme.font(2, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(anchor="w", pady=(0, 10))

        form_frame = tk.Frame(
            pad, bg=bg_card, padx=12, pady=12, relief=tk.SOLID, bd=1,
            highlightbackground=border, highlightthickness=1
        )
        form_frame.pack(fill=tk.X, pady=(0, 10))

        # 1. Поставщик API (динамически из data/core/templates/)
        self.providers_info = get_available_providers()
        self.prov_names = [name for _, name, _ in self.providers_info]
        self.prov_map = {name: (key, def_m) for key, name, def_m in self.providers_info}

        r1 = tk.Frame(form_frame, bg=bg_card)
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text=t("wizard_provider", "Поставщик API:"), font=theme.font(0, "bold"), fg=fg_pri, width=17, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r1, "provider").pack(side=tk.LEFT, padx=(0, 6))
        
        self.combo_prov = ttk.Combobox(r1, values=self.prov_names, state="readonly", width=28)
        if self.prov_names:
            self.combo_prov.set(self.prov_names[0])
        self.combo_prov.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo_prov.bind("<<ComboboxSelected>>", self._on_provider_change)

        # 2. Название сервиса
        r2 = tk.Frame(form_frame, bg=bg_card)
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text=t("wizard_name", "Название сервиса:"), font=theme.font(0, "bold"), fg=fg_pri, width=17, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r2, "name").pack(side=tk.LEFT, padx=(0, 6))
        self.e_name = tk.Entry(r2, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_name.insert(0, "My New AI Service")
        self.e_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.e_name.bind("<KeyRelease>", self._auto_fill_id)
        attach_entry_context_menu(self.e_name)

        # 3. ID папки
        r3 = tk.Frame(form_frame, bg=bg_card)
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text=t("wizard_id", "Папка / ID сервиса:"), font=theme.font(0, "bold"), fg=fg_pri, width=17, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r3, "id").pack(side=tk.LEFT, padx=(0, 6))
        self.e_id = tk.Entry(r3, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_id.insert(0, "my_new_ai_service")
        self.e_id.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_id)

        # 4. Идентификатор модели
        r4 = tk.Frame(form_frame, bg=bg_card)
        r4.pack(fill=tk.X, pady=4)
        tk.Label(r4, text=t("wizard_model", "Идентификатор модели:"), font=theme.font(0, "bold"), fg=fg_pri, width=17, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r4, "model").pack(side=tk.LEFT, padx=(0, 6))
        self.e_model = tk.Entry(r4, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        initial_def_model = self.providers_info[0][2] if self.providers_info else "deepseek-flash"
        self.e_model.insert(0, initial_def_model)
        self.e_model.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_model)

        # 5. Уникальный ID в QTranslate
        r5 = tk.Frame(form_frame, bg=bg_card)
        r5.pack(fill=tk.X, pady=4)
        tk.Label(r5, text=t("wizard_qtid", "ID в QTranslate:"), font=theme.font(0, "bold"), fg=fg_pri, width=17, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r5, "qt_id").pack(side=tk.LEFT, padx=(0, 6))
        self.e_qtid = tk.Entry(r5, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=10)
        self.e_qtid.insert(0, str(get_next_available_qt_id()))
        self.e_qtid.pack(side=tk.LEFT)
        attach_entry_context_menu(self.e_qtid)

        info_box = tk.LabelFrame(
            pad, text=t("wizard_icon_box_title", "Памятка по иконкам сервиса"),
            font=theme.font(-1, "bold"), fg=fg_pri, bg=bg_card, padx=10, pady=8
        )
        info_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        default_info = (
            "Хаб создаст все нужные файлы и зарегистрирует сервис автоматически!\n\n"
            "Иконку можно добавить в любое время:\n"
            "* Для Хаба: положите файл Service.png в папку data/services/<id>/\n"
            "* Для QTranslate: положите файл Service.ico в папку Services/<Имя>/\n\n"
            "* Если иконки нет, в Хабе отобразится значок [AI], а в QTranslate — текст кнопки."
        )
        tk.Label(
            info_box, text=t("wizard_icon_box_text", default_info),
            font=theme.font(-1), justify="left", fg=theme.get_color("fg_secondary"), bg=bg_card
        ).pack(anchor="w")

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_bar, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_bar, text=t("wizard_btn_create", "Создать сервис"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=16, pady=4, command=self._on_create
        ).pack(side=tk.RIGHT)

    def _on_provider_change(self, event):
        chosen_display = self.combo_prov.get()
        if chosen_display in self.prov_map:
            _, def_model = self.prov_map[chosen_display]
            self.e_model.delete(0, tk.END)
            self.e_model.insert(0, def_model)

    def _auto_fill_id(self, event):
        name = self.e_name.get().strip()
        slug = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')
        slug = re.sub(r'_+', '_', slug)
        self.e_id.delete(0, tk.END)
        self.e_id.insert(0, slug)

    def _on_create(self):
        chosen_display = self.combo_prov.get()
        prov_key, _ = self.prov_map.get(chosen_display, ("openai_compatible", "deepseek-flash"))

        name = self.e_name.get().strip()
        s_id = self.e_id.get().strip()
        m_id = self.e_model.get().strip()
        qt_id_val = self.e_qtid.get().strip()

        if not name or not s_id or not m_id:
            messagebox.showwarning(
                t("btn_settings", "Внимание"),
                t("wizard_warn_fill", "Заполните все обязательные поля!"),
                parent=self
            )
            return

        try:
            ok, clean_id, js_path, py_path = create_service_from_template(
                provider=prov_key,
                name=name,
                service_id=s_id,
                model_id=m_id,
                qt_id=qt_id_val
            )

            logger.system(f"Мастер создания сервиса: создан сервис '{name}' (ID: {clean_id}, QT_ID: {qt_id_val})")

            if self.on_created:
                self.on_created()

            msg = (
                f"Сервис '{name}' успешно создан и активирован!\n\n"
                f"* Python плагин: {py_path}\n"
                f"* QTranslate скрипт: {js_path}\n"
                f"* Уникальный ID: {qt_id_val}\n\n"
                f"Карточка модели уже добавлена в главное окно Хаба!"
            )
            messagebox.showinfo("OK", msg, parent=self)
            self.destroy()

        except Exception as e:
            logger.system(f"Мастер создания сервиса Ошибка: {e}")
            messagebox.showerror(
                t("status_error", "Ошибка"),
                f"Не удалось создать сервис: {e}",
                parent=self
            )