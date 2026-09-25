# data/gui/ocr_dialog.py
import time
import tkinter as tk
from tkinter import ttk
from data.core.config_manager import config
from data.core.i18n import t
from data.gui.dialog_helpers import attach_entry_context_menu
from data.gui.theme_manager import theme
from data.ocr.ocr_engine import ocr_engine


class OCRSettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_saved_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_saved = on_saved_callback
        bg_main = theme.get_color("bg_main")
        self.title(t("tip_ocr_settings", "Настройки экранного OCR"))
        self.geometry("540x360")
        self.resizable(False, False)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()
        self._last_ctrl_time = 0
        self._last_alt_time = 0
        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 540, 360
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")

        pad = tk.Frame(self, bg=bg_main, padx=16, pady=12)
        pad.pack(fill=tk.BOTH, expand=True)

        r1 = tk.Frame(pad, bg=bg_main)
        r1.pack(fill=tk.X, pady=(0, 10))
        tk.Label(r1, text=t("ocr_model_label", "Активная модель распознавания:"), font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT)
        self.combo_model = ttk.Combobox(r1, values=ocr_engine.get_available_models(), state="readonly", width=14, font=theme.font(0))
        self.combo_model.set(ocr_engine.get_active_model())
        self.combo_model.pack(side=tk.RIGHT)

        r2 = tk.Frame(pad, bg=bg_main)
        r2.pack(fill=tk.X, pady=(0, 8))
        tk.Label(r2, text=t("ocr_key_label", "Клавиша вызова QTranslate:"), font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT)
        cur_key = config.get_str("QTRANSLATE", "SummonHotkey", "F1").strip()
        self.entry_key = tk.Entry(r2, font=theme.font(1, "bold"), width=16, justify="center", bg=in_bg, fg=theme.get_color("accent"), relief=tk.SOLID, bd=1)
        self.entry_key.insert(0, cur_key)
        self.entry_key.pack(side=tk.RIGHT)
        self.entry_key.bind("<KeyPress>", self._on_key_press)
        attach_entry_context_menu(self.entry_key)

        help_box = tk.LabelFrame(pad, text=t("ocr_help_title", "Справка по интеграции с QTranslate"), font=theme.font(-1, "bold"), fg=fg_pri, bg=bg_card, padx=10, pady=8)
        help_box.pack(fill=tk.BOTH, expand=True, pady=(2, 12))

        default_ocr_help = (
            "1. Распознанный с экрана текст автоматически копируется в буфер обмена Windows.\n"
            "2. Хаб передает команду вызова окна перевода в QTranslate по указанной клавише.\n"
            "3. Текст автоматически вставляется в активное поле ввода и отправляется на перевод.\n"
            "Поддерживаются как одиночные клавиши (F1, F2), так и комбинации (Ctrl+Q) или двойные нажатия (double_ctrl)."
        )
        tk.Label(help_box, text=t("ocr_help_text", default_ocr_help), font=theme.font(-1), justify="left", fg=theme.get_color("fg_secondary"), bg=bg_card).pack(anchor="w")

        btn_bar = tk.Frame(pad, bg=bg_main)
        btn_bar.pack(fill=tk.X)

        tk.Button(btn_bar, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=10, command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_bar, text=t("btn_save", "Сохранить"), font=theme.font(0, "bold"), relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"), padx=14, command=self._on_save).pack(side=tk.RIGHT)

    def _on_key_press(self, event):
        keysym = event.keysym
        now = time.time()
        if keysym in ("Delete", "BackSpace"):
            self.entry_key.delete(0, tk.END)
            return "break"
        if keysym in ("Control_L", "Control_R"):
            if now - self._last_ctrl_time < 0.35:
                self.entry_key.delete(0, tk.END)
                self.entry_key.insert(0, "double_ctrl")
                self._last_ctrl_time = 0
                return "break"
            self._last_ctrl_time = now
            return "break"
        if keysym in ("Alt_L", "Alt_R"):
            if now - self._last_alt_time < 0.35:
                self.entry_key.delete(0, tk.END)
                self.entry_key.insert(0, "double_alt")
                self._last_alt_time = 0
                return "break"
            self._last_alt_time = now
            return "break"

        mods = []
        state = event.state
        if state & 0x0004:
            mods.append("Ctrl")
        if state & 0x20000 or state & 0x0008:
            mods.append("Alt")
        if state & 0x0001:
            mods.append("Shift")

        key_name = keysym
        if keysym.startswith("F") and keysym[1:].isdigit():
            key_name = keysym.upper()
        elif len(keysym) == 1:
            key_name = keysym.upper()
        elif keysym in ("Return", "KP_Enter"):
            key_name = "Enter"
        elif keysym == "Escape":
            key_name = "Esc"
        elif keysym in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
            return "break"

        res = "+".join(mods + [key_name]) if (mods and key_name not in mods) else key_name
        self.entry_key.delete(0, tk.END)
        self.entry_key.insert(0, res)
        return "break"

    def _on_save(self):
        new_model = self.combo_model.get()
        new_key = self.entry_key.get().strip() or "F1"
        ocr_engine.set_active_model(new_model)
        config.set_value("QTRANSLATE", "SummonHotkey", new_key)
        if self.on_saved:
            self.on_saved(new_model, new_key)
        self.destroy()