# data/services/bing/service.py
# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from data.services.base_service import BaseService, USER_AGENT
from data.core.logger import logger


class BingService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="bing",
            name="Bing Translator",
            route_name="/bing",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False
        self.supports_glossary = False

    def get_config_fields(self):
        return []

    def is_ready(self):
        return True, "Сервис Bing Translator готов к работе"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        from_lang = src_lang if src_lang and src_lang != "auto" else "auto-detect"
        to_lang = trg_lang if trg_lang and trg_lang != "auto" else "ru"

        if to_lang == "zh-cn":
            to_lang = "zh-Hans"
        elif to_lang == "zh-tw":
            to_lang = "zh-Hant"

        url = "https://www.bing.com/ttranslatev3"
        payload = {
            "text": clean_input,
            "fromLang": from_lang,
            "to": to_lang
        }
        data_encoded = urllib.parse.urlencode(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://www.bing.com/translator"
        }

        try:
            req = urllib.request.Request(url, data=data_encoded, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                raw_str = raw_bytes.decode("utf-8", errors="replace")
                data = json.loads(raw_str)

                if isinstance(data, list) and len(data) > 0:
                    translations = data[0].get("translations", [])
                    if translations and len(translations) > 0:
                        res = translations[0].get("text", "")
                        return str(res).strip()

                return clean_input
        except urllib.error.HTTPError as he:
            err_msg = f"[Bing Ошибка HTTP {he.code}]"
            logger.system(f"{self.name}: {err_msg}")
            return err_msg
        except Exception as e:
            err_msg = f"[Bing Ошибка соединения: {e}]"
            logger.system(f"{self.name}: {err_msg}")
            return err_msg


service = BingService()