# data/gui/model_selector_dialog.py
import os
import sys
import json
import re
import time
import socket
import ssl
import threading
import urllib.request
import urllib.parse
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
from data.core.i18n import t, i18n
from data.core.config_manager import config
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import ToolTip, attach_entry_context_menu
from data.gui.code_editor_dialog import open_file_in_smart_editor
from data.core.templates.unified_engine import (
    dechunk_http_body,
    parse_proxy_string,
    resolve_doh,
    UNIFIED_DOH_PRESETS
)


class ModelSelectorDialog(tk.Toplevel):
    def __init__(self, parent, endpoint_url, api_key="", template_id="", connection_mode="direct", proxy="", account_id="", on_select_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.endpoint_url = endpoint_url.strip()
        self.api_key = api_key.strip()
        self.template_id = template_id.strip()
        self.connection_mode = connection_mode
        self.proxy = proxy.strip()
        self.account_id = account_id.strip()
        self.on_select_callback = on_select_callback
        self.models_data = []
        self.displayed_items = []
        self.selected_model = None
        self._raw_models_json = ""

        theme.apply_ttk_theme(self)
        self.title("Выбор модели API — QTranslate AI Hub")
        self.geometry("820x660")
        self.minsize(680, 480)
        self.configure(bg=theme.get_color("bg_main"))
        if parent:
            self.transient(parent)

        self._build_ui()
        self._center_window()
        self._start_fetch(self.ent_url.get().strip())

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 800
        ph = self.parent.winfo_height() if self.parent else 600
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 820, 660
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _resolve_models_url(self, endpoint, tmpl_id, acc_id):
        raw = endpoint.strip()
        if "cloudflare" in tmpl_id or "cloudflare" in raw:
            aid = acc_id if acc_id else "b53d06890fe315cfac0a5e6c074f99b4"
            return f"https://api.cloudflare.com/client/v4/accounts/{aid}/ai/models/search"
        parsed = urllib.parse.urlparse(raw)
        path = parsed.path
        if "/chat/completions" in path:
            new_path = path.replace("/chat/completions", "/models")
        elif path.endswith("/v1") or path.endswith("/v1/"):
            new_path = path.rstrip("/") + "/models"
        elif "/v1beta" in path:
            new_path = "/v1beta/models"
        else:
            new_path = "/v1/models"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        btn_bg = theme.get_color("btn_bg")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad = tk.Frame(self, bg=bg_main, padx=12, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        url_box = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1)
        url_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(url_box, text="URL моделей:", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        default_url = self._resolve_models_url(self.endpoint_url, self.template_id, self.account_id)
        self.ent_url = tk.Entry(url_box, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_url.insert(0, default_url)
        self.ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        attach_entry_context_menu(self.ent_url)

        tk.Button(
            url_box, text="Запрос", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=10,
            command=lambda: self._start_fetch(self.ent_url.get().strip())
        ).pack(side=tk.LEFT, padx=(0, 4))

        btn_opt = tk.Button(
            url_box, text="OPTIONS", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=6, command=self._check_options
        )
        btn_opt.pack(side=tk.LEFT)
        ToolTip(btn_opt, "Проверить поддерживаемые методы сервера (HTTP OPTIONS)")

        filter_box = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1)
        filter_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(filter_box, text="Поиск:", font=theme.font(0), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.e_search = tk.Entry(filter_box, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=22)
        self.e_search.pack(side=tk.LEFT, padx=(4, 10))
        self.e_search.bind("<KeyRelease>", lambda e: self._apply_filter())
        attach_entry_context_menu(self.e_search)

        self.var_free_only = tk.BooleanVar(value=False)
        self.chk_free = tk.Checkbutton(
            filter_box, text="Только бесплатные (:free)", variable=self.var_free_only,
            bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._apply_filter
        )
        self.chk_free.pack(side=tk.LEFT)

        self.lbl_count = tk.Label(filter_box, text="Ожидание запроса...", font=theme.font(-1), bg=bg_card, fg=theme.get_color("fg_muted"))
        self.lbl_count.pack(side=tk.RIGHT)

        body_frame = tk.Frame(pad, bg=bg_main)
        body_frame.pack(fill=tk.BOTH, expand=True)

        list_frame = tk.Frame(body_frame, bg=bg_main)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        self.lb_models = tk.Listbox(
            list_frame, font=("Consolas", 10), bg=in_bg, fg=in_fg,
            selectbackground=theme.get_color("accent"), selectforeground=theme.get_color("accent_text"),
            relief=tk.SOLID, bd=1, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set
        )
        scroll_y.config(command=self.lb_models.yview)
        scroll_x.config(command=self.lb_models.xview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.lb_models.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.lb_models.bind("<Double-Button-1>", lambda e: self._on_select())
        self.lb_models.bind("<<ListboxSelect>>", self._on_list_select)
        self._bind_context_menu()

        detail_box = tk.LabelFrame(pad, text=" Детали модели ", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        detail_box.pack(fill=tk.X, pady=(6, 0))

        self.txt_details = tk.Text(detail_box, height=4, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, wrap=tk.WORD)
        self.txt_details.pack(fill=tk.X)
        self.txt_details.insert("1.0", "Выберите модель из списка для просмотра параметров.")
        self.txt_details.config(state=tk.DISABLED)

        btn_bar = tk.Frame(pad, bg=bg_main, pady=6)
        btn_bar.pack(fill=tk.X)

        tk.Button(
            btn_bar, text="Закрыть", font=theme.font(0), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=12, command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_bar, text="Выбрать", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=16,
            command=self._on_select
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_bar, text="Копировать ID", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, command=self._copy_selection
        ).pack(side=tk.LEFT, padx=(0, 4))

        btn_ai_search = tk.Button(
            btn_bar, text="Справка ИИ о модели", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=theme.get_color("accent"), padx=8, command=self._show_ai_model_help
        )
        btn_ai_search.pack(side=tk.LEFT, padx=(0, 4))
        ToolTip(btn_ai_search, "Найти подробные характеристики, бенчмарки и назначение модели через поиск Google")

        tk.Button(
            btn_bar, text="Экспорт в TXT", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, command=self._export_to_txt
        ).pack(side=tk.LEFT)

    def _start_fetch(self, target_url):
        self.lb_models.delete(0, tk.END)
        self.lbl_count.config(text="Загрузка списка моделей...")
        self.models_data.clear()

        def _worker():
            try:
                headers = {
                    "User-Agent": "QTranslate-AI-Hub/2.0",
                    "Accept": "application/json"
                }
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                if "openrouter" in target_url:
                    headers["HTTP-Referer"] = "https://github.com/MAX-EMELKIN/AI-Hub"
                    headers["X-Title"] = "QTranslate AI Hub"

                conn_mode = str(self.connection_mode).lower().strip()
                if conn_mode in ("socks5", "proxy"):
                    raw = self._socks5_request(target_url, headers, proxy_str=self.proxy, timeout=12, method="GET")
                elif conn_mode == "doh":
                    raw = self._doh_request(target_url, headers, timeout=12, method="GET")
                else:
                    raw = self._direct_request(target_url, headers, timeout=12, method="GET")

                self._raw_models_json = raw
                parsed_models = self._parse_models(raw)
                self.after(0, lambda: self._on_fetch_success(parsed_models))
            except Exception as e:
                self.after(0, lambda: self._on_fetch_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _direct_request(self, url, headers, timeout=12, method="GET"):
        req = urllib.request.Request(url, headers=headers, method=method)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                if method == "OPTIONS":
                    allow = resp.headers.get("Allow", "Не указано")
                    cors = resp.headers.get("Access-Control-Allow-Methods", "Не указано")
                    return f"Allow: {allow}\nCORS Methods: {cors}"
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            if method == "OPTIONS":
                allow = he.headers.get("Allow", "Не указано")
                cors = he.headers.get("Access-Control-Allow-Methods", "Не указано")
                return f"HTTP {he.code}\nAllow: {allow}\nCORS Methods: {cors}\n\n{err_body}"
            raise RuntimeError(f"HTTP {he.code}: {err_body[:300]}")

    def _doh_request(self, url, headers, timeout=12, method="GET"):
        parsed = urllib.parse.urlparse(url)
        dest_host = parsed.hostname or "localhost"
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        preset_info = UNIFIED_DOH_PRESETS.get("Comss.one (SmartDNS / РФ обход)", {})
        doh_url = preset_info.get("url", "https://dns.comss.one/dns-query")
        ip = resolve_doh(dest_host, doh_url)

        target = url
        req_headers = dict(headers)
        if ip and ip != dest_host:
            req_headers["Host"] = dest_host
            port_str = f":{dest_port}" if parsed.port else ""
            target = urllib.parse.urlunparse((parsed.scheme, f"{ip}{port_str}", parsed.path, parsed.params, parsed.query, parsed.fragment))
        return self._direct_request(target, req_headers, timeout=timeout, method=method)

    def _socks5_request(self, url, headers, proxy_str, timeout=12, method="GET"):
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        p_host, p_port = parse_proxy_string(proxy_str if proxy_str else "213.165.38.49:1080")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((p_host, int(p_port)))
        sock.sendall(b"\x05\x01\x00")
        if sock.recv(2) != b"\x05\x00":
            sock.close()
            raise ConnectionError("SOCKS5: Аутентификация отклонена")

        d_bytes = host.encode("idna")
        req = bytearray(b"\x05\x01\x00\x03") + bytearray([len(d_bytes)]) + d_bytes + port.to_bytes(2, "big")
        sock.sendall(req)
        rep = sock.recv(10)
        if len(rep) < 4 or rep[1] != 0:
            sock.close()
            raise ConnectionError(f"SOCKS5: Ошибка соединения с хостом (код {rep[1] if len(rep) > 1 else 'unknown'})")

        client = ssl.create_default_context().wrap_socket(sock, server_hostname=host) if parsed.scheme == "https" else sock
        lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
        for k, v in headers.items():
            lines.append(f"{k}: {v}")
        client.sendall("\r\n".join(lines).encode("utf-8") + b"\r\n\r\n")

        chunks = []
        while True:
            try:
                b = client.recv(16384)
                if not b:
                    break
                chunks.append(b)
            except socket.timeout:
                break
        client.close()

        raw = b"".join(chunks)
        sep = raw.find(b"\r\n\r\n")
        if sep == -1:
            return raw.decode("latin1", errors="replace")
        h_part = raw[:sep].decode("latin1", errors="replace")
        b_part = raw[sep+4:]
        if method == "OPTIONS":
            return h_part
        if "chunked" in h_part.lower():
            b_part = dechunk_http_body(b_part)

        status = 200
        m_code = re.search(r'HTTP/\S+\s+(\d+)', h_part)
        if m_code:
            status = int(m_code.group(1))
        if status >= 400:
            raise RuntimeError(f"HTTP {status}: {b_part.decode('utf-8', errors='replace')[:300]}")

        return b_part.decode("utf-8", errors="replace")

    def _check_options(self):
        url = self.ent_url.get().strip()
        self.lbl_count.config(text="Проверка OPTIONS...")

        def _worker():
            try:
                headers = {"User-Agent": "QTranslate-AI-Hub/2.0", "Accept": "*/*"}
                conn_mode = str(self.connection_mode).lower().strip()
                if conn_mode in ("socks5", "proxy"):
                    info = self._socks5_request(url, headers, proxy_str=self.proxy, timeout=8, method="OPTIONS")
                elif conn_mode == "doh":
                    info = self._doh_request(url, headers, timeout=8, method="OPTIONS")
                else:
                    info = self._direct_request(url, headers, timeout=8, method="OPTIONS")
                self.after(0, lambda: messagebox.showinfo("HTTP OPTIONS", info, parent=self))
                self.after(0, lambda: self.lbl_count.config(text="Готово"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Ошибка OPTIONS", str(e), parent=self))

        threading.Thread(target=_worker, daemon=True).start()

    def _parse_models(self, raw_str):
        try:
            data = json.loads(raw_str)
        except Exception:
            raise ValueError(f"Сервер вернул не JSON ответ:\n{raw_str[:250]}")

        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise RuntimeError(f"Ошибка API: {err_msg}")

        models = []
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                items = data["data"]
            elif "models" in data and isinstance(data["models"], list):
                items = data["models"]
            elif "result" in data and isinstance(data["result"], list):
                items = data["result"]
            elif "result" in data and isinstance(data["result"], dict) and "models" in data["result"]:
                items = data["result"]["models"]

        for item in items:
            if isinstance(item, str):
                m_id = item.strip()
                models.append({
                    "id": m_id,
                    "context": None,
                    "pricing": None,
                    "desc": None,
                    "modality": None
                })
            elif isinstance(item, dict):
                name_val = str(item.get("name") or "").strip()
                id_val = str(item.get("id") or "").strip()

                is_uuid = bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', id_val, re.I))
                if is_uuid and name_val:
                    m_id = name_val
                elif name_val.startswith("@cf/"):
                    m_id = name_val
                else:
                    m_id = id_val or name_val or str(item.get("model") or "").strip()

                if not m_id:
                    continue

                if str(m_id).startswith("models/"):
                    m_id = str(m_id)[7:]

                ctx = item.get("context_length") or item.get("inputTokenLimit")
                pricing = item.get("pricing")
                desc = item.get("description")

                arch = None
                if isinstance(item.get("task"), dict):
                    arch = item["task"].get("name")
                elif isinstance(item.get("architecture"), dict):
                    arch = item["architecture"].get("modality")

                models.append({
                    "id": str(m_id).strip(),
                    "context": ctx,
                    "pricing": pricing,
                    "desc": desc,
                    "modality": arch
                })
        return models

    def _is_model_free(self, m):
        m_id = m["id"]
        low = m_id.lower()
        if ":free" in low or low.startswith("free:") or "free" in low:
            return True
        if isinstance(m.get("pricing"), dict) and str(m["pricing"].get("prompt")) == "0":
            return True
        return False

    def _on_fetch_success(self, parsed_models):
        self.models_data = parsed_models
        self._apply_filter()

    def _on_fetch_error(self, err_msg):
        self.lbl_count.config(text="Ошибка загрузки")
        self.txt_details.config(state=tk.NORMAL)
        self.txt_details.delete("1.0", tk.END)
        self.txt_details.insert("1.0", f"Не удалось получить список моделей:\n{err_msg}")
        self.txt_details.config(state=tk.DISABLED)

    def _apply_filter(self):
        q = self.e_search.get().strip().lower()
        free_only = self.var_free_only.get()
        self.lb_models.delete(0, tk.END)
        self.displayed_items = []

        for m in self.models_data:
            m_id = m["id"]
            low = m_id.lower()
            is_free = self._is_model_free(m)

            if free_only and not is_free:
                continue
            if q and q not in low:
                continue
            self.displayed_items.append(m)
            prefix = "[FREE] " if is_free else ""
            self.lb_models.insert(tk.END, f"{prefix}{m_id}")

        self.lbl_count.config(text=f"Найдено: {len(self.displayed_items)} из {len(self.models_data)}")

    def _on_list_select(self, event=None):
        sel = self.lb_models.curselection()
        if not sel or sel[0] >= len(self.displayed_items):
            return
        m = self.displayed_items[sel[0]]
        lines = [f"ID модели: {m['id']}"]

        if self._is_model_free(m):
            lines.append("Тариф: Бесплатный режим (:free)")

        has_extra_info = bool(m.get("context") or m.get("pricing") or m.get("desc") or m.get("modality"))

        if m.get("context"):
            try:
                ctx_val = int(m['context'])
                lines.append(f"Контекст: {ctx_val:,} токенов")
            except Exception:
                lines.append(f"Контекст: {m['context']}")

        if isinstance(m.get("pricing"), dict):
            p = m["pricing"]
            p_in = p.get("prompt", "0")
            p_out = p.get("completion", "0")
            lines.append(f"Стоимость: Вход: ${p_in}/1M, Выход: ${p_out}/1M")

        if m.get("modality"):
            lines.append(f"Модальность: {m['modality']}")
        if m.get("desc"):
            lines.append(f"Описание: {m['desc']}")

        if not has_extra_info:
            lines.append("")
            lines.append("Провайдер не передал расширенных характеристик (контекст, цены, описание) через этот эндпоинт.")
            lines.append("Нажмите кнопку «Справка ИИ о модели» ниже, чтобы запросить характеристики и бенчмарки через умный поиск Google.")

        self.txt_details.config(state=tk.NORMAL)
        self.txt_details.delete("1.0", tk.END)
        self.txt_details.insert("1.0", "\n".join(lines))
        self.txt_details.config(state=tk.DISABLED)

    def _on_select(self):
        sel = self.lb_models.curselection()
        if not sel or sel[0] >= len(self.displayed_items):
            return
        self.selected_model = self.displayed_items[sel[0]]["id"]
        if self.on_select_callback:
            self.on_select_callback(self.selected_model)
        self.destroy()

    def _copy_selection(self):
        sel = self.lb_models.curselection()
        if sel and sel[0] < len(self.displayed_items):
            val = self.displayed_items[sel[0]]["id"]
            self.clipboard_clear()
            self.clipboard_append(val)
        else:
            txt = self.txt_details.get("1.0", tk.END).strip()
            if txt:
                self.clipboard_clear()
                self.clipboard_append(txt)

    def _show_ai_model_help(self):
        sel = self.lb_models.curselection()
        if not sel or sel[0] >= len(self.displayed_items):
            messagebox.showinfo("Инфо", "Сначала выберите модель из списка.", parent=self)
            return

        m = self.displayed_items[sel[0]]
        model_id = m["id"]

        top = tk.Toplevel(self)
        top.title(f"Справка ИИ: {model_id}")
        top.geometry("740x560")
        theme.apply_ttk_theme(top)
        top.configure(bg=theme.get_color("bg_main"))
        top.transient(self)

        pad = tk.Frame(top, bg=theme.get_color("bg_main"), padx=10, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        bar_top = tk.Frame(pad, bg=theme.get_color("bg_card"), padx=8, pady=6, relief=tk.SOLID, bd=1)
        bar_top.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            bar_top, text="Поисковик:", font=theme.font(-1, "bold"),
            bg=theme.get_color("bg_card"), fg=theme.get_color("fg_primary")
        ).pack(side=tk.LEFT)

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
            default_query = f"Модель нейросети {model_id}: характеристики, контекст, бенчмарки, для чего подходит и цены API"
        else:
            default_query = f"AI model {model_id}: specs, context length, benchmarks, use cases and API pricing"

        ent_q = tk.Entry(bar_top, font=theme.font(-1), bg=theme.get_color("input_bg"), fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1)
        ent_q.insert(0, default_query)
        ent_q.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        attach_entry_context_menu(ent_q)

        lbl_status = tk.Label(
            pad, text="Поиск информации о модели через ИИ...", font=theme.font(-1, "bold"),
            bg=theme.get_color("bg_main"), fg=theme.get_color("status_ready")
        )
        lbl_status.pack(anchor="w", pady=(0, 4))

        frame_txt = tk.Frame(pad, bg=theme.get_color("bg_main"))
        frame_txt.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        sc_y = ttk.Scrollbar(frame_txt, orient=tk.VERTICAL)
        txt = tk.Text(
            frame_txt, font=theme.font(-1), bg=theme.get_color("input_bg"),
            fg=theme.get_color("input_fg"), relief=tk.SOLID, bd=1, wrap=tk.WORD,
            yscrollcommand=sc_y.set
        )
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

    def _export_to_txt(self):
        if not self.models_data:
            return
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "available_models_list.txt")
        out_path = os.path.abspath(out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Список доступных моделей (Всего: {len(self.models_data)}):\n\n")
            for m in self.models_data:
                f.write(f"- {m['id']}\n")
                if m.get("context"):
                    f.write(f"  Контекст: {m['context']}\n")
                if m.get("pricing"):
                    f.write(f"  Цены: {m['pricing']}\n")
                if m.get("desc"):
                    f.write(f"  Описание: {m['desc']}\n")
        open_file_in_smart_editor(out_path, self)

    def _bind_context_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Справка ИИ о модели", command=self._show_ai_model_help)
        menu.add_command(label="Копировать ID", command=self._copy_selection)
        menu.add_command(label="Выбрать", command=self._on_select)
        self.lb_models.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))