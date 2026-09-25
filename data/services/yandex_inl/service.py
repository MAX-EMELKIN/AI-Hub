# data/services/yandex_inl/service.py
# -*- coding: utf-8 -*-
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from data.services.base_service import BaseService, USER_AGENT
from data.core.logger import logger


class YandexInLService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="yandex_inl",
            name="YandexInL",
            route_name="/yandex_inl",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False
        self.supports_glossary = False

    def get_config_fields(self):
        return []

    def is_ready(self):
        return True, "Сервис YandexInL готов к работе"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        t0 = time.time()
        src = src_lang if src_lang and src_lang != "auto" else ""
        trg = trg_lang or "ru"
        lang_pair = f"{src}-{trg}" if src else trg

        params = {
            "lang": lang_pair,
            "text": clean_input,
            "format": "plain"
        }
        url = "https://translate.yandex.net/api/v1/tr.json/translate?" + urllib.parse.urlencode(params)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                raw_str = raw_bytes.decode("utf-8", errors="replace")
                data = json.loads(raw_str)

                if isinstance(data, dict) and "text" in data and isinstance(data["text"], list) and len(data["text"]) > 0:
                    res = "".join(data["text"]).strip()
                    elapsed = round(time.time() - t0, 2)
                    print(f"[{self.name} готов за {elapsed}с]: {res[:70]}...")
                    return res

                return clean_input
        except urllib.error.HTTPError as he:
            err_msg = f"[YandexInL Ошибка HTTP {he.code}]"
            logger.system(f"{self.name}: {err_msg}")
            fast = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            return fast or err_msg
        except Exception as e:
            err_msg = f"[YandexInL Ошибка соединения: {e}]"
            logger.system(f"{self.name}: {err_msg}")
            fast = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            return fast or err_msg


service = YandexInLService()