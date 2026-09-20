# -*- coding: utf-8 -*-
# data/gui/wizard_dialog.py

import os, sys, json, re, socket, ssl, subprocess, threading, time
import urllib.request, urllib.parse, urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.i18n import t
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import HelpPopup, attach_entry_context_menu, attach_text_context_menu, ToolTip
from data.core.service_generator import (
    get_next_available_qt_id, get_known_providers, get_provider_spec,
    create_unified_service, test_ping_service, slugify
)
from data.core.api_config import api_config
from data.core.logger import logger
from data.services.base_service import load_all_services

DOH_PRESET_OPTIONS = [
    "Comss.one (SmartDNS / РФ обход)",
    "Control D (Uncensored)",
    "Cloudflare (1.1.1.1)",
    "Google (8.8.8.8)"
]

THINKING_POLICY_OPTIONS = [
    ("none", "Отключено (Стандартные модели: Cerebras, Mistral, Llama)"),
    ("disabled_type", "thinking.type: disabled (DeepSeek, Kimi, Boltch)"),
    ("exclude_reasoning", "reasoning.max_tokens: 0 (OpenRouter)"),
    ("enable_thinking_false", "enable_thinking: false (Alibaba DashScope / Qwen)"),
    ("reasoning_effort_low", "reasoning_effort: low (GLM, OpenAI, Kimi K3)")
]

WIZARD_HELP_FALLBACK = {
    "provider": (
        "ПОСТАВЩИК / АГРЕГАТОР\n\n"
        "Шаблоны автоматически считываются из папки data/core/templates/:\n"
        "* Cerebras — сверхскоростной аппаратный инференс (Llama 3.1/3.3).\n"
        "* SiliconFlow — агрегатор с бесплатными квотами (DeepSeek V3, Qwen 2.5 72B).\n"
        "* Mistral AI — официальные модели Mistral Small, Codestral.\n"
        "* Pollinations AI — бесплатные анонимные запросы без обязательного ключа.\n"
        "* Boltch.cloud — бесплатный ротационный пул (free:kimi, free:deepseek).\n"
        "* OpenRouter.ai — модели :free с поддержкой SOCKS5.\n"
        "* Alibaba DashScope — Qwen Turbo / Plus / Max (1M токенов).\n"
        "* DeepSeek Official — официальный прямой API.\n"
        "* Пользовательский шаблон — ручная настройка любых URL и заголовков с нуля."
    ),
    "name": (
        "НАЗВАНИЕ СЕРВИСА\n\n"
        "Отображаемое имя, которое появится на кнопке в QTranslate и в шапке карточки в Хабе."
    ),
    "id": (
        "СИСТЕМНЫЙ ID / ПАПКА\n\n"
        "Уникальное имя папки на английском языке (формируется автоматически из названия)."
    ),
    "model": (
        "ИДЕНТИФИКАТОР МОДЕЛИ\n\n"
        "Точный системный ID модели в API (например: llama3.1-8b, deepseek-ai/DeepSeek-V3, qwen-turbo).\n"
        "Используйте кнопку 'Запрос', чтобы запросить список моделей у провайдера или отправить свой URL."
    ),
    "endpoint": (
        "ЭНДПОИНТ (URL)\n\n"
        "Полный веб-адрес до точки /chat/completions на сервере провайдера."
    ),
    "api_key": (
        "API КЛЮЧ\n\n"
        "Токен доступа к выбранной платформе. Если вы уже вводили ключ этого агрегатора ранее, Хаб подставит его автоматически из providers.ini."
    ),
    "connection": (
        "РЕЖИМ СЕТИ\n\n"
        "* direct — прямое подключение.\n"
        "* proxy — через SOCKS5-прокси (RFC 1928).\n"
        "* doh — через DoH SmartDNS (для обхода блокировок в РФ)."
    ),
    "thinking": (
        "ПОЛИТИКА РАЗМЫШЛЕНИЙ\n\n"
        "Способ подавления раздутых рассуждений модели, чтобы перевод отдавался за 1-3 секунды вместо 40."
    ),
    "path": (
        "ПУТЬ К ТЕКСТУ ОТВЕТА (JSON Path)\n\n"
        "Указывает скрипту, из какого вложенного поля ответа забрать сам перевод.\n\n"
        "* Стандарт: choices.0.message.content\n"
        "* Для 99% нейросетей в мире менять это значение НЕ НУЖНО."
    ),
    "qt_id": (
        "ID КНОПКИ В QTRANSLATE\n\n"
        "Уникальный системный номер кнопки в QTranslate (выбирается автоматически, например 711, 712)."
    )
}

def open_file_in_smart_editor(file_path, parent_window=None):
    if not file_path or not os.path.exists(file_path):
        return

    editor_setting = "auto"
    try:
        from data.core.config_manager import config
        editor_setting = config.get_str("GENERAL", "CodeEditor", "auto").strip()
    except Exception:
        pass

    if editor_setting.lower() == "builtin":
        CodeEditorDialog(parent_window, file_path)
        return

    if editor_setting != "auto" and os.path.exists(editor_setting):
        try:
            subprocess.Popen([editor_setting, file_path])
            return
        except Exception:
            pass

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Notepad++\notepad++.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Notepad++\notepad++.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles%\Sublime Text\sublime_text.exe"),
        os.path.expandvars(r"%ProgramFiles%\Sublime Text 3\sublime_text.exe"),
        os.path.expandvars(r"%ProgramFiles%\AkelPad\AkelPad.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\AkelPad\AkelPad.exe")
    ]
    for exe in candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, file_path])
                return
            except Exception:
                pass

    CodeEditorDialog(parent_window, file_path)

