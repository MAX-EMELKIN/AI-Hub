# -*- coding: utf-8 -*-
# data/services/chatgpt_web/service.py
import time
import json
import re
from data.services.base_service import BaseService
from data.core.cdp_client import browser_cdp
from data.core.logger import logger

CHATGPT_UI_JUNK = [
    "Text", "Text", "Edit", "Copy", "Bad response", "Good response",
    "Read aloud", "Text", "Text", "Share", "Text", "Text",
    "Text Text Text", "Message ChatGPT", "Text Text Text", "Ask anything"
]

JS_AUTO_DISMISS_POPUPS = """
(() => {
    const closeBtns = document.querySelectorAll('button[data-testid="close-button"], button[aria-label="Close"], button[aria-label="Text"], div[role="dialog"] button');
    closeBtns.forEach(b => {
        try {
            if (!b.getAttribute('data-testid') || !b.getAttribute('data-testid').includes('send')) {
                b.click();
            }
        } catch(e) {}
    });

    const buttons = document.querySelectorAll('button, a[role="button"], div[role="button"]');
    for (const btn of buttons) {
        const txt = (btn.innerText || "").trim().toLowerCase();
        if (
            txt.includes("Text") ||
            txt.includes("continue") ||
            txt.includes("stay logged out") ||
            txt.includes("Text") ||
            txt.includes("got it") ||
            txt.includes("dismiss") ||
            txt.includes("Text")
        ) {
            const testId = btn.getAttribute('data-testid') || '';
            if (!testId.includes('send') && !testId.includes('stop')) {
                try {
                    btn.click();
                    return true;
                } catch(e) {}
            }
        }
    }
    return false;
})()
"""

