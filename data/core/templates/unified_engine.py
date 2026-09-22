# -*- coding: utf-8 -*-
# data/core/templates/unified_engine.py

import os, sys, time, json, socket, ssl, struct, re, threading
import urllib.request, urllib.parse, urllib.error

UNIFIED_DOH_PRESETS = {
    "Comss.one (SmartDNS / Text Text)": {
        "url": "https://dns.comss.one/dns-query",
        "host": "dns.comss.one",
        "bootstrap_ip": "195.133.25.16"
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

_doh_dns_cache = {}
_doh_dns_lock = threading.Lock()

def resolve_doh(hostname, doh_url):
    with _doh_dns_lock:
        if hostname in _doh_dns_cache:
            return _doh_dns_cache[hostname]

    try:
        url = f"{doh_url}?name={hostname}&type=A"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/dns-json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:
                    ip = ans.get("data")
                    with _doh_dns_lock:
                        _doh_dns_cache[hostname] = ip
                    return ip
    except Exception:
        pass
    return None

def _recv_all(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Text Text Text Text.")
        data.extend(packet)
    return bytes(data)

def create_socks5_socket(proxy_host, proxy_port, dest_host, dest_port, timeout=8.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))

    s.sendall(b"\x05\x01\x00")
    resp = _recv_all(s, 2)
    if resp[0] != 5 or resp[1] != 0:
        s.close()
        raise ConnectionError("SOCKS5 Text Text Text Text Text.")

    dest_bytes = dest_host.encode("utf-8")
    req = b"\x05\x01\x00\x03" + bytes([len(dest_bytes)]) + dest_bytes + struct.pack("!H", dest_port)
    s.sendall(req)

    resp_header = _recv_all(s, 4)
    if resp_header[0] != 5 or resp_header[1] != 0:
        s.close()
        raise ConnectionError(f"SOCKS5 Text Text (Text: {resp_header[1]})")

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

def extract_clean_json_body(raw_str):
    start = raw_str.find('{')
    end = raw_str.rfind('}')
    if start != -1 and end != -1 and end > start:
        return raw_str[start:end + 1]
    return raw_str

def execute_test_ping(service_id, test_data, quick_mode=True):
    endpoint = str(test_data.get("endpoint", "")).strip()
    model = str(test_data.get("model", "")).strip()
    api_key = str(test_data.get("api_key", "")).strip()
    account_id = str(test_data.get("account_id", "")).strip()
    conn_mode = str(test_data.get("connection_mode", "direct")).lower().strip()
    proxy_val = str(test_data.get("proxy", "213.165.38.49:1080")).strip()
    doh_preset = str(test_data.get("doh_preset", "smartdns")).strip()

    if not endpoint or not model:
        return False, "Text Text URL Text Text Text Text."

    if "{account_id}" in endpoint:
        aid = account_id if account_id else "b53d06890fe315cfac0a5e6c074f99b4"
        endpoint = endpoint.replace("{account_id}", aid)
    if "{model}" in endpoint:
        endpoint = endpoint.replace("{model}", model)

    prompt = "Ping. Answer with only: OK" if quick_mode else "Translate to Russian: Hello world"
    max_tokens = 16 if quick_mode else 128

    if "cloudflare" in endpoint:
        payload = {"prompt": prompt, "max_tokens": max_tokens}
    else:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "QTranslate-AI-Hub/2.0"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if "openrouter" in endpoint:
        headers["HTTP-Referer"] = "https://github.com/MAX-EMELKIN/AI-Hub"
        headers["X-Title"] = "QTranslate AI Hub"

    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    timeout = 8.0
    t0 = time.time()

    try:
        parsed = urllib.parse.urlparse(endpoint)
        dest_host = parsed.hostname or "localhost"
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        if conn_mode == "socks5":
            p_host, p_port = parse_proxy_string(proxy_val)
            sock = create_socks5_socket(p_host, p_port, dest_host, dest_port, timeout=timeout)
            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
                client_sock = ctx.wrap_socket(sock, server_hostname=dest_host)
            else:
                client_sock = sock

            lines = [f"POST {path} HTTP/1.1", f"Host: {dest_host}", f"Content-Length: {len(payload_bytes)}", "Connection: close"]
            for k, v in headers.items():
                lines.append(f"{k}: {v}")
            client_sock.sendall("\r\n".join(lines).encode("utf-8") + b"\r\n\r\n" + payload_bytes)

            chunks = []
            while True:
                try:
                    c = client_sock.recv(8192)
                    if not c: break
                    chunks.append(c)
                except socket.timeout:
                    break
            client_sock.close()

            raw_resp = b"".join(chunks)
            sep = raw_resp.find(b"\r\n\r\n")
            if sep == -1:
                return False, "Text Text Text Text."
            h_part = raw_resp[:sep].decode("latin1", errors="replace")
            b_part = raw_resp[sep+4:]

            if "chunked" in h_part.lower():
                b_part = dechunk_http_body(b_part)

            body_str = b_part.decode("utf-8", errors="replace")
            status = 200
            m_code = re.search(r'HTTP/\S+\s+(\d+)', h_part)
            if m_code:
                status = int(m_code.group(1))

            if status >= 400:
                return False, f"HTTP {status}: {body_str[:200]}"
            raw_text = body_str

        else:
            target_url = endpoint
            if conn_mode == "doh":
                preset_info = UNIFIED_DOH_PRESETS.get(doh_preset, {})
                doh_url = preset_info.get("url", "https://dns.comss.one/dns-query")
                ip = resolve_doh(dest_host, doh_url)
                if ip and ip != dest_host:
                    headers["Host"] = dest_host
                    port_str = f":{dest_port}" if parsed.port else ""
                    target_url = urllib.parse.urlunparse((parsed.scheme, f"{ip}{port_str}", parsed.path, parsed.params, parsed.query, parsed.fragment))

            req = urllib.request.Request(target_url, data=payload_bytes, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                raw_text = resp.read().decode("utf-8", errors="replace")

        elapsed = round(time.time() - t0, 2)
        clean_json = extract_clean_json_body(raw_text)

        try:
            data = json.loads(clean_json)
        except Exception:
            data = None

        if data and isinstance(data, dict) and data.get("error"):
            err_msg = data["error"].get("message", str(data["error"]))
            return False, f"Error API: {err_msg}"

        if not quick_mode:
            if data:
                try:
                    pretty = json.dumps(data, indent=2, ensure_ascii=False)
                    return True, f"HTTP 200 OK | Text Text: {elapsed}Text\n{pretty}"
                except Exception:
                    pass
            return True, f"HTTP 200 OK | Text Text: {elapsed}Text\n{raw_text}"

        result = ""
        if data:
            if "choices" in data and len(data["choices"]) > 0:
                c = data["choices"][0]
                result = c.get("message", {}).get("content") or c.get("text", "")
            elif "result" in data and isinstance(data["result"], dict):
                result = data["result"].get("response", "")
            elif "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts:
                    result = parts[0].get("text", "")

        if not result:
            result = raw_text[:120]

        result = re.sub(r'<think>[\s\S]*?</think>', '', str(result), flags=re.IGNORECASE).strip()
        ans_clean = result if result else "OK"
        return True, f"Response: {ans_clean} | Text: {elapsed}Text"

    except socket.timeout:
        return False, "Text Text Text Text (8 Text)."
    except urllib.error.HTTPError as he:
        try:
            err_body = he.read().decode("utf-8", errors="replace")
            err_json = json.loads(extract_clean_json_body(err_body))
            msg = err_json.get("error", {}).get("message", err_body[:180])
        except Exception:
            msg = str(he)
        return False, f"HTTP {he.code}: {msg}"
    except Exception as ex:
        return False, f"Text Text: {ex}"

UNIFIED_PYTHON_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
Text: data/services/{SERVICE_ID_SLUG}/service.py
Text: Text {SERVICE_NAME} Text Text Text Text Text Text.
            Text: {PROVIDER_KEY} | Text: {MODEL_ID}
\"\"\"

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
from data.core.logger import logger

UNIFIED_DOH_PRESETS = {
    "Comss.one (SmartDNS / Text Text)": {
        "url": "https://dns.comss.one/dns-query",
        "host": "dns.comss.one",
        "bootstrap_ip": "195.133.25.16"
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

_doh_dns_cache = {}
_doh_dns_lock = threading.Lock()

def resolve_doh(hostname, doh_url):
    with _doh_dns_lock:
        if hostname in _doh_dns_cache:
            return _doh_dns_cache[hostname]

    try:
        url = f"{doh_url}?name={hostname}&type=A"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/dns-json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:
                    ip = ans.get("data")
                    with _doh_dns_lock:
                        _doh_dns_cache[hostname] = ip
                    return ip
    except Exception:
        pass
    return None

def _recv_all(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Text Text Text Text.")
        data.extend(packet)
    return bytes(data)

def create_socks5_socket(proxy_host, proxy_port, dest_host, dest_port, timeout=30.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))

    s.sendall(b"\\x05\\x01\\x00")
    resp = _recv_all(s, 2)
    if resp[0] != 5 or resp[1] != 0:
        s.close()
        raise ConnectionError("SOCKS5 Text Text Text Text Text.")

    dest_bytes = dest_host.encode("utf-8")
    req = b"\\x05\\x01\\x00\\x03" + bytes([len(dest_bytes)]) + dest_bytes + struct.pack("!H", dest_port)
    s.sendall(req)

    resp_header = _recv_all(s, 4)
    if resp_header[0] != 5 or resp_header[1] != 0:
        s.close()
        raise ConnectionError(f"SOCKS5 Text Text (Text: {resp_header[1]})")

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
        crlf_idx = raw_bytes.find(b"\\r\\n", pos)
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

def extract_clean_json_body(raw_str):
    start = raw_str.find('{')
    end = raw_str.rfind('}')
    if start != -1 and end != -1 and end > start:
        return raw_str[start:end + 1]
    return raw_str

def _get_nested_value(data_obj, path_str):
    if not path_str or not data_obj:
        return None
    keys = path_str.split('.')
    val = data_obj
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        elif isinstance(val, list) and k.isdigit() and int(k) < len(val):
            val = val[int(k)]
        else:
            return None
    return val

class UnifiedService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="{SERVICE_ID_SLUG}",
            name="{SERVICE_NAME}",
            route_name="/{SERVICE_ID_SLUG}",
            icon_name="Service.png"
        )
        self.provider_key = "{PROVIDER_KEY}"
        self.auth_header_type = "{AUTH_HEADER_TYPE}"
        self.thinking_policy = "{THINKING_POLICY}"
        self.response_path = "{RESPONSE_PATH}"
        self.extra_headers_json = '{EXTRA_HEADERS_JSON}'

    def get_config_fields(self):
        fields = []
        if self.auth_header_type != "none":
            fields.append({"key": "api_key", "label": "API Text:", "required": True})
        fields.extend([
            {"key": "model", "label": "Text:", "required": True},
            {"key": "endpoint", "label": "Text (URL):", "required": True},
            {"key": "connection_mode", "label": "Text Text (direct/proxy/doh):", "required": True},
            {"key": "proxy", "label": "Text SOCKS5 (Text:Text):", "required": False},
            {"key": "doh_preset", "label": "DoH Text:", "required": False}
        ])
        return fields

    def is_ready(self):
        if self.auth_header_type != "none":
            api_key = self.get_config_val("api_key", "").strip()
            if not api_key:
                return False, f"Text API Key Text {self.name} Text Text"
        ep = self.get_config_val("endpoint", "{ENDPOINT}").strip()
        if not ep:
            return False, "Text URL Text Text Text"
        return True, f"Text {self.name} Text Text Text Text Text"

    def _execute_request_raw(self, url, payload_bytes, headers, timeout=60.0):
        conn_mode = self.get_config_val("connection_mode", "direct").lower().strip()
        proxy_val = self.get_config_val("proxy", "127.0.0.1:10808").strip()

        parsed = urllib.parse.urlparse(url)
        dest_host = parsed.hostname or "localhost"
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        if conn_mode == "proxy":
            p_host, p_port = parse_proxy_string(proxy_val)
            raw_sock = create_socks5_socket(p_host, p_port, dest_host, dest_port, timeout=timeout)

            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
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
            header_data = "\\r\\n".join(header_lines) + "\\r\\n\\r\\n"

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

            parts = bytes(response_bytes).split(b"\\r\\n\\r\\n", 1)
            header_bytes = parts[0]
            body_bytes = parts[1] if len(parts) > 1 else b""

            header_str = header_bytes.decode("utf-8", errors="replace")
            if "chunked" in header_str.lower():
                body_bytes = dechunk_http_body(body_bytes)

            raw_str = body_bytes.decode("utf-8", errors="replace")
            status_code = 200
            m_status = re.search(r'HTTP/\\S+\\s+(\\d+)', header_str)
            if m_status:
                status_code = int(m_status.group(1))

            return status_code, raw_str

        elif conn_mode == "doh":
            preset_name = self.get_config_val("doh_preset", "Comss.one (SmartDNS / Text Text)")
            doh_url = UNIFIED_DOH_PRESETS.get(preset_name, {}).get("url") or "https://dns.comss.one/dns-query"
            ip = resolve_doh(dest_host, doh_url)

            req = urllib.request.Request(url, data=payload_bytes, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_bytes = resp.read()
                    return resp.status, raw_bytes.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as he:
                err_str = he.read().decode("utf-8", errors="replace")
                return he.code, err_str

        else:
            req = urllib.request.Request(url, data=payload_bytes, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_bytes = resp.read()
                    return resp.status, raw_bytes.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as he:
                err_str = he.read().decode("utf-8", errors="replace")
                return he.code, err_str

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        ok, reason = self.is_ready()
        if not ok:
            return f"[{self.name}]: {reason}\"

        raw_api_key = self.get_config_val("api_key", "")
        api_key = re.sub(r'^(?:Key|Token|Bearer)\\s+', '', str(raw_api_key), flags=re.IGNORECASE).strip()

        model = self.get_config_val("model", "{MODEL_ID}")
        endpoint = self.get_config_val("endpoint", "{ENDPOINT}")

        clean_input = text.strip() if text else ""
        if not clean_input:
            return ""

        t0 = time.time()
        if len(clean_input.split()) <= 2 and len(clean_input) < 15 and '\\n' not in clean_input:
            fast_res = self.fetch_fast_word(clean_input, src=src_lang, trg=trg_lang)
            if fast_res:
                return fast_res

        annotated_text, system_prompt = self.prepare_text_and_prompt(
            clean_input, src_lang=src_lang, trg_lang=trg_lang, preset=preset
        )

        try: temp_val = float(self.get_config_val("temperature", "0.2"))
        except Exception: temp_val = 0.2
        try: top_p_val = float(self.get_config_val("top_p", "0.3"))
        except Exception: top_p_val = 0.3
        try: max_tokens_val = int(self.get_config_val("max_tokens", "4096"))
        except Exception: max_tokens_val = 4096

        enable_think = self.get_config_val("enable_thinking", "0") in ("1", "true", "yes")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": annotated_text}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens_val,
            "temperature": temp_val,
            "top_p": top_p_val
        }

        policy = self.thinking_policy.lower().strip()
        if policy == "disabled_type":
            payload["thinking"] = {"type": "enabled" if enable_think else "disabled"}
        elif policy == "exclude_reasoning":
            payload["reasoning"] = {"max_tokens": 4096 if enable_think else 0, "exclude": not enable_think}
        elif policy == "reasoning_effort_low":
            payload["reasoning_effort"] = "high" if enable_think else "low"
            payload["include_reasoning"] = enable_think
        elif policy == "enable_thinking_false":
            payload["enable_thinking"] = enable_think

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        auth_type = self.auth_header_type.strip()
        if auth_type == "Bearer" and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "x-api-key" and api_key:
            headers["x-api-key"] = api_key
        elif auth_type == "x-goog-api-key" and api_key:
            headers["x-goog-api-key"] = api_key

        if self.extra_headers_json:
            try:
                extra = json.loads(self.extra_headers_json)
                headers.update(extra)
            except Exception:
                pass

        logger.api_payload(self.name, model, endpoint, headers, payload)
        t_call = time.time()

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            status_code, raw_str = self._execute_request_raw(endpoint, data_bytes, headers, timeout=60.0)
            elapsed = time.time() - t_call

            logger.api_raw_response(self.name, status_code, elapsed, raw_str)
            logger.api_summary(self.name, model, elapsed, status_code)

            clean_json = extract_clean_json_body(raw_str)

            if status_code >= 400:
                try:
                    err_data = json.loads(clean_json)
                    err_msg = err_data.get("error", {}).get("message", raw_str[:200])
                except Exception:
                    err_msg = raw_str[:200]
                return f"[{self.name} HTTP {status_code}]: {err_msg}"

            data = json.loads(clean_json)

            if data.get("error"):
                err_msg = data["error"].get("message", str(data["error"]))
                return f"[{self.name} Error: {err_msg}]"

            path_to_use = self.response_path or "choices.0.message.content"
            extracted_val = _get_nested_value(data, path_to_use)

            if extracted_val is None:
                if data.get("choices") and len(data["choices"]) > 0:
                    c = data["choices"][0]
                    extracted_val = c.get("message", {}).get("content") or c.get("text")
                elif data.get("result"):
                    extracted_val = data["result"].get("response")

            if not extracted_val:
                return f"[{self.name}: Text Text Text]"

            content = str(extracted_val)
            content = re.sub(r'<think>[\\s\\S]*?</think>', '', content, flags=re.IGNORECASE)
            final = self.clean_response(content)

            elapsed_total = round(time.time() - t0, 2)
            print(f"[{self.name} ({model}) Text Text {elapsed_total}Text]: {final[:70]}...")
            return final if final else clean_input

        except Exception as e:
            elapsed = time.time() - t_call
            logger.api_summary(self.name, model, elapsed, 0, note=f"Exception: {e}")
            return f"Error {self.name}: {e}"

service = UnifiedService()

try:
    from data.core.server import register_service_route
    register_service_route("{SERVICE_ID_SLUG}", service.translate)
    register_service_route("/{SERVICE_ID_SLUG}", service.translate)
except Exception:
    pass
"""
