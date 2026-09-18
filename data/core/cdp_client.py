# -*- coding: utf-8 -*-
# data/core/cdp_client.py
import os
import sys
import time
import json
import socket
import struct
import base64
import subprocess
import atexit
import threading
import ctypes
from ctypes import wintypes
import urllib.parse
import urllib.request
import urllib.error
from data.core.logger import logger

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_RESTORE = 9
SW_SHOW = 5
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SWP_ASYNCWINDOWPOS = 0x4000

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

if ctypes.sizeof(ctypes.c_void_p) == 8:
    GetWindowLong = user32.GetWindowLongPtrW
    SetWindowLong = user32.SetWindowLongPtrW
    GetWindowLong.restype = ctypes.c_void_p
    GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    SetWindowLong.restype = ctypes.c_void_p
    SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
else:
    GetWindowLong = user32.GetWindowLongW
    SetWindowLong = user32.SetWindowLongW
    GetWindowLong.restype = ctypes.c_long
    GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    SetWindowLong.restype = ctypes.c_long
    SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

class FastWebSocketClient:
    def __init__(self, ws_url, cdp_port=9222):
        self.ws_url = ws_url
        self.cdp_port = cdp_port
        self.is_alive = True
        parsed = urllib.parse.urlparse(ws_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or cdp_port
        self.path = parsed.path or "/"

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(4.0)
        self.sock.connect((self.host, self.port))
        self._handshake()
        self.sock.settimeout(0.04)

    def _handshake(self):
        sec_key = base64.b64encode(os.urandom(16)).decode('utf-8')
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://127.0.0.1:{self.cdp_port}\r\n\r\n"
        )
        self.sock.sendall(req.encode('utf-8'))
        resp = self.sock.recv(4096).decode('utf-8', errors='ignore')
        if " 101 " not in resp:
            self.is_alive = False
            raise Exception("WebSocket handshake failed")

    def send(self, data_str):
        if not self.is_alive:
            raise BrokenPipeError("Socket is dead")
        try:
            data = data_str.encode('utf-8')
            length = len(data)
            mask_key = os.urandom(4)
            masked_data = bytearray(length)

            for i in range(length):
                masked_data[i] = data[i] ^ mask_key[i % 4]

            frame = bytearray([0x81])
            if length <= 125:
                frame.append(0x80 | length)
            elif length <= 65535:
                frame.append(0x80 | 126)
                frame.extend(struct.pack("!H", length))
            else:
                frame.append(0x80 | 127)
                frame.extend(struct.pack("!Q", length))

            frame.extend(mask_key)
            frame.extend(masked_data)
            self.sock.sendall(frame)
        except Exception:
            self.is_alive = False
            raise

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    self.is_alive = False
                    return None
                buf.extend(chunk)
            except (socket.timeout, BlockingIOError):
                return None
            except Exception:
                self.is_alive = False
                return None
        return bytes(buf)

    def recv_frame(self):
        if not self.is_alive:
            return None
        try:
            head = self.sock.recv(2)
            if not head or len(head) < 2:
                if head == b"":
                    self.is_alive = False
                return None
            b1, b2 = head[0], head[1]
            if (b1 & 0x0F) == 0x8:
                self.is_alive = False
                return None

            is_masked = bool(b2 & 0x80)
            length = b2 & 0x7F
            if length == 126:
                ext = self._recv_exact(2)
                if not ext:
                    return None
                length = struct.unpack("!H", ext)[0]
            elif length == 127:
                ext = self._recv_exact(8)
                if not ext:
                    return None
                length = struct.unpack("!Q", ext)[0]

            mask = self._recv_exact(4) if is_masked else None
            payload = self._recv_exact(length)
            if payload is None:
                return None

            if is_masked and mask:
                payload = bytearray(payload)
                for i in range(len(payload)):
                    payload[i] ^= mask[i % 4]

            return payload.decode('utf-8', errors='ignore')
        except (socket.timeout, BlockingIOError):
            return None
        except Exception:
            self.is_alive = False
            return None

    def close(self):
        self.is_alive = False
        try:
            self.sock.close()
        except Exception:
            pass

