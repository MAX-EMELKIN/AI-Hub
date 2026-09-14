# -*- coding: utf-8 -*-
"""
Модуль: data/services/google_ai/service.py
Назначение: Плагин Google AI Mode с безопасным DOM-парсером (без зависания V8/Blink),
                защитой от бесконечных таймаутов, автоматическим fallback-переводом
                и интеграцией с модулем logger.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64)
"""

import time
import re
import json
import urllib.parse
from data.services.base_service import BaseService
from data.core.cdp_client import browser_cdp
from data.core.logger import logger

GOOGLE_UI_JUNK = [
    "Преобразование речи в текст…", "Преобразование речи в текст...",
    "Добавить файлы и инструменты", "Микрофон", "Остановить", "Повторить",
    "Копировать", "Поделиться", "Хороший ответ", "Плохой ответ",
    "Перейти к основному контенту", "Справка по использованию специальных возможностей",
    "Режим ИИ", "Все", "Картинки", "Видео", "Новости", "Ещё", "Войти",
    "Результаты поиска", "Быстрый ответ", "Оставить отзыв", "Источники",
    "Показать больше", "Развернуть", "Свернуть", "История режима ИИ",
    "Новый чат", "Скопировано", "Изменить", "Facebook", "Gmail", "Reddit",
    "WhatsApp", "Поделиться ссылкой", "Отправить", "Задать вопрос по теме:",
    "Центр управления рекламой", "Приложения Google", "Экономит время",
    "Очистить", "Полезный", "Подробный", "Другое", "Неверный", "Недопустимый",
    "Не работает", "Нет", "Спасибо, что сообщили нам.", "Показать все"
]

JS_EXTRACT_DOM = """
(() => {
    if (document.querySelector('#af-error-container') || (document.title && document.title.includes("414."))) {
        return "ERROR_414";
    }

    const aiSelectors = [
        'div[data-attrid*="wa:"]',
        'div[data-attrid="Overview"]',
        'div[jscontroller="e4fBqb"]',
        'div.wDYxhc',
        'div.UD7Fr',
        'div.kno-rdesc',
        'div#rso',
        'div[role="main"]'
    ];

    for (let sel of aiSelectors) {
        let el = document.querySelector(sel);
        if (!el) continue;

        let txt = (el.innerText || "").trim();
        if (!txt) continue;

        if (txt.includes("###END###") || txt.includes("### END ###") || txt.includes("[END]")) {
            return txt;
        }
    }

    let mainEl = document.querySelector('div#rso') || document.querySelector('div[role="main"]');
    if (mainEl) {
        return (mainEl.innerText || "").trim();
    }

    return "";
})()
"""

