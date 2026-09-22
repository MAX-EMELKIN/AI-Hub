# -*- coding: utf-8 -*-
# data/core/i18n.py

import ctypes
import json
import os
import sys

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

KNOWN_LANG_NAMES = {
    'ru': 'Russian',
    'en': 'English',
    'de': 'Deutsch',
    'fr': 'Francais',
    'es': 'Espanol',
    'zh': 'Chinese (Simplified)',
    'zh-cn': 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)',
    'cs': 'Cestina',
    'tr': 'Turkce',
    'it': 'Italiano',
    'pl': 'Polski',
    'uk': 'Ukrainian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'pt': 'Portugues'
}

EMERGENCY_FALLBACK = {
    'ru': {'error': 'Error', 'btn_close': 'Close', 'btn_save': 'Save'},
    'en': {'error': 'Error', 'btn_close': 'Close', 'btn_save': 'Save'}
}

class I18nManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.locales_dir = os.path.join(self.base_dir, 'data', 'locales')
        self.prompts_file = os.path.join(self.locales_dir, 'prompts.json')
        self.current_lang = 'ru'
        self._file_cache = {}
        self.translations = {}
        self._fallback_en = {}
        self._fallback_ru = {}
        self._prompts = {}
        self._load_prompts()
        self._load_fallbacks()
        self.reload()

    def _read_json_file(self, file_path):
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._file_cache[file_path] = data
                    return data
            except Exception:
                pass
        return {}

    def _load_locale_file(self, filename):
        file_path = os.path.join(self.locales_dir, filename)
        return self._read_json_file(file_path)

    def _load_prompts(self):
        self._prompts = self._read_json_file(self.prompts_file)

    def _load_fallbacks(self):
        self._fallback_en = self._load_locale_file('en.json') or EMERGENCY_FALLBACK.get('en', {})
        self._fallback_ru = self._load_locale_file('ru.json') or EMERGENCY_FALLBACK.get('ru', {})

    def _lookup_key(self, dictionary, key):
        if not dictionary or not key:
            return None
        if key in dictionary:
            val = dictionary[key]
            if isinstance(val, str):
                return val
        parts = key.split('.')
        curr = dictionary
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                return None
        return curr if isinstance(curr, str) else None

    def get_available_languages(self):
        langs = [('auto', 'Auto (Windows)')]
        discovered = set(KNOWN_LANG_NAMES.keys())
        if os.path.exists(self.locales_dir):
            try:
                for item in os.listdir(self.locales_dir):
                    if item.lower().endswith('.json') and item.lower() != 'prompts.json':
                        discovered.add(item[:-5].lower())
            except Exception:
                pass
        for code in sorted(discovered):
            native_name = ''
            data = self._load_locale_file(f'{code}.json')
            if data and isinstance(data, dict):
                native_name = data.get('__lang_name__', '')
            if not native_name:
                native_name = KNOWN_LANG_NAMES.get(code, code.upper())
            langs.append((code, native_name))
        return langs

    def detect_windows_language(self):
        try:
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if lcid in (0x0419, 0x0422, 0x0423):
                return 'ru'
            if (lcid & 0xFF) == 0x07:
                return 'de'
            if (lcid & 0xFF) == 0x0C:
                return 'fr'
            if (lcid & 0xFF) == 0x0A:
                return 'es'
            if (lcid & 0xFF) == 0x10:
                return 'it'
            if lcid == 0x0405:
                return 'cs'
            if lcid == 0x041F:
                return 'tr'
            if (lcid & 0xFF) == 0x04:
                return 'zh'
            return 'en'
        except Exception:
            return 'ru'

    def reload(self, lang_override=None):
        self._file_cache.clear()
        self._load_prompts()
        self._load_fallbacks()
        if lang_override:
            chosen = lang_override
        else:
            try:
                from data.core.config_manager import config
                cfg_lang = config.get_str('GENERAL', 'UILanguage', 'auto').lower()
            except Exception:
                cfg_lang = 'auto'
            chosen = self.detect_windows_language() if cfg_lang == 'auto' else cfg_lang
        self.current_lang = chosen
        self.translations = self._load_locale_file(f'{chosen}.json')

    def t(self, key, default=None, **kwargs):
        val = self._lookup_key(self.translations, key)
        if val is None:
            val = self._lookup_key(self._fallback_en, key)
        if val is None:
            val = self._lookup_key(self._fallback_ru, key)
        if val is None:
            val = default if default is not None else str(key)
        if kwargs and isinstance(val, str):
            try:
                val = val.format(**kwargs)
            except Exception:
                pass
        return val

    def get_prompt(self, key, **kwargs):
        val = self._lookup_key(self._prompts, key)
        if val is None:
            val = str(key)
        if kwargs and isinstance(val, str):
            try:
                val = val.format(**kwargs)
            except Exception:
                pass
        return val

    def set_language(self, lang_code):
        clean_code = str(lang_code).lower().strip()
        try:
            from data.core.config_manager import config
            config.set_value('GENERAL', 'UILanguage', clean_code)
        except Exception:
            pass
        self.reload(lang_override=(None if clean_code == 'auto' else clean_code))

i18n = I18nManager()
t = i18n.t
_ = t
get_prompt = i18n.get_prompt
