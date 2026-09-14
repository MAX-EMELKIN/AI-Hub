# -*- coding: utf-8 -*-
"""
Модуль: data/services/yandex/service.py
Назначение: Яндекс Переводчик с постоянной YU-сессией и srv=android,
            интегрированный с модулем логирования (logger) для отладки.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import json
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from data.services.base_service import BaseService
from data.core.logger import logger

class YandexService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="yandex",
            name="Yandex Translate",
            route_name="/yandex",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False

    def is_ready(self):
        return True, "Работает через шлюз Яндекс Android (без ключей)"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        if not text or not text.strip():
            return ""

        t0 = time.time()
        src = src_lang if (src_lang and src_lang != "auto") else ""
        trg = trg_lang or "ru"
        lang_pair = f"{src}-{trg}" if src else trg
        req_uuid = uuid.uuid4().hex

        url = f"https://translate.yandex.net/api/v1/tr.json/translate?uuid={req_uuid}&srv=android&lang={lang_pair}&reason=auto&format=text&yu=2210680511641235828"
        
        post_data = {"text": text}
        data_payload = urllib.parse.urlencode(post_data).encode("utf-8")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://translate.yandex.com/"
        }

        logger.api_payload(self.name, "Yandex API (Android)", url, headers, post_data)

        try:
            req = urllib.request.Request(url, data=data_payload, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t0
                raw_str = raw_bytes.decode("utf-8")
                raw_json = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, "Yandex API (Android)", elapsed, resp.status)

            res = ""
            if "text" in raw_json and isinstance(raw_json["text"], list):
                res = "\n".join(raw_json["text"])

            final = self.clean_response(res)
            print(f"[{self.name} готов за {elapsed:.2f}с]: {final[:70]}...")
            return final if final else text

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t0
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.api_raw_response(self.name, he.code, elapsed, err_body)
            logger.api_summary(self.name, "Yandex API (Android)", elapsed, he.code, note=f"HTTP Error {he.code}")
            
            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            return f"Ошибка Yandex: HTTP {he.code}"

        except Exception as e:
            elapsed = time.time() - t0
            logger.api_summary(self.name, "Yandex API (Android)", elapsed, 0, note=f"Ошибка: {e}")
            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            print(f"[❌ Yandex Error]: {e}")
            return f"Ошибка Yandex: {e}"

service = YandexService()