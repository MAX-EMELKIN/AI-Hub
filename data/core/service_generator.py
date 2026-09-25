# data/core/service_generator.py
import os
import sys
import re
import shutil
import importlib.util
from data.core.api_config import api_config
from data.core.logger import logger
from data.core.launcher import restart_qtranslate


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))


DEFAULT_DOCS = {
    "openrouter": "https://openrouter.ai/docs",
    "dashscope": "https://help.aliyun.com/zh/model-studio/developer-reference/compatibility-of-openai-with-dashscope",
    "gemini": "https://ai.google.dev/gemini-api/docs",
    "cloudflare": "https://developers.cloudflare.com/workers-ai/",
    "boltch": "https://boltch.cloud",
    "deepseek": "https://api-docs.deepseek.com/",
    "siliconflow": "https://docs.siliconflow.cn/",
    "cerebras": "https://inference-docs.cerebras.net/",
    "mistral": "https://docs.mistral.ai/",
    "pollinations": "https://pollinations.ai/",
    "openai_compatible": "https://platform.openai.com/docs/api-reference"
}


def delete_service_completely(service_id, display_name=None):
    base_dir = get_base_dir()
    sec_id = str(service_id).strip().lower()

    if api_config.models.has_section(sec_id):
        api_config.models.remove_section(sec_id)
        api_config.save_models()

    try:
        from data.core.config_manager import config
        order = config.get_service_order()
        if sec_id in order:
            order.remove(sec_id)
            config.save_service_order(order)
    except Exception:
        pass

    hub_service_dir = os.path.join(base_dir, "data", "services", sec_id)
    if os.path.exists(hub_service_dir):
        try:
            shutil.rmtree(hub_service_dir)
        except Exception:
            pass

    presets_dir = os.path.join(base_dir, "data", "presets", sec_id)
    if os.path.exists(presets_dir):
        try:
            shutil.rmtree(presets_dir)
        except Exception:
            pass

    folder_name = display_name or sec_id
    clean_folder = re.sub(r'[\\/*?:"<>|]', '', str(folder_name).strip())
    qt_service_dir = os.path.join(base_dir, "Services", clean_folder)
    if os.path.exists(qt_service_dir):
        try:
            shutil.rmtree(qt_service_dir)
        except Exception:
            pass

    try:
        restart_qtranslate()
    except Exception:
        pass


