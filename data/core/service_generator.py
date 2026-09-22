# -*- coding: utf-8 -*-
# data/core/service_generator.py

import os, sys, re, shutil, importlib.util
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
                "name": getattr(module, "TEMPLATE_NAME", template_id.capitalize()),
                "provider": getattr(module, "PROVIDER_ID", template_id),
                "description": getattr(module, "TEMPLATE_DESC", ""),
                "docs_url": docs,
                "default_endpoint": getattr(module, "DEFAULT_ENDPOINT", ""),
                "default_model": getattr(module, "DEFAULT_MODEL", ""),
                "default_connection_mode": getattr(module, "DEFAULT_CONNECTION_MODE", "direct"),
                "default_proxy": getattr(module, "DEFAULT_PROXY", "213.165.38.49:1080"),
                "default_doh": getattr(module, "DEFAULT_DOH", "smartdns"),
                "supports_thinking": getattr(module, "SUPPORTS_THINKING", False),
                "thinking_policy": getattr(module, "DEFAULT_THINKING_POLICY", "strip"),
                "auth_header_format": getattr(module, "AUTH_HEADER_FORMAT", "Bearer {api_key}"),
                "extra_headers": getattr(module, "EXTRA_HEADERS", {}),
                "module": module
            }
        except Exception as e:
            logger.error(f"Error Text Text Text {template_id}: {e}")
            return None

    def get_template_docs_url(self, template_id):
        meta = self._load_template_metadata(template_id, os.path.join(self.templates_dir, f"{template_id}.py"))
        if meta and meta.get("docs_url"):
            return meta["docs_url"]
        return DEFAULT_DOCS.get(template_id, "https://openrouter.ai/docs")

    def generate(self, display_name, template_id, api_key="", model_name="",
                 endpoint="", connection_mode=None, proxy="", doh_preset="smartdns",
                 temperature="0.3", top_p="0.9", max_tokens="2048",
                 thinking_policy="strip", restart_qt=True):
        templates = {t["id"]: t for t in self.get_available_templates()}
        tmpl = templates.get(template_id)
        if not tmpl:
            raise ValueError(f"Template '{template_id}' not found.")

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
        self._write_hub_service_file(hub_service_file, service_id, template_id)

        qt_service_dir = os.path.join(self.services_qt_dir, folder_name)
        os.makedirs(qt_service_dir, exist_ok=True)
        qt_service_file = os.path.join(qt_service_dir, "service.js")
        self._write_qt_service_file(qt_service_file, folder_name, service_id)

        self._setup_service_icons(tmpl, hub_service_dir, qt_service_dir)

        logger.system(f"Text '{folder_name}' (ID: {service_id}) Text Text.")

        if restart_qt:
            try:
                restart_qtranslate()
                logger.system("QTranslate Text Text Text Text Text.")
            except Exception as e:
                logger.error(f"Failed to restart QTranslate: {e}")

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
                        f.write(f"Text — Text Text. Text Text Text Text Text Text Text {style}.")

    def _write_hub_service_file(self, target_path, service_id, template_id):
        content = f"""# -*- coding: utf-8 -*-
# data/services/{service_id}/service.py

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from data.core.templates.unified_engine import execute_request

SERVICE_ID = "{service_id}"
TEMPLATE_ID = "{template_id}"

def translate(text, from_lang="auto", to_lang="ru", preset_name="default", **kwargs):
    return execute_request(SERVICE_ID, TEMPLATE_ID, text, from_lang, to_lang, preset_name, **kwargs)
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_qt_service_file(self, target_path, display_name, service_id):
        content = f"""// QTranslate Service Script: {display_name}
// Generated by QTranslate AI Hub Studio
var name = "{display_name}";
var hub_service_id = "{service_id}";

function getRequest(text, from, to) {{
    var url = "http://127.0.0.1:8080/translate";
    var escapedText = text.replace(/\\\\/g, "\\\\\\\\")
                          .replace(/\"/g, "\\\\\"")
                          .replace(/\\r/g, "\\\\r")
                          .replace(/\\n/g, "\\\\n")
                          .replace(/\\t/g, "\\\\t");

    var jsonBody = '{{"service":"' + hub_service_id + '","from":"' + from + '","to":"' + to + '","text":"' + escapedText + '"}}';

    return {{
        url: url,
        postData: jsonBody,
        headers: {{
            "Content-Type": "application/json; charset=utf-8"
        }}
    }};
}}

function getResponse(text) {{
    if (!text || text.length === 0) {{
        return "Error: Text Text Text AI Hub";
    }}
    try {{
        if (text.indexOf('{{"result":') === 0 || text.indexOf('{{"error":') === 0) {{
            var res = eval("(" + text + ")");
            if (res.error) {{
                return "Error AI Hub: " + res.error;
            }}
            return res.result;
        }}
    }} catch (e) {{
    }}
    return text;
}}
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _setup_service_icons(self, tmpl, hub_service_dir, qt_service_dir):
        template_id = tmpl["id"]
        source_ico = os.path.join(self.templates_dir, f"{template_id}.ico")
        source_png = os.path.join(self.templates_dir, f"{template_id}.png")
        default_ico = os.path.join(self.base_dir, "data", "gui", "AI_Hub.ico")

        target_ico = os.path.join(qt_service_dir, "service.ico")
        if os.path.exists(source_ico):
            shutil.copy2(source_ico, target_ico)
        elif os.path.exists(default_ico):
            shutil.copy2(default_ico, target_ico)

        target_png = os.path.join(hub_service_dir, "service.png")
        if os.path.exists(source_png):
            shutil.copy2(source_png, target_png)

    def delete_service(self, service_id_or_name):
        sec = api_config._resolve_section(service_id_or_name)
        display_name = ""
        if api_config.models.has_section(sec) and api_config.models.has_option(sec, "display_name"):
            display_name = api_config.models.get(sec, "display_name")
        if not display_name:
            display_name = service_id_or_name

        qt_dir = os.path.join(self.services_qt_dir, display_name)
        if os.path.exists(qt_dir):
            try:
                shutil.rmtree(qt_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Text Text Text Text QTranslate {qt_dir}: {e}")

        hub_dir = os.path.join(self.services_hub_dir, sec)
        if os.path.exists(hub_dir):
            try:
                shutil.rmtree(hub_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Text Text Text Text Hub {hub_dir}: {e}")

        preset_dir = os.path.join(self.presets_dir, sec)
        if os.path.exists(preset_dir):
            try:
                shutil.rmtree(preset_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Text Text Text Text Text {preset_dir}: {e}")

        if api_config.models.has_section(sec):
            api_config.models.remove_section(sec)
            api_config.save_models()

        logger.system(f"Text '{display_name}' ({sec}) Text Text.")
        try:
            restart_qtranslate()
        except Exception:
            pass

service_generator = ServiceGenerator()
delete_service_completely = service_generator.delete_service
