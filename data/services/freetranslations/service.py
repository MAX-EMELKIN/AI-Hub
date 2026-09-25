# data/services/freetranslations/service.py
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


class FreeTranslationsService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="freetranslations",
            name="FreeTranslations",
            route_name="/freetranslations",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False
        self.supports_glossary = False

    def get_config_fields(self):
        return []

    def is_ready(self):
        return True, "Сервис FreeTranslations готов к работе"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        from_lang = src_lang if src_lang and src_lang != "auto" else "auto"
        to_lang = trg_lang if trg_lang and trg_lang != "auto" else "ru"

        url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode({
            "client": "gtx",
            "sl": from_lang,
            "tl": to_lang,
            "dt": "t",
            "q": clean_input
        })

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                raw_str = raw_bytes.decode("utf-8", errors="replace")
                data = json.loads(raw_str)

                if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                    translated_parts = [p[0] for p in data[0] if p and len(p) > 0 and p[0]]
                    if translated_parts:
                        return "".join(translated_parts).strip()

                return clean_input
        except urllib.error.HTTPError as he:
            err_msg = f"[FreeTranslations Ошибка HTTP {he.code}]"
            logger.system(f"{self.name}: {err_msg}")
            return err_msg
        except Exception as e:
            err_msg = f"[FreeTranslations Ошибка: {e}]"
            logger.system(f"{self.name}: {err_msg}")
            return err_msg


service = FreeTranslationsService()