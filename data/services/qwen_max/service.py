# -*- coding: utf-8 -*-
# data/services/qwen_max/service.py
import json
import time
import re
import urllib.request
import urllib.error
from data.services.base_service import BaseService
from data.core.logger import logger

class QwenMaxService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="qwen_max",
            name="Qwen Max (Alibaba DashScope)",
            route_name="/qwen_max",
            icon_name="Service.png"
        )

    def get_config_fields(self):
        return [
            {"key": "api_key", "label": "DashScope API Key:", "required": True},
            {"key": "model", "label": "Модель:", "required": True},
            {"key": "endpoint", "label": "Эндпоинт (URL):", "required": True}
        ]

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        ok, reason = self.is_ready()
        if not ok:
            return f"[{self.name}]: {reason}"

        raw_api_key = self.get_config_val("api_key")
        api_key = re.sub(r'^(?:Key|Token|Bearer)\s+', '', str(raw_api_key), flags=re.IGNORECASE).strip()

        model = self.get_config_val("model", "qwen-max")
        endpoint = self.get_config_val(
            "endpoint",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
        )

        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        t0 = time.time()
        if len(clean_input.split()) <= 2 and len(clean_input) < 15 and '\n' not in clean_input:
            fast_res = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            if fast_res:
                return fast_res

        annotated_text, system_prompt = self.prepare_text_and_prompt(
            clean_input, src_lang=src_lang, trg_lang=trg_lang, preset=preset
        )

        try: temp_val = float(self.get_config_val("temperature", "0.1"))
        except Exception: temp_val = 0.1
        try: top_p_val = float(self.get_config_val("top_p", "0.3"))
        except Exception: top_p_val = 0.3
        try: max_tokens_val = int(self.get_config_val("max_tokens", "4096"))
        except Exception: max_tokens_val = 4096

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": annotated_text}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens_val,
            "temperature": temp_val,
            "top_p": top_p_val,
            "enable_thinking": False
        }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        logger.api_payload(self.name, model, endpoint, headers, payload)
        t_call = time.time()

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data_bytes, headers=headers)
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t_call
                raw_str = raw_bytes.decode("utf-8")
                data = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, model, elapsed, resp.status)

            if data.get("error"):
                err_msg = data["error"].get("message", str(data["error"]))
                return f"[DashScope Error: {err_msg}]"

            if not data.get("choices") or len(data["choices"]) == 0:
                return f"[{self.name}: Пустой ответ сервера]"

            msg = data["choices"][0].get("message", {})
            content = msg.get("content", "")

            content = re.sub(r'<think>[\s\S]*?</think>', '', str(content), flags=re.IGNORECASE)
            final = self.clean_response(content)

            elapsed_total = round(time.time() - t0, 2)
            print(f"[{self.name} готов за {elapsed_total}с]: {final[:70]}...")
            return final if final else clean_input

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t_call
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.api_raw_response(self.name, he.code, elapsed, err_body)
            logger.api_summary(self.name, model, elapsed, he.code, note=f"HTTP Error {he.code}")
            return f"Ошибка DashScope (HTTP {he.code}): {err_body[:200]}"
        except Exception as e:
            elapsed = time.time() - t_call
            logger.api_summary(self.name, model, elapsed, 0, note=f"Exception: {e}")
            return f"Ошибка Qwen Max: {e}"

service = QwenMaxService()

try:
    from data.core.server import register_service_route
    register_service_route("qwen_max", service.translate)
    register_service_route("/qwen_max", service.translate)
except Exception:
    pass
