# -*- coding: utf-8 -*-
# data/core/templates/dashscope.py

PROVIDER_KEY = "dashscope"
PROVIDER_NAME = "Alibaba Cloud (Qwen DashScope)"
DEFAULT_ENDPOINT = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-turbo"
AUTH_HEADER_TYPE = "Bearer"
THINKING_POLICY = "enable_thinking_false"
RESPONSE_PATH = "choices.0.message.content"
CONNECTION_MODE = "direct"
DEFAULT_PROXY = "127.0.0.1:10808"
EXTRA_HEADERS = {}

def setup_config(api_config, slug, model_str):
    existing_key = api_config.get_provider_val(PROVIDER_KEY, "api_key", "")
    api_config.set_provider_val(PROVIDER_KEY, "api_key", existing_key)
    api_config.set_provider_val(PROVIDER_KEY, "connection_mode", CONNECTION_MODE)
    api_config.set_provider_val(PROVIDER_KEY, "proxy", DEFAULT_PROXY)
    api_config.set_val(slug, "provider", PROVIDER_KEY)
    api_config.set_val(slug, "model", model_str or DEFAULT_MODEL)
    api_config.set_val(slug, "endpoint", DEFAULT_ENDPOINT)
    api_config.set_val(slug, "temperature", "0.1")
    api_config.set_val(slug, "top_p", "0.3")
    api_config.set_val(slug, "max_tokens", "4096")
    api_config.set_val(slug, "enable_thinking", "0")
    api_config.set_val(slug, "enable_glossary", "1")
