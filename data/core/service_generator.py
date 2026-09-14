# -*- coding: utf-8 -*-
"""
Модуль: data/core/service_generator.py
Назначение: Облегченный модульный координатор генератора сервисов.
            Динамически подхватывает шаблоны из data/core/templates/ (Boltch, OpenRouter,
            Cloudflare, OpenAI-совместимые API) и автоматически генерирует Python-плагин
            в data/services/, JS-кнопку в Services/ и конфигурацию.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import sys
import re
import shutil
import json
import importlib
import configparser

from data.core.templates.common_js import JS_SERVICE_TEMPLATE

__all__ = [
    "slugify",
    "get_next_available_qt_id",
    "get_available_providers",
    "create_service_from_template",
    "delete_service_completely",
]

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

def slugify(text):
    text = re.sub(r'[^a-zA-Z0-9_]', '_', text.lower()).strip('_')
    return re.sub(r'_+', '_', text)

def get_next_available_qt_id():
    base_dir = get_base_dir()
    used_ids = {675, 681, 685, 686, 694, 696, 698, 700, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 103, 111, 11, 118, 119}

    services_dir = os.path.join(base_dir, "Services")
    if os.path.exists(services_dir):
        for root, _, files in os.walk(services_dir):
            for file in files:
                if file.lower() == "service.js":
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            content = f.read()
                            m = re.search(r'SERVICE_ID\s*=\s*(\d+)', content)
                            if m:
                                used_ids.add(int(m.group(1)))
                    except Exception:
                        pass

    candidate = 711
    while candidate in used_ids:
        candidate += 1
    return candidate

def get_available_providers():
    """
    Сканирует папку data/core/templates/ и возвращает список доступных провайдеров.
    Формат: [("boltch", "Boltch.cloud (Free Pool)", "free:kimi-k2.6"), ...]
    """
    providers = []
    base_dir = get_base_dir()
    tpl_dir = os.path.join(base_dir, "data", "core", "templates")
    if not os.path.exists(tpl_dir):
        return [
            ("boltch", "Boltch.cloud (Free Pool)", "free:kimi-k2.6"),
            ("openrouter", "OpenRouter.ai (Free & Paid)", "nvidia/nemotron-3.5-lightning:free"),
            ("cloudflare", "Cloudflare Workers AI", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
            ("openai_compatible", "OpenAI-совместимый API (DeepSeek, Qwen и др.)", "deepseek-flash")
        ]

    for item in os.listdir(tpl_dir):
        if item.endswith(".py") and not item.startswith("__") and item != "common_js.py":
            mod_name = item[:-3]
            try:
                mod = importlib.import_module(f"data.core.templates.{mod_name}")
                p_key = getattr(mod, "PROVIDER_KEY", mod_name)
                p_name = getattr(mod, "PROVIDER_NAME", mod_name.capitalize())
                p_model = getattr(mod, "DEFAULT_MODEL", "")
                providers.append((p_key, p_name, p_model))
            except Exception:
                pass

    if not providers:
        providers = [
            ("boltch", "Boltch.cloud (Free Pool)", "free:kimi-k2.6"),
            ("openrouter", "OpenRouter.ai (Free & Paid)", "nvidia/nemotron-3.5-lightning:free"),
            ("cloudflare", "Cloudflare Workers AI", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
            ("openai_compatible", "OpenAI-совместимый API (DeepSeek, Qwen и др.)", "deepseek-flash")
        ]

    return providers

def _get_template_module(provider_key):
    try:
        return importlib.import_module(f"data.core.templates.{provider_key}")
    except Exception:
        try:
            return importlib.import_module("data.core.templates.openai_compatible")
        except Exception:
            return None

def create_service_from_template(provider="boltch", name="My Model", service_id=None, model_id=None, qt_id=None):
    base_dir = get_base_dir()
    slug = slugify(service_id or name)
    if not slug:
        slug = "custom_model"

    target_qt_id = int(qt_id) if qt_id else get_next_available_qt_id()
    tpl_mod = _get_template_module(provider)

    default_model_str = getattr(tpl_mod, "DEFAULT_MODEL", "deepseek-flash") if tpl_mod else "deepseek-flash"
    model_str = model_id or default_model_str

    py_template = getattr(tpl_mod, "PYTHON_TEMPLATE", "") if tpl_mod else ""
    if not py_template:
        from data.core.templates.openai_compatible import PYTHON_TEMPLATE as py_template

    py_dir = os.path.join(base_dir, "data", "services", slug)
    os.makedirs(py_dir, exist_ok=True)
    py_file = os.path.join(py_dir, "service.py")

    code = (py_template
            .replace("{SERVICE_NAME}", name)
            .replace("{SERVICE_ID_SLUG}", slug)
            .replace("{MODEL_ID}", model_str)
            .replace("{QT_ID}", str(target_qt_id)))

    with open(py_file, "w", encoding="utf-8") as f:
        f.write(code)

    js_folder_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip() or slug
    js_dir = os.path.join(base_dir, "Services", js_folder_name)
    os.makedirs(js_dir, exist_ok=True)
    js_file = os.path.join(js_dir, "service.js")

    js_code = (JS_SERVICE_TEMPLATE
               .replace("{SERVICE_NAME}", name)
               .replace("{SERVICE_ID_SLUG}", slug)
               .replace("{QT_ID}", str(target_qt_id)))

    with open(js_file, "w", encoding="utf-8") as f:
        f.write(js_code)

    from data.core.api_config import api_config
    if tpl_mod and hasattr(tpl_mod, "setup_config"):
        tpl_mod.setup_config(api_config, slug, model_str)
    else:
        api_config.set_val(slug, "model", model_str)
        api_config.set_val(slug, "temperature", "0.2")
        api_config.set_val(slug, "max_tokens", "4096")

    preset_dir = os.path.join(base_dir, "data", "presets", slug)
    os.makedirs(preset_dir, exist_ok=True)
    def_preset = os.path.join(preset_dir, "default.txt")
    if not os.path.exists(def_preset):
        with open(def_preset, "w", encoding="utf-8") as f:
            f.write(
                "Сделай профессиональный перевод на {TARGET_LANG} с точной передачей стиля оригинала.\n"
                "ПРАВИЛА:\n"
                "1. Стиль и мимикрия: точно воспроизводи стиль, регистр и тональность источника.\n"
                "2. Терминология: устоявшиеся официальные термины пиши на целевом языке, уникальные бренды — в оригинале."
            )

    from data.services.base_service import load_all_services
    load_all_services()

    return True, slug, js_file, py_file

def delete_service_completely(service_id, service_name):
    base_dir = get_base_dir()
    slug = slugify(service_id)

    py_dir = os.path.join(base_dir, "data", "services", slug)
    if os.path.exists(py_dir):
        shutil.rmtree(py_dir, ignore_errors=True)

    js_candidates = [
        os.path.join(base_dir, "Services", service_name),
        os.path.join(base_dir, "Services", slug),
        os.path.join(base_dir, "Services", slug.capitalize())
    ]
    for p in js_candidates:
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)

    preset_dir = os.path.join(base_dir, "data", "presets", slug)
    if os.path.exists(preset_dir):
        shutil.rmtree(preset_dir, ignore_errors=True)

    from data.core.api_config import api_config
    if api_config.config.has_section(slug):
        api_config.config.remove_section(slug)
        api_config.save()

    from data.services.base_service import LOADED_SERVICES, load_all_services
    if slug in LOADED_SERVICES:
        del LOADED_SERVICES[slug]
    load_all_services()
    return True