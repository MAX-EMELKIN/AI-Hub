# -*- coding: utf-8 -*-
# data/gui/main_window.py

import os, sys, time, threading
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.config_manager import config
from data.core.logger import logger
from data.core.i18n import t, i18n
from data.core.launcher import launch_qtranslate, restart_qtranslate, check_and_autostart_qtranslate, is_qtranslate_running
from data.gui.theme_manager import theme
from data.gui.service_card import ServiceCard
from data.gui.dialog_helpers import ToolTip
from data.gui.tool_windows import BatchWindow, GlossaryWindow, SettingsWindow, ChatWindow
from data.gui.wizard_dialog import AddServiceWizardDialog
from data.services.base_service import LOADED_SERVICES

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', '..'))

MT_SERVICE_IDS = {"bing", "yandex", "yandex_inl", "webtran", "freetranslations", "google_web"}

class SafeTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        self.widget.bind("<Enter>", self._schedule, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")
        self._after_id = None

    def _schedule(self, event=None):
        self._after_id = self.widget.after(400, self._show)

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")

        lbl = tk.Label(
            self.tip,
            text=self.text,
            justify=tk.LEFT,
            background="#1E232A",
            foreground="#E2E8F0",
            font=("Segoe UI", 9),
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6
        )
        lbl.pack()

    def _hide(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

class MainWindow(tk.Tk):
    def __init__(self, on_hide_to_tray_callback=None):
        super().__init__()
        self.on_hide_to_tray = on_hide_to_tray_callback

        self.title("QTranslate AI Hub v2.0 RC")
        self.minsize(560, 380)

        self.service_cards = {}
        self.ordered_service_ids = []
        self._geo_save_timer = None
        self.browser_icon_photo = None

        base_dir = get_base_dir()
        ico_candidates = [
            os.path.join(base_dir, "data", "gui", "AI_Hub.ico"),
            os.path.join(base_dir, "data", "AI_Hub.ico"),
            os.path.join(base_dir, "data", "gui", "icon.ico"),
            os.path.join(base_dir, "AI_Hub.ico")
        ]
        for ico_path in ico_candidates:
            if os.path.exists(ico_path):
                try:
                    self.iconbitmap(ico_path)
                    break
                except Exception:
                    pass

        self._apply_theme_colors()
        self._restore_geometry()
        self._build_ui()
        self._load_services_list()

        self.bind("<Configure>", self._on_window_configure)
        self.protocol("WM_DELETE_WINDOW", self._on_close_clicked)
        logger.system("Главное окно GUI инициализировано")

    def _apply_theme_colors(self):
        self.configure(bg=theme.get_color("bg_main"))
        theme.apply_ttk_theme(self)

    def _is_ai_service(self, service_obj):
        if not service_obj:
            return False
        s_id = getattr(service_obj, "service_id", "").lower().strip()
        if s_id in MT_SERVICE_IDS:
            return False
        if getattr(service_obj, "is_ai_service", True) is False:
            return False
        return True

    def _restore_geometry(self):
        x, y, w, h = config.get_window_geometry()
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        w = max(520, min(w, screen_w - 40))
        h = max(400, min(h, screen_h - 60))

        if 0 <= x <= screen_w - 100 and 0 <= y <= screen_h - 100:
            self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            cx = max(0, (screen_w - w) // 2)
            cy = max(0, (screen_h - h) // 2)
            self.geometry(f"{w}x{h}+{cx}+{cy}")

    def _on_window_configure(self, event):
        if event.widget == self:
            if self.state() == "normal" and self.winfo_viewable():
                if self._geo_save_timer:
                    self.after_cancel(self._geo_save_timer)
                self._geo_save_timer = self.after(400, self._save_current_geometry)

    def _save_current_geometry(self):
        try:
            if self.state() != "normal" or not self.winfo_viewable():
                return
            w, h = self.winfo_width(), self.winfo_height()
            x, y = self.winfo_x(), self.winfo_y()
            screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()

            if 450 <= w <= screen_w and 350 <= h <= screen_h and 0 <= x <= screen_w - 50 and 0 <= y <= screen_h - 50:
                config.save_window_geometry(x, y, w, h)
        except Exception:
            pass

    def _on_close_clicked(self):
        if self.state() == "normal" and self.winfo_viewable():
            self._save_current_geometry()
        if self.on_hide_to_tray:
            self.on_hide_to_tray()
        else:
            self.withdraw()

    def _extract_chrome_icon(self, target_size=18):
        base_dir = get_base_dir()
        png_candidates = [
            os.path.join(base_dir, "browser", "chrome.png"),
            os.path.join(base_dir, "browser", "engine", "chrome.png"),
            os.path.join(base_dir, "browser", "engine", "Supermium", "chrome.png")
        ]
        for p in png_candidates:
            if os.path.exists(p):
                try:
                    img = tk.PhotoImage(file=p)
                    if img.width() > target_size:
                        scale = max(1, round(img.width() / target_size))
                        img = img.subsample(scale, scale)
                    return img
                except Exception:
                    pass
        return None

    def _build_ui(self):
        for widget in self.winfo_children():
            widget.destroy()

        bg_main = theme.get_color("bg_main")
        bg_hdr = theme.get_color("bg_header")
        bg_tool = theme.get_color("bg_toolbar")
        fg_pri = theme.get_color("fg_primary")
        accent = theme.get_color("accent")
        btn_bg = theme.get_color("btn_bg")

        header_frame = tk.Frame(
            self, bg=bg_hdr, padx=12, pady=6, relief=tk.SOLID, bd=1,
            highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
        )
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame, text=t("services_title", "ПОДКЛЮЧЕННЫЕ НЕЙРОСЕТИ И ПЕРЕВОДЧИКИ"),
            font=theme.font(0, "bold"), fg=accent, bg=bg_hdr
        ).pack(side=tk.LEFT)

        self.btn_add = tk.Button(
            header_frame,
            text="Студия подключения и настройки сервисов",
            font=theme.font(-1, "bold"),
            relief=tk.FLAT,
            bg=theme.get_color("help_btn_bg"),
            fg=theme.get_color("help_btn_fg"),
            cursor="hand2",
            padx=10,
            pady=3,
            command=self._on_add_custom_service
        )
        self.btn_add.pack(side=tk.RIGHT)

        tooltip_text = (
            "Студия подключения и настройки сервисов:\n"
            "- Подключение моделей по шаблонам (OpenRouter, Qwen, DeepSeek, Gemini и др.)\n"
            "- Онлайн-запрос списка моделей, лимитов контекста и цен через API\n"
            "- Проверка методов сервера (OPTIONS) и ручная отправка запросов\n"
            "- Быстрый пинг и тестирование модели до создания файлов\n"
            "- Генерация кнопок QTranslate (service.js) и скриптов Хаба (service.py)"
        )
        SafeTooltip(self.btn_add, tooltip_text)

        list_outer = tk.Frame(self, bg=bg_main, padx=8, pady=6)
        list_outer.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(list_outer, bg=bg_main, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview)

        self.cards_frame = tk.Frame(self.canvas, bg=bg_main)
        self.cards_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        def _on_wheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        bottom_toolbar = tk.Frame(
            self, bg=bg_tool, padx=6, pady=4, relief=tk.SOLID, bd=1,
            highlightbackground=theme.get_color("bg_card_border"), highlightthickness=1
        )
        bottom_toolbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.browser_icon_photo = self._extract_chrome_icon(target_size=18)
        btn_browser_opts = {
            "text": " " + t("btn_browser", "Браузер"),
            "font": theme.font(-1, "bold"),
            "relief": tk.FLAT,
            "bg": btn_bg,
            "fg": fg_pri,
            "cursor": "hand2",
            "padx": 6,
            "pady": 2,
            "command": self._on_open_browser_click
        }
        if self.browser_icon_photo:
            btn_browser_opts["image"] = self.browser_icon_photo
            btn_browser_opts["compound"] = tk.LEFT

        self.btn_browser = tk.Button(bottom_toolbar, **btn_browser_opts)
        if self.browser_icon_photo:
            self.btn_browser.image = self.browser_icon_photo
        self.btn_browser.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_browser, t("tip_browser", "Открыть окно браузера"))

        ocr_frame = tk.Frame(bottom_toolbar, bg=bg_tool)
        ocr_frame.pack(side=tk.LEFT, padx=2)

        btn_ocr = tk.Button(
            ocr_frame, text=t("btn_ocr", "Снимок OCR"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=btn_bg, fg=fg_pri, cursor="hand2", padx=6, pady=2,
            command=self._on_ocr_snip_click
        )
        btn_ocr.pack(side=tk.LEFT)
        ToolTip(btn_ocr, t("tip_ocr", "Сканирование текста с экрана с передачей в QTranslate."))

        btn_ocr_settings = tk.Button(
            ocr_frame, text="⚙", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, activebackground=theme.get_color("btn_hover"),
            cursor="hand2", padx=3, pady=2, command=self._on_ocr_settings_click
        )
        btn_ocr_settings.pack(side=tk.LEFT, padx=(1, 0))
        ToolTip(btn_ocr_settings, t("tip_ocr_settings", "Настройка OCR"))

        btn_chat = tk.Button(
            bottom_toolbar, text=t("btn_chat", "Чат с ИИ"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"),
            cursor="hand2", padx=6, pady=2, command=self._on_chat_click
        )
        btn_chat.pack(side=tk.LEFT, padx=(8, 2))
        ToolTip(btn_chat, t("tip_chat", "Свободное общение с ИИ-моделями (с учетом контекста и поиском)"))

        btn_dict = tk.Button(
            bottom_toolbar, text=t("btn_dict", "Словарь"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=btn_bg, fg=fg_pri, cursor="hand2", padx=6, pady=2,
            command=self._on_dict_click
        )
        btn_dict.pack(side=tk.LEFT, padx=2)
        ToolTip(btn_dict, t("tip_dict", "Словарь терминов и умный глоссарий"))

        btn_batch = tk.Button(
            bottom_toolbar, text=t("btn_batch", "Пакетный перевод"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=btn_bg, fg=fg_pri, cursor="hand2", padx=6, pady=2,
            command=self._on_batch_click
        )
        btn_batch.pack(side=tk.LEFT, padx=2)
        ToolTip(btn_batch, t("tip_batch", "Пакетный перевод файлов и модов"))

        btn_settings = tk.Button(
            bottom_toolbar, text=t("btn_settings", "Настройки"), font=theme.font(-1, "bold"),
            relief=tk.FLAT, bg=btn_bg, fg=fg_pri, cursor="hand2", padx=6, pady=2,
            command=self._on_global_settings_click
        )
        btn_settings.pack(side=tk.RIGHT, padx=2)
        ToolTip(btn_settings, t("tip_settings", "Настройки программы"))

    def _load_services_list(self):
        saved_order = config.get_service_order()
        ai_services = [s_id for s_id, s in LOADED_SERVICES.items() if self._is_ai_service(s)]

        final_order = [s_id for s_id in saved_order if s_id in ai_services]
        for s_id in ai_services:
            if s_id not in final_order:
                final_order.append(s_id)

        self.ordered_service_ids = final_order
        self._repack_cards_full()

    def _repack_cards_full(self):
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.service_cards.clear()

        for s_id in self.ordered_service_ids:
            service = LOADED_SERVICES.get(s_id)
            if not service or not self._is_ai_service(service):
                continue

            card = ServiceCard(
                self.cards_frame, service=service,
                on_reorder_step_callback=self._on_card_reorder_step,
                on_drag_end_callback=self._on_card_drag_end,
                on_settings_callback=self._open_service_settings,
                on_delete_callback=self._on_delete_service_click,
                on_edit_preset_callback=self._open_preset_editor,
                on_add_preset_callback=self._open_add_preset
            )
            card.pack(fill=tk.X, expand=True, pady=2)
            self.service_cards[s_id] = card

    def _on_card_reorder_step(self, service_id, direction):
        if service_id not in self.ordered_service_ids:
            return False
        idx = self.ordered_service_ids.index(service_id)
        new_idx = idx + direction

        if 0 <= new_idx < len(self.ordered_service_ids):
            self.ordered_service_ids[idx], self.ordered_service_ids[new_idx] = (
                self.ordered_service_ids[new_idx], self.ordered_service_ids[idx]
            )
            for s_id in self.ordered_service_ids:
                card = self.service_cards.get(s_id)
                if card and card.winfo_exists():
                    card.pack_forget()

            for s_id in self.ordered_service_ids:
                card = self.service_cards.get(s_id)
                if card and card.winfo_exists() and self._is_ai_service(card.service):
                    card.pack(fill=tk.X, expand=True, pady=2)
            return True
        return False

    def _on_card_drag_end(self, service_id):
        config.save_service_order(self.ordered_service_ids)
        logger.system(f"Главное окно: сохранен новый порядок сервисов: {', '.join(self.ordered_service_ids)}")

    def _on_delete_service_click(self, service):
        msg = t("confirm_delete_msg", f"Вы действительно хотите удалить сервис «{service.name}»?", name=service.name, id=service.service_id)
        if messagebox.askyesno(t("confirm_delete_title", "Подтверждение удаления"), msg, icon="warning", parent=self):
            delete_service_completely(service.service_id, service.name)
            logger.system(f"Главное окно: сервис {service.name} ({service.service_id}) удален пользователем")
            self._load_services_list()
            messagebox.showinfo(t("deleted_title", "Удалено"), t("deleted_msg", f"Сервис «{service.name}» удален.", name=service.name), parent=self)

    def reload_entire_gui(self):
        self._apply_theme_colors()
        self.title(t("app_title", "QTranslate AI Hub"))
        self._build_ui()
        self._load_services_list()
        logger.system("Главное окно: интерфейс полностью перезагружен")

    def _open_service_settings(self, service, on_saved=None):
        ServiceSettingsDialog(self, service, on_saved_callback=on_saved)

    def _open_preset_editor(self, service_id, preset_name):
        def _on_saved(name):
            if service_id in self.service_cards:
                self.service_cards[service_id].refresh_presets()
        PresetEditorDialog(self, service_id, preset_name=preset_name, is_new=False, on_saved_callback=_on_saved)

    def _open_add_preset(self, service_id):
        def _on_saved(name):
            if service_id in self.service_cards:
                self.service_cards[service_id].refresh_presets()
        PresetEditorDialog(self, service_id, preset_name="", is_new=True, on_saved_callback=_on_saved)

    def _on_add_custom_service(self):
        AddServiceWizardDialog(self, on_created_callback=self._load_services_list)

    def _on_open_browser_click(self):
        try:
            from data.core.cdp_client import browser_cdp
            browser_cdp.toggle_browser_window()
        except Exception as e:
            messagebox.showerror(t("status_error", "Ошибка"), str(e), parent=self)

    def _on_ocr_settings_click(self):
        OCRSettingsDialog(self)

    def _on_ocr_snip_click(self):
        self.withdraw()
        self.after(100, lambda: ocr_engine.snip_screen_interactive(self))

    def _on_chat_click(self):
        ChatWindow(self)

    def _on_dict_click(self):
        GlossaryWindow(self)

    def _on_batch_click(self):
        BatchWindow(self)

    def _on_global_settings_click(self):
        SettingsWindow(self, on_settings_updated=self.reload_entire_gui)