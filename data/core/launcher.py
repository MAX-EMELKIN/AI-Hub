# -*- coding: utf-8 -*-
"""
Модуль: data/core/launcher.py
Назначение: Проверка, автозапуск и автоматический перезапуск QTranslate.exe
            для мгновенного подхвата новых JS-кнопок без ручных действий.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import sys
import time
import subprocess
import ctypes
from ctypes import wintypes
from data.core.logger import logger

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_void_p),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_char * 260)
    ]

def is_process_running(exe_name):
    """Сверхбыстрая проверка работы процесса через системный WinAPI без мигания консолей."""
    exe_name_lower = exe_name.lower().encode('utf-8')
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

    if snapshot == -1:
        return False

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

    try:
        if kernel32.Process32First(snapshot, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.lower() == exe_name_lower:
                    kernel32.CloseHandle(snapshot)
                    return True
                if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                    break
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(snapshot)

    return False

def find_qtranslate_exe():
    """Ищет файл QTranslate.exe в корне проекта или родительских каталогах."""
    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, "QTranslate.exe"),
        os.path.join(os.path.dirname(base_dir), "QTranslate.exe"),
        os.path.join(base_dir, "qtranslate.exe")
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None

def launch_qtranslate():
    """Запускает QTranslate.exe в фоновом независимом режиме."""
    exe_path = find_qtranslate_exe()
    if not exe_path:
        logger.system("Launcher: QTranslate.exe не найден в папке приложения.")
        print("[Launcher]: QTranslate.exe не найден в папке приложения.")
        return False

    try:
        work_dir = os.path.dirname(exe_path)
        subprocess.Popen(
            [exe_path],
            cwd=work_dir,
            creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0x00000008) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200)
        )
        logger.system(f"Launcher: Успешно запущен QTranslate: {exe_path}")
        print(f"[Launcher]: Успешно запущен QTranslate: {exe_path}")
        return True
    except Exception as e:
        logger.system(f"Launcher Ошибка запуска QTranslate.exe: {e}")
        print(f"[Launcher Error]: Не удалось запустить QTranslate.exe: {e}")
        return False

def kill_qtranslate():
    """Принудительно останавливает процесс QTranslate.exe."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "QTranslate.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        logger.system("Launcher: Процесс QTranslate.exe завершен")
    except Exception:
        pass

def restart_qtranslate():
    """Автоматически перезапускает QTranslate для моментального подхвата новых кнопок."""
    logger.system("Launcher: Выполняется автоматический перезапуск QTranslate...")
    kill_qtranslate()
    time.sleep(0.4)
    return launch_qtranslate()

def check_and_autostart_qtranslate():
    """Проверяет настройки config.ini и стартует QTranslate при необходимости."""
    try:
        from data.core.config_manager import config
        auto_launch = config.get_bool("GENERAL", "AutoLaunchQTranslate", default=True)
    except Exception:
        auto_launch = True

    if not auto_launch:
        return

    if not is_process_running("QTranslate.exe"):
        print("[Launcher]: QTranslate не запущен. Выполняется автозапуск...")
        launch_qtranslate()
    else:
        print("[Launcher]: QTranslate.exe уже работает.")

def kill_stale_processes(names=None):
    """Снимает зависшие процессы перед запуском."""
    if names is None:
        names = ["chrome.exe", "msedge.exe", "GoogleAI_Bridge.exe"]
    for name in names:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception:
            pass