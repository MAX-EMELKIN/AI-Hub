# -*- coding: utf-8 -*-
# data/services/yandex_inl/service.py
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from data.services.base_service import BaseService
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

    def is_ready(self):
        return True, "Text Text Text-Text Text Text (Text Text)"

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        if not text or not text.strip():
            return ""

        t0 = time.time()
        trg = trg_lang or "ru"

        url = "https://api.browser.yandex.com/instaserp/translate"
        post_data = {
            "text": text,
            "brandID": "int",
            "statLang": trg,
            "targetLang": "auto",
            "locale": trg,
            "clid": "2270494",
            "disable": "serp",
            "use_llm_srv": "0"
        }
        encoded_data = urllib.parse.urlencode(post_data).encode("utf-8")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36"
        }

        logger.api_payload(self.name, "YandexInL API", url, headers, post_data)

        try:
            req = urllib.request.Request(url, data=encoded_data, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t0
                raw_str = raw_bytes.decode("utf-8")
                data = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, "YandexInL API", elapsed, resp.status)

            res = ""
            if isinstance(data, list) and len(data) > 0:
                res = data[0].get("text", "")
            elif isinstance(data, dict):
                res = data.get("text", "")

            final = self.clean_response(res)
            print(f"[{self.name} Text Text {elapsed:.2f}Text]: {final[:70]}...")
            return final if final else text

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t0
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.api_raw_response(self.name, he.code, elapsed, err_body)
            logger.api_summary(self.name, "YandexInL API", elapsed, he.code, note=f"HTTP Error {he.code}")

            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            return f"Error YandexInL: HTTP {he.code}"

        except Exception as e:
            elapsed = time.time() - t0
            logger.api_summary(self.name, "YandexInL API", elapsed, 0, note=f"Error: {e}")

            fast = self.fetch_fast_word(text, src=src_lang, trg=trg_lang)
            if fast: return fast
            print(f"[❌ YandexInL Error]: {e}")
            return f"Error YandexInL: {e}"

service = YandexInLService()
