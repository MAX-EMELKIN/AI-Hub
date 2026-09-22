# -*- coding: utf-8 -*-
# data/gui/code_editor_dialog.py

import os, sys, subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from data.core.config_manager import config
from data.core.i18n import t
from data.gui.theme_manager import theme
from data.gui.dialogs import attach_entry_context_menu

def open_file_in_smart_editor(file_path, parent_window=None):
    if not file_path or not os.path.exists(file_path):
        return

    editor_setting = "auto"
    try:
        editor_setting = config.get_str("GENERAL", "CodeEditor", "auto").strip()
    except Exception:
        pass

    if editor_setting.lower() == "builtin":
        CodeEditorDialog(parent_window, file_path)
        return

    if editor_setting != "auto" and os.path.exists(editor_setting):
        try:
            subprocess.Popen([editor_setting, file_path])
            return
        except Exception:
            pass

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\AkelPad\AkelPad.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\AkelPad\AkelPad.exe"),
        os.path.expandvars(r"%ProgramFiles%\Notepad++\notepad++.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Notepad++\notepad++.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%ProgramFiles%\Sublime Text\sublime_text.exe"),
        os.path.expandvars(r"%ProgramFiles%\Sublime Text 3\sublime_text.exe")
    ]
    for exe in candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, file_path])
                return
            except Exception:
                pass

    CodeEditorDialog(parent_window, file_path)

class CodeEditorDialog(tk.Toplevel):
    def __init__(self, parent, file_path):
        super().__init__(parent)
        self.parent = parent
        self.file_path = file_path

        theme.apply_ttk_theme(self)

        bg_main = theme.get_color("bg_main")
        bg_card = theme.get_color("bg_card")
        fg_pri = theme.get_color("fg_primary")

        fname = os.path.basename(file_path)
        self.title(f"Text")
        self.geometry("740x560")
        self.minsize(540, 380)
        self.configure(bg=bg_main)
        if parent:
            self.transient(parent)

        pad = tk.Frame(self, bg=bg_main, padx=10, pady=10)
        pad.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(pad, bg=bg_card, padx=8, pady=6, relief=tk.SOLID, bd=1)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            top_bar, text=f"Text",
            font=theme.font(-1, "bold"), fg=theme.get_color("accent"), bg=bg_card, anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        text_frame = tk.Frame(pad, bg=bg_main)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        self.text_area = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg=theme.get_color("input_bg"),
            fg=theme.get_color("input_fg"),
            insertbackground=theme.get_color("fg_primary"),
            relief=tk.SOLID,
            bd=1,
            yscrollcommand=self.scrollbar.set
        )
        self.scrollbar.config(command=self.text_area.yview)

        h_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text_area.xview)
        self.text_area.config(xscrollcommand=h_scroll.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        attach_entry_context_menu(self.text_area)

        btn_bar = tk.Frame(pad, bg=bg_main, pady=6)
        btn_bar.pack(fill=tk.X)

        tk.Button(
            btn_bar, text=t("btn_cancel", "Text"), font=theme.font(0),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=12,
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_bar, text=t("btn_save", "Text"), font=theme.font(0, "bold"),
            relief=tk.FLAT, bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            padx=16, command=self._save_file
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_bar, text="Text", font=theme.font(-1),
            relief=tk.FLAT, bg=theme.get_color("btn_bg"), fg=fg_pri, padx=10,
            command=self._load_file
        ).pack(side=tk.LEFT)

        self._load_file()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 800
        ph = self.parent.winfo_height() if self.parent else 600
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 740, 560
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _load_file(self):
        if not os.path.exists(self.file_path):
            return
        content = ""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(self.file_path, "r", encoding="cp1251") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Text", f"Text", parent=self)
                return
        except Exception as e:
            messagebox.showerror("Text", f"Text", parent=self)
            return

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)

    def _save_file(self):
        content = self.text_area.get("1.0", tk.END)
        if content.endswith("\n"):
            content = content[:-1]

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Text", "Text", parent=self)
        except Exception as e:
            messagebox.showerror("Text", f"Text", parent=self)
