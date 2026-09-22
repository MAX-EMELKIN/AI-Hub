# -*- coding: utf-8 -*-
# data/services/deepl_web/service.py
import time
import json
import re
from data.services.base_service import BaseService
from data.core.cdp_client import browser_cdp
from data.core.logger import logger

class DeepLWebService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="deepl_web",
            name="DeepL (Web)",
            route_name="/deepl_web",
            icon_name="Service.png"
        )
        self.is_ai_service = False
        self.supports_hyperparameters = False
        self.supports_glossary = False

    def get_config_fields(self):
        return [
            {"key": "endpoint", "label": "Text-Text DeepL:", "required": True}
        ]

    def is_ready(self):
        return True, "Text Text Text-Text DeepL Text Supermium (Text API-Text)"

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
                logger.api_summary(self.name, "DeepL QuickWord", elapsed, 200, note="Text-Text 1 Text")
                print(f"[DeepL Web]: Text Text 1 Text ({elapsed}Text): {fast_res}")
                return fast_res

        src_code = (src_lang or "auto").lower()
        trg_code = (trg_lang or "ru").lower()
        if src_code in ("zh-cn", "zh-tw", "auto-detect"):
            src_code = "auto"
        if trg_code in ("zh-cn", "zh-tw"):
            trg_code = "zh"

        logger.browser_event(f"DeepL Web: Text Text ({src_code} -> {trg_code}, Text: {len(clean_input)} Text.)")

        try:
            browser_cdp.ensure_browser_running()
            browser_cdp.send_tab_cdp_command("deepl", "Page.bringToFront", await_response=False)

            target_hash = f"#{src_code}/{trg_code}/"

            js_force_lang = f"""
            (() => {{
                try {{
                    const currentHash = window.location.hash;
                    if (!currentHash.startsWith('{target_hash}')) {{
                        localStorage.removeItem('lmt_text_translator.lastUsedSourceLanguages');
                        localStorage.removeItem('lmt_text_translator.lastUsedTargetLanguages');
                        window.location.replace("https://www.deepl.com/translator{target_hash}");
                        return true;
                    }}
                }} catch(e) {{}}
                return false;
            }})()
            """

            did_navigate = browser_cdp.evaluate_js_on_tab("deepl", js_force_lang)
            if did_navigate:
                logger.browser_event(f"DeepL Web: Text Text Text Text {target_hash}")
                time.sleep(0.5)

            has_input = False
            for _ in range(25):
                time.sleep(0.15)
                ready = browser_cdp.evaluate_js_on_tab(
                    "deepl",
                    "!!(document.querySelector('d-textarea[name=\"source\"]') || document.querySelector('[data-testid=\"translator-source-input\"]'))"
                )
                if ready:
                    has_input = True
                    break

            if not has_input:
                err = "[DeepL Web: Text Text Text Text Text. Text Text.]"
                logger.browser_event(f"DeepL Web: {err}")
                return err

            js_focus_and_clear = """
            (() => {
                document.querySelectorAll('button[data-testid="close-button"], .cookie-banner button, [aria-label="Close"]').forEach(b => { try { b.click(); } catch(e){} });

                const srcHost = document.querySelector('d-textarea[name="source"]') || document.querySelector('[data-testid="translator-source-input"]');
                if (!srcHost) return false;

                let editable = srcHost.shadowRoot ? srcHost.shadowRoot.querySelector('[contenteditable="true"], textarea') : srcHost.querySelector('[contenteditable="true"], textarea');
                if (!editable) editable = srcHost;

                editable.focus();

                if (editable.tagName === "TEXTAREA" || editable.tagName === "INPUT") {
                    editable.value = "";
                    editable.dispatchEvent(new Event('input', { bubbles: true }));
                    editable.dispatchEvent(new Event('change', { bubbles: true }));
                } else {
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(editable);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    document.execCommand('delete', false, null);
                }
                return true;
            })()
            """
            browser_cdp.evaluate_js_on_tab("deepl", js_focus_and_clear)
            time.sleep(0.2)

            browser_cdp.send_tab_cdp_command("deepl", "Input.insertText", {"text": clean_input}, await_response=False)

            js_extract = f"""
            (() => {{
                const originalText = {json.dumps(clean_input)}.trim().toLowerCase();

                function getTargetText() {{
                    const targetHost = document.querySelector('d-textarea[name="target"]') ||
                                       document.querySelector('[data-testid="translator-target-input"]');
                    if (targetHost) {{
                        let el = targetHost.shadowRoot ? targetHost.shadowRoot.querySelector('[contenteditable="true"], p, textarea') : targetHost.querySelector('[contenteditable="true"], p, textarea');
                        if (el && el.innerText) return el.innerText.trim();
                        if (targetHost.value) return targetHost.value.trim();
                    }}
                    return "";
                }}

                const result = getTargetText();
                const isBusy = !!document.querySelector('[data-testid="translator-target-loading"]') ||
                               !!document.querySelector('.loading-indicator') ||
                               !!document.querySelector('[data-testid="translator-target-skeleton"]');

                const isValid = (!isBusy && result.length > 0 && result.toLowerCase() !== originalText);

                return JSON.stringify({{
                    ready: isValid,
                    text: result
                }});
            }})()
            """

            final_translation = ""
            last_len = 0
            stable_count = 0

            for attempt in range(1, 80):
                time.sleep(0.15)
                poll_raw = browser_cdp.evaluate_js_on_tab("deepl", js_extract)
                if not poll_raw:
                    continue

                try:
                    p_data = json.loads(poll_raw)
                except Exception:
                    continue

                resp_text = p_data.get("text", "").strip()
                is_ready = p_data.get("ready", False)

                if resp_text and resp_text.lower() != clean_input.lower():
                    if is_ready:
                        if len(resp_text) == last_len:
                            stable_count += 1
                            if stable_count >= 2:
                                final_translation = resp_text
                                logger.browser_event(f"DeepL Web: Text Text Text Text {attempt}")
                                break
                        else:
                            stable_count = 0
                            last_len = len(resp_text)

            if not final_translation:
                if 'resp_text' in locals() and resp_text:
                    final_translation = resp_text
                else:
                    err = "[DeepL Web: Text Text Text Text. Text Text Text.]"
                    logger.browser_event(f"DeepL Web: {err}")
                    return err

            final_clean = self.clean_response(final_translation)
            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "DeepL Web", elapsed, 200)
            print(f"[{self.name} Text Text {elapsed}Text]: {final_clean[:70]}...")
            return final_clean

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            logger.api_summary(self.name, "DeepL Web", elapsed, 0, note=f"Error: {e}")
            print(f"[DeepL Web Error]: {e}")
            return f"Error DeepL Web: {e}"

service = DeepLWebService()
