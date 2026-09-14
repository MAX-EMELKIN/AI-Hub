# -*- coding: utf-8 -*-
"""
Модуль: data/core/api_config.py
Назначение: Управление api_keys.ini, расположенным внутри папки data/.
            Включает параметры моделей Gemini, DoH SmartDNS, прокси, Google Search Grounding
            и настраиваемый поисковый промпт.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64)
"""

import os
import sys
import shutil
import configparser
from data.core.web_search import DEFAULT_SEARCH_PROMPT
from data.core.logger import logger

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

DEFAULT_API_CONFIG = {
    "gemini_family": {
        "api_key": "",
        "model": "gemini-3.8-flash",
        "connection_mode": "doh",
        "doh_preset": "Comss.one (SmartDNS / РФ обход)",
        "doh_custom_url": "https://xbox-dns.ru/dns-query",
        "proxy": "",
        "temperature": "0.2",
        "top_p": "0.2",
        "max_tokens": "3072",
        "thinking_mode": "Низкий (LOW / Быстрый)",
        "enable_web_search": "0",
        "search_prompt": DEFAULT_SEARCH_PROMPT,
        "enable_glossary": "1"
    },
    "openai_120b": {
        "account_id": "",
        "api_token": "",
        "model": "@cf/openai/gpt-oss-120b",
        "endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        "temperature": "0.1",
        "top_p": "0.2",
        "max_tokens": "3072",
        "enable_thinking": "0",
        "enable_glossary": "1"
    },
    "deepseek_flash": {
        "api_key": "",
        "model": "deepseek/deepseek-v4-flash-free",
        "endpoint": "https://api.orcarouter.ai/v1/chat/completions",
        "temperature": "0.2",
        "top_p": "0.2",
        "max_tokens": "2048",
        "enable_thinking": "0",
        "enable_web_search": "0",
        "search_prompt": DEFAULT_SEARCH_PROMPT,
        "enable_glossary": "1"
    },
    "tencent_hy3": {
        "api_key": "",
        "model": "tencent/hy3-free",
        "endpoint": "https://api.orcarouter.ai/v1/chat/completions",
        "temperature": "0.2",
        "top_p": "0.2",
        "max_tokens": "2048",
        "enable_thinking": "0",
        "enable_web_search": "0",
        "search_prompt": DEFAULT_SEARCH_PROMPT,
        "enable_glossary": "1"
    },
    "qwen_orca": {
        "api_key": "",
        "model": "qwen3.8-flash",
        "endpoint": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "temperature": "0.1",
        "top_p": "0.3",
        "max_tokens": "4096",
        "enable_thinking": "0",
        "enable_web_search": "0",
        "search_prompt": DEFAULT_SEARCH_PROMPT,
        "enable_glossary": "1"
    },
    "google_ai": {
        "endpoint": "https://www.google.com/search",
        "enable_glossary": "1"
    }
}

class APIConfigManager:
    def __init__(self, filename="api_keys.ini"):
        self.base_dir = get_base_dir()
        self.config_path = os.path.join(self.base_dir, "data", filename)
        
        old_root_path = os.path.join(self.base_dir, filename)
        if os.path.exists(old_root_path) and not os.path.exists(self.config_path):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                shutil.move(old_root_path, self.config_path)
                logger.system("Миграция api_keys.ini в папку data/ завершена.")
            except Exception: 
                pass

        self.config = configparser.ConfigParser(interpolation=None)
        self.load()

    def load(self):
        for sec, values in DEFAULT_API_CONFIG.items():
            if not self.config.has_section(sec):
                self.config.add_section(sec)
            for k, v in values.items():
                if not self.config.has_option(sec, k):
                    self.config.set(sec, k, str(v))

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config.read_file(f)
            except Exception:
                try:
                    with open(self.config_path, "r", encoding="cp1251") as f:
                        self.config.read_file(f)
                except Exception: 
                    pass
        else:
            self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                self.config.write(f)
            return True
        except Exception as e:
            logger.system(f"APIConfigManager Ошибка сохранения: {e}")
            return False

    def get_val(self, service_id, key, default=""):
        sec = service_id.lower().strip()
        try:
            if self.config.has_section(sec) and self.config.has_option(sec, key):
                val = self.config.get(sec, key)
                if val is not None and str(val).strip():
                    return val
        except Exception: 
            pass

        if key == "search_prompt":
            return DEFAULT_SEARCH_PROMPT

        return default

    def set_val(self, service_id, key, value):
        sec = service_id.lower().strip()
        if not self.config.has_section(sec):
            self.config.add_section(sec)
        self.config.set(sec, key, str(value).strip())
        self.save()

api_config = APIConfigManager()