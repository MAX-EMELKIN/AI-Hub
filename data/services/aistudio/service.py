# data/services/aistudio/service.py
# -*- coding: utf-8 -*-
import json
import time
import re
from data.services.base_service import BaseService
from data.core.cdp_client import browser_cdp
from data.core.logger import logger

AISTUDIO_URL = "https://aistudio.google.com/prompts/new_chat?model=gemini-3.8-flash"

AISTUDIO_UI_JUNK = [
    "edit", "more_vert", "User", "Model", "Thoughts", "keyboard_return",
    "Expand to view model thoughts", "chevron_right", "content_copy",
    "thumb_up", "thumb_down", "progress_activity", "Run Ctrl", "Stop"
]


class AIStudioService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="aistudio",
            name="Google AI Studio (Gemini 3.8 Flash)",
            route_name="/aistudio",
            icon_name="Service.png"
        )
        self.supports_hyperparameters = False
        self.supports_glossary = True
        self._session_initialized = False

    def get_config_fields(self):
        return [
            {
                "key": "endpoint",
                "label": "Веб-интерфейс AI Studio:",
                "default": AISTUDIO_URL,
                "required": False
            }
        ]

    def is_ready(self):
        return True, "Прямое подключение к Google AI Studio (Gemini 3.8 Flash) через браузер"

    def _log_step(self, step_text, t0):
        elapsed = round(time.time() - t0, 2)
        msg = f"AI Studio [{elapsed:.2f}с]: {step_text}"
        logger.browser_event(msg)
        print(f"[CDP Browser]: {msg}")

    def _extract_clean_translation(self, raw_text, is_single_word=False):
        if not raw_text:
            return ""
        t = raw_text.strip()
        for marker in [self.end_marker, "### END ###", "###END", "[[END]]", "[END]", "###КОНЕЦ###"]:
            if marker in t:
                t = t.split(marker)[0].strip()
                break
        cleaned = self.clean_response(t, ui_junk_list=AISTUDIO_UI_JUNK)
        cleaned = re.sub(r'(- [^\n]+)\n\n(?=- )', r'\1\n', cleaned)
        cleaned = re.sub(r'(\d+\.\s[^\n]+)\n\n(?=\d+\.\s)', r'\1\n', cleaned)
        logger.text_filtering(self.name, "Очистка служебных маркеров", raw_text, cleaned)
        return cleaned

    def _ensure_thinking_low(self, t0):
        js = """
        (() => {
            const sel = document.querySelector('mat-select[aria-label="Thinking Level"], mat-select');
            if (!sel) return "not_found";
            const val = (sel.innerText || '').trim().toLowerCase();
            if (val.includes('low')) return "already_low";
            sel.click();
            return "clicked";
        })();
        """
        res = browser_cdp.evaluate_js_on_tab("aistudio", js)
        if res == "clicked":
            time.sleep(0.25)
            picked = browser_cdp.evaluate_js_on_tab("aistudio", """
                (() => {
                    const opts = Array.from(document.querySelectorAll('mat-option, [role="option"]'));
                    const low = opts.find(o => (o.innerText || '').trim().toLowerCase() === 'low');
                    if (low) {
                        low.click();
                        return true;
                    }
                    return false;
                })();
            """)
            time.sleep(0.15)
            self._log_step(f"Thinking Level переключен в режим Low (успех: {picked})", t0)
        elif res == "already_low":
            self._log_step("Thinking Level уже находится в режиме Low", t0)
        else:
            self._log_step("Переключатель Thinking Level не найден на странице", t0)

    def _wait_for_input_ready(self, t0):
        for _ in range(60):
            ready = browser_cdp.evaluate_js_on_tab("aistudio", """
                (() => {
                    const ta = document.querySelector('textarea.cdk-textarea-autosize, textarea');
                    return ta && !ta.disabled && document.readyState === 'complete';
                })();
            """)
            if ready:
                self._log_step("Поле ввода textarea готово к приему данных", t0)
                return True
            time.sleep(0.2)
        self._log_step("Таймаут: поле ввода textarea не стало готовым за 12 секунд", t0)
        return False

    def _dismiss_welcome_dialog(self, t0):
        js_dismiss = """
        (() => {
            const dialog = document.querySelector('mat-dialog-container, [role="dialog"]');
            if (!dialog) return false;
            const checkboxes = Array.from(dialog.querySelectorAll('input[type="checkbox"], mat-checkbox'));
            checkboxes.forEach(cb => {
                if (!cb.checked && cb.getAttribute('aria-checked') !== 'true') cb.click();
            });
            const continueBtn = Array.from(dialog.querySelectorAll('button')).find(b => {
                const t = (b.innerText || '').trim().toLowerCase();
                return t.includes('continue') || t.includes('продолжить');
            });
            if (continueBtn && !continueBtn.disabled) {
                continueBtn.click();
                return true;
            }
            return false;
        })();
        """
        dismissed = browser_cdp.evaluate_js_on_tab("aistudio", js_dismiss)
        if dismissed:
            self._log_step("Приветственное окно лицензии обнаружено и закрыто", t0)

    def _inject_and_run(self, prompt_text, t0):
        payload_json = json.dumps(prompt_text, ensure_ascii=False)
        js_inject = f"""
        (() => {{
            const ta = document.querySelector('textarea.cdk-textarea-autosize, textarea');
            if (!ta) return JSON.stringify({{ ok: false, error: 'textarea_not_found' }});
            ta.focus();
            ta.value = '';
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            ta.value = {payload_json};
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return JSON.stringify({{ ok: true, len: ta.value.length }});
        }})();
        """
        inject_raw = browser_cdp.evaluate_js_on_tab("aistudio", js_inject)
        try:
            inject_res = json.loads(inject_raw) if inject_raw else {}
        except Exception:
            inject_res = {}

        if not inject_res.get("ok"):
            err_msg = inject_res.get("error", "unknown_error")
            self._log_step(f"Ошибка вставки текста в textarea: {err_msg}", t0)
            raise Exception(f"Поле ввода недоступно ({err_msg}).")

        self._log_step(f"Поле ввода очищено, новый текст вставлен ({inject_res.get('len', 0)} симв.)", t0)
        time.sleep(0.1)

        js_click_run = """
        (() => {
            const btn = document.querySelector('button.ctrl-enter-submits, button[aria-label*="Run"]');
            if (!btn) return JSON.stringify({ ok: false, error: 'btn_not_found' });
            if (btn.disabled) return JSON.stringify({ ok: false, error: 'btn_disabled' });
            btn.click();
            return JSON.stringify({ ok: true, text: (btn.innerText || '').replace(/\\n/g, ' ') });
        })();
        """
        click_raw = browser_cdp.evaluate_js_on_tab("aistudio", js_click_run)
        try:
            click_res = json.loads(click_raw) if click_raw else {}
        except Exception:
            click_res = {}

        if click_res.get("ok"):
            self._log_step(f"Кнопка отправки нажата кликом мышью ('{click_res.get('text', '')}')", t0)
        else:
            self._log_step("Клик по кнопке не сработал, отправка через сочетание клавиш Ctrl+Enter", t0)
            browser_cdp.send_tab_cdp_command("aistudio", "Input.dispatchKeyEvent", {
                "type": "rawKeyDown", "windowsVirtualKeyCode": 17, "nativeVirtualKeyCode": 17
            }, await_response=False)
            browser_cdp.send_tab_cdp_command("aistudio", "Input.dispatchKeyEvent", {
                "type": "rawKeyDown", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
                "modifiers": 2
            }, await_response=False)
            browser_cdp.send_tab_cdp_command("aistudio", "Input.dispatchKeyEvent", {
                "type": "keyUp", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
                "modifiers": 2
            }, await_response=False)
            browser_cdp.send_tab_cdp_command("aistudio", "Input.dispatchKeyEvent", {
                "type": "keyUp", "windowsVirtualKeyCode": 17, "nativeVirtualKeyCode": 17
            }, await_response=False)

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        if not text or not str(text).strip():
            return ""

        t0 = time.time()
        source_text = str(text).strip()
        is_single_word = len(source_text.split()) == 1 and not source_text.endswith(".")
        query = self.build_prompt_query(source_text, src_lang=src_lang, trg_lang=trg_lang, preset=preset)

        logger.api_payload(self.name, "gemini-3.8-flash", AISTUDIO_URL, {"Content-Type": "text/plain"}, query)
        self._log_step(f"Старт перевода ({src_lang} -> {trg_lang}, {len(source_text)} симв.)", t0)

        browser_cdp.ensure_browser_running()
        client = browser_cdp.get_tab_client("aistudio")
        if not client:
            raise Exception("Не удалось подключиться к вкладке Google AI Studio по CDP.")

        browser_cdp.send_tab_cdp_command("aistudio", "Page.bringToFront", await_response=False)

        current_url = browser_cdp.evaluate_js_on_tab("aistudio", "window.location.href") or ""
        if "aistudio.google.com" not in current_url:
            self._log_step(f"Вкладка не открыта, переход по URL: {AISTUDIO_URL}", t0)
            browser_cdp.navigate_tab("aistudio", AISTUDIO_URL)
            for _ in range(40):
                time.sleep(0.3)
                c_url = browser_cdp.evaluate_js_on_tab("aistudio", "window.location.href") or ""
                ready_state = browser_cdp.evaluate_js_on_tab("aistudio", "document.readyState")
                if "aistudio.google.com" in c_url and ready_state == "complete":
                    break
            time.sleep(1.5)
            self._log_step("Страница загружена, пауза 1.5с для инициализации сессии Google", t0)
            self._session_initialized = False
        else:
            self._log_step(f"Используется уже открытая сессия AI Studio ({current_url[:45]}...)", t0)

        self._dismiss_welcome_dialog(t0)
        self._wait_for_input_ready(t0)

        if not self._session_initialized:
            self._ensure_thinking_low(t0)
            self._session_initialized = True

        js_count_turns = "document.querySelectorAll('ms-chat-turn').length;"
        initial_turns = int(browser_cdp.evaluate_js_on_tab("aistudio", js_count_turns) or 0)
        self._log_step(f"Зафиксировано ходов в чате до отправки: {initial_turns}", t0)

        self._inject_and_run(query, t0)

        timeout = 45.0
        t_poll_start = time.time()
        raw_result = ""
        has_seen_stop = False
        last_reported_len = -1
        last_text_seen = ""
        stable_ticks = 0

        js_poll = """
        (() => {
            const btn = document.querySelector('button.ctrl-enter-submits, button[aria-label*="Run"]');
            const btnText = btn ? (btn.innerText || '') : '';
            const isStop = btnText.includes('Stop');

            const allTurns = Array.from(document.querySelectorAll('ms-chat-turn'));
            const totalTurns = allTurns.length;

            let lastTurnText = '';
            let hasInternalError = false;

            if (totalTurns > 0) {
                const lastTurn = allTurns[totalTurns - 1];
                const rawTurnContent = lastTurn.innerText || '';
                if (rawTurnContent.includes('An internal error has occurred')) {
                    hasInternalError = true;
                }
                const chunks = Array.from(lastTurn.querySelectorAll('ms-text-chunk'))
                    .filter(c => !c.closest('.thought-activity-host'));

                chunks.forEach(chunk => {
                    chunk.querySelectorAll('ul li').forEach(li => {
                        if (!li.dataset.hubMarked) {
                            const target = li.querySelector('p') || li;
                            target.prepend(document.createTextNode('- '));
                            li.dataset.hubMarked = '1';
                        }
                    });
                    chunk.querySelectorAll('ol li').forEach((li, idx) => {
                        if (!li.dataset.hubMarked) {
                            const target = li.querySelector('p') || li;
                            target.prepend(document.createTextNode((idx + 1) + '. '));
                            li.dataset.hubMarked = '1';
                        }
                    });
                });

                lastTurnText = chunks.map(c => (c.innerText || '').trim()).filter(Boolean).join('\\n\\n');
                lastTurnText = lastTurnText.replace(/(- [^\\n]+)\\n\\n(?=- )/g, '$1\\n');
                lastTurnText = lastTurnText.replace(/(\\d+\\.\\s[^\\n]+)\\n\\n(?=\\d+\\.\\s)/g, '$1\\n');
            }

            return JSON.stringify({
                isStop: isStop,
                totalTurns: totalTurns,
                btnText: btnText.replace(/\\n/g, ' ').trim(),
                hasInternalError: hasInternalError,
                text: lastTurnText
            });
        })();
        """

        while time.time() - t_poll_start < timeout:
            time.sleep(0.3)
            poll_raw = browser_cdp.evaluate_js_on_tab("aistudio", js_poll)
            try:
                st = json.loads(poll_raw) if poll_raw else {}
            except Exception:
                continue

            is_stop = st.get("isStop", False)
            total_turns = st.get("totalTurns", 0)
            current_text = st.get("text", "")
            btn_text = st.get("btnText", "")
            has_internal_err = st.get("hasInternalError", False)

            if has_internal_err:
                self._log_step("Внимание: сайт Google вывел 'An internal error has occurred'", t0)
                return "Ошибка Google AI Studio: An internal error has occurred. Обновите страницу чата вручную."

            has_end_marker = any(m in current_text for m in [self.end_marker, "###END###", "### END ###", "###END"])
            if has_end_marker:
                raw_result = current_text
                self._log_step(f"Маркер конца ###END### обнаружен в ответе ({len(current_text)} симв.)!", t0)
                break

            if is_stop:
                if not has_seen_stop:
                    has_seen_stop = True
                    self._log_step(f"Обнаружен статус генерации (кнопка: '{btn_text}')", t0)

                if current_text and len(current_text) != last_reported_len:
                    last_reported_len = len(current_text)
                    raw_result = current_text
                    self._log_step(f"Поток ответа: получено {len(current_text)} симв.", t0)
                continue

            if has_seen_stop and not is_stop:
                if current_text == last_text_seen and len(current_text) > 0:
                    stable_ticks += 1
                    self._log_step(f"Кнопка Run, ожидание стабилизации текста ({stable_ticks}/2, {len(current_text)} симв.)", t0)
                    if stable_ticks >= 2:
                        raw_result = current_text
                        self._log_step(f"Генерация завершена сайтом (текст зафиксирован, {len(current_text)} симв.)", t0)
                        break
                else:
                    stable_ticks = 0
                    last_text_seen = current_text
                    raw_result = current_text
                    self._log_step(f"Поток продолжается: получено {len(current_text)} симв.", t0)
                continue

            if total_turns > initial_turns and current_text:
                if current_text == last_text_seen:
                    stable_ticks += 1
                    if stable_ticks >= 3:
                        raw_result = current_text
                        self._log_step(f"Генерация завершена по таймауту стабильности ({len(current_text)} симв.)", t0)
                        break
                else:
                    stable_ticks = 0
                    last_text_seen = current_text
                    raw_result = current_text

        elapsed_total = round(time.time() - t0, 2)

        logger.api_raw_response(self.name, 200, elapsed_total, raw_result)
        logger.api_summary(self.name, "gemini-3.8-flash", elapsed_total, 200 if raw_result else 0)

        if not raw_result:
            self._log_step(f"Таймаут ожидания ответа ({elapsed_total}с), ответ пуст", t0)
            return "[Google AI Studio: Превышено время ожидания ответа от модели]"

        clean_result = self._extract_clean_translation(raw_result, is_single_word)
        final_text = clean_result if clean_result else raw_result

        self._log_step(f"Перевод полностью готов за {elapsed_total}с ({len(final_text)} симв.)", t0)
        return final_text


service = AIStudioService()