# -*- coding: utf-8 -*-
"""
Модуль: data/batch/pipeline.py
Назначение: Фоновый конвейер пакетного перевода с гарантией работы строго выбранного сервиса,
            сохранением разметки, защитой кода и подробным логированием каждого блока.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import sys
import time
import threading

from data.batch.chunker import text_chunker
from data.batch.code_protector import code_protector
from data.services.base_service import LOADED_SERVICES
from data.core.logger import logger

class BatchPipeline:
    def __init__(self):
        self._thread = None
        self._is_running = False
        self._cancel_flag = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def is_active(self):
        return self._is_running

    def pause(self):
        self._pause_event.clear()
        logger.system("Пакетный перевод: приостановлен пользователем (Пауза)")

    def resume(self):
        self._pause_event.set()
        logger.system("Пакетный перевод: возобновлен пользователем")

    def cancel(self):
        self._cancel_flag = True
        self._pause_event.set()
        logger.system("Пакетный перевод: сигнал отмены процесса")

    def start_file_translation(self, input_file, output_file, service_id="bing",
                               src_lang="auto", trg_lang="ru", preset=None,
                               on_progress=None, on_complete=None, on_error=None):
        if self._is_running:
            err = "Пакетный перевод уже выполняется."
            logger.system(f"Пакетный перевод Ошибка: {err}")
            if on_error:
                on_error(err)
            return False

        self._cancel_flag = False
        self._pause_event.set()
        self._is_running = True

        def _worker():
            try:
                self._run_pipeline(
                    input_file=input_file,
                    output_file=output_file,
                    service_id=service_id,
                    src_lang=src_lang,
                    trg_lang=trg_lang,
                    preset=preset,
                    on_progress=on_progress,
                    on_complete=on_complete,
                    on_error=on_error
                )
            finally:
                self._is_running = False

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return True

    def _run_pipeline(self, input_file, output_file, service_id, src_lang, trg_lang, preset,
                      on_progress, on_complete, on_error):
        try:
            content, enc = text_chunker.read_file_safe(input_file)
            logger.system(f"Пакетный перевод: прочитан файл {os.path.basename(input_file)} (кодировка: {enc}, размер: {len(content)} симв.)")
        except Exception as e:
            err = f"Ошибка чтения файла: {e}"
            logger.system(f"Пакетный перевод: {err}")
            if on_error:
                on_error(err)
            return

        chunks = text_chunker.split_into_chunks(content)
        total_chunks = len(chunks)
        if total_chunks == 0:
            err = "Файл пуст или не содержит текста."
            logger.system(f"Пакетный перевод: {err}")
            if on_error:
                on_error(err)
            return

        service = None
        target = str(service_id).lower().strip().replace("/", "")
        for k, s in LOADED_SERVICES.items():
            if k.lower() == target or s.service_id.lower() == target or s.name.lower() == target:
                service = s
                break

        if not service:
            err = f"Выбранный сервис '{service_id}' не найден среди загруженных плагинов."
            logger.system(f"Пакетный перевод: {err}")
            if on_error:
                on_error(err)
            return

        try:
            from data.core.config_manager import config
            protect_code = config.get_bool("BATCH", "ProtectCode", True)
        except Exception:
            protect_code = True

        logger.system(
            f"Пакетный перевод: старт обработки {total_chunks} порций через {service.name} "
            f"({src_lang} -> {trg_lang}, защита кода: {'вкл' if protect_code else 'выкл'})"
        )

        translated_chunks = []

        for idx, chunk in enumerate(chunks):
            if self._cancel_flag:
                err = "Перевод был отменен пользователем."
                logger.system(f"Пакетный перевод: {err}")
                if on_error:
                    on_error(err)
                return

            self._pause_event.wait()

            tokens = {}
            text_to_translate = chunk

            if protect_code:
                text_to_translate, tokens = code_protector.mask(chunk)

            translated_part = ""
            for attempt in range(2):
                try:
                    translated_part = service.translate(
                        text=text_to_translate,
                        src_lang=src_lang,
                        trg_lang=trg_lang,
                        preset=preset
                    )
                    if translated_part and not translated_part.startswith("Ошибка") and not translated_part.startswith("[Bing Error"):
                        break
                except Exception as e:
                    logger.system(f"Пакетный перевод: сбой на порции {idx + 1} (попытка {attempt + 1}): {e}")
                    print(f"[Pipeline Chunk Error]: {e}")
                    time.sleep(0.5)

            if not translated_part or translated_part.startswith("Ошибка") or translated_part.startswith("[Bing Error"):
                logger.system(f"Пакетный перевод: порция {idx + 1} вернула ошибку, оставлен оригинал")
                translated_part = chunk

            if protect_code and tokens:
                translated_part = code_protector.restore(translated_part, tokens)

            translated_chunks.append(translated_part)

            percent = int(((idx + 1) / total_chunks) * 100)
            preview = translated_part[:120].replace('\n', ' ')
            logger.system(f"Пакетный перевод: порция {idx + 1}/{total_chunks} ({percent}%) переведена")

            if on_progress:
                on_progress(idx + 1, total_chunks, percent, preview)

            time.sleep(0.1)

        try:
            final_text = text_chunker.assemble(translated_chunks)
            text_chunker.write_file_safe(output_file, final_text, encoding="utf-8")
            logger.system(f"Пакетный перевод: успешно завершен и сохранен в {output_file}")
            if on_complete:
                on_complete(output_file)
        except Exception as e:
            err = f"Ошибка сохранения: {e}"
            logger.system(f"Пакетный перевод: {err}")
            if on_error:
                on_error(err)

batch_pipeline = BatchPipeline()