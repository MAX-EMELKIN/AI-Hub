# -*- coding: utf-8 -*-
# data/services/bing/service.py
import json
import time
import re
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from data.services.base_service import BaseService
from data.core.logger import logger

BING_MAX_CHUNK = 850

class BingTranslatorService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="bing",
            name="Bing Translator",
            route_name="/bing",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False
        self._ig = ""
        self._iid = "translator.5027"
        self._key = ""
        self._token = ""
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._last_auth_time = 0

    def is_ready(self):
        return True, "Работает через сессионный веб-шлюз Bing Translator (без ключей)"

    def _refresh_session(self):
        url = "https://www.bing.com/translator"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with self._opener.open(req, timeout=10.0) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            m_ig = re.search(r'IG:"([A-Fa-f0-9]+)"', html) or re.search(r'\"ig\":\"(.*?)\"', html) or re.search(r'data-ig="([^"]+)"', html)
            if m_ig:
                self._ig = m_ig.group(1)

            m_iid = re.findall(r'data-iid="([^"]+)"', html)
            if m_iid:
                self._iid = m_iid[-1]

            m_helper = re.search(r'params_AbusePreventionHelper\s*=\s*\[\s*(\d+)\s*,\s*"([^"]+)"', html)
            if not m_helper:
                m_helper = re.search(r'\[\s*(\d{10,15})\s*,\s*"([A-Za-z0-9+/=_\-]+)"', html)

            if m_helper:
                self._key = m_helper.group(1)
                self._token = m_helper.group(2)
                self._last_auth_time = time.time()
                logger.system("Bing Translator: сессионные токены успешно обновлены")
                return True
        except Exception as e:
            logger.system(f"Bing Translator: ошибка обновления токенов сессии: {e}")
        return False

    def _split_into_bing_chunks(self, text, max_len=850):
        if len(text) <= max_len:
            return [text]

        lines = text.split('\n')
        chunks = []
        cur_lines = []
        cur_len = 0

        for line in lines:
            line_len = len(line) + 1
            if cur_len + line_len > max_len and cur_lines:
                chunks.append("\n".join(cur_lines))
                cur_lines = [line]
                cur_len = line_len
            else:
                cur_lines.append(line)
                cur_len += line_len

        if cur_lines:
            chunks.append("\n".join(cur_lines))

        final_chunks = []
        for ch in chunks:
            if len(ch) <= max_len:
                final_chunks.append(ch)
            else:
                sentences = re.split(r'(?<=[.!?…])\s+', ch)
                s_cur = []
                s_len = 0
                for s in sentences:
                    if s_len + len(s) + 1 > max_len and s_cur:
                        final_chunks.append(" ".join(s_cur))
                        s_cur = [s]
                        s_len = len(s)
                    else:
                        s_cur.append(s)
                        s_len += len(s) + 1
                if s_cur:
                    final_chunks.append(" ".join(s_cur))

        return final_chunks

    def _translate_single_chunk(self, chunk_text, src, trg):
        url = f"https://www.bing.com/ttranslatev3?isVertical=1&&IG={self._ig}&IID={self._iid}"

        post_data = {
            "text": chunk_text,
            "fromLang": src,
            "to": trg,
            "token": self._token,
            "key": self._key,
            "tryFetchingGenderDebiasedTranslations": "true"
        }
        encoded_data = urllib.parse.urlencode(post_data).encode("utf-8")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.bing.com/translator",
            "Origin": "https://www.bing.com",
            "Accept": "*/*"
        }

        logger.api_payload(self.name, "Bing v3", url, headers, post_data)
        t_call = time.time()

        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=encoded_data, headers=headers)
                with self._opener.open(req, timeout=12.0) as resp:
                    raw_bytes = resp.read()
                    elapsed = time.time() - t_call
                    raw_str = raw_bytes.decode("utf-8")
                    raw_json = json.loads(raw_str)

                    logger.api_raw_response(self.name, resp.status, elapsed, raw_str)

                if isinstance(raw_json, list) and len(raw_json) > 0:
                    translations = raw_json[0].get("translations", [])
                    if translations:
                        return "".join(t_item.get("text", "") for t_item in translations)
            except Exception as e:
                elapsed = time.time() - t_call
                logger.api_summary(self.name, "Bing v3", elapsed, 0, note=f"Ошибка куска: {e}")
                self._refresh_session()
                time.sleep(0.3)

        return chunk_text

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        if not text or not text.strip():
            return ""

        t0 = time.time()
        if (time.time() - self._last_auth_time > 500) or not self._token or not self._ig:
            self._refresh_session()

        src = src_lang if (src_lang and src_lang != "auto") else "auto-detect"
        trg = trg_lang or "ru"
        if trg == "zh-CN":
            trg = "zh-Hans"
        if trg == "zh-TW":
            trg = "zh-Hant"

        sub_chunks = self._split_into_bing_chunks(text, max_len=BING_MAX_CHUNK)
        translated_parts = []

        for ch in sub_chunks:
            part_res = self._translate_single_chunk(ch, src, trg)
            translated_parts.append(part_res)

        final = "\n".join(translated_parts) if '\n' in text else " ".join(translated_parts)
        final = self.clean_response(final)

        elapsed = round(time.time() - t0, 2)
        logger.api_summary(self.name, "Bing v3", elapsed, 200, note=f"{len(sub_chunks)} микро-порций")
        print(f"[{self.name} готов за {elapsed}с ({len(sub_chunks)} микро-порций)]: {final[:70]}...")
        return final if final else text

service = BingTranslatorService()