class GoogleAIService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="google_ai",
            name="Google AI Mode",
            route_name="/google_ai",
            icon_name="Service.png"
        )
        self.supports_hyperparameters = False
        self.supports_glossary = True

    def get_config_fields(self):
        return [
            {"key": "endpoint", "label": "Поисковый URL:", "required": True}
        ]

    def is_ready(self):
        return True, "Работает через браузер Supermium (без API-ключей)"

    def is_meaningful(self, text):
        if not text or text == "ERROR_414" or len(text.strip()) < 2:
            return False
        if "<style>" in text.lower() or "af-error-container" in text.lower() or "aihubmax" in text.lower():
            return False
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            return False
        real_lines = [l for l in lines if not any(j.lower() in l.lower() for j in GOOGLE_UI_JUNK)]
        return len(real_lines) > 0 and bool(re.search(r'\w{2,}', "".join(real_lines), re.UNICODE))

    def _strip_prompt_leakage(self, text):
        if not text or text == "ERROR_414":
            return ""

        if '"""' in text:
            parts = text.split('"""')
            text = parts[-1].strip() if len(parts) > 1 else parts[0].strip()

        text = re.sub(r'^(?:"""|\"|\'|«|“|”|\s|\n)+', '', text)
        text = re.sub(r'(?:"""|\"|\'|»|”|\s|\n)+$', '', text)

        forbidden = ["ПРАВИЛА:", "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:", "Сделай профессиональный перевод", "КРИТИЧЕСКОЕ ПРАВИЛО"]
        lines = text.split('\n')
        clean_lines = [l for l in lines if not any(l.strip().startswith(b) for b in forbidden)]

        return "\n".join(clean_lines).strip()

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        clean_input = re.sub(r'[\ufeff\u200b\u200e\u200f\x00]', '', text).strip()
        if not clean_input:
            return ""

        words = clean_input.split()
        word_count = len(words)
        t0 = time.time()

        target_code = trg_lang or "ru"
        source_code = src_lang or "auto"

        if (word_count == 1 and len(clean_input) < 25 and '\n' not in clean_input) or (len(clean_input) <= 2 and re.search(r'[\u4e00-\u9fff]', clean_input)):
            fast_res = self.fetch_fast_word(clean_input, src=source_code, trg=target_code)
            if fast_res:
                elapsed = round(time.time() - t0, 3)
                logger.api_summary(self.name, "Google QuickWord", elapsed, 200, note="Микро-перевод 1 слова")
                print(f"[Google AI]: Быстрый перевод 1 слова ({elapsed}с): {fast_res}")
                return fast_res

        logger.browser_event(f"Google AI: старт запроса ({source_code} -> {target_code}, длина: {len(clean_input)} симв.)")
        query = self.build_prompt_query(clean_input, src_lang=source_code, trg_lang=target_code, preset=preset)

        endpoint = self.get_config_val("endpoint", "https://www.google.com/search")
        params = {"q": query, "udm": "50", "aep": "109", "hl": "ru", "gl": "ru"}
        full_url = endpoint + "?" + urllib.parse.urlencode(params)

        if len(full_url) > 7800:
            logger.browser_event("Google AI: URL превысил 7800 байт (HTTP 414 limit), переключение на fallback")
            fallback = self.fetch_fast_word(clean_input, src=source_code, trg=target_code)
            return fallback or "[Google AI: Ошибка 414. Текст слишком длинный для поискового запроса.]"

        try:
            browser_cdp.ensure_browser_running()
            browser_cdp.navigate_tab("google", full_url)
            time.sleep(0.3)

            final_translation = ""
            last_len = 0
            stable_count = 0

            for attempt in range(1, 26):
                time.sleep(0.15)
                raw_text = browser_cdp.evaluate_js_on_tab("google", JS_EXTRACT_DOM)
                if not raw_text:
                    continue

                if raw_text == "ERROR_414":
                    logger.browser_event("Google AI: зафиксирована ошибка 414 на странице, переключение на fallback")
                    break

                raw_without_prompt = self._strip_prompt_leakage(raw_text)
                cleaned = self.clean_response(raw_without_prompt, ui_junk_list=GOOGLE_UI_JUNK)
                has_end_marker = any(m in raw_text for m in [self.end_marker, "### END ###", "[[END]]", "[END]"])

                if self.is_meaningful(cleaned) and cleaned.lower() != clean_input.lower():
                    if has_end_marker:
                        final_translation = cleaned
                        logger.browser_event(f"Google AI: маркер окончания зафиксирован на такте {attempt}")
                        break

                    if len(cleaned) == last_len and len(cleaned) > 5:
                        stable_count += 1
                        if stable_count >= 2:
                            final_translation = cleaned
                            logger.browser_event(f"Google AI: текст стабилизировался на такте {attempt}")
                            break
                    else:
                        stable_count = 0
                        last_len = len(cleaned)

            if not final_translation:
                logger.browser_event("Google AI: ответ не успел сформироваться вовремя, выполняется fallback")
                fallback_res = self.fetch_fast_word(clean_input, src=source_code, trg=target_code)
                if fallback_res:
                    final_translation = fallback_res
                else:
                    final_translation = "[Google AI: Сервис поиска не вернул перевод. Проверьте окно браузера.]"

            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "Google Search AI", elapsed, 200)
            print(f"[{self.name} готов за {elapsed}с]: {final_translation[:70]}...")
            return final_translation

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "Google Search AI", elapsed, 0, note=f"Ошибка: {e}")
            fallback_res = self.fetch_fast_word(clean_input, src=source_code, trg=target_code)
            if fallback_res:
                return fallback_res
            return f"Ошибка Google AI: {e}"

service = GoogleAIService()