# data/ocr/ocr_engine.py
import os
import sys
import time
import ctypes
from ctypes import wintypes
import threading
import subprocess
from data.core.win_api import (
    user32, kernel32, EM_SETSEL, WM_PASTE, WM_KEYDOWN, WM_KEYUP, VK_RETURN,
    simulate_hardware_hotkey, put_clipboard_text, bring_window_to_front_safe
)
from data.core.logger import logger


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))


def is_window_of_qtranslate(hwnd):
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False
    h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
    if h_proc:
        try:
            name_buf = (ctypes.c_wchar * 260)()
            size = wintypes.DWORD(260)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, name_buf, ctypes.byref(size)):
                return os.path.basename(name_buf.value).lower() == "qtranslate.exe"
        except Exception:
            pass
        finally:
            kernel32.CloseHandle(h_proc)
    return False


def find_qtranslate_main_and_edit_controls():
    main_hwnd = None
    edits = []

    def _enum_windows(h, lp):
        nonlocal main_hwnd
        if user32.IsWindowVisible(h) and is_window_of_qtranslate(h):
            buf = (ctypes.c_wchar * 256)()
            user32.GetClassNameW(h, buf, 256)
            c_name = buf.value.lower()
            if "tool" not in c_name and "popup" not in c_name:
                main_hwnd = h
                return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum_windows), 0)
    if not main_hwnd:
        return None, []

    def _enum_children(child_h, lp):
        buf = (ctypes.c_wchar * 256)()
        user32.GetClassNameW(child_h, buf, 256)
        c_name = buf.value.lower()
        if "richedit" in c_name or "edit" in c_name:
            rect = wintypes.RECT()
            user32.GetWindowRect(child_h, ctypes.byref(rect))
            if (rect.bottom - rect.top) > 35:
                edits.append((rect.top, child_h))
        return True

    user32.EnumChildWindows(main_hwnd, WNDENUMPROC(_enum_children), 0)
    edits.sort(key=lambda x: x[0])
    return main_hwnd, [e[1] for e in edits]


