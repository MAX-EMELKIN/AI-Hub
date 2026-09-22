# -*- coding: utf-8 -*-
# data/core/launcher.py

import os, sys, time, subprocess, ctypes
from ctypes import wintypes

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', '..'))

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * wintypes.MAX_PATH)
    ]

def get_running_processes():
    names = []
    if sys.platform != "win32":
        return names

    k32 = ctypes.windll.kernel32
    h_snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h_snap == -1 or h_snap == wintypes.HANDLE(-1).value:
        return names

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    if k32.Process32FirstW(h_snap, ctypes.byref(pe)):
        while True:
            names.append(pe.szExeFile)
            if not k32.Process32NextW(h_snap, ctypes.byref(pe)):
                break

    k32.CloseHandle(h_snap)
    return names

def is_process_running(process_name):
    target = process_name.lower().strip()
    for name in get_running_processes():
        if name.lower() == target:
            return True
    return False

def is_qtranslate_running():
    return is_process_running("QTranslate.exe")

def find_qtranslate_path():
    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, "QTranslate.exe"),
        os.path.join(base_dir, "..", "QTranslate.exe"),
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "QTranslate", "QTranslate.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "QTranslate", "QTranslate.exe")
    ]

    for p in candidates:
        norm_p = os.path.normpath(p)
        if os.path.exists(norm_p):
            return norm_p
    return ""

def kill_process(process_name):
    if sys.platform == "win32":
        try:
            cmd = f'taskkill /F /IM "{process_name}"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def kill_qtranslate():
    kill_process("QTranslate.exe")

def launch_qtranslate():
    qt_path = find_qtranslate_path()
    if qt_path and os.path.exists(qt_path):
        try:
            cwd = os.path.dirname(qt_path)
            subprocess.Popen([qt_path], cwd=cwd)
            return True
        except Exception as e:
            sys.stderr.write(f"Startup error QTranslate: {e}\n")
    return False

def start_qtranslate():
    return launch_qtranslate()

def check_and_autostart_qtranslate():
    try:
        if not is_qtranslate_running():
            return launch_qtranslate()
        return True
    except Exception as e:
        sys.stderr.write(f"Error Text check_and_autostart_qtranslate: {e}\n")
        return False

def restart_qtranslate():
    qt_path = find_qtranslate_path()
    if not qt_path:
        return False

    kill_qtranslate()
    time.sleep(0.5)

    return launch_qtranslate()

def set_autostart(enable=True):
    if sys.platform != "win32":
        return

    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "QTranslate_AI_Hub"

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                if getattr(sys, 'frozen', False):
                    exe_path = f'"{sys.executable}"'
                else:
                    main_py = os.path.join(get_base_dir(), "data", "main.py")
                    exe_path = f'"{sys.executable}" "{main_py}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
    except Exception as e:
        sys.stderr.write(f"Error Text Text: {e}\n")

def is_autostart_enabled():
    if sys.platform != "win32":
        return False

    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "QTranslate_AI_Hub"

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, app_name)
            return bool(val)
    except Exception:
        return False
