# data/ocr/screen_snipper.py
import ctypes
import os
import struct
import uuid
import tkinter as tk
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
WHITENESS = 0x00FF0062
HALFTONE = 4


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]


gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetStretchBltMode.restype = ctypes.c_int
gdi32.StretchBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.DWORD
]
gdi32.StretchBlt.restype = wintypes.BOOL


def capture_exact_screen_box(target_path, x, y, w, h, base_pad=24):
    if w <= 0 or h <= 0:
        return False

    scale = 1
    if h < 45 or w < 120:
        scale = 3
    elif h < 80 or w < 200:
        scale = 2

    scaled_w = w * scale
    scaled_h = h * scale
    pad = base_pad * scale
    dst_w = scaled_w + (pad * 2)
    dst_h = scaled_h + (pad * 2)

    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbm = gdi32.CreateCompatibleBitmap(hdc_screen, dst_w, dst_h)
    gdi32.SelectObject(hdc_mem, hbm)
    gdi32.PatBlt(hdc_mem, 0, 0, dst_w, dst_h, WHITENESS)

    if scale > 1:
        gdi32.SetStretchBltMode(hdc_mem, HALFTONE)
        gdi32.StretchBlt(hdc_mem, pad, pad, scaled_w, scaled_h, hdc_screen, x, y, w, h, SRCCOPY)
    else:
        gdi32.BitBlt(hdc_mem, pad, pad, w, h, hdc_screen, x, y, SRCCOPY)

    bih = BITMAPINFOHEADER()
    bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bih.biWidth = dst_w
    bih.biHeight = dst_h
    bih.biPlanes = 1
    bih.biBitCount = 24
    bih.biCompression = 0

    row_stride = ((dst_w * 3 + 3) // 4) * 4
    img_size = row_stride * dst_h
    buf = (ctypes.c_ubyte * img_size)()

    gdi32.GetDIBits(hdc_mem, hbm, 0, dst_h, buf, ctypes.byref(bih), 0)

    user32.ReleaseDC(None, hdc_screen)
    gdi32.DeleteDC(hdc_mem)
    gdi32.DeleteObject(hbm)

    offset = 54
    total_size = offset + img_size
    bmp_header = struct.pack("<2sIHHI", b"BM", total_size, 0, 0, offset)
    bmp_info = struct.pack("<IIIHHIIIIII", 40, dst_w, dst_h, 1, 24, 0, img_size, 2835, 2835, 0, 0)

    out_dir = os.path.dirname(target_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(target_path, "wb") as f:
        f.write(bmp_header)
        f.write(bmp_info)
        f.write(buf)

    return True


class ScreenSnipper:
    def __init__(self, on_cropped_callback):
        self.callback = on_cropped_callback
        self.start_x_root = 0
        self.start_y_root = 0
        self.cur_rect = None

    def start(self, parent_tk):
        self.overlay = tk.Toplevel(parent_tk)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.30)
        self.overlay.config(cursor="crosshair")

        self.canvas = tk.Canvas(self.overlay, cursor="crosshair", bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", lambda e: self.overlay.destroy())

    def _on_press(self, event):
        self.start_x_root = event.x_root
        self.start_y_root = event.y_root
        self.cur_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00e5ff", width=2, fill="#ffffff"
        )

    def _on_drag(self, event):
        x0 = min(self.start_x_root, event.x_root) - self.overlay.winfo_rootx()
        y0 = min(self.start_y_root, event.y_root) - self.overlay.winfo_rooty()
        x1 = max(self.start_x_root, event.x_root) - self.overlay.winfo_rootx()
        y1 = max(self.start_y_root, event.y_root) - self.overlay.winfo_rooty()
        self.canvas.coords(self.cur_rect, x0, y0, x1, y1)

    def _on_release(self, event):
        end_x_root = event.x_root
        end_y_root = event.y_root

        self.overlay.withdraw()
        self.overlay.update()

        x1 = min(self.start_x_root, end_x_root)
        y1 = min(self.start_y_root, end_y_root)
        x2 = max(self.start_x_root, end_x_root)
        y2 = max(self.start_y_root, end_y_root)

        w = x2 - x1
        h = y2 - y1

        self.overlay.destroy()

        if w > 5 and h > 5:
            print(f"[OCR Snipper]: Область захвата: {w}x{h} пикс. (X: {x1}, Y: {y1})")
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            unique_crop = os.path.join(temp_dir, f"crop_{uuid.uuid4().hex[:8]}.bmp")
            ok = capture_exact_screen_box(unique_crop, x1, y1, w, h, base_pad=24)
            if ok and self.callback:
                self.callback(unique_crop)