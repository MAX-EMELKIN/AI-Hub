# data/services/gemini_family/service.py
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import socket
import ssl
import struct
import re
import urllib.request
import urllib.parse
import urllib.error
import threading

from data.services.base_service import BaseService
from data.core.api_config import api_config
from data.core.web_search import GEMINI_WEB_TOOLS, execute_tool_call, DEFAULT_SEARCH_PROMPT
from data.core.logger import logger
from data.core.i18n import t

ALLOWED_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro"
]

THINKING_MODES = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "OFF"
]

DOH_PRESETS = {
    "Comss.one (SmartDNS)": {
        "url": "https://dns.comss.one/dns-query",
        "host": "dns.comss.one",
        "bootstrap_ip": "195.133.25.16"
    },
    "Comss.one (SmartDNS / РФ обход)": {
        "url": "https://dns.comss.one/dns-query",
        "host": "dns.comss.one",
        "bootstrap_ip": "195.133.25.16"
    },
    "Xbox DNS (SmartDNS / РФ обход)": {
        "url": "https://xbox-dns.ru/dns-query",
        "host": "xbox-dns.ru",
        "bootstrap_ip": "111.88.96.54"
    },
    "Control D (Uncensored)": {
        "url": "https://freedns.controld.com/uncensored",
        "host": "freedns.controld.com",
        "bootstrap_ip": "76.76.2.11"
    },
    "Cloudflare (1.1.1.1)": {
        "url": "https://cloudflare-dns.com/dns-query",
        "host": "cloudflare-dns.com",
        "bootstrap_ip": "1.1.1.1"
    },
    "Google (8.8.8.8)": {
        "url": "https://dns.google/dns-query",
        "host": "dns.google",
        "bootstrap_ip": "8.8.8.8"
    }
}

BOOTSTRAP_HOSTS = {
    "dns.comss.one": "195.133.25.16",
    "xbox-dns.ru": "111.88.96.54",
    "freedns.controld.com": "76.76.2.11",
    "cloudflare-dns.com": "1.1.1.1",
    "dns.google": "8.8.8.8"
}

_dns_cache = {}
_dns_lock = threading.Lock()
_orig_getaddrinfo = socket.getaddrinfo


def _make_dns_query_wire(hostname):
    header = struct.pack("!HHHHHH", 0x1A2B, 0x0100, 1, 0, 0, 0)
    parts = hostname.strip(".").split(".")
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in parts) + b"\x00"
    question = qname + struct.pack("!HH", 1, 1)
    return header + question


def _parse_dns_response_wire(raw):
    if len(raw) < 12:
        return None
    _, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", raw[:12])
    if (flags & 0x000F) != 0:
        return None
    idx = 12
    for _ in range(qdcount):
        while idx < len(raw):
            length = raw[idx]
            if length == 0:
                idx += 1
                break
            elif (length & 0xC0) == 0xC0:
                idx += 2
                break
            else:
                idx += 1 + length
        idx += 4
    for _ in range(ancount):
        if idx >= len(raw):
            break
        while idx < len(raw):
            length = raw[idx]
            if length == 0:
                idx += 1
                break
            elif (length & 0xC0) == 0xC0:
                idx += 2
                break
            else:
                idx += 1 + length
        if idx + 10 > len(raw):
            break
        rtype, _, _, rdlength = struct.unpack("!HHIH", raw[idx:idx+10])
        idx += 10
        if rtype == 1 and rdlength == 4 and idx + 4 <= len(raw):
            return ".".join(str(b) for b in raw[idx:idx+4])
        idx += rdlength
    return None


