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
        "fallback_url": "https://router.comss.one/dns-query"
    },
    "Comss.one (SmartDNS / РФ обход)": {
        "url": "https://dns.comss.one/dns-query",
        "fallback_url": "https://router.comss.one/dns-query"
    },
    "Xbox DNS (SmartDNS / РФ обход)": {
        "url": "https://xbox-dns.ru/dns-query",
        "fallback_url": "https://dns.comss.one/dns-query"
    },
    "Control D (Uncensored)": {
        "url": "https://freedns.controld.com/uncensored"
    },
    "Cloudflare (1.1.1.1)": {
        "url": "https://cloudflare-dns.com/dns-query"
    },
    "Google (8.8.8.8)": {
        "url": "https://dns.google/dns-query"
    }
}

SMARTDNS_FALLBACK_IPS = ["45.155.204.190", "185.250.151.49"]

_dns_cache = {}
_dns_lock = threading.Lock()


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


def resolve_doh(hostname, doh_url):
    with _dns_lock:
        if hostname in _dns_cache:
            return _dns_cache[hostname]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 1. RFC 8484 binary wireformat POST
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

    # 2. JSON DoH fallback
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


def _recv_all(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Соединение разорвано удаленной стороной.")
        data.extend(packet)
    return bytes(data)


def create_socks5_socket(proxy_host, proxy_port, dest_host, dest_port, timeout=15.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))
    s.sendall(b"\x05\x01\x00")
    resp = _recv_all(s, 2)
    if resp[0] != 5 or resp[1] != 0:
        s.close()
        raise ConnectionError("SOCKS5: Аутентификация отклонена сервером.")
    dest_bytes = dest_host.encode("utf-8")
    req = b"\x05\x01\x00\x03" + bytes([len(dest_bytes)]) + dest_bytes + struct.pack("!H", dest_port)
    s.sendall(req)
    resp_header = _recv_all(s, 4)
    if resp_header[0] != 5 or resp_header[1] != 0:
        s.close()
        raise ConnectionError(f"SOCKS5: Ошибка запроса соединения (код: {resp_header[1]})")
    atyp = resp_header[3]
    if atyp == 1:
        _recv_all(s, 6)
    elif atyp == 3:
        length = _recv_all(s, 1)[0]
        _recv_all(s, length + 2)
    elif atyp == 4:
        _recv_all(s, 18)
    return s


def parse_proxy_string(proxy_str):
    clean = re.sub(r'^(?:socks5h?|https?|socks)://', '', str(proxy_str).strip(), flags=re.IGNORECASE)
    parts = clean.split(':')
    if len(parts) >= 2:
        try:
            return parts[0].strip(), int(parts[1].strip())
        except ValueError:
            pass
    return "127.0.0.1", 10808


