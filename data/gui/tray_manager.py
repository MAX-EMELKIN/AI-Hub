# -*- coding: utf-8 -*-
# data/gui/tray_manager.py
import os
import sys
import ctypes
import threading
from ctypes import wintypes

from data.core.config_manager import config
from data.core.i18n import t, i18n
from data.core.hotkey_manager import hotkey_manager
from data.core.logger import logger

if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT = ctypes.c_int64
    WPARAM = ctypes.c_uint64
    LPARAM = ctypes.c_int64
else:
    LRESULT = ctypes.c_long
    WPARAM = ctypes.c_uint
    LPARAM = ctypes.c_long

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('hWnd', wintypes.HWND),
        ('uID', wintypes.UINT),
        ('uFlags', wintypes.UINT),
        ('uCallbackMessage', wintypes.UINT),
        ('hIcon', wintypes.HICON),
        ('szTip', wintypes.WCHAR * 128)
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.UINT),
        ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HICON),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm', wintypes.HICON)
    ]

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = wintypes.HICON
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = wintypes.HMENU

user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.DestroyMenu.restype = wintypes.BOOL

user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = wintypes.UINT

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_DESTROY = 0x0002
WM_NULL = 0x0000

NIM_ADD = 0x00000000
NIM_MODIFY = 0x0001
NIM_DELETE = 0x0002
NIF_MESSAGE = 0x0001
NIF_ICON = 0x0002
NIF_TIP = 0x0004

WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008
MF_UNCHECKED = 0x0000
MF_POPUP = 0x0010
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

