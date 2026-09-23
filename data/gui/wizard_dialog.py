# -*- coding: utf-8 -*-
# data/gui/wizard_dialog.py

import os, sys, threading, re
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.config_manager import config
from data.core.api_config import api_config
from data.core.service_generator import service_generator
from data.core.logger import logger
from data.core.i18n import t, i18n
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import ToolTip, HelpPopup, attach_entry_context_menu
from data.gui.code_editor_dialog import CodeEditorDialog, open_file_in_smart_editor
from data.gui.model_selector_dialog import ModelSelectorDialog

WIZARD_HELP_FALLBACK = {
    "openrouter": "OpenRouter: доступ к сотням моделей. Для бесплатных моделей используйте тег :free (например, google/gemma-4-31b-it:free). В РФ требует SOCKS5-прокси.",
    "dashscope": "Alibaba DashScope (Qwen): международный портал qwencloud.com. Модели qwen-turbo, qwen-plus, qwen-max, qwen3.8-flash. Выделяется 1 000 000 токенов на 90 дней бесплатно.",
    "gemini": "Google Gemini: модели gemini-2.5, gemini-3.7. Бессрочный бесплатный тариф в Google AI Studio. Поддерживается обход блокировок через DoH SmartDNS.",
    "cloudflare": "Cloudflare Workers AI: бесплатный ежедневный лимит нейронов. Модель @cf/openai/gpt-oss-120b. Требуются Account ID и API Token.",
    "deepseek": "DeepSeek Official: модели deepseek-chat и deepseek-reasoner. Требует положительный баланс на аккаунте.",
    "boltch": "Boltch Cloud: бесплатный пул моделей (free:deepseek-v4-flash, free:kimi-k2.6). Кулдаун между запросами 15-20 секунд.",
    "siliconflow": "SiliconFlow: международный агрегатор моделей DeepSeek и Qwen. Требует привязки ключа.",
    "cerebras": "Cerebras: сверхскоростной инференс моделей Llama 3 на специализированных процессорах CS-3.",
    "mistral": "Mistral AI: официальный европейский API Mistral, Codestral и Mixtral.",
    "pollinations": "Pollinations: бесплатный шлюз без обязательной регистрации для тестирования моделей.",
    "openai_compatible": "OpenAI-Compatible: подключение любых локальных (LM Studio, Ollama) или кастомных прокси-серверов."
}

FIELD_HELP = {
    "tmpl": "Выберите базовый шаблон провайдера. Шаблон автоматически заполнит рекомендованный эндпоинт, режим сети и параметры.",
    "name": "Понятное имя сервиса на кнопке в панели QTranslate и на карточке в AI Hub.",
    "id": "Имя папки в data/services/ и секции в models.ini. Заполняется автоматически латиницей без пробелов.",
    "model": "Идентификатор модели на сервере провайдера. Кнопка «Запрос» открывает список моделей с ценами и контекстом.",
    "endpoint": "Полный веб-адрес API (URL) для отправки запросов chat completions.",
    "account_id": "Идентификатор аккаунта (Account ID). Обязателен для Cloudflare. Для остальных оставляйте пустым.",
    "key": "Секретный токен доступа (API-ключ). Сохраняется локально и передается только целевому провайдеру.",
    "net": "Режим сети: direct (прямой), socks5 (через прокси для обхода блокировок), doh (встроенный SmartDNS).",
    "thinking": "Политика мыслей (<think>): вырезать рассуждения, сохранять в ответе или отключать в API.",
    "json_path": "Путь к тексту в JSON-ответе (по умолчанию choices.0.message.content).",
    "btn_id": "Числовой ID кнопки в клиенте QTranslate."
}