class OCREngine:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.ocr_dir = os.path.join(self.base_dir, "data", "ocr")
        self.bin_dir = os.path.join(self.ocr_dir, "bin")
        self.models_dir = os.path.join(self.ocr_dir, "models")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.bin_dir, exist_ok=True)
        os.makedirs(os.path.join(self.models_dir, "cyrillic"), exist_ok=True)
        os.makedirs(os.path.join(self.models_dir, "medium"), exist_ok=True)

    def get_available_models(self):
        models = []
        if os.path.exists(self.models_dir):
            for item in os.listdir(self.models_dir):
                item_path = os.path.join(self.models_dir, item)
                if os.path.isdir(item_path):
                    models.append(item)
        if not models:
            models = ["cyrillic", "medium"]
        return models

    def get_active_model(self):
        try:
            from data.core.config_manager import config
            return config.get_str("OCR", "ActiveModel", "cyrillic").lower()
        except Exception:
            return "cyrillic"

    def set_active_model(self, model_name):
        try:
            from data.core.config_manager import config
            config.set_value("OCR", "ActiveModel", model_name.lower())
            logger.system(f"OCR: Установлена активная модель '{model_name}'")
            return True
        except Exception:
            return False

    def _find_ocr_executable(self):
        candidates = [
            "rt_ocr.exe", "nbocr.exe", "rust_paddle_ocr.exe",
            "PaddleOCR-json.exe", "RapidOCR-json.exe", "MnnOcr.exe", "ocr.exe"
        ]
        for name in candidates:
            p = os.path.join(self.bin_dir, name)
            if os.path.exists(p):
                return p
        if os.path.exists(self.bin_dir):
            for f in os.listdir(self.bin_dir):
                if f.lower().endswith(".exe"):
                    return os.path.join(self.bin_dir, f)
        return None

    def _find_model_files(self, model_name):
        candidate_dirs = [
            os.path.join(self.models_dir, model_name),
            self.models_dir,
            os.path.join(self.bin_dir, "models"),
            os.path.join(self.bin_dir, model_name),
            self.bin_dir
        ]
        det_f, rec_f, keys_f = None, None, None
        for target_dir in candidate_dirs:
            if not os.path.exists(target_dir):
                continue
            for f in os.listdir(target_dir):
                fl = f.lower()
                fp = os.path.abspath(os.path.join(target_dir, f))
                if not det_f and "det" in fl and (fl.endswith(".mnn") or fl.endswith(".onnx")):
                    det_f = fp
                elif not rec_f and ("rec" in fl or "cyr" in fl or "med" in fl) and (fl.endswith(".mnn") or fl.endswith(".onnx")):
                    rec_f = fp
                elif not keys_f and (fl.endswith(".txt") or "keys" in fl or "dict" in fl or "charset" in fl):
                    keys_f = fp
        return det_f, rec_f, keys_f

    def send_text_to_qtranslate(self, text):
        if not text or not text.strip():
            return
        clean_val = text.strip()
        if clean_val.startswith("Error") or "ошибка" in clean_val.lower():
            return

        ok = put_clipboard_text(clean_val)
        if not ok:
            logger.system("OCR Ошибка: Не удалось поместить текст в буфер обмена")
            print("[OCR Ошибка]: Не удалось записать текст в буфер обмена.")
            return

        logger.system(f"OCR: Распознанный текст помещен в буфер ({len(clean_val)} симв.): '{clean_val[:60]}...'")
        print(f"[OCR Буфер]: \"{clean_val}\" -> Текст помещен в буфер обмена")

        try:
            from data.core.config_manager import config
            summon_key = config.get_str("QTRANSLATE", "SummonHotkey", "F1").strip()
        except Exception:
            summon_key = "F1"

        logger.system(f"OCR: Отправка горячей клавиши '{summon_key}' в QTranslate")
        print(f"[OCR]: Отправка горячей клавиши '{summon_key}' в QTranslate...")
        simulate_hardware_hotkey(summon_key)

        main_hwnd, edits = None, []
        for _ in range(25):
            time.sleep(0.04)
            main_hwnd, edits = find_qtranslate_main_and_edit_controls()
            if main_hwnd and edits:
                break

        if main_hwnd and edits:
            bring_window_to_front_safe(main_hwnd)
            time.sleep(0.12)
            top_edit_hwnd = edits[0]
            user32.SendMessageW(top_edit_hwnd, EM_SETSEL, 0, -1)
            time.sleep(0.03)
            user32.SendMessageW(top_edit_hwnd, WM_PASTE, 0, 0)
            time.sleep(0.04)
            user32.PostMessageW(top_edit_hwnd, WM_KEYDOWN, VK_RETURN, 0)
            user32.PostMessageW(top_edit_hwnd, WM_KEYUP, VK_RETURN, 0)
            logger.system(f"OCR: Текст успешно вставлен в окно QTranslate (HWND: {top_edit_hwnd}) и запущен перевод")
            print("[OCR]: Текст успешно передан в QTranslate и отправлен на перевод.")
        else:
            logger.system("OCR: Окно ввода QTranslate не найдено, текст остался в буфере обмена")
            print("[OCR]: Текст сохранен в системном буфере обмена Windows.")

    def recognize_image_file(self, image_path, model_name=None):
        if not os.path.exists(image_path):
            return ""

        exe_path = self._find_ocr_executable()
        if not exe_path:
            err = "[OCR]: Исполняемый файл движка OCR не найден в каталоге data/ocr/bin/."
            logger.system(err)
            return err

        model = model_name or self.get_active_model()
        det_f, rec_f, keys_f = self._find_model_files(model)

        cmd = [exe_path, "-f", os.path.abspath(image_path)]
        if det_f:
            cmd.extend(["--det_model", det_f])
        if rec_f:
            cmd.extend(["--rec_model", rec_f])
        if keys_f:
            cmd.extend(["--charset", keys_f])

        logger.system(f"OCR: Запуск команды распознавания: {' '.join(cmd)}")
        print(f"[OCR]: Команда распознавания -> {' '.join(cmd)}")
        t0 = time.time()

        try:
            res = subprocess.run(
                cmd,
                input="\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=False,
                timeout=6.0,
                cwd=os.path.dirname(exe_path),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            )
            raw = res.stdout.strip()
            elapsed = time.time() - t0

            if "<OCR_RESULTS_BEGIN>" in raw:
                parts = raw.split("<OCR_RESULTS_BEGIN>")
                if len(parts) > 1:
                    sub = parts[1]
                    if "<OCR_RESULTS_END>" in sub:
                        raw = sub.split("<OCR_RESULTS_END>")[0]
                    else:
                        raw = sub

            clean_lines = []
            for line in raw.splitlines():
                l_strip = line.strip()
                if not l_strip:
                    continue
                l_low = l_strip.lower()
                if any(x in l_low for x in ["the device supports:", "press enter to exit", "usage:", "options:", "rt_ocr", "<ocr_results"]):
                    continue
                clean_lines.append(line.rstrip())

            result = "\n".join(clean_lines).strip()
            logger.system(f"OCR: Распознавание завершено за {elapsed:.2f}с, строк получено: {len(clean_lines)}")
            return result
        except Exception as e:
            err = f"Ошибка выполнения OCR: {e}"
            logger.system(f"OCR: {err}")
            return err

    def snip_screen_interactive(self, parent_tk):
        from data.ocr.screen_snipper import ScreenSnipper
        logger.system("OCR: Запуск экранного выделения области (Snipper)")

        def _on_cropped(crop_bmp_path):
            def _async_ocr():
                try:
                    text_res = self.recognize_image_file(crop_bmp_path)
                    if text_res and not text_res.startswith("Error") and not text_res.startswith("Ошибка"):
                        self.send_text_to_qtranslate(text_res)
                    else:
                        logger.system("OCR: Текст в выделенной области не обнаружен")
                        print("[OCR]: Текст в выделенной области не найден.")
                finally:
                    if os.path.exists(crop_bmp_path):
                        try:
                            os.remove(crop_bmp_path)
                        except Exception:
                            pass

            threading.Thread(target=_async_ocr, daemon=True).start()

        snipper = ScreenSnipper(on_cropped_callback=_on_cropped)
        snipper.start(parent_tk)


ocr_engine = OCREngine()