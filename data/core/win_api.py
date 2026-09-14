# -*- coding: utf-8 -*-
"""
Модуль: data/core/win_api.py
Назначение: Системные функции WinAPI, константы сообщений (SetWindowTextW, EM_SETSEL, WM_PASTE),
            безопасная работа с буфером обмена и окнами на Windows 7 32-bit (x86) и 64-bit (x64).
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64)
"""

import os
import sys
import time
import re
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
winmm = ctypes.windll.winmm
shell32 = ctypes.windll.shell32

if ctypes.sizeof(ctypes.c_void_p) == 8:
    LRESULT = ctypes.c_int64
    WPARAM = ctypes.c_uint64
    LPARAM = ctypes.c_int64
    ULONG_PTR = ctypes.c_uint64
    C_HANDLE = ctypes.c_void_p
else:
    LRESULT = ctypes.c_long
    WPARAM = ctypes.c_uint
    LPARAM = ctypes.c_long
    ULONG_PTR = ctypes.c_ulong
    C_HANDLE = ctypes.c_void_p

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ULONG_PTR)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)
    ]

class _INPUTunion(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', _INPUTunion)]

LP_INPUT = ctypes.POINTER(INPUT)

user32.SendInput.argtypes = [wintypes.UINT, LP_INPUT, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = C_HANDLE

user32.SetForegroundWindow.argtypes = [C_HANDLE]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [C_HANDLE, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.IsWindow.argtypes = [C_HANDLE]
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [C_HANDLE]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = C_HANDLE

user32.GetWindowThreadProcessId.argtypes = [C_HANDLE, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.SendMessageW.argtypes = [C_HANDLE, wintypes.UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT

user32.PostMessageW.argtypes = [C_HANDLE, wintypes.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

# Прямая нативная функция установки текста в окна Windows без сбоев типов
user32.SetWindowTextW.argtypes = [C_HANDLE, wintypes.LPCWSTR]
user32.SetWindowTextW.restype = wintypes.BOOL

user32.GetClassNameW.argtypes = [C_HANDLE, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [C_HANDLE, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetWindowRect.argtypes = [C_HANDLE, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = C_HANDLE

kernel32.QueryFullProcessImageNameW.argtypes = [C_HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [C_HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = C_HANDLE
kernel32.GlobalLock.argtypes = [C_HANDLE]
kernel32.GlobalLock.restype = C_HANDLE
kernel32.GlobalUnlock.argtypes = [C_HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL

user32.OpenClipboard.argtypes = [C_HANDLE]
user32.OpenClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = C_HANDLE
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, C_HANDLE]
user32.SetClipboardData.restype = C_HANDLE
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.GetClipboardSequenceNumber.argtypes = []
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD

user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
user32.keybd_event.restype = None

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

# Системные сообщения Win32
WM_SETTEXT = 0x000C
EM_SETSEL = 0x00B1
WM_PASTE = 0x0302
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D

VK_MAP = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "menu": 0x12, "win": 0x5B,
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "q": 0x51, "w": 0x57, "e": 0x45, "r": 0x52, "t": 0x54, "y": 0x59, "u": 0x55,
    "i": 0x49, "o": 0x4F, "p": 0x50, "a": 0x41, "s": 0x53, "d": 0x44, "f": 0x46,
    "g": 0x47, "h": 0x48, "j": 0x4A, "k": 0x4B, "l": 0x4C, "z": 0x5A, "x": 0x58,
    "c": 0x43, "v": 0x56, "b": 0x42, "n": 0x4E, "m": 0x4D,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39, "0": 0x30
}

def send_key_event(vk, is_up=False):
    scan = user32.MapVirtualKeyW(vk, 0)
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.wScan = scan
    inp.union.ki.dwFlags = KEYEVENTF_KEYUP if is_up else 0
    user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(INPUT))

def simulate_hardware_hotkey(hotkey_str):
    h = str(hotkey_str).strip().lower()

    if h in ("double_ctrl", "ctrl+ctrl", "ctrl ctrl", "2xctrl", "двойной ctrl"):
        send_key_event(0x11, False)
        send_key_event(0x11, True)
        time.sleep(0.04)
        send_key_event(0x11, False)
        send_key_event(0x11, True)
        return

    if h in ("double_alt", "alt+alt", "alt alt"):
        send_key_event(0x12, False)
        send_key_event(0x12, True)
        time.sleep(0.04)
        send_key_event(0x12, False)
        send_key_event(0x12, True)
        return

    tokens = [k.strip() for k in re.split(r'[\+\s\-]+', h) if k.strip()]
    vk_codes = [VK_MAP.get(k) for k in tokens if k in VK_MAP]

    if not vk_codes:
        vk_codes = [0x70]

    for code in vk_codes:
        send_key_event(code, False)
    time.sleep(0.04)
    for code in reversed(vk_codes):
        send_key_event(code, True)

def put_clipboard_text(text):
    """Гарантированная запись Unicode-текста в буфер обмена Windows."""
    if not text: return False
    text_bytes = (text + "\x00").encode('utf-16-le')
    size_bytes = len(text_bytes)

    for _ in range(10):
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, size_bytes)
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    if ptr:
                        ctypes.memmove(ptr, text_bytes, size_bytes)
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                        return True
            finally:
                user32.CloseClipboard()
        time.sleep(0.02)
    return False

def read_clipboard_text():
    text = ""
    for _ in range(6):
        if user32.OpenClipboard(None):
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if h_data:
                    ptr = kernel32.GlobalLock(h_data)
                    if ptr:
                        try:
                            text = ctypes.wstring_at(ptr).strip()
                        finally:
                            kernel32.GlobalUnlock(h_data)
                        if text: break
            finally:
                user32.CloseClipboard()
        time.sleep(0.02)
    return text

def bring_window_to_front_safe(hwnd):
    if not hwnd or not user32.IsWindow(hwnd):
        return False

    hwnd_fore = user32.GetForegroundWindow()
    own_tid = kernel32.GetCurrentThreadId()
    fore_tid = user32.GetWindowThreadProcessId(hwnd_fore, None)
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)

    if fore_tid and fore_tid != own_tid:
        user32.AttachThreadInput(own_tid, fore_tid, True)
    if target_tid and target_tid != own_tid:
        user32.AttachThreadInput(own_tid, target_tid, True)

    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        return True
    finally:
        if target_tid and target_tid != own_tid:
            user32.AttachThreadInput(own_tid, target_tid, False)
        if fore_tid and fore_tid != own_tid:
            user32.AttachThreadInput(own_tid, fore_tid, False)