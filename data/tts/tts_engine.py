# -*- coding: utf-8 -*-
"""
Модуль: data/tts/tts_engine.py
Назначение: Студийная нейро-озвучка Edge-TTS с прямым синтезом по WebSocket (RFC 6455),
            безопасным перехватом выделенного текста из целевого окна Windows,
            воспроизведением через winmm MCI и интеграцией с модулем logger.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

import os
import sys
import time
import json
import uuid
import struct
import ssl
import socket
import hashlib
import threading
import urllib.parse
import urllib.request

from data.core.win_api import (
    user32, kernel32, winmm, INPUT, send_key_event, read_clipboard_text
)
from data.core.logger import logger

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
WIN_EPOCH = 11644473600
SEC_MS_GEC_VERSION = "1-140.0.3485.14"

POPULAR_VOICES = {
    "ru": [
        ("ru-RU-SvetlanaNeural", "Светлана (Женский, РФ)"),
        ("ru-RU-DmitryNeural", "Дмитрий (Мужской, РФ)")
    ],
    "en": [
        ("en-US-JennyNeural", "Jenny (Женский, США)"),
        ("en-US-GuyNeural", "Guy (Мужской, США)"),
        ("en-GB-SoniaNeural", "Sonia (Женский, Британия)")
    ],
    "de": [
        ("de-DE-KatjaNeural", "Katja (Женский, Германия)"),
        ("de-DE-StefanNeural", "Stefan (Мужской, Германия)")
    ],
    "zh": [
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (Женский, Китай)"),
        ("zh-CN-YunxiNeural", "Yunxi (Мужской, Китай)")
    ],
    "ja": [
        ("ja-JP-NanamiNeural", "Nanami (Женский, Япония)"),
        ("ja-JP-KeitaNeural", "Keita (Мужской, Япония)")
    ],
    "es": [
        ("es-ES-ElviraNeural", "Elvira (Женский, Испания)"),
        ("es-ES-AlvaroNeural", "Alvaro (Мужской, Испания)")
    ],
    "fr": [
        ("fr-FR-DeniseNeural", "Denise (Женский, Франция)"),
        ("fr-FR-HenriNeural", "Henri (Мужской, Франция)")
    ]
}

def generate_sec_ms_gec():
    ticks = int(time.time()) + WIN_EPOCH
    ticks -= ticks % 300
    ticks_100ns = ticks * 10000000
    str_to_hash = f"{ticks_100ns}{TRUSTED_CLIENT_TOKEN}"
    return hashlib.sha256(str_to_hash.encode("ascii")).hexdigest().upper()

def grab_selection_from_target_hwnd(target_hwnd=None):
    """Возвращает фокус целевому окну и безопасно забирает выделенный текст."""
    if not target_hwnd or not user32.IsWindow(target_hwnd):
        try:
            from data.core.hotkey_manager import window_tracker
            target_hwnd = window_tracker.last_user_hwnd
        except Exception:
            target_hwnd = None

    if target_hwnd and user32.IsWindow(target_hwnd):
        user32.ShowWindow(target_hwnd, 5)
        user32.SetForegroundWindow(target_hwnd)
        time.sleep(0.05)

    hwnd_fore = user32.GetForegroundWindow()
    own_tid = kernel32.GetCurrentThreadId()
    fore_tid = user32.GetWindowThreadProcessId(hwnd_fore, None)

    old_seq = user32.GetClipboardSequenceNumber()

    if fore_tid and fore_tid != own_tid:
        user32.AttachThreadInput(own_tid, fore_tid, True)

    try:
        send_key_event(0x12, True)
        send_key_event(0x10, True)
        send_key_event(0x11, True)
        time.sleep(0.02)

        send_key_event(0x11, False)
        send_key_event(0x43, False)
        send_key_event(0x43, True)
        send_key_event(0x11, True)

        for _ in range(10):
            time.sleep(0.02)
            if user32.GetClipboardSequenceNumber() != old_seq:
                break
    finally:
        if fore_tid and fore_tid != own_tid:
            user32.AttachThreadInput(own_tid, fore_tid, False)

    text = read_clipboard_text()
    if text:
        logger.system(f"TTS: захвачен выделенный текст ({len(text)} симв.): '{text[:60]}...'")
    return text

get_selected_text_from_active_window = grab_selection_from_target_hwnd

class TTSEngine:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.tts_dir = os.path.join(self.base_dir, "data", "tts")
        self._file_counter = 0
        self._lock = threading.Lock()
        os.makedirs(self.tts_dir, exist_ok=True)
        self._register_in_server()

    def _register_in_server(self):
        try:
            from data.core.server import register_service_route
            register_service_route("tts", self.handle_server_request)
        except Exception:
            pass

    def handle_server_request(self, text, lang="ru", **kwargs):
        voice = self.get_voice_for_lang(lang)
        speed = self.get_speed()
        return self.generate_edge_tts_mp3(text, voice=voice, speed=speed)

    def is_playing(self):
        try:
            buf = ctypes.create_unicode_buffer(64)
            res = winmm.mciSendStringW("status qsound mode", buf, 64, None)
            if res == 0 and buf.value.strip().lower() == "playing":
                return True
        except Exception:
            pass
        return False

    def stop_speech(self):
        with self._lock:
            try:
                winmm.mciSendStringW("stop qsound", None, 0, None)
                winmm.mciSendStringW("close qsound", None, 0, None)
                logger.system("TTS: воспроизведение звука остановлено")
                print("[TTS]: Воспроизведение звука остановлено.")
                return True
            except Exception:
                pass
        return False

    def get_voice_for_lang(self, lang_code):
        code = str(lang_code).lower().split("-")[0]
        if code in POPULAR_VOICES:
            return POPULAR_VOICES[code][0][0]
        try:
            from data.core.config_manager import config
            return config.get_str("TTS", "Voice", "ru-RU-SvetlanaNeural")
        except Exception:
            return "ru-RU-SvetlanaNeural"

    def get_speed(self):
        try:
            from data.core.config_manager import config
            return config.get_float("TTS", "Speed", 1.0)
        except Exception:
            return 1.0

    def generate_edge_tts_mp3(self, text, voice="ru-RU-SvetlanaNeural", speed=1.0):
        if not text or not text.strip():
            return b""

        clean_text = text.strip()
        if len(clean_text) > 800:
            clean_text = clean_text[:800].rsplit(" ", 1)[0] + "..."

        clean_text = clean_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        speed_percent = int((speed - 1.0) * 100)
        speed_str = f"{speed_percent:+d}%"

        ssml = (
            f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
            f"<voice name='{voice}'>"
            f"<prosody rate='{speed_str}'>{clean_text}</prosody>"
            f"</voice></speak>"
        )

        conn_id = uuid.uuid4().hex
        sec_ms_gec = generate_sec_ms_gec()

        ws_url = (
            f"wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1"
            f"?TrustedClientToken={TRUSTED_CLIENT_TOKEN}"
            f"&ConnectionId={conn_id}"
            f"&Sec-MS-GEC={sec_ms_gec}"
            f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
        )

        t0 = time.time()
        logger.system(f"TTS: генерация речи (голос: {voice}, скорость: {speed_str}, символов: {len(clean_text)})")

        try:
            parsed = urllib.parse.urlparse(ws_url)
            host = parsed.hostname
            port = parsed.port or 443
            path = parsed.path + "?" + parsed.query

            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(6.0)
            context = ssl.create_default_context()
            sock = context.wrap_socket(raw_sock, server_hostname=host)
            sock.connect((host, port))

            sec_key = "dGhlIHNhbXBsZSBub25jZQ=="
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {sec_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"Origin: chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold\r\n"
                f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0\r\n\r\n"
            )
            sock.sendall(handshake.encode("utf-8"))
            resp = sock.recv(2048).decode("utf-8", errors="ignore")
            if " 101 " not in resp:
                sock.close()
                err_line = resp.split('\r\n')[0] if resp else "Нет ответа"
                raise Exception(f"Microsoft Edge TTS вернул: {err_line}")

            cfg_payload = (
                f"X-Timestamp:{time.strftime('%a %b %d %Y %H:%M:%S GMT+0000')}\r\n"
                f"Content-Type:application/json; charset=utf-8\r\n"
                f"Path:speech.config\r\n\r\n"
                f'{{"context":{{"synthesis":{{"audio":{{"metadataoptions":{{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"}},"outputFormat":"audio-24khz-48kbitrate-mono-mp3"}}}}}}}}'
            )
            self._send_ws_text(sock, cfg_payload)

            req_id = uuid.uuid4().hex
            ssml_payload = (
                f"X-RequestId:{req_id}\r\n"
                f"Content-Type:application/ssml+xml\r\n"
                f"Path:ssml\r\n\r\n{ssml}"
            )
            self._send_ws_text(sock, ssml_payload)

            audio_bytes = bytearray()
            sock.settimeout(5.0)

            while True:
                head = sock.recv(2)
                if len(head) < 2:
                    break
                b1, b2 = head[0], head[1]
                length = b2 & 0x7F
                if length == 126:
                    length = struct.unpack("!H", sock.recv(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", sock.recv(8))[0]

                payload = bytearray()
                while len(payload) < length:
                    chunk = sock.recv(length - len(payload))
                    if not chunk:
                        break
                    payload.extend(chunk)

                if (b1 & 0x0F) == 0x2 and len(payload) > 2:
                    header_len = struct.unpack("!H", payload[:2])[0]
                    audio_bytes.extend(payload[2 + header_len:])

                if (b1 & 0x0F) == 0x1 and b"Path:turn.end" in payload:
                    break

            sock.close()
            elapsed = time.time() - t0
            logger.system(f"TTS: аудиопоток успешно получен за {elapsed:.2f}с ({len(audio_bytes)} байт)")
            return bytes(audio_bytes)

        except Exception as e:
            logger.system(f"TTS Ошибка: {e}")
            print(f"[TTS Error]: {e}")
            raise e

    def _send_ws_text(self, sock, text):
        data = text.encode("utf-8")
        length = len(data)
        mask = os.urandom(4)
        masked = bytearray(data[i] ^ mask[i % 4] for i in range(length))
        frame = bytearray([0x81])
        if length <= 125:
            frame.append(0x80 | length)
        elif length <= 65535:
            frame.append(0x80 | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack("!Q", length))
        frame.extend(mask)
        frame.extend(masked)
        sock.sendall(frame)

    def play_audio_in_windows(self, audio_bytes):
        if not audio_bytes:
            return False
        with self._lock:
            try:
                winmm.mciSendStringW("stop qsound", None, 0, None)
                winmm.mciSendStringW("close qsound", None, 0, None)
                time.sleep(0.02)

                self._file_counter = (self._file_counter + 1) % 10
                temp_file = os.path.join(self.tts_dir, f"speech_{self._file_counter}.mp3")

                with open(temp_file, "wb") as f:
                    f.write(audio_bytes)

                winmm.mciSendStringW(f'open "{temp_file}" type mpegvideo alias qsound', None, 0, None)
                winmm.mciSendStringW("play qsound", None, 0, None)
                logger.system(f"TTS: воспроизведение через winmm mci ({len(audio_bytes)} байт)")
                print(f"[TTS]: Воспроизведение звука ({len(audio_bytes)} байт)")
                return True
            except Exception as e:
                logger.system(f"TTS Ошибка воспроизведения: {e}")
                print(f"[Audio Player Error]: {e}")
                return False

    def speak_text(self, text, voice=None, speed=None, lang="ru"):
        if self.is_playing():
            self.stop_speech()
            return True

        if not text or not text.strip():
            return False

        v = voice or self.get_voice_for_lang(lang)
        s = speed if speed is not None else self.get_speed()
        audio = self.generate_edge_tts_mp3(text, voice=v, speed=s)
        if audio:
            self.play_audio_in_windows(audio)
            return True
        return False

tts_engine = TTSEngine()