def resolve_doh_stdlib(hostname, doh_url):
    with _dns_lock:
        if hostname in _dns_cache:
            return _dns_cache[hostname]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 1. RFC 8484 binary wireformat POST (PowerDNS, Comss.one, Xbox-DNS)
    try:
        wire_data = _make_dns_query_wire(hostname)
        req = urllib.request.Request(
            doh_url,
            data=wire_data,
            headers={
                "Content-Type": "application/dns-message",
                "Accept": "application/dns-message",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=3.5) as resp:
            if resp.status == 200:
                ip = _parse_dns_response_wire(resp.read())
                if ip:
                    with _dns_lock:
                        _dns_cache[hostname] = ip
                    return ip
    except Exception:
        pass

    # 2. JSON DoH fallback (Cloudflare, Google)
    try:
        url = f"{doh_url}?name={hostname}&type=A"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/dns-json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, context=ctx, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for ans in data.get("Answer", []):
                if ans.get("type") == 1 and ans.get("data"):
                    ip = ans["data"]
                    with _dns_lock:
                        _dns_cache[hostname] = ip
                    return ip
    except Exception:
        pass

    return None


def custom_gemini_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    host_str = str(host).lower().strip()
    for b_host, b_ip in BOOTSTRAP_HOSTS.items():
        if b_host in host_str:
            return _orig_getaddrinfo(b_ip, port, family, type, proto, flags)

    conn_mode = api_config.get_val("gemini_family", "connection_mode", "doh").lower().strip()
    if conn_mode == "doh" and "googleapis.com" in host_str:
        preset_name = api_config.get_val("gemini_family", "doh_preset", "Comss.one (SmartDNS)").strip()
        doh_url = None
        for p_key, p_val in DOH_PRESETS.items():
            if p_key.lower() in preset_name.lower() or preset_name.lower() in p_key.lower():
                doh_url = p_val.get("url")
                break
        if not doh_url:
            doh_url = api_config.get_val(
                "gemini_family", "doh_custom_url", "https://dns.comss.one/dns-query"
            ).strip()
        if not doh_url:
            doh_url = "https://dns.comss.one/dns-query"

        ip = resolve_doh_stdlib(str(host), doh_url)
        if ip:
            return _orig_getaddrinfo(ip, port, family, type, proto, flags)

    return _orig_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = custom_gemini_getaddrinfo


class GeminiFamilyService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="gemini_family",
            name="Gemini (DoH / Proxy)",
            route_name="/gemini_family",
            icon_name="Service.png"
        )
        self.supports_hyperparameters = True
        self.supports_glossary = True
        self.rate_timestamps = []
        self.rate_lock = threading.Lock()

    def get_config_fields(self):
        return [
            {"key": "api_key", "label": t("lbl_api_key"), "required": True},
            {"key": "model", "label": t("lbl_model"), "required": True},
            {"key": "connection_mode", "label": t("lbl_connection_mode"), "required": True},
            {"key": "doh_preset", "label": t("lbl_doh_preset"), "required": False},
            {"key": "doh_custom_url", "label": t("lbl_doh_custom"), "required": False},
            {"key": "proxy", "label": t("lbl_proxy_url"), "required": False},
            {"key": "search_prompt", "label": t("lbl_search_prompt"), "required": False}
        ]

    def is_ready(self):
        api_key = self.get_config_val("api_key", "").strip()
        if not api_key:
            return False, t("status_not_ready")
        return True, t("common.ready")

    def _wait_rate_limit(self, max_rpm=15, window=60.0):
        with self.rate_lock:
            now = time.time()
            self.rate_timestamps = [t for t in self.rate_timestamps if now - t < window]
            if len(self.rate_timestamps) >= max_rpm:
                oldest = self.rate_timestamps[0]
                wait_sec = window - (now - oldest) + 0.3
                if wait_sec > 0:
                    time.sleep(wait_sec)
                    now = time.time()
                    self.rate_timestamps = [t for t in self.rate_timestamps if now - t < window]
            self.rate_timestamps.append(time.time())

    def _build_generation_payload(self, contents, system_prompt="", model_name="", is_ping=False, enable_tools=False):
        if isinstance(contents, str):
            contents_payload = [{"role": "user", "parts": [{"text": contents}]}]
        else:
            contents_payload = contents

        payload = {
            "contents": contents_payload
        }

        gen_config = {}
        if is_ping:
            gen_config["maxOutputTokens"] = 1
            gen_config["thinkingConfig"] = {"thinkingLevel": "low"}
        else:
            try:
                temp = float(self.get_config_val("temperature", "0.2"))
            except Exception:
                temp = 0.2
            try:
                top_p = float(self.get_config_val("top_p", "0.2"))
            except Exception:
                top_p = 0.2
            try:
                max_tokens = int(self.get_config_val("max_tokens", "3072"))
            except Exception:
                max_tokens = 3072

            gen_config["temperature"] = temp
            gen_config["topP"] = top_p
            gen_config["maxOutputTokens"] = max_tokens

            thinking_map_raw = self.get_config_val("model_thinking", "")
            mode_str = ""
            if thinking_map_raw:
                try:
                    thinking_map = json.loads(thinking_map_raw)
                    mode_str = thinking_map.get(model_name, "")
                except Exception:
                    pass
            if not mode_str:
                mode_str = self.get_config_val("thinking_mode", "LOW")

            mode_str_lower = mode_str.lower()
            if "low" in mode_str_lower or "низк" in mode_str_lower:
                gen_config["thinkingConfig"] = {"thinkingLevel": "low"}
            elif "med" in mode_str_lower or "средн" in mode_str_lower:
                gen_config["thinkingConfig"] = {"thinkingLevel": "medium"}
            elif "high" in mode_str_lower or "высок" in mode_str_lower:
                gen_config["thinkingConfig"] = {"thinkingLevel": "high"}

            if system_prompt:
                payload["system_instruction"] = {
                    "parts": [{"text": system_prompt}]
                }

            if enable_tools and not is_ping:
                payload["tools"] = GEMINI_WEB_TOOLS

        payload["generationConfig"] = gen_config
        return payload

    def _get_opener(self):
        conn_mode = self.get_config_val("connection_mode", "doh")
        handlers = []
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))

        if conn_mode == "proxy":
            proxy_addr = self.get_config_val("proxy", "").strip()
            if proxy_addr:
                handlers.append(urllib.request.ProxyHandler({"http": proxy_addr, "https": proxy_addr}))
        return urllib.request.build_opener(*handlers)

    def ping_model(self, model_name=None):
        api_key = self.get_config_val("api_key", "").strip()
        if not api_key:
            return False, t("wizard.status_ping_fail"), 0

        target_model = model_name or self.get_config_val("model", ALLOWED_MODELS[0])
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
        payload = self._build_generation_payload("1", is_ping=True, model_name=target_model)
        data_bytes = json.dumps(payload).encode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        opener = self._get_opener()
        t0 = time.time()
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=data_bytes, headers=headers)
                with opener.open(req, timeout=10.0) as resp:
                    elapsed = round(time.time() - t0, 2)
                    if resp.status == 200:
                        logger.api_summary(self.name, target_model, elapsed, resp.status, note="Ping OK")
                        return True, f"{elapsed}s", elapsed
            except urllib.error.HTTPError as he:
                elapsed = round(time.time() - t0, 2)
                logger.api_summary(self.name, target_model, elapsed, he.code, note=f"HTTP Error {he.code}")
                if he.code == 429:
                    return False, "HTTP 429 (Rate Limit)", 0
                elif he.code == 404:
                    return False, "HTTP 404 (Not Found)", 0
                elif he.code == 401:
                    return False, "HTTP 401 (Unauthorized)", 0
                else:
                    return False, f"HTTP {he.code}", 0
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return False, f"Network Error: {e}", 0
        return False, "Connection Timeout", 0

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        ok, reason = self.is_ready()
        if not ok:
            return f"[{self.name}]: {reason}"

        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        t0 = time.time()
        if len(clean_input.split()) <= 2 and len(clean_input) < 15 and '\n' not in clean_input:
            fast_res = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            if fast_res:
                return fast_res

        annotated_text, system_prompt = self.prepare_text_and_prompt(
            clean_input, src_lang=src_lang, trg_lang=trg_lang, preset=preset
        )

        system_prompt += (
            "\n\nOUTPUT RULE: Provide ONLY the direct translation of the source text.\n"
            "Preserve original formatting, line breaks, and punctuation accurately.\n"
            "Do not add greetings, explanations, notes, or commentary."
        )

        enable_search = (self.get_config_val("enable_web_search", "0") in ("1", "true", "yes"))
        if enable_search:
            custom_search_prompt = self.get_config_val("search_prompt", "").strip()
            if not custom_search_prompt:
                custom_search_prompt = DEFAULT_SEARCH_PROMPT
            system_prompt += f"\n\n{custom_search_prompt}"

        api_key = self.get_config_val("api_key", "").strip()
        cur_model = self.get_config_val("model", ALLOWED_MODELS[0])

        opener = self._get_opener()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        self._wait_rate_limit(max_rpm=15, window=60.0)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cur_model}:generateContent"
        dialog_history = [{"role": "user", "parts": [{"text": annotated_text}]}]
        max_agent_steps = 3 if enable_search else 1

        for step in range(max_agent_steps):
            payload = self._build_generation_payload(
                dialog_history,
                system_prompt=system_prompt,
                model_name=cur_model,
                enable_tools=enable_search
            )
            data_bytes = json.dumps(payload).encode('utf-8')

            logger.api_payload(self.name, cur_model, url, headers, payload)
            t_call = time.time()

            try:
                req = urllib.request.Request(url, data=data_bytes, headers=headers)
                with opener.open(req, timeout=35.0) as resp:
                    raw_bytes = resp.read()
                    elapsed = time.time() - t_call
                    raw_str = raw_bytes.decode('utf-8')
                    raw_data = json.loads(raw_str)

                    logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                    logger.api_summary(self.name, cur_model, elapsed, resp.status)

            except urllib.error.HTTPError as he:
                elapsed = time.time() - t_call
                err_body = he.read().decode('utf-8', errors='ignore')
                logger.api_raw_response(self.name, he.code, elapsed, err_body)
                logger.api_summary(self.name, cur_model, elapsed, he.code, note=f"HTTP Error {he.code}")

                if he.code in (500, 502, 503, 504):
                    return f"[{self.name} (HTTP {he.code})]: Server Error"
                elif he.code == 429:
                    return f"[{self.name} (HTTP 429)]: Rate Limit Exceeded"
                elif he.code == 401:
                    return f"[{self.name} (HTTP 401)]: Invalid API Key"
                else:
                    return f"[{self.name} ({cur_model}, HTTP {he.code})]: {err_body[:200]}"
            except Exception as e:
                elapsed = time.time() - t_call
                logger.api_summary(self.name, cur_model, elapsed, 0, note=f"Exception: {e}")
                return f"[{self.name}]: Network Error: {e}"

            if not raw_data.get("candidates"):
                return f"[{self.name} ({cur_model})]: Empty response"

            cand_content = raw_data["candidates"][0].get("content", {})
            parts = cand_content.get("parts", [])

            function_call_found = None
            res_text = ""
            for p in parts:
                if "functionCall" in p:
                    function_call_found = p["functionCall"]
                elif "text" in p and p["text"]:
                    res_text += p["text"]

            if function_call_found and enable_search:
                fn_name = function_call_found.get("name")
                fn_args = function_call_found.get("args", {})

                dialog_history.append({"role": "model", "parts": [{"functionCall": function_call_found}]})
                tool_output = execute_tool_call(fn_name, fn_args)
                logger.tool_call(self.name, step + 1, fn_name, fn_args, tool_output)

                dialog_history.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": fn_name,
                            "response": {"result": tool_output}
                        }
                    }]
                })
                continue

            if res_text:
                final = self.clean_response(res_text)
                elapsed = round(time.time() - t0, 2)
                print(f"[{self.name} ({cur_model}) {elapsed}s]: {final[:70]}...")
                return final if final else clean_input

        return f"Error: [{self.name}]: Translation failed"

    def query_llm_raw(self, system_prompt, user_content, max_tokens=800, temperature=0.1):
        api_key = self.get_config_val("api_key", "").strip()
        if not api_key:
            return ""

        cur_model = self.get_config_val("model", ALLOWED_MODELS[0])
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cur_model}:generateContent"
        payload = self._build_generation_payload(user_content, system_prompt=system_prompt, model_name=cur_model)
        payload["generationConfig"]["maxOutputTokens"] = max_tokens
        payload["generationConfig"]["temperature"] = temperature

        opener = self._get_opener()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        logger.api_payload(self.name, cur_model, url, headers, payload)
        t_call = time.time()

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with opener.open(req, timeout=20.0) as resp:
                raw_bytes = resp.read()
                elapsed = time.time() - t_call
                raw_str = raw_bytes.decode('utf-8')
                data = json.loads(raw_str)

                logger.api_raw_response(self.name, resp.status, elapsed, raw_str)
                logger.api_summary(self.name, cur_model, elapsed, resp.status)

                res = ""
                if data.get("candidates") and len(data["candidates"]) > 0:
                    for p in data["candidates"][0].get("content", {}).get("parts", []):
                        if p.get("text"):
                            res += p["text"]
                return str(res).strip()
        except Exception as e:
            elapsed = time.time() - t_call
            logger.api_summary(self.name, cur_model, elapsed, 0, note=f"Exception: {e}")
            return ""


service = GeminiFamilyService()