class CDPBrowserManager:

    def __init__(self):
        self.base_dir = get_base_dir()
        self.browser_pid = None
        self._tab_clients = {}
        self._lock = threading.Lock()

    def _get_cdp_port(self):
        try:
            from data.core.config_manager import config
            return config.get_int("BROWSER", "CDPPort", 9222)
        except Exception:
            return 9222

    def _find_browser_executable(self):
        candidates = [
            os.path.join(self.base_dir, "browser", "engine", "chrome.exe"),
            os.path.join(self.base_dir, "browser", "engine", "Supermium", "chrome.exe"),
            os.path.join(self.base_dir, "browser", "engine", "prog", "chrome.exe"),
            os.path.join(self.base_dir, "browser", "chrome.exe"),
        ]
        for port_path in candidates:
            if os.path.exists(port_path):
                return os.path.abspath(port_path), "Supermium Portable"

        browser_dir = os.path.join(self.base_dir, "browser")
        if os.path.exists(browser_dir):
            for root, _, files in os.walk(browser_dir):
                for file in files:
                    if file.lower() in ("chrome.exe", "supermium.exe"):
                        return os.path.abspath(os.path.join(root, file)), "Supermium Portable"

        return None, "Не найден"

    def _clean_stale_profile_locks(self, profile_dir):
        if not os.path.exists(profile_dir):
            return
        for lock in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"]:
            p = os.path.join(profile_dir, lock)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        pref_path = os.path.join(profile_dir, "Default", "Preferences")
        if os.path.exists(pref_path):
            try:
                with open(pref_path, "r", encoding="utf-8", errors="ignore") as f:
                    pref_data = json.load(f)

                changed = False
                if "profile" in pref_data and isinstance(pref_data["profile"], dict):
                    if pref_data["profile"].get("exit_type") != "Normal":
                        pref_data["profile"]["exit_type"] = "Normal"
                        changed = True
                    if pref_data["profile"].get("exited_cleanly") is not True:
                        pref_data["profile"]["exited_cleanly"] = True
                        changed = True

                if changed:
                    with open(pref_path, "w", encoding="utf-8") as f:
                        json.dump(pref_data, f)
            except Exception:
                pass

    def _find_browser_windows(self):
        hwnds = []
        def _enum_proc(hwnd, lparam):
            if user32.IsWindow(hwnd):
                buf = (ctypes.c_wchar * 256)()
                user32.GetClassNameW(hwnd, buf, 256)
                c_name = buf.value.lower()
                if "chrome_widgetwin_1" in c_name:
                    hwnds.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)
        return hwnds

    def _find_browser_window_hwnd(self):
        hwnds = self._find_browser_windows()
        return hwnds[0] if hwnds else None

    def _hide_from_taskbar_and_screen(self, hwnd):
        if not hwnd or not user32.IsWindow(hwnd):
            return
        try:
            ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
            if ex_style is not None:
                new_style = (int(ex_style) & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
                SetWindowLong(hwnd, GWL_EXSTYLE, new_style)

            sw = user32.GetSystemMetrics(0)
            user32.SetWindowPos(
                hwnd, 0, sw + 2000, 100, 1150, 750,
                SWP_SHOWWINDOW | SWP_FRAMECHANGED | SWP_NOZORDER | SWP_ASYNCWINDOWPOS
            )
        except Exception as e:
            logger.browser_event(f"Ошибка скрытия окна: {e}")

    def _create_tab_safe(self, url):
        cdp_port = self._get_cdp_port()
        encoded_url = urllib.parse.quote(url, safe=':/?=')
        endpoint = f"http://127.0.0.1:{cdp_port}/json/new?{encoded_url}"
        logger.browser_event(f"Создание вкладки для URL: {url}")

        try:
            req = urllib.request.Request(endpoint, method="PUT")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code != 405:
                pass
        except Exception:
            pass

        try:
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.browser_event(f"Ошибка создания вкладки: {e}")

        return None

    def _prewarm_tabs(self):
        time.sleep(1.0)
        try:
            self.get_tab_client("chatgpt")
            self.get_tab_client("google")
            logger.browser_event("Вкладки ChatGPT и Google успешно прогреты в фоне")
            print("[CDP Browser]: Вкладки ChatGPT и Google успешно прогреты в фоне.")
        except Exception as e:
            logger.browser_event(f"Ошибка фонового прогрева вкладок: {e}")

    def ensure_browser_running(self):
        with self._lock:
            cdp_port = self._get_cdp_port()

            try:
                req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1)
                tabs = json.loads(req.read().decode('utf-8'))
                if tabs:
                    return True
            except Exception:
                pass

            browser_exe, name = self._find_browser_executable()
            if not browser_exe:
                err = "Браузер не найден в browser/engine/!"
                logger.browser_event(err)
                raise Exception(err)

            profile_dir = os.path.join(self.base_dir, "browser", "profile")
            os.makedirs(profile_dir, exist_ok=True)
            self._clean_stale_profile_locks(profile_dir)

            logger.browser_event(f"Запуск {name} на порту {cdp_port}")
            print(f"[CDP Browser]: Запуск {name} на порту {cdp_port}...")

            cmd = [
                browser_exe,
                f"--remote-debugging-port={cdp_port}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--hide-crash-restore-bubble",
                "--disable-infobars",
                "--disable-notifications",
                "--restore-last-session=false",
                "--disable-backgrounding-occluded-windows",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=CalculateNativeWinOcclusion",
                "--window-position=9999,9999",
                "--window-size=1200,800",
                "about:blank"
            ]

            proc = subprocess.Popen(cmd)
            self.browser_pid = proc.pid

            for _ in range(25):
                time.sleep(0.1)
                hwnds = self._find_browser_windows()
                if hwnds:
                    for h in hwnds:
                        self._hide_from_taskbar_and_screen(h)
                    break

            for _ in range(30):
                time.sleep(0.2)
                try:
                    req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1)
                    tabs = json.loads(req.read().decode('utf-8'))
                    if tabs:
                        logger.browser_event("Браузер готов к работе через CDP")
                        print("[CDP Browser]: Браузер готов к фоновому переводу.")
                        threading.Thread(target=self._prewarm_tabs, daemon=True).start()
                        return True
                except Exception:
                    pass

            err_msg = "Не удалось подключиться к порту CDP браузера."
            logger.browser_event(err_msg)
            raise Exception(err_msg)

    def get_tab_client(self, service_type="google"):
        self.ensure_browser_running()
        cdp_port = self._get_cdp_port()

        existing = self._tab_clients.get(service_type)
        if existing and existing.is_alive and existing.sock:
            return existing
        else:
            if existing:
                try:
                    existing.close()
                except Exception:
                    pass
                self._tab_clients.pop(service_type, None)

        url_map = {
            "google": ("google.com", "https://www.google.com/"),
            "chatgpt": ("chatgpt.com", "https://chatgpt.com/"),
            "deepl": ("deepl.com", "https://www.deepl.com/translator")
        }
        kw, default_url = url_map.get(service_type, ("google.com", "https://www.google.com/"))

        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1.5)
            tabs = json.loads(req.read().decode('utf-8'))
            page_tabs = [t for t in tabs if t.get('type') == 'page' and 'webSocketDebuggerUrl' in t]

            target_tab = None
            for t in page_tabs:
                if kw in t.get("url", ""):
                    target_tab = t
                    break

            if not target_tab:
                blank_tabs = [t for t in page_tabs if t.get("url", "") in ("about:blank", "about:blank/")]
                if blank_tabs and service_type == "google":
                    target_tab = blank_tabs[0]
                else:
                    target_tab = self._create_tab_safe(default_url)

            if target_tab and 'webSocketDebuggerUrl' in target_tab:
                client = FastWebSocketClient(target_tab['webSocketDebuggerUrl'], cdp_port=cdp_port)
                self._tab_clients[service_type] = client
                return client

        except Exception as e:
            logger.browser_event(f"Ошибка получения вкладки ({service_type}): {e}")

        return None

    def show_browser_window(self):
        self.ensure_browser_running()
        hwnd = self._find_browser_window_hwnd()
        if hwnd:
            try:
                ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
                if ex_style is not None:
                    new_style = (int(ex_style) & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
                    SetWindowLong(hwnd, GWL_EXSTYLE, new_style)

                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
                win_w, win_h = 1150, 750
                pos_x = max(20, (sw - win_w) // 2)
                pos_y = max(20, (sh - win_h) // 2)

                user32.SetWindowPos(
                    hwnd, 0, pos_x, pos_y, win_w, win_h,
                    SWP_SHOWWINDOW | SWP_FRAMECHANGED | SWP_ASYNCWINDOWPOS
                )
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                logger.browser_event("Окно браузера выведено по центру экрана")
            except Exception as e:
                logger.browser_event(f"Ошибка вывода окна браузера: {e}")

    def hide_browser_window(self):
        hwnds = self._find_browser_windows()
        for h in hwnds:
            self._hide_from_taskbar_and_screen(h)
        logger.browser_event("Окно браузера скрыто за физический край экрана")

    def toggle_browser_window(self):
        self.ensure_browser_running()
        hwnd = self._find_browser_window_hwnd()
        if not hwnd:
            return

        try:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            sw = user32.GetSystemMetrics(0)

            if rect.left < sw - 50:
                self.hide_browser_window()
                print("[CDP Browser]: Окно убрано за экран.")
            else:
                self.show_browser_window()
                print("[CDP Browser]: Окно выведено по центру экрана.")
        except Exception:
            pass

    def open_browser_window(self, url=None):
        self.show_browser_window()
        if url:
            srv = "chatgpt" if "chatgpt.com" in url else ("deepl" if "deepl.com" in url else "google")
            self.navigate_tab(srv, url)

    def send_tab_cdp_command(self, service_type, method, params=None, await_response=True):
        client = self.get_tab_client(service_type)
        if not client or not client.is_alive:
            return {}

        req_id = int(time.time() * 1000) % 1000000
        msg = {"id": req_id, "method": method, "params": params or {}}
        try:
            client.send(json.dumps(msg))
            if not await_response:
                return True
            t_start = time.time()
            while time.time() - t_start < 0.7:
                frame = client.recv_frame()
                if not frame:
                    time.sleep(0.01)
                    continue
                try:
                    data = json.loads(frame)
                    if data.get("id") == req_id:
                        return data.get("result", {})
                except Exception:
                    pass
        except Exception as e:
            logger.browser_event(f"Сбой отправки CDP команды {method}: {e}")
            self._tab_clients.pop(service_type, None)
        return {}

    def evaluate_js_on_tab(self, service_type, js_code):
        res = self.send_tab_cdp_command(service_type, "Runtime.evaluate", {
            "expression": js_code,
            "returnByValue": True,
            "awaitPromise": True
        })
        return res.get("result", {}).get("value", "")

    def navigate_tab(self, service_type, url):
        logger.browser_event(f"Навигация вкладки {service_type} -> {url}")
        self.send_tab_cdp_command(service_type, "Page.navigate", {"url": url}, await_response=False)

    def evaluate_js(self, js_code):
        return self.evaluate_js_on_tab("google", js_code)

    def navigate_url(self, url):
        self.navigate_tab("google", url)

    def close_browser(self):
        try:
            for client in list(self._tab_clients.values()):
                try:
                    client.close()
                except Exception:
                    pass
            self._tab_clients.clear()

            if self.browser_pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.browser_pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
                except Exception:
                    pass
                self.browser_pid = None

            profile_dir = os.path.join(self.base_dir, "browser", "profile")
            self._clean_stale_profile_locks(profile_dir)
            logger.browser_event("Браузер Supermium полностью остановлен")
        except Exception:
            pass

browser_cdp = CDPBrowserManager()
atexit.register(browser_cdp.close_browser)
