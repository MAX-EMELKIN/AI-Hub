# -*- coding: utf-8 -*-
"""
Модуль: data/main.py
Назначение: Главный оркестратор с системным Windows Mutex (100% защита от запуска дублей процессов),
            инициализацией консоли отладки, очисткой логов и запуском подсистем.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11
"""

import os
import sys
import ctypes
from ctypes import wintypes

# 1. СИСТЕМНЫЙ MUTEX (Защита от повторного запуска)
kernel32 = ctypes.windll.kernel32
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.GetLastError.restype = wintypes.DWORD

MUTEX_NAME = "Global\\QTranslate_AI_Hub_SingleInstance_Mutex"
_singleton_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

# 2. Корневой каталог программы
data_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(data_dir)

for path in [base_dir, data_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    os.chdir(base_dir)
except Exception:
    pass

from data.core.config_manager import config
from data.core.api_config import api_config
from data.core.logger import logger
from data.core.launcher import check_and_autostart_qtranslate
from data.core.server import start_server, stop_server
from data.core.cdp_client import browser_cdp
from data.services.base_service import load_all_services
from data.dictionary.glossary_engine import glossary_engine
from data.presets.preset_manager import preset_manager
from data.gui.main_window import MainWindow
from data.gui.tray_manager import TrayManager

def run():
    # 1. Проверка очистки старого лога и включение консоли
    logger.check_startup_cleanup()
    if config.get_bool("LOGGING", "showconsole", False):
        logger.show_console(True)

    print("=================================================================")
    print("  Инициализация QTranslate AI Hub...                             ")
    print(f"  Рабочий каталог: {base_dir}                                    ")
    print("=================================================================")

    logger.system("Старт приложения QTranslate AI Hub")

    # 2. Автозапуск QTranslate (если разрешено в config.ini)
    check_and_autostart_qtranslate()

    # 3. Сканируем и регистрируем сервисы
    load_all_services()

    # 4. Инициализируем глоссарий и пресеты
    glossary_engine.reload()
    preset_manager._ensure_default_presets()

    # 5. Запускаем локальный HTTP-сервер
    start_server(block=False)

    # 6. Главное окно GUI
    app = MainWindow()

    # 7. Очистка при выходе
    def _on_app_exit():
        print("\n[AI Hub]: Завершение работы...")
        logger.system("Завершение работы QTranslate AI Hub")
        stop_server()
        try:
            browser_cdp.close_browser()
        except Exception:
            pass
        try:
            app.destroy()
        except Exception:
            pass
        sys.exit(0)

    # 8. Системный трей
    tray = TrayManager(app, on_exit_callback=_on_app_exit)
    app.on_hide_to_tray = tray.toggle_window

    # 9. Запуск свернутым
    start_minimized = config.get_bool("GENERAL", "StartMinimized", default=True)
    if start_minimized:
        app.withdraw()
        print("[AI Hub]: Приложение готово и свернуто в трей.")
        logger.system("Приложение свернуто в трей")
    else:
        app.deiconify()

    # 10. Главный цикл Tkinter
    try:
        app.mainloop()
    except KeyboardInterrupt:
        _on_app_exit()

if __name__ == "__main__":
    run()