class CodeEditorDialog(tk.Toplevel):
    def __init__(self, parent, file_path):
        super().__init__(parent)
        self.parent = parent
        self.file_path = file_path

        bg_main = theme.get_color("bg_main")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        filename = os.path.basename(file_path)
        self.title(f"Редактор кода — {filename}")
        self.geometry("740x560")
        self.minsize(520, 380)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(pad, bg=bg_main)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            top_bar, text=f"Файл: {file_path}",
            font=theme.font(-1, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(side=tk.LEFT)

        text_border = tk.Frame(pad, relief=tk.SOLID, bd=1, bg=in_bg)
        text_border.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        font_to_use = ("Consolas", 10) if sys.platform.startswith("win") else theme.font(0)
        self.code_text = tk.Text(
            text_border, font=font_to_use, bg=in_bg, fg=in_fg,
            wrap=tk.NONE, bd=0, padx=8, pady=8
        )

        sb_y = ttk.Scrollbar(text_border, orient="vertical", command=self.code_text.yview)
        sb_x = ttk.Scrollbar(text_border, orient="horizontal", command=self.code_text.xview)
        self.code_text.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.code_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_text_context_menu(self.code_text)

        self._load_content()

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_bar, text="Закрыть", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=16, pady=4, cursor="hand2",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_bar, text="Сохранить файл", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=18, pady=4, command=self._save_content
        ).pack(side=tk.RIGHT)

    def _load_content(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.code_text.insert("1.0", content)
            except Exception as e:
                self.code_text.insert("1.0", f"# Ошибка чтения файла: {e}")

    def _save_content(self):
        content = self.code_text.get("1.0", tk.END)
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
            load_all_services()
            logger.system(f"Встроенный редактор: файл {self.file_path} сохранен пользователем")
            messagebox.showinfo("Сохранено", f"Файл успешно сохранен на диске!\n{self.file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось записать файл:\n{e}", parent=self)

class ModelSelectorDialog(tk.Toplevel):
    def __init__(self, parent, endpoint, api_key, conn_mode, proxy, doh_preset, on_select):
        super().__init__(parent)
        self.endpoint = endpoint.strip()
        self.api_key = api_key.strip()
        self.conn_mode = conn_mode
        self.proxy = proxy.strip()
        self.doh_preset = doh_preset
        self.on_select = on_select

        bg_main = theme.get_color("bg_main")
        fg_pri = theme.get_color("fg_primary")

        self.title("Выбор модели провайдера")
        self.geometry("700x560")
        self.minsize(560, 420)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        self.all_models = []
        self.filtered_models = []
        self.diagnostic_lines = []

        self._init_vars()
        self._build_ui()

        initial_url = self._resolve_models_url()
        self.ent_url.delete(0, tk.END)
        self.ent_url.insert(0, initial_url)
        self._start_fetch(initial_url)

    def _init_vars(self):
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *args: self._apply_filter())
        self.var_only_free = tk.BooleanVar(value=False)
        self.var_status = tk.StringVar(value="Подключение к API и получение списка моделей (таймаут 12с)...")
        self.var_count = tk.StringVar(value="")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        # 1. Строка пользовательского URL запроса
        r_url = tk.Frame(pad, bg=bg_main)
        r_url.pack(fill=tk.X, pady=(0, 6))

        tk.Label(r_url, text="URL запроса:", font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT, padx=(0, 4))
        self.ent_url = tk.Entry(r_url, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        attach_entry_context_menu(self.ent_url)
        self.ent_url.bind("<Return>", lambda e: self._on_manual_fetch())

        self.btn_send_req = tk.Button(
            r_url, text="Отправить", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=10, pady=2,
            cursor="hand2", command=self._on_manual_fetch
        )
        self.btn_send_req.pack(side=tk.LEFT)
        ToolTip(self.btn_send_req, "Отправить запрос по указанному URL (Enter)")

        # 2. Строка локального поиска и фильтра Free
        top = tk.Frame(pad, bg=bg_main)
        top.pack(fill=tk.X, pady=(0, 6))

        tk.Label(top, text="Поиск в списке:", font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT, padx=(0, 4))
        self.ent_search = tk.Entry(top, textvariable=self.var_search, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        attach_entry_context_menu(self.ent_search)

        chk_free = tk.Checkbutton(
            top, text="Только бесплатные (Free)", variable=self.var_only_free,
            bg=bg_main, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._apply_filter
        )
        chk_free.pack(side=tk.LEFT, padx=(0, 4))

        # 3. Список моделей
        mid = tk.Frame(pad, relief=tk.SOLID, bd=1, bg=in_bg)
        mid.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(mid, font=theme.font(0), bg=in_bg, fg=in_fg, selectmode=tk.SINGLE, bd=0)
        ys = ttk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.listbox.bind("<Double-Button-1>", lambda e: self._on_confirm())
        self.listbox.bind("<Return>", lambda e: self._on_confirm())
        self.listbox.bind("<Control-c>", lambda e: self._copy_selected())
        self.listbox.bind("<Control-C>", lambda e: self._copy_selected())
        self._bind_listbox_context_menu()

        # 4. Информационная панель статуса
        info_bar = tk.Frame(pad, bg=bg_main)
        info_bar.pack(fill=tk.X, pady=(4, 6))
        lbl_st = tk.Label(info_bar, textvariable=self.var_status, font=theme.font(-2), fg=theme.get_color("fg_muted"), bg=bg_main, wraplength=480, justify="left")
        lbl_st.pack(side=tk.LEFT)
        lbl_cnt = tk.Label(info_bar, textvariable=self.var_count, font=theme.font(-1, "bold"), fg=theme.get_color("accent"), bg=bg_main)
        lbl_cnt.pack(side=tk.RIGHT)

        # 5. Нижняя панель действий
        bot = tk.Frame(pad, bg=bg_main)
        bot.pack(fill=tk.X)

        self.btn_copy = tk.Button(
            bot, text="Копировать", font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=10, pady=3, command=self._copy_selected
        )
        self.btn_copy.pack(side=tk.LEFT, padx=(0, 4))
        ToolTip(self.btn_copy, "Скопировать выделенную строку (или отчет об ошибке) в буфер обмена Windows (Ctrl+C)")

        self.btn_export = tk.Button(
            bot, text="Экспорт в TXT", font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=10, pady=3, state="disabled", command=self._export_to_txt
        )
        self.btn_export.pack(side=tk.LEFT)
        ToolTip(self.btn_export, "Сохранить список всех полученных моделей в файл и открыть в редакторе")

        self.btn_ok = tk.Button(
            bot, text="Выбрать", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=14, pady=3, state="disabled", command=self._on_confirm
        )
        self.btn_ok.pack(side=tk.RIGHT, padx=(6, 0))

        btn_cancel = tk.Button(
            bot, text="Отмена", font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12, pady=3, command=self.destroy
        )
        btn_cancel.pack(side=tk.RIGHT)

    def _bind_listbox_context_menu(self):
        menu = tk.Menu(self.listbox, tearoff=0)
        menu.add_command(label="Копировать выделенное (Ctrl+C)", command=self._copy_selected)
        menu.add_command(label="Копировать весь список / ошибку", command=self._copy_all)

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.listbox.bind("<Button-3>", popup)

    def _copy_selected(self):
        sel = self.listbox.curselection()
        if sel:
            txt = self.listbox.get(sel[0])
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.var_status.set("Выделенная строка скопирована в буфер обмена.")
        else:
            self._copy_all()

    def _copy_all(self):
        items = self.listbox.get(0, tk.END)
        if items:
            txt = "\n".join(items)
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.var_status.set("Весь текст из окна скопирован в буфер обмена.")

    def _resolve_models_url(self):
        ep = self.endpoint.strip()

        # Google Gemini API
        if "generativelanguage.googleapis.com" in ep:
            base = "https://generativelanguage.googleapis.com/v1beta/models"
            key = self.api_key or api_config.get_provider_val("gemini", "api_key", "")
            return f"{base}?key={key}" if key else base

        # Cloudflare Workers AI
        if "api.cloudflare.com" in ep:
            account_id = ""
            m = re.search(r"/accounts/([^/]+)/", ep)
            if m and "{" not in m.group(1):
                account_id = m.group(1).strip()

            if not account_id:
                account_id = api_config.get_provider_val("cloudflare", "account_id", "").strip()
            if not account_id:
                account_id = api_config.get_val("openai_120b", "account_id", "").strip()

            if not account_id or "{" in account_id:
                return "https://api.cloudflare.com/client/v4/ai/models/search"

            return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search"

        # Стандартные OpenAI-совместимые провайдеры
        if "/chat/completions" in ep:
            return ep.replace("/chat/completions", "/models")
        clean = ep.rstrip("/")
        if clean.endswith("/v1"):
            return clean + "/models"
        return clean + "/v1/models" if "/v1" not in clean else clean + "/models"

    def _on_manual_fetch(self):
        target_url = self.ent_url.get().strip()
        if not target_url:
            messagebox.showwarning("Внимание", "Укажите URL для запроса.", parent=self)
            return
        self._start_fetch(target_url)

    def _start_fetch(self, target_url=None):
        url = target_url or self.ent_url.get().strip() or self._resolve_models_url()
        self.var_status.set(f"Подключение к API (таймаут 12с)...")
        self.btn_send_req.config(state="disabled")
        self.btn_ok.config(state="disabled")
        threading.Thread(target=self._worker_fetch, args=(url,), daemon=True).start()

    def _worker_fetch(self, url):
        token = self.api_key
        if not token and "cloudflare" in url:
            token = api_config.get_provider_val("cloudflare", "api_token", "") or api_config.get_provider_val("cloudflare", "api_key", "")

        masked_key = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else ("есть" if token else "нет")

        logger.system(f"[MODELS API] Запрос эндпоинта моделей: {url}")
        logger.system(f"[MODELS API] Сеть: {self.conn_mode} | Прокси: {self.proxy or 'нет'} | Ключ: {masked_key} | Таймаут: 12с")

        headers = {
            "Accept": "application/json",
            "User-Agent": "QTranslate-AI-Hub/2.0"
        }
        if token and "generativelanguage.googleapis.com" not in url:
            headers["Authorization"] = f"Bearer {token}"
        if "openrouter" in url:
            headers["HTTP-Referer"] = "https://github.com/MAX-EMELKIN/AI-Hub"
            headers["X-Title"] = "QTranslate AI Hub"

        error_summary = None
        error_body = ""
        raw_text = ""

        try:
            if self.conn_mode == "proxy" and self.proxy:
                raw_text = self._socks5_get(url, headers, self.proxy, timeout=12)
            else:
                raw_text = self._direct_get(url, headers, timeout=12)
        except urllib.error.HTTPError as he:
            error_summary = f"HTTP Error {he.code}: {he.reason}"
            try:
                error_body = he.read().decode("utf-8", "replace")
            except Exception:
                error_body = str(he)
            logger.system(f"[MODELS API] Ошибка сервера {he.code}: {error_body[:300]}")
        except Exception as e:
            error_summary = str(e)
            logger.system(f"[MODELS API] Сбой соединения: {e}")

        self.after(0, lambda: self.btn_send_req.config(state="normal"))

        if error_summary:
            self.after(0, self._on_fetch_error, url, error_summary, error_body)
        else:
            self.after(0, self._on_fetch_success, url, raw_text)

    def _socks5_get(self, url, headers, proxy_str, timeout=12):
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")

        p_host, p_port = proxy_str.split(":", 1)
        p_port = int(p_port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((p_host, p_port))
        sock.sendall(b"\x05\x01\x00")
        if sock.recv(2) != b"\x05\x00":
            sock.close()
            raise ConnectionError("SOCKS5-прокси отклонил подключение без авторизации")

        dom_b = host.encode("idna")
        req = bytearray(b"\x05\x01\x00\x03")
        req.append(len(dom_b))
        req.extend(dom_b)
        req.extend(port.to_bytes(2, "big"))
        sock.sendall(req)

        resp = sock.recv(10)
        if len(resp) < 4 or resp[1] != 0:
            sock.close()
            raise ConnectionError(f"Ошибка SOCKS5 CONNECT (код ошибки: {resp[1] if len(resp) > 1 else 'EOF'})")

        c_sock = sock
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            c_sock = ctx.wrap_socket(sock, server_hostname=host)

        req_lines = [f"GET {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
        for k, v in headers.items():
            req_lines.append(f"{k}: {v}")
        c_sock.sendall("\r\n".join(req_lines).encode("utf-8") + b"\r\n\r\n")

        chunks = []
        while True:
            try:
                data = c_sock.recv(32768)
                if not data:
                    break
                chunks.append(data)
            except socket.timeout:
                break
        c_sock.close()

        raw = b"".join(chunks)
        h_end = raw.find(b"\r\n\r\n")
        if h_end == -1:
            raise ValueError("Сервер разорвал соединение до передачи HTTP-заголовков")
        h_text = raw[:h_end].decode("latin1", "ignore")
        b_bytes = raw[h_end + 4:]

        first_line = h_text.splitlines()[0] if h_text else ""
        parts = first_line.split(" ", 2)
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 200

        if "chunked" in h_text.lower():
            from data.core.templates.unified_engine import dechunk_http_body
            b_bytes = dechunk_http_body(b_bytes)

        body_str = b_bytes.decode("utf-8", "replace")
        if code >= 400:
            raise urllib.error.HTTPError(url, code, f"HTTP {code}", {}, None)
        return body_str

    def _direct_get(self, url, headers, timeout=12):
        if self.conn_mode != "doh":
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")

        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")

        connect_host = host
        try:
            from data.core.templates.unified_engine import resolve_doh
            resolved_ip = resolve_doh(host, self.doh_preset)
            if resolved_ip and resolved_ip != host:
                connect_host = resolved_ip
        except Exception:
            pass

        sock = socket.create_connection((connect_host, port), timeout=timeout)
        c_sock = sock
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            c_sock = ctx.wrap_socket(sock, server_hostname=host)

        req_lines = [f"GET {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
        for k, v in headers.items():
            req_lines.append(f"{k}: {v}")
        c_sock.sendall("\r\n".join(req_lines).encode("utf-8") + b"\r\n\r\n")

        chunks = []
        while True:
            try:
                data = c_sock.recv(32768)
                if not data:
                    break
                chunks.append(data)
            except socket.timeout:
                break
        c_sock.close()

        raw = b"".join(chunks)
        h_end = raw.find(b"\r\n\r\n")
        if h_end == -1:
            raise ValueError("Сервер разорвал соединение до передачи заголовков")
        h_text = raw[:h_end].decode("latin1", "ignore")
        b_bytes = raw[h_end + 4:]

        first_line = h_text.splitlines()[0] if h_text else ""
        parts = first_line.split(" ", 2)
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 200

        if "chunked" in h_text.lower():
            from data.core.templates.unified_engine import dechunk_http_body
            b_bytes = dechunk_http_body(b_bytes)

        body_str = b_bytes.decode("utf-8", "replace")
        if code >= 400:
            raise urllib.error.HTTPError(url, code, f"HTTP {code}", {}, None)
        return body_str

    def _on_fetch_error(self, url, err_summary, err_body):
        self.var_status.set(f"Сбой: {err_summary}")
        self.listbox.delete(0, tk.END)

        lines = [
            f"[ОШИБКА ЗАПРОСА К API МОДЕЛЕЙ]",
            f"URL: {url}",
            f"Статус: {err_summary}",
            ""
        ]
        if err_body:
            lines.append("--- Ответ сервера ---")
            for line in err_body.splitlines()[:20]:
                lines.append(line.strip())
        else:
            lines.append("Сервер не прислал тело ответа (таймаут 12с или блокировка соединения).")
            lines.append("Совет: Переключите 'Режим сети' на proxy (SOCKS5) или doh (SmartDNS) и повторите запрос.")

        self.diagnostic_lines = lines
        for l in lines:
            self.listbox.insert(tk.END, l)

        self.btn_export.config(state="normal")
        self.var_count.set("0 моделей")

    def _on_fetch_success(self, url, raw_json):
        logger.system(f"[MODELS API] Успешный ответ от {url} ({len(raw_json)} байт). Разбор...")
        try:
            data = json.loads(raw_json)
        except Exception as e:
            self._on_fetch_error(url, f"Ошибка парсинга JSON: {e}", raw_json[:300])
            return

        items = []
        if isinstance(data, dict) and "models" in data:
            for gm in data["models"]:
                mid = str(gm.get("name", "")).replace("models/", "")
                methods = gm.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    items.append({"id": mid, "free": True})
        elif isinstance(data, dict) and "data" in data:
            items = data["data"]
        elif isinstance(data, dict) and "result" in data:
            items = data["result"]
        elif isinstance(data, list):
            items = data

        parsed_list = []
        dashscope_promo = {"qwen-turbo", "qwen-plus", "qwen-max", "qwen3.8-flash"}

        for it in items:
            mid = ""
            is_free = False
            if isinstance(it, dict):
                c_name = str(it.get("name") or "").strip()
                c_id = str(it.get("id") or "").strip()
                if c_name.startswith("@cf/") or (c_name and len(c_id) == 36 and "-" in c_id):
                    mid = c_name
                else:
                    mid = c_id or c_name

                if it.get("free") is True:
                    is_free = True
                pricing = it.get("pricing") or {}
                p_in = str(pricing.get("prompt", "")).strip()
                p_out = str(pricing.get("completion", "")).strip()
                if p_in == "0" and p_out == "0":
                    is_free = True
            elif isinstance(it, str):
                mid = it.strip()

            if not mid:
                continue

            mid_lower = mid.lower()
            if (
                ":free" in mid_lower or
                "free:" in mid_lower or
                "-free" in mid_lower or
                mid_lower in dashscope_promo or
                "gemini-2.0-flash" in mid_lower or
                "gemini-1.5-flash" in mid_lower or
                mid.startswith("@cf/")
            ):
                is_free = True

            parsed_list.append((mid, is_free))

        parsed_list.sort(key=lambda x: (not x[1], x[0].lower()))
        self.all_models = parsed_list

        logger.system(f"[MODELS API] Найдено моделей: {len(self.all_models)}")
        self.var_status.set("Список моделей успешно загружен.")
        self.btn_export.config(state="normal")
        self.btn_ok.config(state="normal")
        self._apply_filter()

    def _apply_filter(self):
        query = self.var_search.get().strip().lower()
        only_free = self.var_only_free.get()

        self.filtered_models = []
        display_items = []

        for mid, is_free in self.all_models:
            if only_free and not is_free:
                continue
            if query and query not in mid.lower():
                continue
            self.filtered_models.append(mid)
            tag = " [FREE]" if is_free else ""
            display_items.append(f"{mid}{tag}")

        self.listbox.delete(0, tk.END)
        for d in display_items:
            self.listbox.insert(tk.END, d)

        self.var_count.set(f"Показано: {len(self.filtered_models)} из {len(self.all_models)}")

    def _on_confirm(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self.filtered_models):
            return
        selected_model = self.filtered_models[sel[0]]
        self.on_select(selected_model)
        self.destroy()

    def _export_to_txt(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        temp_dir = os.path.join(base_dir, "data", "logs")
        os.makedirs(temp_dir, exist_ok=True)
        export_path = os.path.join(temp_dir, "available_models_list.txt")

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(f"Отчет по моделям для эндпоинта: {self.endpoint}\n")
                f.write(f"Режим подключения: {self.conn_mode} | Прокси: {self.proxy or 'нет'}\n\n")

                if self.diagnostic_lines:
                    f.write("--- ДИАГНОСТИКА СБОЯ ---\n")
                    for d in self.diagnostic_lines:
                        f.write(d + "\n")
                elif self.all_models:
                    f.write(f"Всего получено моделей: {len(self.all_models)}\n\n")
                    f.write("--- БЕСПЛАТНЫЕ / ПРОМО МОДЕЛИ (FREE) ---\n")
                    for mid, is_free in self.all_models:
                        if is_free:
                            f.write(mid + "\n")
                    f.write("\n--- ПОЛНЫЙ СПИСОК ВСЕХ МОДЕЛЕЙ ---\n")
                    for mid, is_free in self.all_models:
                        f.write(f"{mid}{' [FREE]' if is_free else ''}\n")

            open_file_in_smart_editor(export_path, self)
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", str(e), parent=self)

class AddServiceWizardDialog(tk.Toplevel):
    def __init__(self, parent, on_created_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_created = on_created_callback
        self._active_help_popup = None

        self.last_created_slug = None
        self.last_py_path = None
        self.last_js_path = None

        bg_main = theme.get_color("bg_main")
        self.title("Студия подключения сервисов — QTranslate AI Hub")
        self.geometry("680x720")
        self.minsize(620, 600)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_window()
        self._on_provider_change()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 680, 720
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _show_help(self, anchor_widget, help_key):
        if self._active_help_popup and self._active_help_popup.winfo_exists():
            self._active_help_popup.destroy()
        text = WIZARD_HELP_FALLBACK.get(help_key, "")
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

        pad = tk.Frame(self, bg=bg_main, padx=14, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        header_box = tk.Frame(pad, bg=bg_main)
        header_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            header_box, text="Студия подключения и настройки сервисов",
            font=theme.font(2, "bold"), fg=theme.get_color("accent"), bg=bg_main
        ).pack(side=tk.LEFT)

        canvas_frame = tk.Frame(pad, bg=bg_main)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg=bg_main, highlightthickness=0)
        sb = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.form_inner = tk.Frame(self.canvas, bg=bg_card, padx=12, pady=10, relief=tk.SOLID, bd=1, highlightbackground=border, highlightthickness=1)

        self.form_window = self.canvas.create_window((0, 0), window=self.form_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.form_window, width=e.width))
        self.form_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        r_prov = tk.Frame(self.form_inner, bg=bg_card)
        r_prov.pack(fill=tk.X, pady=3)
        tk.Label(r_prov, text="Провайдер / Шаблон:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_prov, "provider").pack(side=tk.LEFT, padx=(0, 6))

        self.provider_items = get_known_providers()
        self.prov_display_names = [name for _, name in self.provider_items]
        self.prov_map = {name: key for key, name in self.provider_items}

        self.combo_prov = ttk.Combobox(r_prov, values=self.prov_display_names, state="readonly", width=34)
        if self.prov_display_names:
            self.combo_prov.set(self.prov_display_names[0])
        self.combo_prov.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo_prov.bind("<<ComboboxSelected>>", self._on_provider_change)

        r_name = tk.Frame(self.form_inner, bg=bg_card)
        r_name.pack(fill=tk.X, pady=3)
        tk.Label(r_name, text="Название сервиса:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_name, "name").pack(side=tk.LEFT, padx=(0, 6))
        self.e_name = tk.Entry(r_name, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_name.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.e_name.bind("<KeyRelease>", self._auto_fill_id)
        attach_entry_context_menu(self.e_name)

        r_id = tk.Frame(self.form_inner, bg=bg_card)
        r_id.pack(fill=tk.X, pady=3)
        tk.Label(r_id, text="ID папки / сервиса:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_id, "id").pack(side=tk.LEFT, padx=(0, 6))
        self.e_id = tk.Entry(r_id, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_id.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_id)

        r_mod = tk.Frame(self.form_inner, bg=bg_card)
        r_mod.pack(fill=tk.X, pady=3)
        tk.Label(r_mod, text="Идентификатор модели:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_mod, "model").pack(side=tk.LEFT, padx=(0, 6))
        self.e_model = tk.Entry(r_mod, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_model.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_model)

        btn_sel = tk.Button(
            r_mod, text="Запрос", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, cursor="hand2", padx=8, command=self._open_model_selector
        )
        btn_sel.pack(side=tk.LEFT, padx=(6, 0))
        ToolTip(btn_sel, "Отправить запрос к API провайдера для получения списка моделей")

        r_ep = tk.Frame(self.form_inner, bg=bg_card)
        r_ep.pack(fill=tk.X, pady=3)
        tk.Label(r_ep, text="Эндпоинт (URL):", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_ep, "endpoint").pack(side=tk.LEFT, padx=(0, 6))
        self.e_endpoint = tk.Entry(r_ep, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_endpoint.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_endpoint)

        r_key = tk.Frame(self.form_inner, bg=bg_card)
        r_key.pack(fill=tk.X, pady=3)
        tk.Label(r_key, text="API Ключ провайдера:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_key, "api_key").pack(side=tk.LEFT, padx=(0, 6))
        self.e_api_key = tk.Entry(r_key, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_api_key.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_api_key)

        r_net = tk.Frame(self.form_inner, bg=bg_card)
        r_net.pack(fill=tk.X, pady=3)
        tk.Label(r_net, text="Режим сети:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_net, "connection").pack(side=tk.LEFT, padx=(0, 6))
        self.combo_net = ttk.Combobox(r_net, values=["direct", "proxy (SOCKS5)", "doh (SmartDNS)"], state="readonly", width=22)
        self.combo_net.set("direct")
        self.combo_net.pack(side=tk.LEFT)
        self.combo_net.bind("<<ComboboxSelected>>", self._toggle_net_fields)

        self.r_proxy = tk.Frame(self.form_inner, bg=bg_card)
        tk.Label(self.r_proxy, text="Адрес SOCKS5 (хост:порт):", font=theme.font(-1, "bold"), fg=fg_pri, width=22, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self.e_proxy = tk.Entry(self.r_proxy, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_proxy.insert(0, "213.165.38.49:1080")
        self.e_proxy.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_proxy)

        self.r_doh = tk.Frame(self.form_inner, bg=bg_card)
        tk.Label(self.r_doh, text="DoH Пресет:", font=theme.font(-1, "bold"), fg=fg_pri, width=22, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self.combo_doh = ttk.Combobox(self.r_doh, values=DOH_PRESET_OPTIONS, state="readonly", width=30)
        self.combo_doh.set(DOH_PRESET_OPTIONS[0])
        self.combo_doh.pack(side=tk.LEFT)

        r_think = tk.Frame(self.form_inner, bg=bg_card)
        r_think.pack(fill=tk.X, pady=3)
        tk.Label(r_think, text="Размышления (Thinking):", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_think, "thinking").pack(side=tk.LEFT, padx=(0, 6))
        self.combo_think = ttk.Combobox(r_think, values=[name for _, name in THINKING_POLICY_OPTIONS], state="readonly")
        self.combo_think.set(THINKING_POLICY_OPTIONS[0][1])
        self.combo_think.pack(side=tk.LEFT, fill=tk.X, expand=True)

        r_qtid = tk.Frame(self.form_inner, bg=bg_card)
        r_qtid.pack(fill=tk.X, pady=3)
        tk.Label(r_qtid, text="ID кнопки в QTranslate:", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_qtid, "qt_id").pack(side=tk.LEFT, padx=(0, 6))
        self.e_qtid = tk.Entry(r_qtid, font=theme.font(0, "bold"), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=10)
        self.e_qtid.insert(0, str(get_next_available_qt_id()))
        self.e_qtid.pack(side=tk.LEFT)
        attach_entry_context_menu(self.e_qtid)

        r_path = tk.Frame(self.form_inner, bg=bg_card)
        r_path.pack(fill=tk.X, pady=(3, 1))
        tk.Label(r_path, text="Путь ответа (JSON Path):", font=theme.font(0, "bold"), fg=fg_pri, width=19, anchor="w", bg=bg_card).pack(side=tk.LEFT)
        self._create_help_btn(r_path, "path").pack(side=tk.LEFT, padx=(0, 6))
        self.e_path = tk.Entry(r_path, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.e_path.insert(0, "choices.0.message.content")
        self.e_path.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.e_path)

        tk.Label(
            self.form_inner,
            text="* По умолчанию: choices.0.message.content (для 99% нейросетей менять не нужно)",
            font=theme.font(-2, "italic"), fg=theme.get_color("fg_muted"), bg=bg_card
        ).pack(anchor="w", padx=(27, 0), pady=(0, 4))

        self.action_panel = tk.LabelFrame(
            pad, text=" Тестирование и проверка созданного сервиса ",
            font=theme.font(0, "bold"), fg=theme.get_color("accent"), bg=bg_card, padx=10, pady=8
        )

        self.lbl_status_badge = tk.Label(
            self.action_panel, text="Сервис успешно создан. QTranslate перезапущен.",
            font=theme.font(0, "bold"), fg=theme.get_color("status_ready"), bg=bg_card
        )
        self.lbl_status_badge.pack(anchor="w", pady=(0, 6))

        r_test_btns = tk.Frame(self.action_panel, bg=bg_card)
        r_test_btns.pack(fill=tk.X, pady=2)

        self.btn_ping_fast = tk.Button(
            r_test_btns, text="Быстрый пинг (Hello)", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, cursor="hand2", padx=8, pady=2, command=self._on_fast_ping
        )
        self.btn_ping_fast.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_ping_full = tk.Button(
            r_test_btns, text="Полный пинг (Сырой ответ)", font=theme.font(-1), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, cursor="hand2", padx=8, pady=2, command=self._on_full_ping
        )
        self.btn_ping_full.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_edit_py = tk.Button(
            r_test_btns, text="Открыть service.py", font=theme.font(-1), relief=tk.FLAT,
            bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"), cursor="hand2", padx=6, pady=2,
            command=self._on_edit_py
        )
        self.btn_edit_py.pack(side=tk.LEFT, padx=(0, 4))
        ToolTip(self.btn_edit_py, "Открыть код плагина в выбранном редакторе")

        self.btn_edit_js = tk.Button(
            r_test_btns, text="Открыть service.js", font=theme.font(-1), relief=tk.FLAT,
            bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"), cursor="hand2", padx=6, pady=2,
            command=self._on_edit_js
        )
        self.btn_edit_js.pack(side=tk.LEFT)
        ToolTip(self.btn_edit_js, "Открыть JS-скрипт кнопки в выбранном редакторе")

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))

        self.btn_close = tk.Button(
            btn_bar, text="Закрыть", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=16, pady=4, cursor="hand2", command=self.destroy
        )
        self.btn_close.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_create = tk.Button(
            btn_bar, text="Создать сервис", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), cursor="hand2", padx=18, pady=4,
            command=self._on_create
        )
        self.btn_create.pack(side=tk.RIGHT)

    def _open_model_selector(self):
        ep = self.e_endpoint.get().strip()
        if not ep:
            messagebox.showwarning("Внимание", "Сначала укажите URL эндпоинта или выберите шаблон.", parent=self)
            return

        net_mode_raw = self.combo_net.get()
        conn_mode = "proxy" if "proxy" in net_mode_raw else ("doh" if "doh" in net_mode_raw else "direct")
        proxy_val = self.e_proxy.get().strip()
        doh_preset_val = self.combo_doh.get().strip()

        ModelSelectorDialog(
            parent=self,
            endpoint=ep,
            api_key=self.e_api_key.get().strip(),
            conn_mode=conn_mode,
            proxy=proxy_val,
            doh_preset=doh_preset_val,
            on_select=self._set_selected_model
        )

    def _set_selected_model(self, model_id):
        self.e_model.delete(0, tk.END)
        self.e_model.insert(0, model_id)

    def _toggle_net_fields(self, event=None):
        mode_raw = self.combo_net.get()
        self.r_proxy.pack_forget()
        self.r_doh.pack_forget()

        if "proxy" in mode_raw:
            self.r_proxy.pack(fill=tk.X, pady=2, padx=(27, 0))
        elif "doh" in mode_raw:
            self.r_doh.pack(fill=tk.X, pady=2, padx=(27, 0))

    def _on_provider_change(self, event=None):
        chosen_name = self.combo_prov.get()
        p_key = self.prov_map.get(chosen_name, "custom")
        spec = get_provider_spec(p_key)

        if p_key != "custom":
            self.e_name.delete(0, tk.END)
            self.e_name.insert(0, spec["name"])
            self._auto_fill_id()

            self.e_model.delete(0, tk.END)
            self.e_model.insert(0, spec["default_model"])

            self.e_endpoint.delete(0, tk.END)
            self.e_endpoint.insert(0, spec["endpoint"])

            self.e_path.delete(0, tk.END)
            self.e_path.insert(0, spec.get("response_path", "choices.0.message.content"))

            saved_key = api_config.get_provider_val(p_key, "api_key", "")
            if not saved_key and p_key == "cloudflare":
                saved_key = api_config.get_provider_val(p_key, "api_token", "")
            self.e_api_key.delete(0, tk.END)
            self.e_api_key.insert(0, saved_key)

            saved_mode = api_config.get_provider_val(p_key, "connection_mode", spec.get("connection_mode", "direct"))
            if saved_mode == "proxy":
                self.combo_net.set("proxy (SOCKS5)")
            elif saved_mode == "doh":
                self.combo_net.set("doh (SmartDNS)")
            else:
                self.combo_net.set("direct")

            saved_proxy = api_config.get_provider_val(p_key, "proxy", spec.get("proxy", "213.165.38.49:1080"))
            self.e_proxy.delete(0, tk.END)
            self.e_proxy.insert(0, saved_proxy)

            target_pol = spec.get("thinking_policy", "none")
            for key, display in THINKING_POLICY_OPTIONS:
                if key == target_pol:
                    self.combo_think.set(display)
                    break
        else:
            self.e_name.delete(0, tk.END)
            self.e_id.delete(0, tk.END)
            self.e_model.delete(0, tk.END)
            self.e_endpoint.delete(0, tk.END)
            self.e_endpoint.insert(0, "https://api.example.com/v1/chat/completions")
            self.e_api_key.delete(0, tk.END)
            self.combo_net.set("direct")
            self.combo_think.set(THINKING_POLICY_OPTIONS[0][1])

        self._toggle_net_fields()

    def _auto_fill_id(self, event=None):
        name = self.e_name.get().strip()
        slug = slugify(name)
        self.e_id.delete(0, tk.END)
        self.e_id.insert(0, slug)

    def _get_thinking_policy_key(self):
        chosen_display = self.combo_think.get()
        for k, name in THINKING_POLICY_OPTIONS:
            if name == chosen_display:
                return k
        return "none"

    def _on_create(self):
        chosen_prov_name = self.combo_prov.get()
        p_key = self.prov_map.get(chosen_prov_name, "custom")

        name = self.e_name.get().strip()
        slug = self.e_id.get().strip()
        model_id = self.e_model.get().strip()
        endpoint = self.e_endpoint.get().strip()
        api_key = self.e_api_key.get().strip()
        qt_id_val = self.e_qtid.get().strip()

        net_mode_raw = self.combo_net.get()
        conn_mode = "proxy" if "proxy" in net_mode_raw else ("doh" if "doh" in net_mode_raw else "direct")
        proxy_val = self.e_proxy.get().strip()
        doh_preset_val = self.combo_doh.get().strip()

        thinking_policy = self._get_thinking_policy_key()
        response_path = self.e_path.get().strip() or "choices.0.message.content"

        spec = get_provider_spec(p_key)
        auth_type = spec.get("auth_header_type", "Bearer")
        extra_headers = json.dumps(spec.get("extra_headers", {}))

        if not name or not slug or not model_id or not endpoint:
            messagebox.showwarning("Внимание", "Заполните все обязательные поля (Название, ID, Модель, Эндпоинт)!", parent=self)
            return

        self.btn_create.config(state="disabled", text="Создание...")

        try:
            ok, clean_slug, py_path, js_path = create_unified_service(
                provider_key=p_key,
                service_name=name,
                service_slug=slug,
                model_id=model_id,
                endpoint=endpoint,
                qt_id=qt_id_val,
                auth_header_type=auth_type,
                thinking_policy=thinking_policy,
                response_path=response_path,
                extra_headers_json=extra_headers,
                api_key=api_key,
                connection_mode=conn_mode,
                proxy=proxy_val,
                doh_preset=doh_preset_val
            )

            self.last_created_slug = clean_slug
            self.last_py_path = py_path
            self.last_js_path = js_path

            self.lbl_status_badge.config(
                text=f"Сервис '{name}' успешно создан! QTranslate перезапущен (ID: {qt_id_val}).",
                fg=theme.get_color("status_ready")
            )
            self.action_panel.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 6))

            if self.on_created:
                self.on_created()

            self.btn_create.config(state="normal", text="Обновить сервис")

        except Exception as e:
            self.btn_create.config(state="normal", text="Создать сервис")
            logger.system(f"Студия создания Ошибка: {e}")
            messagebox.showerror("Ошибка", f"Не удалось создать сервис:\n{e}", parent=self)

    def _on_fast_ping(self):
        if not self.last_created_slug:
            return
        self.btn_ping_fast.config(state="disabled", text="Пинг...")

        def _worker():
            ok, res, elapsed = test_ping_service(
                self.last_created_slug,
                text="Hello world! This is a test ping.",
                src="en", trg="ru"
            )
            def _ui():
                self.btn_ping_fast.config(state="normal", text="Быстрый пинг (Hello)")
                if ok:
                    msg = f"Успех ({elapsed}с):\n\n{res}"
                    messagebox.showinfo("Пинг успешен", msg, parent=self)
                else:
                    msg = f"Ошибка ({elapsed}с):\n\n{res}"
                    messagebox.showerror("Ошибка пинга", msg, parent=self)
            self.after(0, _ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_full_ping(self):
        if not self.last_created_slug:
            return
        self.btn_ping_full.config(state="disabled", text="Запрос...")

        def _worker():
            ok, res, elapsed = test_ping_service(
                self.last_created_slug,
                text="Compatibility with Automatron and Far Harbor. Testing raw response payload.",
                src="en", trg="ru"
            )
            def _ui():
                self.btn_ping_full.config(state="normal", text="Полный пинг (Сырой ответ)")
                self._show_raw_dialog(res, elapsed, ok)
            self.after(0, _ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _show_raw_dialog(self, text, elapsed, ok):
        dlg = tk.Toplevel(self)
        dlg.title(f"Отчет тестирования ({elapsed}с)")
        dlg.geometry("560x400")
        dlg.configure(bg=theme.get_color("bg_main"))
        dlg.transient(self)
        dlg.grab_set()

        pad = tk.Frame(dlg, bg=theme.get_color("bg_main"), padx=12, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        status_text = f"Статус: {'Успешно' if ok else 'Сбой'} | Время отклика: {elapsed}с"
        tk.Label(
            pad, text=status_text, font=theme.font(1, "bold"),
            fg=theme.get_color("status_ready" if ok else "status_error"), bg=theme.get_color("bg_main")
        ).pack(anchor="w", pady=(0, 6))

        t_border = tk.Frame(pad, relief=tk.SOLID, bd=1, bg=theme.get_color("input_bg"))
        t_border.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        t_box = tk.Text(t_border, font=theme.font(0), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), wrap=tk.WORD, bd=0)
        sb = tk.Scrollbar(t_border, command=t_box.yview)
        t_box.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        t_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        t_box.insert("1.0", text)
        attach_text_context_menu(t_box)

        tk.Button(
            pad, text="Закрыть", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=theme.get_color("fg_primary"),
            cursor="hand2", padx=16, pady=4, command=dlg.destroy
        ).pack(anchor="e")

    def _on_edit_py(self):
        if self.last_py_path and os.path.exists(self.last_py_path):
            open_file_in_smart_editor(self.last_py_path, self)

    def _on_edit_js(self):
        if self.last_js_path and os.path.exists(self.last_js_path):
            open_file_in_smart_editor(self.last_js_path, self)

WizardDialog = AddServiceWizardDialog