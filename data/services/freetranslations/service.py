# -*- coding: utf-8 -*-
# data/services/freetranslations/service.py
import json
import time
import re
import urllib.request
from data.services.base_service import BaseService
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

    def is_ready(self):
        return True, "Text Text FreeTranslations / Google PA (Text Text)"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        if not text or not text.strip():
            return ""

        t0 = time.time()
        src = src_lang if (src_lang and src_lang != "auto") else "auto"
        trg = trg_lang or "ru"

        formatted_input = re.sub(r'\r?\n', '<br>\u200C', text)

        url = "https://translate-pa.googleapis.com/v1/translateHtml"
        payload = [[[formatted_input], src, trg], "te"]

        headers = {
            "Content-Type": "application/json+protobuf; charset=utf-8",
            "X-goog-api-key": "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520",
            "Origin": "https://www.freetranslations.org",
            "Referer": "https://www.freetranslations.org/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        logger.api_payload(self.name, "Google PA API", url, headers, payload)

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t0
                raw_str = raw_bytes.decode("utf-8")
                data = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, "Google PA API", elapsed, resp.status)

            res = ""
            if data and isinstance(data, list) and len(data) > 0 and data[0] and data[0][0]:
                raw_html = data[0][0]
                raw_html = re.sub(r'\s*<\/?br[^>]*>(?:\u200C|&#8204;|&zwnj;)?\s*', '\n', raw_html, flags=re.IGNORECASE)
                raw_html = re.sub(r'[\u200C\ufeff]', '', raw_html)
                res = raw_html

            final = self.clean_response(res)
            print(f"[{self.name} Text Text {elapsed:.2f}Text]: {final[:70]}...")
            return final if final else text

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t0
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.api_raw_response(self.name, he.code, elapsed, err_body)
            logger.api_summary(self.name, "Google PA API", elapsed, he.code, note=f"HTTP Error {he.code}")

            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            return f"Error FreeTranslations: HTTP {he.code}"

        except Exception as e:
            elapsed = time.time() - t0
            logger.api_summary(self.name, "Google PA API", elapsed, 0, note=f"Error: {e}")

            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            print(f"[❌ FreeTranslations Error]: {e}")
            return f"Error FreeTranslations: {e}"

service = FreeTranslationsService()