class ServiceGenerator:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.templates_dir = os.path.join(self.base_dir, "data", "core", "templates")
        self.services_qt_dir = os.path.join(self.base_dir, "Services")
        self.services_hub_dir = os.path.join(self.base_dir, "data", "services")
        self.presets_dir = os.path.join(self.base_dir, "data", "presets")

    def sanitize_id(self, name):
        if not name:
            return "service_custom"
        s = name.strip().lower()
        s = re.sub(r'[\s\-_\.]+', '_', s)
        s = re.sub(r'[^a-z0-9_]', '', s)
        s = s.strip('_')
        return s if s else "service_custom"

    def sanitize_folder_name(self, name):
        if not name:
            return "Custom Service"
        clean = re.sub(r'[\\/*?:"<>|]', '', name.strip())
        return clean if clean else "Custom Service"

    def get_available_templates(self):
        templates = []
        if not os.path.exists(self.templates_dir):
            return templates
        system_files = {"__init__.py", "unified_engine.py", "common_js.py"}
        for fname in sorted(os.listdir(self.templates_dir)):
            if fname.endswith(".py") and fname not in system_files:
                template_id = fname[:-3]
                meta = self._load_template_metadata(template_id, os.path.join(self.templates_dir, fname))
                if meta:
                    templates.append(meta)
        return templates

    def _load_template_metadata(self, template_id, file_path):
        try:
            spec = importlib.util.spec_from_file_location(f"template_{template_id}", file_path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            docs = getattr(module, "DOCS_URL", DEFAULT_DOCS.get(template_id, ""))
            return {
                "id": template_id,
                "name": getattr(module, "PROVIDER_NAME", template_id.capitalize()),
                "provider": getattr(module, "PROVIDER_KEY", template_id),
                "description": getattr(module, "TEMPLATE_DESC", ""),
                "docs_url": docs,
                "default_endpoint": getattr(module, "DEFAULT_ENDPOINT", ""),
                "default_model": getattr(module, "DEFAULT_MODEL", ""),
                "default_connection_mode": getattr(module, "CONNECTION_MODE", "direct"),
                "default_proxy": getattr(module, "DEFAULT_PROXY", "213.165.38.49:1080"),
                "default_doh": "Comss.one (SmartDNS / РФ обход)",
                "supports_thinking": getattr(module, "SUPPORTS_THINKING", False),
                "thinking_policy": getattr(module, "THINKING_POLICY", "strip"),
                "auth_header_format": getattr(module, "AUTH_HEADER_TYPE", "Bearer"),
                "extra_headers": getattr(module, "EXTRA_HEADERS", {}),
                "module": module
            }
        except Exception as e:
            logger.system(f"Ошибка загрузки метаданных шаблона {template_id}: {e}")
            return None

    def get_template_docs_url(self, template_id):
        meta = self._load_template_metadata(template_id, os.path.join(self.templates_dir, f"{template_id}.py"))
        if meta and meta.get("docs_url"):
            return meta["docs_url"]
        return DEFAULT_DOCS.get(template_id, "https://openrouter.ai/docs")

    def generate(self, display_name, template_id, api_key="", model_name="",
                 endpoint="", connection_mode=None, proxy="", doh_preset="Comss.one (SmartDNS / РФ обход)",
                 temperature="0.3", top_p="0.9", max_tokens="2048",
                 thinking_policy="strip", restart_qt=True):
        templates = {t["id"]: t for t in self.get_available_templates()}
        tmpl = templates.get(template_id)
        if not tmpl:
            raise ValueError(f"Шаблон '{template_id}' не найден.")

        service_id = self.sanitize_id(display_name)
        folder_name = self.sanitize_folder_name(display_name)
        provider_id = tmpl["provider"].lower().strip()

        final_endpoint = endpoint.strip() if endpoint.strip() else tmpl["default_endpoint"]
        final_model = model_name.strip() if model_name.strip() else tmpl["default_model"]
        final_conn_mode = connection_mode if connection_mode is not None else tmpl["default_connection_mode"]
        final_proxy = proxy.strip() if proxy.strip() else tmpl["default_proxy"]
        final_api_key = api_key.strip()

        if not api_config.models.has_section(service_id):
            api_config.models.add_section(service_id)

        api_config.models.set(service_id, "provider", provider_id)
        api_config.models.set(service_id, "endpoint", final_endpoint)
        api_config.models.set(service_id, "model", final_model)
        api_config.models.set(service_id, "display_name", folder_name)
        api_config.models.set(service_id, "temperature", str(temperature))
        api_config.models.set(service_id, "top_p", str(top_p))
        api_config.models.set(service_id, "max_tokens", str(max_tokens))
        api_config.models.set(service_id, "thinking_policy", str(thinking_policy))
        api_config.models.set(service_id, "connection_mode", str(final_conn_mode))
        api_config.models.set(service_id, "proxy", str(final_proxy))
        api_config.models.set(service_id, "doh_preset", str(doh_preset))

        if provider_id == "custom":
            api_config.models.set(service_id, "api_key", final_api_key)
        else:
            existing_prov_key = api_config.get_provider_val(provider_id, "api_key", "")
            if not existing_prov_key and final_api_key:
                api_config.set_provider_val(provider_id, "api_key", final_api_key)
                api_config.set_provider_val(provider_id, "connection_mode", final_conn_mode)
                api_config.set_provider_val(provider_id, "proxy", final_proxy)
                api_config.set_provider_val(provider_id, "doh_preset", doh_preset)
            elif final_api_key and final_api_key != existing_prov_key:
                api_config.models.set(service_id, "api_key", final_api_key)
            else:
                api_config.models.set(service_id, "api_key", "")

        api_config.save_models()
        api_config.save_providers()

        self._setup_service_presets(service_id)

        hub_service_dir = os.path.join(self.services_hub_dir, service_id)
        os.makedirs(hub_service_dir, exist_ok=True)
        hub_service_file = os.path.join(hub_service_dir, "service.py")
        self._write_hub_service_file(hub_service_file, service_id, folder_name, tmpl, final_model, final_endpoint, final_api_key)

        qt_service_dir = os.path.join(self.services_qt_dir, folder_name)
        os.makedirs(qt_service_dir, exist_ok=True)
        qt_service_file = os.path.join(qt_service_dir, "service.js")
        self._write_qt_service_file(qt_service_file, folder_name, service_id)

        self._setup_service_icons(tmpl, hub_service_dir, qt_service_dir)

        logger.system(f"Сервис '{folder_name}' (ID: {service_id}) успешно сгенерирован и настроен.")

        if restart_qt:
            try:
                restart_qtranslate()
                logger.system("QTranslate успешно перезапущен для загрузки плагина.")
            except Exception as e:
                logger.system(f"Не удалось перезапустить QTranslate: {e}")

        return service_id

    def _setup_service_presets(self, service_id):
        target_preset_dir = os.path.join(self.presets_dir, service_id)
        os.makedirs(target_preset_dir, exist_ok=True)
        styles = ["academic", "code", "default", "games", "literary"]
        source_dir = os.path.join(self.presets_dir, "qwen_turbo")
        if not os.path.exists(source_dir):
            source_dir = self.presets_dir

        for style in styles:
            target_file = os.path.join(target_preset_dir, f"{style}.txt")
            if not os.path.exists(target_file):
                src_file = os.path.join(source_dir, f"{style}.txt")
                if os.path.exists(src_file):
                    try:
                        shutil.copy2(src_file, target_file)
                    except Exception:
                        pass
                else:
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(f"Сделай профессиональный перевод текста на {{TARGET_LANG}} в стиле: {style}.")

    def _write_hub_service_file(self, target_path, service_id, display_name, tmpl, model, endpoint, api_key):
        module = tmpl.get("module")
        template_code = getattr(module, "PYTHON_TEMPLATE", None)

        if template_code:
            code = template_code.replace("{SERVICE_ID_SLUG}", service_id)
            code = code.replace("{SERVICE_NAME}", display_name)
            code = code.replace("{MODEL_ID}", model)
            code = code.replace("{ENDPOINT}", endpoint)
        else:
            from data.core.templates.unified_engine import UNIFIED_PYTHON_TEMPLATE
            code = UNIFIED_PYTHON_TEMPLATE.replace("{SERVICE_ID_SLUG}", service_id)
            code = code.replace("{SERVICE_NAME}", display_name)
            code = code.replace("{PROVIDER_KEY}", tmpl.get("provider", "custom"))
            code = code.replace("{MODEL_ID}", model)
            code = code.replace("{ENDPOINT}", endpoint)
            code = code.replace("{AUTH_HEADER_TYPE}", tmpl.get("auth_header_format", "Bearer"))
            code = code.replace("{THINKING_POLICY}", tmpl.get("thinking_policy", "strip"))
            code = code.replace("{RESPONSE_PATH}", "choices.0.message.content")
            code = code.replace("{EXTRA_HEADERS_JSON}", "")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(code)

    def _write_qt_service_file(self, target_path, display_name, service_id):
        from data.core.templates.common_js import JS_SERVICE_TEMPLATE
        h = sum(ord(c) for c in service_id) % 800 + 700
        js_code = JS_SERVICE_TEMPLATE.replace("{SERVICE_NAME}", display_name)
        js_code = js_code.replace("{SERVICE_ID_SLUG}", service_id)
        js_code = js_code.replace("{QT_ID}", str(h))

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(js_code)

    def _setup_service_icons(self, tmpl, hub_service_dir, qt_service_dir):
        icon_names = ["Service.png", "Service.ico", "icon.png"]
        src_icon = None

        tmpl_dir = os.path.dirname(os.path.abspath(__file__))
        icons_search = [
            os.path.join(self.base_dir, "data", "gui", "AI_Hub.ico"),
            os.path.join(self.base_dir, "AI_Hub.ico")
        ]

        for p in icons_search:
            if os.path.exists(p):
                src_icon = p
                break

        if src_icon:
            for d in [hub_service_dir, qt_service_dir]:
                target_ico = os.path.join(d, "Service.ico")
                if not os.path.exists(target_ico):
                    try:
                        shutil.copy2(src_icon, target_ico)
                    except Exception:
                        pass


service_generator = ServiceGenerator()