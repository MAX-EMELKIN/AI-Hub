# -*- coding: utf-8 -*-
# data/core/i18n.py

import ctypes, json, os, sys
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

KNOWN_LANG_NAMES = {
    'ru': 'Русский',
    'en': 'English',
    'de': 'Deutsch',
    'fr': 'Français',
    'es': 'Español',
    'zh': '简体中文',
    'zh-cn': '简体中文',
    'zh-tw': '繁體中文',
    'cs': 'Čeština',
    'tr': 'Türkçe',
    'it': 'Italiano',
    'pl': 'Polski',
    'uk': 'Українська',
    'ja': '日本語',
    'ko': '한국어',
    'pt': 'Português'
}

EMERGENCY_FALLBACK = {
    'ru': {'error': 'Ошибка', 'btn_close': 'Закрыть', 'btn_save': 'Сохранить'},
    'en': {'error': 'Error', 'btn_close': 'Close', 'btn_save': 'Save'}
}

class I18nManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.locales_dir = os.path.join(self.base_dir, 'data', 'locales')
        self.current_lang = 'ru'
        self.translations = {}
        self._fallback_en = {}
        self._fallback_ru = {}
        self._load_fallbacks()
        self.reload()

    def _load_fallbacks(self):
        self._fallback_en = self._load_locale_file('en.json') or EMERGENCY_FALLBACK.get('en', {})
        self._fallback_ru = self._load_locale_file('ru.json') or EMERGENCY_FALLBACK.get('ru', {})

    def _load_locale_file(self, filename):
        file_path = os.path.join(self.locales_dir, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get_available_languages(self):
        langs = [('auto', 'Авто (Windows)')]
        discovered = set(KNOWN_LANG_NAMES.keys())
        if os.path.exists(self.locales_dir):
            for item in os.listdir(self.locales_dir):
                if item.lower().endswith('.json'):
                    discovered.add(item[:-5].lower())
        for code in sorted(discovered):
            native_name = ''
            data = self._load_locale_file(f'{code}.json')
            if data:
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
        loaded = self._load_locale_file(f'{chosen}.json')
        self.translations = {**self._fallback_ru, **self._fallback_en, **loaded}

    def t(self, key, default=None, **kwargs):
        val = self.translations.get(key)
        if val is None:
            val = default if default is not None else self._fallback_en.get(key, self._fallback_ru.get(key, key))
        if kwargs:
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