def dechunk_http_body(raw_bytes):
    pos = 0
    decoded = bytearray()
    length = len(raw_bytes)
    while pos < length:
        crlf_idx = raw_bytes.find(b"\r\n", pos)
        if crlf_idx == -1:
            break
        chunk_header = raw_bytes[pos:crlf_idx].strip()
        if not chunk_header:
            pos = crlf_idx + 2
            continue
        hex_len = chunk_header.split(b";")[0].strip()
        try:
            chunk_size = int(hex_len, 16)
        except ValueError:
            return raw_bytes
        if chunk_size == 0:
            break
        data_start = crlf_idx + 2
        data_end = data_start + chunk_size
        decoded.extend(raw_bytes[data_start:data_end])
        pos = data_end + 2
    return bytes(decoded) if decoded else raw_bytes


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

    def _execute_request_raw(self, url, payload_bytes, headers, timeout=35.0):
        conn_mode = self.get_config_val("connection_mode", "doh").lower().strip()
        proxy_val = self.get_config_val("proxy", "127.0.0.1:10808").strip()
        parsed = urllib.parse.urlparse(url)
        dest_host = parsed.hostname or "generativelanguage.googleapis.com"
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        if conn_mode in ("proxy", "socks5"):
            p_host, p_port = parse_proxy_string(proxy_val)
            raw_sock = create_socks5_socket(p_host, p_port, dest_host, dest_port, timeout=timeout)
            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(raw_sock, server_hostname=dest_host)
            else:
                sock = raw_sock

            req_headers = dict(headers)
            req_headers["Host"] = dest_host
            req_headers["Content-Length"] = str(len(payload_bytes))
            req_headers["Connection"] = "close"

            header_lines = [f"POST {path} HTTP/1.1"]
            for k, v in req_headers.items():
                header_lines.append(f"{k}: {v}")
            header_data = "\r\n".join(header_lines) + "\r\n\r\n"

            sock.sendall(header_data.encode("utf-8") + payload_bytes)
            response_bytes = bytearray()
            sock.settimeout(timeout)
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_bytes.extend(chunk)
                except ConnectionResetError:
                    break
            sock.close()

            parts = bytes(response_bytes).split(b"\r\n\r\n", 1)
            header_bytes = parts[0]
            body_bytes = parts[1] if len(parts) > 1 else b""
            header_str = header_bytes.decode("utf-8", errors="replace")
            if "chunked" in header_str.lower():
                body_bytes = dechunk_http_body(body_bytes)
            raw_str = body_bytes.decode("utf-8", errors="replace")
            status_code = 200
            m_status = re.search(r'HTTP/\S+\s+(\d+)', header_str)
            if m_status:
                status_code = int(m_status.group(1))
            return status_code, raw_str

        elif conn_mode == "doh":
            preset_name = self.get_config_val("doh_preset", "Comss.one (SmartDNS)").strip()
            preset_info = None
            for p_key, p_val in DOH_PRESETS.items():
                if p_key.lower() in preset_name.lower() or preset_name.lower() in p_key.lower():
                    preset_info = p_val
                    break

            doh_url = preset_info.get("url") if preset_info else None
            if not doh_url:
                doh_url = self.get_config_val("doh_custom_url", "https://dns.comss.one/dns-query").strip()
            if not doh_url:
                doh_url = "https://dns.comss.one/dns-query"

            ip = resolve_doh(dest_host, doh_url)
            if not ip and preset_info and preset_info.get("fallback_url"):
                ip = resolve_doh(dest_host, preset_info["fallback_url"])
            if not ip:
                ip = resolve_doh(dest_host, "https://xbox-dns.ru/dns-query")
            if not ip:
                for fallback_ip in SMARTDNS_FALLBACK_IPS:
                    ip = fallback_ip
                    break

            target_ip = ip if ip else dest_host

            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(timeout)
            raw_sock.connect((target_ip, dest_port))

            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(raw_sock, server_hostname=dest_host)
            else:
                sock = raw_sock

            req_headers = dict(headers)
            req_headers["Host"] = dest_host
            req_headers["Content-Length"] = str(len(payload_bytes))
            req_headers["Connection"] = "close"

            header_lines = [f"POST {path} HTTP/1.1"]
            for k, v in req_headers.items():
                header_lines.append(f"{k}: {v}")
            header_data = "\r\n".join(header_lines) + "\r\n\r\n"

            sock.sendall(header_data.encode("utf-8") + payload_bytes)
            response_bytes = bytearray()
            sock.settimeout(timeout)
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_bytes.extend(chunk)
                except ConnectionResetError:
                    break
            sock.close()

            parts = bytes(response_bytes).split(b"\r\n\r\n", 1)
            header_bytes = parts[0]
            body_bytes = parts[1] if len(parts) > 1 else b""
            header_str = header_bytes.decode("utf-8", errors="replace")
            if "chunked" in header_str.lower():
                body_bytes = dechunk_http_body(body_bytes)
            raw_str = body_bytes.decode("utf-8", errors="replace")
            status_code = 200
            m_status = re.search(r'HTTP/\S+\s+(\d+)', header_str)
            if m_status:
                status_code = int(m_status.group(1))
            return status_code, raw_str

        else:
            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                    return resp.status, resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as he:
                return he.code, he.read().decode("utf-8", errors="replace")

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

        t0 = time.time()
        for attempt in range(2):
            try:
                status_code, raw_str = self._execute_request_raw(url, data_bytes, headers, timeout=12.0)
                elapsed = round(time.time() - t0, 2)
                if status_code == 200:
                    logger.api_summary(self.name, target_model, elapsed, status_code, note="Ping OK")
                    return True, f"{elapsed}s", elapsed
                else:
                    logger.api_summary(self.name, target_model, elapsed, status_code, note=f"HTTP {status_code}")
                    if status_code == 429:
                        return False, "HTTP 429 (Rate Limit)", 0
                    elif status_code == 404:
                        return False, "HTTP 404 (Not Found)", 0
                    elif status_code == 401:
                        return False, "HTTP 401 (Unauthorized)", 0
                    elif status_code == 400:
                        return False, f"HTTP 400: {raw_str[:120]}", 0
                    else:
                        return False, f"HTTP {status_code}", 0
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
                status_code, raw_str = self._execute_request_raw(url, data_bytes, headers, timeout=35.0)
                elapsed = time.time() - t_call
                logger.api_raw_response(self.name, status_code, elapsed, raw_str)
                logger.api_summary(self.name, cur_model, elapsed, status_code)

                if status_code >= 400:
                    if status_code in (500, 502, 503, 504):
                        return f"[{self.name} (HTTP {status_code})]: Server Error"
                    elif status_code == 429:
                        return f"[{self.name} (HTTP 429)]: Rate Limit Exceeded"
                    elif status_code == 401:
                        return f"[{self.name} (HTTP 401)]: Invalid API Key"
                    else:
                        return f"[{self.name} ({cur_model}, HTTP {status_code})]: {raw_str[:200]}"

                raw_data = json.loads(raw_str)

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

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        logger.api_payload(self.name, cur_model, url, headers, payload)
        t_call = time.time()

        try:
            data_bytes = json.dumps(payload).encode('utf-8')
            status_code, raw_str = self._execute_request_raw(url, data_bytes, headers, timeout=20.0)
            elapsed = time.time() - t_call
            logger.api_raw_response(self.name, status_code, elapsed, raw_str)
            logger.api_summary(self.name, cur_model, elapsed, status_code)

            if status_code != 200:
                return ""

            data = json.loads(raw_str)
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