class TrayManager:
    def __init__(self, main_window, on_exit_callback=None):
        self.main_window = main_window
        self.on_exit = on_exit_callback
        self.hwnd = None
        self.hicon = None
        self._thread = None
        self._is_alive = True
        self._wndproc_ref = WNDPROC(self._wnd_proc)
        self._tray_lang_map = {}

        self._start_tray_thread()

    def _find_icon(self):
        try:
            h_inst = kernel32.GetModuleHandleW(None)
            h = user32.LoadIconW(h_inst, ctypes.cast(1, wintypes.LPCWSTR))
            if h:
                return h
        except Exception:
            pass

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates = [
            os.path.join(base_dir, "data", "gui", "AI_Hub.ico"),
            os.path.join(base_dir, "data", "AI_Hub.ico"),
            os.path.join(base_dir, "data", "gui", "icon.ico"),
            os.path.join(base_dir, "AI_Hub.ico")
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    h = user32.LoadImageW(None, path, 1, 16, 16, 0x0010)
                    if h:
                        return h
                except Exception:
                    pass

        try:
            return user32.LoadIconW(None, ctypes.cast(32512, wintypes.LPCWSTR))
        except Exception:
            return None

    def _start_tray_thread(self):
        def _loop():
            hinst = kernel32.GetModuleHandleW(None)
            class_name = f"QTranslateAIHubTray_{os.getpid()}"

            wndclass = WNDCLASSEXW()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wndclass.style = 0
            wndclass.lpfnWndProc = self._wndproc_ref
            wndclass.hInstance = hinst
            wndclass.lpszClassName = class_name

            user32.RegisterClassExW(ctypes.byref(wndclass))

            self.hwnd = user32.CreateWindowExW(
                0, class_name, "QTranslateAIHubTrayMsgWindow",
                0, 0, 0, 0, 0, None, None, hinst, None
            )

            self.hicon = self._find_icon()
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.hwnd
            nid.uID = 1001
            nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
            nid.uCallbackMessage = WM_TRAYICON
            nid.hIcon = self.hicon
            nid.szTip = "QTranslate AI Hub"

            shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            hotkey_manager.install_hook(self.main_window)

            msg = wintypes.MSG()
            while self._is_alive and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            hotkey_manager.uninstall_hook()
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            evt = lparam & 0xFFFF
            if evt in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.main_window.after(0, self.toggle_window)
                return 0
            elif evt == WM_RBUTTONUP:
                self._show_native_popup_menu()
                return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def toggle_window(self):
        try:
            if self.main_window.state() == "withdrawn" or not self.main_window.winfo_viewable():
                self.main_window.deiconify()
                self.main_window.lift()
                self.main_window.focus_force()
            else:
                if self.main_window.state() == "normal" and self.main_window.winfo_viewable():
                    self.main_window._save_current_geometry()
                self.main_window.withdraw()
        except Exception:
            pass

    def _show_native_popup_menu(self):
        hmenu = user32.CreatePopupMenu()

        try:
            is_vis = (self.main_window.state() != "withdrawn" and self.main_window.winfo_viewable())
        except Exception:
            is_vis = False

        show_str = t("tray_hide", "Скрыть в трей") if is_vis else t("tray_show", "Показать главное окно")
        user32.AppendMenuW(hmenu, MF_STRING, 1, show_str)
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        user32.AppendMenuW(hmenu, MF_STRING, 5, "Чат с ИИ")
        user32.AppendMenuW(hmenu, MF_STRING, 4, "Открыть браузер")
        user32.AppendMenuW(hmenu, MF_STRING, 2, "Снимок экрана (OCR)")
        user32.AppendMenuW(hmenu, MF_STRING, 3, "Озвучить буфер (TTS)")

        is_con = logger.is_console_visible()
        con_str = "Скрыть консоль отладки" if is_con else "Показать консоль отладки"
        user32.AppendMenuW(hmenu, MF_STRING, 6, con_str)

        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        lang_sub = user32.CreatePopupMenu()
        cur_cfg_lang = config.get_str("GENERAL", "UILanguage", "auto").lower()
        available_langs = i18n.get_available_languages()

        self._tray_lang_map.clear()
        for idx, (l_code, l_name) in enumerate(available_langs):
            cmd_id = 100 + idx
            self._tray_lang_map[cmd_id] = l_code

            is_checked = (l_code == cur_cfg_lang) or (l_code == "auto" and cur_cfg_lang == "auto")
            flags = MF_STRING | (MF_CHECKED if is_checked else MF_UNCHECKED)
            user32.AppendMenuW(lang_sub, flags, cmd_id, str(l_name))

        user32.AppendMenuW(hmenu, MF_POPUP, lang_sub, "Язык интерфейса")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        user32.AppendMenuW(hmenu, MF_STRING, 99, "Выход")

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(hmenu)

        self._handle_menu_action(cmd)

    def _handle_menu_action(self, cmd):
        if cmd == 1:
            self.main_window.after(0, self.toggle_window)
        elif cmd == 5:
            def _open_chat():
                try:
                    from data.gui.tool_windows import ChatWindow
                    ChatWindow(self.main_window)
                except Exception as e:
                    print(e)
            self.main_window.after(0, _open_chat)
        elif cmd == 4:
            def _open_br():
                try:
                    from data.core.cdp_client import browser_cdp
                    browser_cdp.open_browser_window("https://www.google.com")
                except Exception:
                    pass
            self.main_window.after(0, _open_br)
        elif cmd == 2:
            def _ocr():
                try:
                    from data.ocr.ocr_engine import ocr_engine
                    ocr_engine.snip_screen_interactive(self.main_window)
                except Exception:
                    pass
            self.main_window.after(0, _ocr)
        elif cmd == 3:
            def _tts():
                try:
                    from data.tts.tts_engine import tts_engine, grab_selection_from_target_hwnd
                    from data.core.hotkey_manager import window_tracker
                    if tts_engine.is_playing():
                        tts_engine.stop_speech()
                        return
                    text = grab_selection_from_target_hwnd(window_tracker.last_user_hwnd)
                    if text:
                        tts_engine.speak_text(text, lang=i18n.current_lang)
                except Exception:
                    pass
            self.main_window.after(0, _tts)
        elif cmd == 6:
            def _toggle_con():
                logger.toggle_console()
            self.main_window.after(0, _toggle_con)
        elif cmd in self._tray_lang_map:
            chosen_code = self._tray_lang_map[cmd]
            def _switch_lang():
                i18n.set_language(chosen_code)
                self.main_window.reload_entire_gui()
            self.main_window.after(0, _switch_lang)
        elif cmd == 99:
            try:
                if self.main_window.state() == "normal" and self.main_window.winfo_viewable():
                    self.main_window._save_current_geometry()
            except Exception:
                pass

            self.cleanup()
            if self.on_exit:
                self.main_window.after(0, self.on_exit)

    def cleanup(self):
        self._is_alive = False
        hotkey_manager.uninstall_hook()
        if self.hwnd:
            try:
                user32.PostMessageW(self.hwnd, WM_DESTROY, 0, 0)
            except Exception:
                pass