class AddServiceWizardDialog(tk.Toplevel):
    def __init__(self, parent, on_created_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_created_callback = on_created_callback
        self.created_service_id = None
        self.created_folder_name = None
        self._manual_id_edit = False

        theme.apply_ttk_theme(self)

        self.title("Студия подключения сервисов — QTranslate AI Hub")
        self.geometry("740x800")
        self.minsize(660, 680)
        self.configure(bg=theme.get_color("bg_main"))
        if parent:
            self.transient(parent)

        self._init_variables()
        self._load_templates()
        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 800
        ph = self.parent.winfo_height() if self.parent else 600
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 740, 800
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _init_variables(self):
        self.var_template_id = tk.StringVar()
        self.var_display_name = tk.StringVar()
        self.var_service_id = tk.StringVar()
        self.var_provider = tk.StringVar()
        self.var_endpoint = tk.StringVar()
        self.var_model = tk.StringVar()
        self.var_account_id = tk.StringVar()
        self.var_api_key = tk.StringVar()
        self.var_connection_mode = tk.StringVar(value="direct")
        self.var_proxy = tk.StringVar(value="213.165.38.49:1080")
        self.var_doh_preset = tk.StringVar(value="smartdns")
        self.var_thinking_policy = tk.StringVar(value="strip")
        self.var_json_path = tk.StringVar(value="choices.0.message.content")
        self.var_btn_id = tk.StringVar(value="716")
        self.var_status_msg = tk.StringVar(value="Готов к тестированию модели или созданию плагина.")

    def _load_templates(self):
        self.available_templates = service_generator.get_available_templates()
        self.templates_map = {t["id"]: t for t in self.available_templates}

    def _make_field_row(self, parent, label_text, help_key):
        row = tk.Frame(parent, bg=theme.get_color("bg_card"))
        row.pack(fill=tk.X, pady=2)
        tk.Label(
            row, text=label_text, font=theme.font(0),
            bg=theme.get_color("bg_card"), fg=theme.get_color("fg_primary"),
            width=22, anchor="w"
        ).pack(side=tk.LEFT)

        h_text = FIELD_HELP.get(help_key, "")
        btn_h = tk.Button(
            row, text="?", font=theme.font(-2, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=theme.get_color("accent"),
            cursor="hand2", width=2, padx=1, pady=0,
            command=lambda: HelpPopup(self, "Справка по полю", h_text)
        )
        btn_h.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(btn_h, h_text)
        return row

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        btn_bg = theme.get_color("btn_bg")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad, text="Студия подключения и настройки сервисов",
            font=theme.font(1, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(anchor="w", pady=(0, 6))

        form_box = tk.Frame(pad, bg=bg_card, padx=12, pady=8, relief=tk.SOLID, bd=1)
        form_box.pack(fill=tk.X, pady=(0, 6))

        # 1. Шаблон
        r_tmpl = self._make_field_row(form_box, "Провайдер / Шаблон:", "tmpl")
        tmpl_titles = [f"{t['name']} ({t['id']})" for t in self.available_templates]
        self.cb_templates = ttk.Combobox(r_tmpl, values=tmpl_titles, state="readonly", width=26)
        self.cb_templates.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.cb_templates.bind("<<ComboboxSelected>>", self._on_template_selected)

        btn_docs = tk.Button(
            r_tmpl, text="Документация API", font=theme.font(-2, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=6, pady=2, command=self._open_official_docs
        )
        btn_docs.pack(side=tk.LEFT, padx=(0, 4))
        ToolTip(btn_docs, "Открыть официальное руководство API провайдера в браузере")

        btn_ai_help = tk.Button(
            r_tmpl, text="Справка ИИ", font=theme.font(-2, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=theme.get_color("accent"), padx=6, pady=2, command=self._show_ai_docs_help
        )
        btn_ai_help.pack(side=tk.LEFT)
        ToolTip(btn_ai_help, "Найти документацию через встроенный поиск ИИ и показать выжимку")

        # 2. Название сервиса
        r_name = self._make_field_row(form_box, "Название сервиса:", "name")
        self.ent_name = tk.Entry(r_name, textvariable=self.var_display_name, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_name.bind("<KeyRelease>", self._on_display_name_typed)
        attach_entry_context_menu(self.ent_name)

        # 3. ID папки
        r_id = self._make_field_row(form_box, "ID папки / сервиса:", "id")
        self.ent_id = tk.Entry(r_id, textvariable=self.var_service_id, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_id.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_id.bind("<Key>", lambda e: setattr(self, "_manual_id_edit", True))
        attach_entry_context_menu(self.ent_id)

        # 4. Модель + Запрос
        r_model = self._make_field_row(form_box, "Идентификатор модели:", "model")
        self.ent_model = tk.Entry(r_model, textvariable=self.var_model, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_model.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        attach_entry_context_menu(self.ent_model)

        btn_select_model = tk.Button(
            r_model, text="Запрос", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=10, pady=1,
            command=self._open_model_selector
        )
        btn_select_model.pack(side=tk.RIGHT)
        ToolTip(btn_select_model, "Запросить список моделей с сервера через API, посмотреть лимиты контекста и цены")

        # 5. Эндпоинт
        r_end = self._make_field_row(form_box, "Эндпоинт (URL):", "endpoint")
        self.ent_endpoint = tk.Entry(r_end, textvariable=self.var_endpoint, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_endpoint.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.ent_endpoint)

        # 6. Account ID
        r_acc = self._make_field_row(form_box, "ID аккаунта (Account ID):", "account_id")
        self.ent_acc = tk.Entry(r_acc, textvariable=self.var_account_id, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_acc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.ent_acc)

        # 7. API Ключ (открытый ввод)
        r_key = self._make_field_row(form_box, "API Ключ провайдера:", "key")
        self.ent_key = tk.Entry(r_key, textvariable=self.var_api_key, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_key.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.ent_key)

        # 8. Режим сети
        r_net = self._make_field_row(form_box, "Режим сети:", "net")
        self.cb_net = ttk.Combobox(r_net, textvariable=self.var_connection_mode, values=("direct", "socks5", "doh"), state="readonly", width=16)
        self.cb_net.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(r_net, text="SOCKS5:", font=theme.font(-1), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.ent_proxy = tk.Entry(r_net, textvariable=self.var_proxy, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=22)
        self.ent_proxy.pack(side=tk.LEFT, padx=(4, 0))

        # 9. Размышления (Thinking)
        r_th = self._make_field_row(form_box, "Размышления (Thinking):", "thinking")
        self.cb_th = ttk.Combobox(r_th, textvariable=self.var_thinking_policy, values=("strip", "keep", "disable"), state="readonly")
        self.cb_th.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 10. Путь ответа и ID кнопки
        r_meta = tk.Frame(form_box, bg=bg_card)
        r_meta.pack(fill=tk.X, pady=(4, 2))

        tk.Label(r_meta, text="Путь ответа (JSON Path):", font=theme.font(-1), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.ent_json_path = tk.Entry(r_meta, textvariable=self.var_json_path, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=24)
        self.ent_json_path.pack(side=tk.LEFT, padx=(4, 10))

        tk.Label(r_meta, text="ID кнопки:", font=theme.font(-1), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.ent_btn_id = tk.Entry(r_meta, textvariable=self.var_btn_id, font=theme.font(-1, "bold"), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=8, justify="center")
        self.ent_btn_id.pack(side=tk.LEFT, padx=(4, 0))

        # Блок тестирования
        box_stand = tk.LabelFrame(pad, text=" Тестирование и проверка созданного сервиса ", font=theme.font(0, "bold"), bg=bg_card, fg=fg_pri, padx=10, pady=6)
        box_stand.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.lbl_status_test = tk.Label(box_stand, textvariable=self.var_status_msg, font=theme.font(-1, "bold"), bg=bg_card, fg=theme.get_color("status_ready"), anchor="w")
        self.lbl_status_test.pack(fill=tk.X, pady=(0, 2))

        text_container = tk.Frame(box_stand, bg=bg_card)
        text_container.pack(fill=tk.BOTH, expand=True, pady=(2, 6))

        scroll_res = ttk.Scrollbar(text_container, orient=tk.VERTICAL)
        self.txt_result = tk.Text(
            text_container, height=6, wrap=tk.WORD, font=("Consolas", 9),
            bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, yscrollcommand=scroll_res.set
        )
        scroll_res.config(command=self.txt_result.yview)
        scroll_res.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_result.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_entry_context_menu(self.txt_result)

        bar_stand = tk.Frame(box_stand, bg=bg_card)
        bar_stand.pack(fill=tk.X)

        self.btn_ping_fast = tk.Button(
            bar_stand, text="Быстрый пинг (Hello)", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=10, pady=2, command=lambda: self._run_test(quick=True)
        )
        self.btn_ping_fast.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.btn_ping_fast, "Проверить отклик API и валидность ключа ДО сохранения сервиса")

        self.btn_ping_full = tk.Button(
            bar_stand, text="Полный пинг (Сырой ответ)", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=10, pady=2, command=lambda: self._run_test(quick=False)
        )
        self.btn_ping_full.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.btn_ping_full, "Отправить тестовое предложение и отобразить полный сырой JSON с сервера")

        self.btn_copy_res = tk.Button(
            bar_stand, text="Копировать ответ", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, pady=2, command=self._copy_result_to_clipboard
        )
        self.btn_copy_res.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.btn_copy_res, "Скопировать содержимое окна ответа в буфер обмена")

        self.btn_open_py = tk.Button(
            bar_stand, text="Открыть service.py", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, pady=2, state=tk.DISABLED, command=self._open_py_file
        )
        self.btn_open_py.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_open_js = tk.Button(
            bar_stand, text="Открыть service.js", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, pady=2, state=tk.DISABLED, command=self._open_js_file
        )
        self.btn_open_js.pack(side=tk.LEFT)

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        tk.Button(
            btn_bar, text="Закрыть", font=theme.font(0), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=14, pady=4, command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_create = tk.Button(
            btn_bar, text="Создать сервис", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=18, pady=4,
            command=self._on_create
        )
        self.btn_create.pack(side=tk.RIGHT)

        if self.available_templates:
            self.cb_templates.current(0)
            self._on_template_selected()

    def _copy_result_to_clipboard(self):
        txt = self.txt_result.get("1.0", tk.END).strip()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)

    def _on_display_name_typed(self, event=None):
        if not self._manual_id_edit:
            txt = self.var_display_name.get()
            slug = service_generator.sanitize_id(txt)
            self.var_service_id.set(slug)

    def _on_template_selected(self, event=None):
        idx = self.cb_templates.current()
        if idx < 0 or idx >= len(self.available_templates):
            return
        tmpl = self.available_templates[idx]
        t_id = tmpl["id"]
        prov = tmpl["provider"]

        self.var_template_id.set(t_id)
        self.var_provider.set(prov)

        disp = tmpl.get("name", "")
        self.var_display_name.set(disp)
        if not self._manual_id_edit:
            self.var_service_id.set(service_generator.sanitize_id(disp))

        self.var_endpoint.set(tmpl.get("default_endpoint", ""))
        self.var_model.set(tmpl.get("default_model", ""))
        self.var_connection_mode.set(tmpl.get("default_connection_mode", "direct"))
        self.var_proxy.set(tmpl.get("default_proxy", "213.165.38.49:1080"))
        self.var_thinking_policy.set(tmpl.get("thinking_policy", "strip"))

        if "cloudflare" in t_id or "cloudflare" in prov:
            saved_aid = api_config.get_val("cloudflare", "account_id") or api_config.get_provider_val("cloudflare", "account_id")
            self.var_account_id.set(saved_aid if saved_aid else "b53d06890fe315cfac0a5e6c074f99b4")
            prov_key = api_config.get_val("cloudflare", "api_token") or api_config.get_provider_val("cloudflare", "api_token")
        else:
            self.var_account_id.set("")
            prov_key = api_config.get_provider_val(prov, "api_key", "")

        self.var_api_key.set(prov_key if prov_key else "")

    def _open_official_docs(self):
        tmpl_id = self.var_template_id.get().strip()
        url = service_generator.get_template_docs_url(tmpl_id)
        if url:
            try:
                os.startfile(url)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.shell32.ShellExecuteW(0, "open", url, None, None, 1)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось открыть ссылку:\n{e}", parent=self)
        else:
            messagebox.showinfo("Инфо", "Ссылка на документацию для этого шаблона не указана.", parent=self)

    def _show_ai_docs_help(self):
        tmpl_id = self.var_template_id.get().strip()
        prov_name = self.var_display_name.get().strip() or tmpl_id

        top = tk.Toplevel(self)
        top.title(f"Справка ИИ: {prov_name}")
        top.geometry("740x560")
        theme.apply_ttk_theme(top)
        top.configure(bg=theme.get_color("bg_main"))
        top.transient(self)

        pad = tk.Frame(top, bg=theme.get_color("bg_main"), padx=10, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        bar_top = tk.Frame(pad, bg=theme.get_color("bg_card"), padx=8, pady=6, relief=tk.SOLID, bd=1)
        bar_top.pack(fill=tk.X, pady=(0, 6))

        tk.Label(bar_top, text="Поисковик:", font=theme.font(-1, "bold"), bg=theme.get_color("bg_card"), fg=theme.get_color("fg_primary")).pack(side=tk.LEFT)

        engine_map = {
            "Google (Supermium)": "google",
            "DuckDuckGo": "duckduckgo",
            "Brave": "brave",
            "Tavily": "tavily",
            "Serper": "serper",
            "SearXNG": "searxng"
        }
        cb_eng = ttk.Combobox(bar_top, values=list(engine_map.keys()), state="readonly", width=18)
        cur_eng = config.get_str("SEARCH", "engine", "google").lower()
        cur_title = next((k for k, v in engine_map.items() if v == cur_eng), "Google (Supermium)")
        cb_eng.set(cur_title)
        cb_eng.pack(side=tk.LEFT, padx=4)

        user_lang = getattr(i18n, "current_lang", "ru")
        if user_lang == "ru":
            default_query = f"Дай развернутый ответ как подключить API {prov_name}: базовый URL endpoint, формат POST chat completions, заголовок Authorization, список моделей и пример JSON"
        else:
            default_query = f"Detailed guide on connecting {prov_name} API: base URL endpoint, POST chat completions format, Authorization header, models list and JSON example"

        ent_q = tk.Entry(bar_top, font=theme.font(-1), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1)
        ent_q.insert(0, default_query)
        ent_q.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(ent_q)

        lbl_status = tk.Label(pad, text="Поиск документации и правил API через ИИ...", font=theme.font(-1, "bold"), bg=theme.get_color("bg_main"), fg=theme.get_color("status_ready"))
        lbl_status.pack(anchor="w", pady=(0, 4))

        frame_txt = tk.Frame(pad, bg=theme.get_color("bg_main"))
        frame_txt.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        sc_y = ttk.Scrollbar(frame_txt, orient=tk.VERTICAL)
        txt = tk.Text(frame_txt, font=theme.font(-1), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1, wrap=tk.WORD, yscrollcommand=sc_y.set)
        sc_y.config(command=txt.yview)
        sc_y.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_entry_context_menu(txt)

        txt.tag_config("link", foreground="#3B82F6", underline=1)
        txt.tag_bind("link", "<Enter>", lambda e: txt.config(cursor="hand2"))
        txt.tag_bind("link", "<Leave>", lambda e: txt.config(cursor=""))

        def _make_links_clickable(text_widget):
            content = text_widget.get("1.0", tk.END)
            url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
            for match in url_pattern.finditer(content):
                url = match.group()
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                tag_name = f"link_{match.start()}"
                text_widget.tag_add(tag_name, start_idx, end_idx)
                text_widget.tag_add("link", start_idx, end_idx)
                text_widget.tag_bind(tag_name, "<Button-1>", lambda e, target_url=url: os.startfile(target_url))

        def _do_search():
            chosen_eng = engine_map.get(cb_eng.get(), "google")
            query_text = ent_q.get().strip()
            if not query_text:
                return
            lbl_status.config(text=f"Поиск через {cb_eng.get()}...", fg=theme.get_color("accent"))
            txt.delete("1.0", tk.END)
            txt.insert("1.0", "Выполняется запрос к поисковой системе...")

            def _worker():
                try:
                    from data.core.web_search import search_web
                    res_text = search_web(query_text, engine=chosen_eng, max_results=4)
                    def _show():
                        lbl_status.config(text=f"Результаты поиска ({cb_eng.get()}):", fg=theme.get_color("status_ready"))
                        txt.delete("1.0", tk.END)
                        txt.insert("1.0", res_text)
                        _make_links_clickable(txt)
                    top.after(0, _show)
                except Exception as e:
                    top.after(0, lambda: lbl_status.config(text=f"Ошибка: {e}", fg=theme.get_color("status_error")))

            threading.Thread(target=_worker, daemon=True).start()

        btn_search = tk.Button(
            bar_top, text="Искать", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=8, command=_do_search
        )
        btn_search.pack(side=tk.RIGHT)

        _do_search()

    def _open_model_selector(self):
        ModelSelectorDialog(
            self,
            endpoint_url=self.var_endpoint.get().strip(),
            api_key=self.var_api_key.get().strip(),
            template_id=self.var_template_id.get().strip(),
            connection_mode=self.var_connection_mode.get(),
            proxy=self.var_proxy.get().strip(),
            account_id=self.var_account_id.get().strip(),
            on_select_callback=lambda m_id: self.var_model.set(m_id)
        )

    def _run_test(self, quick=True):
        endpoint = self.var_endpoint.get().strip()
        model = self.var_model.get().strip()
        api_key = self.var_api_key.get().strip()
        account_id = self.var_account_id.get().strip()

        if not endpoint or not model:
            messagebox.showwarning("Внимание", "Укажите эндпоинт и модель перед тестированием.", parent=self)
            return

        self.txt_result.delete("1.0", tk.END)
        self.txt_result.insert("1.0", "Отправка запроса на сервер модели... Пожалуйста, подождите (таймаут 8 сек).")
        self.update_idletasks()

        test_data = {
            "endpoint": endpoint,
            "model": model,
            "api_key": api_key,
            "account_id": account_id,
            "connection_mode": self.var_connection_mode.get(),
            "proxy": self.var_proxy.get().strip(),
            "doh_preset": self.var_doh_preset.get(),
            "doh_custom_url": ""
        }

        def _worker():
            try:
                from data.core.templates.unified_engine import execute_test_ping
                success, msg = execute_test_ping(self.var_service_id.get().strip(), test_data, quick_mode=quick)
                def _update_ui():
                    self.txt_result.delete("1.0", tk.END)
                    self.txt_result.insert("1.0", msg)
                    if success:
                        self.lbl_status_test.config(text="Запрос выполнен успешно.", fg=theme.get_color("status_ready"))
                    else:
                        self.lbl_status_test.config(text="Ошибка ответа сервера.", fg=theme.get_color("status_error"))
                self.after(0, _update_ui)
            except Exception as ex:
                self.after(0, lambda: self._on_test_fail(str(ex)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_test_fail(self, ex_str):
        self.txt_result.delete("1.0", tk.END)
        self.txt_result.insert("1.0", f"Исключение при вызове: {ex_str}")
        self.lbl_status_test.config(text="Сбой соединения.", fg=theme.get_color("status_error"))

    def _on_create(self):
        display_name = self.var_display_name.get().strip()
        template_id = self.var_template_id.get().strip()
        account_id = self.var_account_id.get().strip()

        if not display_name:
            messagebox.showwarning("Внимание", "Укажите название сервиса.", parent=self)
            return

        self.var_status_msg.set("Генерация плагинов и регистрация сервиса...")
        self.update_idletasks()

        try:
            sec_id = service_generator.generate(
                display_name=display_name,
                template_id=template_id,
                api_key=self.var_api_key.get().strip(),
                model_name=self.var_model.get().strip(),
                endpoint=self.var_endpoint.get().strip(),
                connection_mode=self.var_connection_mode.get(),
                proxy=self.var_proxy.get().strip(),
                doh_preset=self.var_doh_preset.get(),
                temperature="0.3",
                top_p="0.9",
                max_tokens="2048",
                thinking_policy=self.var_thinking_policy.get(),
                restart_qt=True
            )

            if account_id:
                api_config.models.set(sec_id, "account_id", account_id)
                if "cloudflare" in template_id or "cloudflare" in sec_id:
                    api_config.set_provider_val("cloudflare", "account_id", account_id)
                api_config.save_models()
                api_config.save_providers()

            self.created_service_id = sec_id
            self.created_folder_name = service_generator.sanitize_folder_name(display_name)

            btn_id_val = self.var_btn_id.get().strip()
            self.var_status_msg.set(f"Сервис '{display_name}' успешно создан! QTranslate перезапущен (ID: {btn_id_val}).")
            self.lbl_status_test.config(fg=theme.get_color("status_ready"))

            self.btn_open_py.config(state=tk.NORMAL)
            self.btn_open_js.config(state=tk.NORMAL)
            self.btn_create.config(text="Обновить сервис")

            if self.on_created_callback:
                try:
                    self.on_created_callback()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Ошибка при создании сервиса: {e}")
            self.var_status_msg.set(f"Ошибка создания: {e}")
            self.lbl_status_test.config(fg=theme.get_color("status_error"))
            messagebox.showerror("Ошибка", str(e), parent=self)

    def _open_py_file(self):
        if not self.created_service_id:
            return
        base_dir = service_generator.base_dir
        py_path = os.path.join(base_dir, "data", "services", self.created_service_id, "service.py")
        open_file_in_smart_editor(py_path, self)

    def _open_js_file(self):
        if not self.created_folder_name:
            return
        base_dir = service_generator.base_dir
        js_path = os.path.join(base_dir, "Services", self.created_folder_name, "service.js")
        open_file_in_smart_editor(js_path, self)

WizardDialog = AddServiceWizardDialog