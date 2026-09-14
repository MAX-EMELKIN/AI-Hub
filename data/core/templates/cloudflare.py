# -*- coding: utf-8 -*-
"""
Модуль: data/core/templates/cloudflare.py
Назначение: Модульный шаблон генератора сервисов для Cloudflare Workers AI.
            Генерирует плагин с поддержкой моделей каталога Cloudflare (@cf/...),
            авторизацией через Account ID / API Token и интеграцией с logger.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

PROVIDER_KEY = "cloudflare"
PROVIDER_NAME = "Cloudflare Workers AI"
DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
DEFAULT_ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

def setup_config(api_config, slug, model_str):
    existing_acc = api_config.get_val("openai_120b", "account_id", "")
    existing_tok = api_config.get_val("openai_120b", "api_token", "")
    api_config.set_val(slug, "account_id", existing_acc)
    api_config.set_val(slug, "api_token", existing_tok)
    api_config.set_val(slug, "model", model_str or DEFAULT_MODEL)
    api_config.set_val(slug, "endpoint", DEFAULT_ENDPOINT)
    api_config.set_val(slug, "temperature", "0.1")
    api_config.set_val(slug, "top_p", "0.2")
    api_config.set_val(slug, "max_tokens", "3072")
    api_config.set_val(slug, "enable_thinking", "0")
    api_config.set_val(slug, "enable_glossary", "1")

PYTHON_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
Модуль: data/services/{SERVICE_ID_SLUG}/service.py
Назначение: Плагин {SERVICE_NAME} via Cloudflare Workers AI.
\"\"\"

import json
import time
import re
import urllib.request
import urllib.error
from data.services.base_service import BaseService
from data.core.logger import logger

class CustomService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="{SERVICE_ID_SLUG}",
            name="{SERVICE_NAME}",
            route_name="/{SERVICE_ID_SLUG}",
            icon_name="Service.png"
        )

    def get_config_fields(self):
        return [
            {"key": "account_id", "label": "Account ID:", "required": True},
            {"key": "api_token", "label": "API Token:", "required": True},
            {"key": "model", "label": "Модель (@cf/...):", "required": True},
            {"key": "endpoint", "label": "Шаблон URL:", "required": True}
        ]

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        ok, reason = self.is_ready()
        if not ok:
            return f"[{self.name}]: {reason}"

        account_id = self.get_config_val("account_id")
        api_token = self.get_config_val("api_token")
        model = self.get_config_val("model", "{MODEL_ID}")
        endpoint_template = self.get_config_val("endpoint", "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}")

        url = endpoint_template.replace("{account_id}", account_id).replace("{model}", model)

        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        t0 = time.time()
        if len(clean_input.split()) <= 2 and len(clean_input) < 15 and '\\n' not in clean_input:
            fast_res = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            if fast_res:
                return fast_res

        annotated_text, system_prompt = self.prepare_text_and_prompt(clean_input, src_lang=src_lang, trg_lang=trg_lang, preset=preset)

        try: temp_val = float(self.get_config_val("temperature", "0.1"))
        except Exception: temp_val = 0.1
        try: max_tokens_val = int(self.get_config_val("max_tokens", "3072"))
        except Exception: max_tokens_val = 3072
        enable_thinking = self.get_config_val("enable_thinking", "0") in ("1", "true", "yes")

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": annotated_text}
            ],
            "reasoning_effort": "medium" if enable_thinking else "low",
            "max_tokens": max_tokens_val,
            "temperature": temp_val
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        logger.api_payload(self.name, model, url, headers, payload)
        t_call = time.time()

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t_call
                raw_str = raw_bytes.decode("utf-8")
                data = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, model, elapsed, resp.status)

            if data.get("errors") and len(data["errors"]) > 0:
                err_msg = data["errors"][0].get("message", str(data["errors"][0]))
                return f"[Cloudflare Error: {err_msg}]"

            res = ""
            if data.get("result"):
                res = data["result"].get("response") or data["result"].get("output_text") or ""
                if not res and data["result"].get("choices") and len(data["result"]["choices"]) > 0:
                    res = data["result"]["choices"][0].get("message", {}).get("content", "")

            if not res:
                return f"[{self.name}: Пустой ответ сервера]"

            res = re.sub(r'<think>[\\s\\S]*?</think>', '', str(res), flags=re.IGNORECASE)
            res = re.sub(r'^(?:Here is the translation:?|Translation:?)\\s*(\\r?\\n)+', '', res, flags=re.IGNORECASE)

            final = self.clean_response(res)
            elapsed_total = round(time.time() - t0, 2)
            print(f"[{self.name} готов за {elapsed_total}с]: {final[:70]}...")
            return final if final else clean_input

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t_call
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.api_raw_response(self.name, he.code, elapsed, err_body)
            logger.api_summary(self.name, model, elapsed, he.code, note=f"HTTP Error {he.code}")
            return f"Ошибка {self.name} (HTTP {he.code}): {err_body[:200]}"
        except Exception as e:
            elapsed = time.time() - t_call
            logger.api_summary(self.name, model, elapsed, 0, note=f"Exception: {e}")
            return f"Ошибка {self.name}: {e}"

service = CustomService()
"""