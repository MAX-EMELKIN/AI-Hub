# -*- coding: utf-8 -*-
# data/gui/model_selector_dialog.py

import os, sys, json, re, time, socket, ssl, threading
import urllib.request, urllib.parse, urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.i18n import t
from data.gui.theme_manager import theme
from data.gui.dialog_helpers import ToolTip, attach_entry_context_menu
from data.gui.code_editor_dialog import open_file_in_smart_editor

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
        self.selected_model = None
        self._raw_models_json = ""

        theme.apply_ttk_theme(self)

        self.title("Text")
        self.geometry("780x640")
        self.minsize(620, 480)
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
        w, h = 780, 640
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

        tk.Label(url_box, text="Text", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        default_url = self._resolve_models_url(self.endpoint_url, self.template_id, self.account_id)
        self.ent_url = tk.Entry(url_box, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.ent_url.insert(0, default_url)
        self.ent_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        attach_entry_context_menu(self.ent_url)

        tk.Button(
            url_box, text="Text", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=8,
            command=lambda: self._start_fetch(self.ent_url.get().strip())
        ).pack(side=tk.LEFT, padx=(0, 4))

        btn_opt = tk.Button(
            url_box, text="OPTIONS", font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=6, command=self._check_options
        )
        btn_opt.pack(side=tk.LEFT)
        ToolTip(btn_opt, "Text")

        filter_box = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1)
        filter_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(filter_box, text="Text", font=theme.font(0), bg=bg_card, fg=fg_pri).pack(side=tk.LEFT)
        self.e_search = tk.Entry(filter_box, font=theme.font(0), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, width=22)
        self.e_search.pack(side=tk.LEFT, padx=(4, 10))
        self.e_search.bind("<KeyRelease>", lambda e: self._apply_filter())
        attach_entry_context_menu(self.e_search)

        self.var_free_only = tk.BooleanVar(value=False)
        self.chk_free = tk.Checkbutton(
            filter_box, text="Text", variable=self.var_free_only,
            bg=bg_card, fg=fg_pri, selectcolor=in_bg, font=theme.font(0), command=self._apply_filter
        )
        self.chk_free.pack(side=tk.LEFT)

        self.lbl_count = tk.Label(filter_box, text="Text", font=theme.font(-1), bg=bg_card, fg=theme.get_color("fg_muted"))
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

        detail_box = tk.LabelFrame(pad, text="Text", font=theme.font(-1, "bold"), bg=bg_card, fg=fg_pri, padx=8, pady=6)
        detail_box.pack(fill=tk.X, pady=(6, 0))

        self.txt_details = tk.Text(detail_box, height=4, font=theme.font(-1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1, wrap=tk.WORD)
        self.txt_details.pack(fill=tk.X)
        self.txt_details.insert("1.0", "Text")
        self.txt_details.config(state=tk.DISABLED)

        btn_bar = tk.Frame(pad, bg=bg_main, pady=6)
        btn_bar.pack(fill=tk.X)

        tk.Button(
            btn_bar, text="Text", font=theme.font(0), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=12, command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_bar, text="Text", font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=14,
            command=self._on_select
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_bar, text="Text", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, command=self._copy_selection
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            btn_bar, text="Text", font=theme.font(-1), relief=tk.FLAT,
            bg=btn_bg, fg=fg_pri, padx=8, command=self._export_to_txt
        ).pack(side=tk.LEFT)

    def _start_fetch(self, target_url):
        self.lb_models.delete(0, tk.END)
        self.lbl_count.config(text="Text")
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

                if self.connection_mode == "socks5":
                    raw = self._socks5_request(target_url, headers, proxy_str=self.proxy, timeout=12, method="GET")
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
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            if method == "OPTIONS":
                allow = resp.headers.get("Allow", "Text")
                cors = resp.headers.get("Access-Control-Allow-Methods", "Text")
                return f"Text"
            return resp.read().decode("utf-8", errors="replace")

    def _socks5_request(self, url, headers, proxy_str, timeout=12, method="GET"):
        from data.core.templates.unified_engine import dechunk_http_body
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        p_host, p_port = proxy_str.split(":") if ":" in proxy_str else (proxy_str, 1080)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((p_host, int(p_port)))

        sock.sendall(b"\x05\x01\x00")
        if sock.recv(2) != b"\x05\x00":
            sock.close()
            raise ConnectionError("Text")

        d_bytes = host.encode("idna")
        req = bytearray(b"\x05\x01\x00\x03") + bytearray([len(d_bytes)]) + d_bytes + port.to_bytes(2, "big")
        sock.sendall(req)
        rep = sock.recv(10)
        if len(rep) < 4 or rep[1] != 0:
            sock.close()
            raise ConnectionError("Text")

        client = ssl.create_default_context().wrap_socket(sock, server_hostname=host) if parsed.scheme == "https" else sock
        lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", "Connection: close"]
        for k, v in headers.items():
            lines.append(f"{k}: {v}")
        client.sendall("\r\n".join(lines).encode("utf-8") + b"\r\n\r\n")

        chunks = []
        while True:
            try:
                b = client.recv(16384)
                if not b: break
                chunks.append(b)
            except socket.timeout:
                break
        client.close()

        raw = b"".join(chunks)
        sep = raw.find(b"\r\n\r\n")
        if sep == -1: return raw.decode("latin1", errors="replace")
        h_part = raw[:sep].decode("latin1", errors="replace")
        b_part = raw[sep+4:]

        if method == "OPTIONS":
            return h_part

        if "chunked" in h_part.lower():
            b_part = dechunk_http_body(b_part)
        return b_part.decode("utf-8", errors="replace")

    def _check_options(self):
        url = self.ent_url.get().strip()
        self.lbl_count.config(text="Text")
        def _worker():
            try:
                headers = {"User-Agent": "QTranslate-AI-Hub/2.0", "Accept": "*/*"}
                if self.connection_mode == "socks5":
                    info = self._socks5_request(url, headers, proxy_str=self.proxy, timeout=8, method="OPTIONS")
                else:
                    info = self._direct_request(url, headers, timeout=8, method="OPTIONS")
                self.after(0, lambda: messagebox.showinfo("Text", info, parent=self))
                self.after(0, lambda: self.lbl_count.config(text="Text"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Text", str(e), parent=self))
        threading.Thread(target=_worker, daemon=True).start()

    def _parse_models(self, raw_str):
        data = json.loads(raw_str)
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

        for item in items:
            if isinstance(item, str):
                models.append({"id": item, "context": None, "pricing": None, "desc": None})
            elif isinstance(item, dict):
                m_id = item.get("id") or item.get("name") or item.get("model")
                if m_id:
                    ctx = item.get("context_length")
                    pricing = item.get("pricing")
                    desc = item.get("description")
                    arch = item.get("architecture", {}).get("modality") if isinstance(item.get("architecture"), dict) else None
                    models.append({
                        "id": str(m_id).strip(),
                        "context": ctx,
                        "pricing": pricing,
                        "desc": desc,
                        "modality": arch
                    })

        return models

    def _on_fetch_success(self, parsed_models):
        self.models_data = parsed_models
        self._apply_filter()

    def _on_fetch_error(self, err_msg):
        self.lbl_count.config(text="Text")
        self.txt_details.config(state=tk.NORMAL)
        self.txt_details.delete("1.0", tk.END)
        self.txt_details.insert("1.0", f"Text")
        self.txt_details.config(state=tk.DISABLED)

    def _apply_filter(self):
        q = self.e_search.get().strip().lower()
        free_only = self.var_free_only.get()

        self.lb_models.delete(0, tk.END)
        self.displayed_items = []

        for m in self.models_data:
            m_id = m["id"]
            low = m_id.lower()
            is_free = ":free" in low or (isinstance(m.get("pricing"), dict) and str(m["pricing"].get("prompt")) == "0")

            if free_only and not is_free:
                continue
            if q and q not in low:
                continue

            self.displayed_items.append(m)
            prefix = "[FREE] " if is_free else ""
            self.lb_models.insert(tk.END, f"{prefix}{m_id}")

        self.lbl_count.config(text=f"Text")

    def _on_list_select(self, event=None):
        sel = self.lb_models.curselection()
        if not sel or sel[0] >= len(self.displayed_items):
            return
        m = self.displayed_items[sel[0]]

        lines = [f"Text"]
        if m.get("context"):
            ctx_val = int(m['context'])
            lines.append(f"Text")
        if isinstance(m.get("pricing"), dict):
            p = m["pricing"]
            lines.append(f"Text")
        if m.get("modality"):
            lines.append(f"Text")
        if m.get("desc"):
            lines.append(f"Text")

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

    def _export_to_txt(self):
        if not self.models_data:
            return
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "available_models_list.txt")
        out_path = os.path.abspath(out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Text")
            for m in self.models_data:
                f.write(f"- {m['id']}\n")
                if m.get("context"):
                    f.write(f"Text")
                if m.get("pricing"):
                    f.write(f"Text")
        open_file_in_smart_editor(out_path, self)

    def _bind_context_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Text", command=self._copy_selection)
        menu.add_command(label="Text", command=self._on_select)
        self.lb_models.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
