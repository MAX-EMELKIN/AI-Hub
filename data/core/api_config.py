# -*- coding: utf-8 -*-
# data/core/api_config.py
import os, sys, re, configparser
from data.core.logger import logger
from data.core.web_search import DEFAULT_SEARCH_PROMPT

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', '..'))

PROVIDER_KEYS = {
    'api_key', 'account_id', 'api_token', 'connection_mode',
    'proxy', 'doh_preset', 'doh_custom_url'
}

class APIConfigManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.providers_path = os.path.join(self.data_dir, 'providers.ini')
        self.models_path = os.path.join(self.data_dir, 'models.ini')
        self.old_config_path = os.path.join(self.data_dir, 'api_keys.ini')
        self.providers = configparser.ConfigParser(interpolation=None)
        self.models = configparser.ConfigParser(interpolation=None)
        self._migrate_if_needed()
        self.load()

    def _normalize_name(self, name):
        if not name:
            return ''
        clean = os.path.basename(str(name)).strip().lower()
        clean = re.sub(r'[\s\-_\.]+', '_', clean)
        return clean.strip('_')

    def _resolve_section(self, service_id):
        if not service_id:
            return ''
        raw_sec = os.path.basename(str(service_id)).strip().lower()
        if self.models.has_section(raw_sec):
            return raw_sec
        norm_target = self._normalize_name(service_id)
        if self.models.has_section(norm_target):
            return norm_target
        for existing_sec in self.models.sections():
            if self._normalize_name(existing_sec) == norm_target:
                return existing_sec
        return norm_target if norm_target else raw_sec

    def _resolve_provider(self, sec):
        if self.models.has_section(sec) and self.models.has_option(sec, 'provider'):
            prov = self.models.get(sec, 'provider').strip().lower()
            return prov if prov else 'custom'
        return 'custom'

    def _resolve_provider_section(self, provider_id):
        if not provider_id:
            return 'custom'
        raw_prov = str(provider_id).strip().lower()
        if self.providers.has_section(raw_prov):
            return raw_prov
        norm_target = self._normalize_name(provider_id)
        if self.providers.has_section(norm_target):
            return norm_target
        for existing_sec in self.providers.sections():
            if self._normalize_name(existing_sec) == norm_target:
                return existing_sec
        return norm_target if norm_target else 'custom'

    def _guess_provider(self, sec, old_conf):
        endpoint = old_conf.get(sec, 'endpoint', fallback='').lower()
        if 'dashscope' in endpoint: return 'dashscope'
        if 'deepseek' in endpoint: return 'deepseek'
        if 'moonshot' in endpoint: return 'moonshot'
        if 'openrouter' in endpoint: return 'openrouter'
        if 'boltch' in endpoint: return 'boltch'
        if 'orcarouter' in endpoint: return 'orcarouter'
        if 'cloudflare' in endpoint: return 'cloudflare'
        if 'generativelanguage' in endpoint or sec == 'gemini_family': return 'gemini'
        if 'siliconflow' in endpoint: return 'siliconflow'
        if 'cerebras' in endpoint: return 'cerebras'
        if 'mistral' in endpoint: return 'mistral'
        if 'pollinations' in endpoint: return 'pollinations'
        return 'custom'

    def _migrate_if_needed(self):
        if os.path.exists(self.providers_path) and os.path.exists(self.models_path):
            return
        old_path = self.old_config_path if os.path.exists(self.old_config_path) else os.path.join(self.base_dir, 'api_keys.ini')
        if os.path.exists(old_path):
            old_conf = configparser.ConfigParser(interpolation=None)
            try:
                old_conf.read(old_path, encoding='utf-8')
            except Exception:
                old_conf.read(old_path, encoding='cp1251')
            for sec in old_conf.sections():
                norm_sec = self._normalize_name(sec)
                provider = self._guess_provider(sec, old_conf)
                if not self.models.has_section(norm_sec):
                    self.models.add_section(norm_sec)
                self.models.set(norm_sec, 'provider', provider)
                norm_prov = self._normalize_name(provider)
                if not self.providers.has_section(norm_prov):
                    self.providers.add_section(norm_prov)
                for k, v in old_conf.items(sec):
                    val_str = str(v).strip()
                    if k in PROVIDER_KEYS:
                        if not self.providers.has_option(norm_prov, k) or (val_str and not self.providers.get(norm_prov, k)):
                            self.providers.set(norm_prov, k, val_str)
                    else:
                        self.models.set(norm_sec, k, val_str)
            self.save_providers()
            self.save_models()
            try:
                os.rename(old_path, old_path + '.bak')
            except Exception:
                pass

    def load(self):
        if os.path.exists(self.providers_path):
            try:
                self.providers.read(self.providers_path, encoding='utf-8')
            except Exception:
                try:
                    self.providers.read(self.providers_path, encoding='cp1251')
                except Exception:
                    pass
        if os.path.exists(self.models_path):
            try:
                self.models.read(self.models_path, encoding='utf-8')
            except Exception:
                try:
                    self.models.read(self.models_path, encoding='cp1251')
                except Exception:
                    pass

    def save_providers(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.providers_path, 'w', encoding='utf-8') as f:
            self.providers.write(f)

    def save_models(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.models_path, 'w', encoding='utf-8') as f:
            self.models.write(f)

    def get_provider_val(self, provider_id, key, default=''):
        prov = self._resolve_provider_section(provider_id)
        if self.providers.has_section(prov) and self.providers.has_option(prov, key):
            val = self.providers.get(prov, key)
            if val is not None and str(val).strip() != '':
                return val
        return default

    def set_provider_val(self, provider_id, key, value):
        prov = self._resolve_provider_section(provider_id)
        if not self.providers.has_section(prov):
            self.providers.add_section(prov)
        self.providers.set(prov, key, str(value).strip())
        self.save_providers()

    def get_val(self, service_id, key, default=''):
        sec = self._resolve_section(service_id)
        if self.models.has_section(sec) and self.models.has_option(sec, key):
            val = self.models.get(sec, key)
            if val is not None and str(val).strip() != '':
                return val

        if key in PROVIDER_KEYS:
            provider = self._resolve_provider(sec)
            if provider != 'custom':
                prov_val = self.get_provider_val(provider, key, '')
                if prov_val:
                    return prov_val

        if key == 'search_prompt':
            return DEFAULT_SEARCH_PROMPT

        return default

    def set_val(self, service_id, key, value, update_provider=False):
        sec = self._resolve_section(service_id)
        val_str = str(value).strip()
        if not self.models.has_section(sec):
            self.models.add_section(sec)

        provider = self._resolve_provider(sec)
        if provider == 'custom':
            self.models.set(sec, key, val_str)
            self.save_models()
            return

        if key in PROVIDER_KEYS:
            if update_provider:
                self.set_provider_val(provider, key, val_str)
            else:
                self.models.set(sec, key, val_str)
                self.save_models()
                if not self.get_provider_val(provider, key, ''):
                    self.set_provider_val(provider, key, val_str)
        else:
            self.models.set(sec, key, val_str)
            self.save_models()

api_config = APIConfigManager()