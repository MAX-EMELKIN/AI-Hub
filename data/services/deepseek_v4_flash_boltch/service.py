# -*- coding: utf-8 -*-
# data/services/deepseek_v4_flash_boltch/service.py
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
import http.client
import threading

from data.services.base_service import BaseService
from data.core.api_config import api_config
from data.core.logger import logger

BOLTCH_DOH_PRESETS = {
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

_dns_cache = {}
_dns_lock = threading.Lock()

def resolve_doh(hostname, doh_url):
    with _dns_lock:
        if hostname in _dns_cache:
            return _dns_cache[hostname]

    try:
        url = f"{doh_url}?name={hostname}&type=A"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/dns-json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:
                    ip = ans.get("data")
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
            raise ConnectionError("Text Text Text Text Text.")
        data.extend(packet)
    return bytes(data)

def create_socks5_socket(proxy_host, proxy_port, dest_host, dest_port, timeout=30.0):
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
    else:
        s.close()
        raise ConnectionError("SOCKS5 Text Text Text Text")

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

class CustomService(BaseService):
    def __init__(self):
        super().__init__(
            service_id="deepseek_v4_flash_boltch",
            name="deepseek-v4-flash Boltch",
            route_name="/deepseek_v4_flash_boltch",
            icon_name="Service.png"
        )

    def get_config_fields(self):
        return [
            {"key": "api_key", "label": "Boltch API Key:", "required": True},
            {"key": "model", "label": "Text (free:...):", "required": True},
            {"key": "endpoint", "label": "Text (URL):", "required": True},
            {"key": "connection_mode", "label": "Text Text (direct/proxy/doh):", "required": True},
            {"key": "proxy", "label": "Text SOCKS5 (Text:Text):", "required": False},
            {"key": "doh_preset", "label": "DoH Text:", "required": False}
        ]

    def is_ready(self):
        api_key = self.get_config_val("api_key", "").strip()
        if not api_key:
            return False, "Text Boltch API Key Text Text"
        return True, "Text deepseek-v4-flash Boltch Text Text Text Text Text"

    def _execute_request_raw(self, url, payload_bytes, headers, timeout=60.0):
        conn_mode = self.get_config_val("connection_mode", "direct").lower().strip()
        proxy_val = self.get_config_val("proxy", "213.165.38.49:1080").strip()

        parsed = urllib.parse.urlparse(url)
        dest_host = parsed.hostname or "boltch.cloud"
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = (parsed.path or "/") + (("?" + parsed.query) if parsed.query else "")

        if conn_mode == "proxy":
            p_host, p_port = parse_proxy_string(proxy_val)
            raw_sock = create_socks5_socket(p_host, p_port, dest_host, dest_port, timeout=timeout)

            if parsed.scheme == "https":
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(raw_sock, server_hostname=dest_host)
                conn = http.client.HTTPSConnection(dest_host, dest_port, context=ctx, timeout=timeout)
            else:
                sock = raw_sock
                conn = http.client.HTTPConnection(dest_host, dest_port, timeout=timeout)

            conn.sock = sock
            conn.request("POST", path, body=payload_bytes, headers=headers)
            resp = conn.getresponse()

            raw_bytes = resp.read()
            status_code = resp.status
            raw_str = raw_bytes.decode("utf-8", errors="replace")
            conn.close()
            return status_code, raw_str

        elif conn_mode == "doh":
            preset_name = self.get_config_val("doh_preset", "Comss.one (SmartDNS / Text Text)")
            doh_url = BOLTCH_DOH_PRESETS.get(preset_name, {}).get("url") or "https://dns.comss.one/dns-query"
            ip = resolve_doh(dest_host, doh_url)

            req = urllib.request.Request(url, data=payload_bytes, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_str = resp.read().decode("utf-8", errors="replace")
                    return resp.status, raw_str
            except urllib.error.HTTPError as he:
                err_str = he.read().decode("utf-8", errors="replace")
                return he.code, err_str

        else:
            req = urllib.request.Request(url, data=payload_bytes, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_str = resp.read().decode("utf-8", errors="replace")
                    return resp.status, raw_str
            except urllib.error.HTTPError as he:
                err_str = he.read().decode("utf-8", errors="replace")
                return he.code, err_str

    def translate(self, text, src_lang="auto", trg_lang="ru", preset=None):
        ok, reason = self.is_ready()
        if not ok:
            return f"[{self.name}]: {reason}"

        raw_api_key = self.get_config_val("api_key")
        api_key = re.sub(r'^(?:Key|Token|Bearer)\s+', '', str(raw_api_key), flags=re.IGNORECASE).strip()

        model = self.get_config_val("model", "free:deepseek-v4-flash")
        endpoint = self.get_config_val("endpoint", "https://boltch.cloud/v1/chat/completions")

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

        try: temp_val = float(self.get_config_val("temperature", "0.2"))
        except Exception: temp_val = 0.2
        try: max_tokens_val = int(self.get_config_val("max_tokens", "4096"))
        except Exception: max_tokens_val = 4096

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": annotated_text}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens_val,
            "temperature": temp_val,
            "thinking": {"type": "disabled"}
        }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        logger.api_payload(self.name, model, endpoint, headers, payload)
        t_call = time.time()

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            status_code, raw_str = self._execute_request_raw(endpoint, data_bytes, headers, timeout=60.0)
            elapsed = time.time() - t_call

            logger.api_raw_response(self.name, status_code, elapsed, raw_str)
            logger.api_summary(self.name, model, elapsed, status_code)

            if status_code >= 400:
                try:
                    err_json = json.loads(raw_str)
                    err_msg = err_json.get("error", {}).get("message", raw_str[:200])
                except Exception:
                    err_msg = raw_str[:200]
                return f"[Boltch HTTP {status_code}]: {err_msg}"

            data = json.loads(raw_str)
            if data.get("error"):
                err_msg = data["error"].get("message", str(data["error"]))
                return f"[Boltch Error: {err_msg}]"

            if not data.get("choices") or len(data["choices"]) == 0:
                return f"[{self.name}: Text Text Text]"

            msg = data["choices"][0].get("message", {})
            content = msg.get("content", "")

            content = re.sub(r'<think>[\s\S]*?</think>', '', str(content), flags=re.IGNORECASE)
            final = self.clean_response(content)

            elapsed_total = round(time.time() - t0, 2)
            print(f"[{self.name} ({model}) Text Text {elapsed_total}Text]: {final[:70]}...")
            return final if final else clean_input

        except Exception as e:
            elapsed = time.time() - t_call
            logger.api_summary(self.name, model, elapsed, 0, note=f"Exception: {e}")
            return f"Error Boltch: {e}"

service = CustomService()
