# data/core/logger.py
import ctypes
import json
import os
import re
import sys
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9
STD_OUTPUT_HANDLE = wintypes.DWORD(-11).value

kernel32.AllocConsole.restype = wintypes.BOOL
kernel32.FreeConsole.restype = wintypes.BOOL
kernel32.GetConsoleWindow.restype = wintypes.HWND
kernel32.SetConsoleTitleW.argtypes = [wintypes.LPCWSTR]
kernel32.SetConsoleTitleW.restype = wintypes.BOOL
kernel32.SetConsoleOutputCP.argtypes = [wintypes.UINT]
kernel32.SetConsoleOutputCP.restype = wintypes.BOOL
kernel32.SetConsoleCP.argtypes = [wintypes.UINT]
kernel32.SetConsoleCP.restype = wintypes.BOOL
kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
kernel32.GetStdHandle.restype = wintypes.HANDLE
kernel32.WriteConsoleW.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p
]
kernel32.WriteConsoleW.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))


class HubLogger:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.log_dir = os.path.join(self.base_dir, "data", "logs")
        self.log_file = os.path.join(self.log_dir, "hub_debug.log")
        self._lock = threading.Lock()
        self._console_allocated = False
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except Exception:
            pass

    def check_startup_cleanup(self):
        try:
            from data.core.config_manager import config
            if config.get_bool("LOGGING", "clearonstartup", True):
                if os.path.exists(self.log_file):
                    with open(self.log_file, "w", encoding="utf-8") as f:
                        f.write(f"--- QTranslate AI Hub Log Started: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
        except Exception:
            pass

    def _write_console_native(self, text):
        try:
            h_out = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            if h_out:
                chars_written = wintypes.DWORD()
                kernel32.WriteConsoleW(h_out, text, len(text), ctypes.byref(chars_written), None)
                return True
        except Exception:
            pass
        return False

    def alloc_console(self):
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            try:
                user32.ShowWindow(hwnd, SW_SHOW)
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return True

        ok = kernel32.AllocConsole()
        if ok:
            self._console_allocated = True
            try:
                kernel32.SetConsoleTitleW("QTranslate AI Hub — Консоль отладки")
            except Exception:
                pass

            try:
                if sys.getwindowsversion().major >= 10:
                    kernel32.SetConsoleOutputCP(65001)
                    kernel32.SetConsoleCP(65001)
            except Exception:
                pass

            try:
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
                sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
            except Exception:
                pass

            try:
                hwnd = kernel32.GetConsoleWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, SW_SHOW)
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

            banner = (
                "=================================================================\n"
                "  QTranslate AI Hub — Системная консоль логирования             \n"
                f"  Время старта: {time.strftime('%Y-%m-%d %H:%M:%S')}             \n"
                "=================================================================\n\n"
            )
            try:
                print(banner, end="", flush=True)
            except Exception:
                self._write_console_native(banner)
            return True
        return False

    def show_console(self, show=True):
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd and show:
            return self.alloc_console()
        if hwnd:
            try:
                cmd = SW_RESTORE if show else SW_HIDE
                user32.ShowWindow(hwnd, cmd)
                if show:
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return True
        return False

    def is_console_visible(self):
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return False
        try:
            return bool(user32.IsWindowVisible(hwnd))
        except Exception:
            return False

    def toggle_console(self):
        current = self.is_console_visible()
        self.show_console(not current)

    def is_enabled(self, category_key):
        try:
            from data.core.config_manager import config
            return config.get_bool("LOGGING", category_key, True)
        except Exception:
            return True

    def mask_sensitive(self, text):
        if not text:
            return ""
        s = str(text)
        s = re.sub(
            r'(Bearer\s+)([A-Za-z0-9_\-\.]{6})[A-Za-z0-9_\-\.]{8,}([A-Za-z0-9_\-\.]{4})',
            r'\1\2***\3',
            s
        )
        s = re.sub(
            r'(AIzaSy[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]{15,}([A-Za-z0-9_\-]{4})',
            r'\1***\2',
            s
        )
        s = re.sub(
            r'("(?:api_key|api_token)"\s*:\s*")([^"]{6})[^"]{8,}([^"]{4})(")',
            r'\1\2***\3\4',
            s
        )
        return s

    def _write_entry(self, level_tag, service_name, content):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        srv_tag = f"[{service_name}] " if service_name else ""
        header = f"[{timestamp}] [{level_tag}] {srv_tag}"
        formatted = f"{header}\n{content}\n"
        try:
            print(formatted, flush=True)
        except Exception:
            self._write_console_native(formatted + "\n")

        try:
            from data.core.config_manager import config
            file_enabled = config.get_bool("LOGGING", "logtofile", True)
        except Exception:
            file_enabled = True

        if file_enabled:
            with self._lock:
                try:
                    with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                        f.write(formatted + "\n")
                except Exception:
                    pass

    def api_summary(self, service_name, model, elapsed_sec, status_code, note=""):
        if not self.is_enabled("log_api_summary"):
            return
        status_str = f"HTTP {status_code}" if status_code else "OK"
        note_str = f" | {note}" if note else ""
        body = f"Модель: {model} | Время: {elapsed_sec:.2f}с | Статус: {status_str}{note_str}"
        self._write_entry("API_SUMMARY", service_name, body)

    def api_payload(self, service_name, model, endpoint, headers, payload):
        if not self.is_enabled("log_api_payload"):
            return
        safe_headers = {k: self.mask_sensitive(v) for k, v in headers.items()}
        try:
            payload_str = json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception:
            payload_str = str(payload)
        safe_payload_str = self.mask_sensitive(payload_str)
        body = (
            f"Эндпоинт: {endpoint}\n"
            f"Модель: {model}\n"
            f"Заголовки:\n{json.dumps(safe_headers, ensure_ascii=False, indent=2)}\n"
            f"Тело запроса:\n{safe_payload_str}"
        )
        self._write_entry("API_PAYLOAD", service_name, body)

    def api_raw_response(self, service_name, status_code, elapsed_sec, raw_body_str):
        if not self.is_enabled("log_api_raw_response"):
            return
        preview = str(raw_body_str).strip()
        try:
            parsed = json.loads(preview)
            formatted_body = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            formatted_body = preview
        body = (
            f"Статус: HTTP {status_code} | Время: {elapsed_sec:.2f}с\n"
            f"Сырой ответ сервера:\n{formatted_body}"
        )
        self._write_entry("API_RAW_RESPONSE", service_name, body)

    def tool_call(self, service_name, step_idx, tool_name, tool_args, tool_result):
        if not self.is_enabled("log_tools"):
            return
        body = (
            f"Шаг агента: {step_idx}\n"
            f"Вызов инструмента: {tool_name}\n"
            f"Аргументы: {json.dumps(tool_args, ensure_ascii=False)}\n"
            f"Результат выполнения:\n{str(tool_result)[:600]}"
        )
        self._write_entry("AGENT_TOOL", service_name, body)

    def glossary_match(self, service_name, matched_pairs):
        if not self.is_enabled("log_glossary"):
            return
        lines = [f"  * '{k}' -> '{v}'" for k, v in matched_pairs]
        body = f"Подставлено терминов глоссария: {len(matched_pairs)}\n" + "\n".join(lines)
        self._write_entry("GLOSSARY", service_name, body)

    def text_filtering(self, service_name, stage_desc, raw_text, cleaned_text):
        if not self.is_enabled("log_filtering"):
            return
        body = (
            f"Этап: {stage_desc}\n"
            f"Исходный текст:\n{str(raw_text)}\n"
            f"Очищенный текст:\n{str(cleaned_text)}"
        )
        self._write_entry("FILTERING", service_name, body)

    def qtranslate_request(self, route, src_lang, trg_lang, text_preview):
        if not self.is_enabled("log_qtranslate"):
            return
        body = (
            f"Маршрут: {route}\n"
            f"Направление: {src_lang} -> {trg_lang}\n"
            f"Фрагмент текста ({len(text_preview)} симв.): {text_preview[:120]}..."
        )
        self._write_entry("QTRANSLATE", "", body)

    def browser_event(self, event_description):
        if not self.is_enabled("log_browser"):
            return
        self._write_entry("BROWSER_CDP", "", event_description)

    def system(self, message):
        self._write_entry("SYSTEM", "", message)


logger = HubLogger()