class ChatGPTWebService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="chatgpt_web",
            name="ChatGPT 4o (Web)",
            route_name="/chatgpt_web",
            icon_name="Service.png"
        )
        self.supports_hyperparameters = False
        self.supports_glossary = True

    def get_config_fields(self):
        return [
            {"key": "endpoint", "label": "Text-Text Text:", "required": True}
        ]

    def is_ready(self):
        return True, "Text Text Text-Text ChatGPT Text Supermium (Text API-Text)"

    def _extract_clean_translation(self, raw_text):
        if not raw_text:
            return ""
        t = raw_text.strip()

        for marker in [self.end_marker, "### END ###", "###END", "[[END]]", "[END]"]:
            if marker in t:
                t = t.split(marker)[0].strip()
                break

        return self.clean_response(t, ui_junk_list=CHATGPT_UI_JUNK)

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        words = clean_input.split()
        t0 = time.time()

        if (len(words) == 1 and len(clean_input) < 25 and '\n' not in clean_input) or (len(clean_input) <= 2 and re.search(r'[\u4e00-\u9fff]', clean_input)):
            fast_res = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            if fast_res:
                elapsed = round(time.time() - t0, 3)
                logger.api_summary(self.name, "ChatGPT QuickWord", elapsed, 200, note="Text-Text 1 Text")
                print(f"[ChatGPT Web]: Text Text 1 Text ({elapsed}Text): {fast_res}")
                return fast_res

        logger.browser_event(f"ChatGPT Web: Text Text ({src_lang} -> {trg_lang}, Text: {len(clean_input)} Text.)")
        query = self.build_prompt_query(clean_input, src_lang=src_lang, trg_lang=trg_lang, preset=preset)

        try:
            browser_cdp.ensure_browser_running()
            browser_cdp.send_tab_cdp_command("chatgpt", "Page.bringToFront", await_response=False)

            current_url = browser_cdp.evaluate_js_on_tab("chatgpt", "window.location.href")
            navigated_fresh = False
            if not current_url or "chatgpt.com" not in current_url:
                browser_cdp.navigate_tab("chatgpt", "https://chatgpt.com/")
                navigated_fresh = True

            browser_cdp.evaluate_js_on_tab("chatgpt", JS_AUTO_DISMISS_POPUPS)

            has_input = False
            max_wait = 25 if navigated_fresh else 10
            for _ in range(max_wait):
                time.sleep(0.15)
                browser_cdp.evaluate_js_on_tab("chatgpt", JS_AUTO_DISMISS_POPUPS)

                ready = browser_cdp.evaluate_js_on_tab(
                    "chatgpt",
                    "!!(document.querySelector('#prompt-textarea') || document.querySelector('div[contenteditable=\"true\"]') || document.querySelector('textarea'))"
                )
                if ready:
                    has_input = True
                    break

            if not has_input:
                is_cf = browser_cdp.evaluate_js_on_tab("chatgpt", "!!document.querySelector('iframe[src*=\"cloudflare\"], #challenge-running, #cf-turnstile')")
                is_login = browser_cdp.evaluate_js_on_tab("chatgpt", "!!document.querySelector('button[data-testid=\"login-button\"], a[href*=\"login\"]')")

                if is_cf:
                    err = "[ChatGPT Web: Text Text Cloudflare Text Text Text]"
                elif is_login:
                    err = "[ChatGPT Web: Text Text Text ChatGPT Text Text Text]"
                else:
                    err = "[ChatGPT Web: Text Text Text Text Text. Text Text.]"

                logger.browser_event(f"ChatGPT Web: {err}")
                return err

            if navigated_fresh:
                time.sleep(0.2)

            js_get_last_prev_text = """
            (() => {
                const els = document.querySelectorAll('.markdown, div[data-message-author-role="assistant"]');
                if (els.length === 0) return "";
                return (els[els.length - 1].innerText || "").trim();
            })()
            """
            prev_last_text = (browser_cdp.evaluate_js_on_tab("chatgpt", js_get_last_prev_text) or "").strip()

            query_json = json.dumps(query)
            js_input_text = f"""
            (() => {{
                const input = document.querySelector('#prompt-textarea') ||
                              document.querySelector('div[contenteditable="true"]') ||
                              document.querySelector('textarea');
                if (!input) return false;

                input.focus();

                if (input.tagName === "TEXTAREA" || input.tagName === "INPUT") {{
                    input.value = {query_json};
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }} else {{
                    const p = input.querySelector('p') || input;
                    p.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, {query_json});
                    input.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: {query_json} }}));
                }}
                return true;
            }})()
            """
            browser_cdp.evaluate_js_on_tab("chatgpt", js_input_text)
            time.sleep(0.06)

            browser_cdp.send_tab_cdp_command("chatgpt", "Input.insertText", {"text": query}, await_response=False)
            time.sleep(0.08)

            js_trigger_send = """
            (() => {
                const sendBtn = document.querySelector('button[data-testid="send-button"]') ||
                                document.querySelector('button[aria-label*="Text"]') ||
                                document.querySelector('button[aria-label*="Send"]');
                if (sendBtn && !sendBtn.disabled) {
                    sendBtn.click();
                    return true;
                }
                const form = document.querySelector('form');
                if (form) {
                    try { form.requestSubmit(); return true; } catch(e){}
                }
                if (sendBtn) {
                    sendBtn.removeAttribute('disabled');
                    sendBtn.disabled = false;
                    sendBtn.click();
                    return true;
                }
                return false;
            })()
            """

            for _ in range(4):
                time.sleep(0.1)
                browser_cdp.evaluate_js_on_tab("chatgpt", js_trigger_send)

                browser_cdp.send_tab_cdp_command("chatgpt", "Input.dispatchKeyEvent", {
                    "type": "rawKeyDown", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
                    "unmodifiedText": "\r", "text": "\r"
                }, await_response=False)
                browser_cdp.send_tab_cdp_command("chatgpt", "Input.dispatchKeyEvent", {
                    "type": "keyUp", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
                    "unmodifiedText": "\r", "text": "\r"
                }, await_response=False)

                check_status_js = """
                (() => {
                    const stopBtn = document.querySelector('button[data-testid="stop-button"], button[aria-label*="Stop"], button[aria-label*="Text"]');
                    return !!stopBtn;
                })()
                """
                if browser_cdp.evaluate_js_on_tab("chatgpt", check_status_js):
                    logger.browser_event("ChatGPT Web: Text Text Text")
                    break

            final_translation = ""
            prev_text_json = json.dumps(prev_last_text)

            js_poll = f"""
            (() => {{
                const els = document.querySelectorAll('.markdown, div[data-message-author-role="assistant"]');
                if (els.length === 0) {{
                    return JSON.stringify({{ state: "waiting", text: "" }});
                }}

                const last = els[els.length - 1];
                const clone = last.cloneNode(true);
                clone.querySelectorAll('button, [role="button"], [role="toolbar"], form, svg, [data-testid*="copy"], [data-testid*="edit"]').forEach(e => e.remove());

                const currentText = (clone.innerText || "").trim();
                const prevText = {prev_text_json};

                const stopBtn = document.querySelector('button[data-testid="stop-button"], button[aria-label*="Stop"], button[aria-label*="Text"]');
                const isGenerating = !!stopBtn;
                const isNew = (currentText.length > 0 && currentText !== prevText);

                return JSON.stringify({{
                    generating: isGenerating,
                    text: currentText,
                    is_new: isNew
                }});
            }})()
            """

            for attempt in range(1, 85):
                time.sleep(0.15)
                poll_raw = browser_cdp.evaluate_js_on_tab("chatgpt", js_poll)
                if not poll_raw:
                    continue

                try:
                    p_data = json.loads(poll_raw)
                except Exception:
                    continue

                resp_text = p_data.get("text", "").strip()
                is_generating = p_data.get("generating", False)
                is_new = p_data.get("is_new", False)

                if is_new and resp_text:
                    has_marker = any(m in resp_text for m in [self.end_marker, "### END ###", "###END"])
                    if has_marker:
                        final_translation = self._extract_clean_translation(resp_text)
                        logger.browser_event(f"ChatGPT Web: Text Text Text Text Text {attempt}")
                        break

                    if not is_generating and len(resp_text) > 5:
                        final_translation = self._extract_clean_translation(resp_text)
                        logger.browser_event(f"ChatGPT Web: Text Text Text Text {attempt}")
                        break

            if not final_translation and 'resp_text' in locals() and resp_text and is_new:
                final_translation = self._extract_clean_translation(resp_text)

            if not final_translation:
                final_translation = "[ChatGPT Web: Text Text Text Text. Text Text Text.]"
                logger.browser_event("ChatGPT Web: Text Text Text Text")

            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "ChatGPT 4o Web", elapsed, 200)
            print(f"[{self.name} Text Text {elapsed}Text]: {final_translation[:70]}...")
            return final_translation

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "ChatGPT 4o Web", elapsed, 0, note=f"Error: {e}")
            return f"Error ChatGPT Web: {e}"

service = ChatGPTWebService()
