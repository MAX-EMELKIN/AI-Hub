# -*- coding: utf-8 -*-
# data/gui/dialog_helpers.py

import tkinter as tk
from data.core.i18n import t
from data.gui.theme_manager import theme
class HelpPopup(tk.Toplevel):
    def __init__(self, anchor_widget, text):
        super().__init__(anchor_widget)
        self.wm_overrideredirect(True)
        bg = theme.get_color("popup_bg")
        border = theme.get_color("popup_border")
        fg = theme.get_color("popup_fg")
        hint_fg = theme.get_color("popup_hint")

        self.configure(bg=bg)
        frame = tk.Frame(
            self, bg=bg, padx=10, pady=8, relief=tk.SOLID, bd=1,
            highlightbackground=border, highlightthickness=1
        )
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(frame, text=text, justify=tk.LEFT, bg=bg, fg=fg, font=theme.font(-1), wraplength=250)
        lbl.pack(anchor="w")

        hint = tk.Label(frame, text=t("help_close_hint", "* Кликните в любом месте, чтобы закрыть"), font=theme.font(-2, "italic"), fg=hint_fg, bg=bg)
        hint.pack(anchor="w", pady=(6, 0))

        self.update_idletasks()
        btn_x = anchor_widget.winfo_rootx()
        btn_y = anchor_widget.winfo_rooty()
        btn_h = anchor_widget.winfo_height()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        pos_x = max(10, min(btn_x - 30, screen_w - w - 20))
        pos_y = btn_y + btn_h + 4
        if pos_y + h > screen_h - 40:
            pos_y = btn_y - h - 4

        self.wm_geometry(f"+{pos_x}+{pos_y}")

        self.bind("<Button-1>", lambda e: self.destroy())
        lbl.bind("<Button-1>", lambda e: self.destroy())
        frame.bind("<Button-1>", lambda e: self.destroy())
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

def attach_entry_context_menu(widget):
    menu = tk.Menu(widget, tearoff=0, font=theme.font(0))

    def _cut():
        try:
            if widget.selection_present():
                widget.clipboard_clear()
                widget.clipboard_append(widget.selection_get())
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception:
            widget.event_generate("<<Cut>>")

    def _copy():
        try:
            if widget.selection_present():
                widget.clipboard_clear()
                widget.clipboard_append(widget.selection_get())
        except Exception:
            widget.event_generate("<<Copy>>")

    def _paste():
        text = ""
        try:
            text = widget.clipboard_get()
        except Exception:
            try:
                from data.core.win_api import read_clipboard_text
                text = read_clipboard_text()
            except Exception:
                text = ""

        if text:
            try:
                if widget.selection_present():
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except Exception:
                pass
            widget.insert(tk.INSERT, text)

    def _select_all():
        widget.selection_range(0, tk.END)
        widget.icursor(tk.END)

    menu.add_command(label=t("menu_paste", "Вставить"), command=_paste)
    menu.add_command(label=t("menu_copy", "Копировать"), command=_copy)
    menu.add_command(label=t("menu_cut", "Вырезать"), command=_cut)
    menu.add_separator()
    menu.add_command(label=t("menu_select_all", "Выделить всё"), command=_select_all)

    widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def _on_key(e):
        if (e.state & 0x0004) or (e.state & 0x0001 and e.state & 0x0004):
            if e.keycode == 86 or e.keysym.lower() in ('v', 'cyrillic_em', 'm'):
                _paste()
                return "break"
            elif e.keycode == 67 or e.keysym.lower() in ('c', 'cyrillic_es', 's'):
                _copy()
                return "break"
            elif e.keycode == 88 or e.keysym.lower() in ('x', 'cyrillic_che'):
                _cut()
                return "break"
            elif e.keycode == 65 or e.keysym.lower() in ('a', 'cyrillic_ef'):
                _select_all()
                return "break"

    widget.bind("<KeyPress>", _on_key)

def attach_text_context_menu(text_widget):
    menu = tk.Menu(text_widget, tearoff=0, font=theme.font(0))

    def _cut():
        try:
            if text_widget.tag_ranges("sel"):
                text_widget.clipboard_clear()
                text_widget.clipboard_append(text_widget.get(tk.SEL_FIRST, tk.SEL_LAST))
                text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception:
            pass

    def _copy():
        try:
            if text_widget.tag_ranges("sel"):
                text_widget.clipboard_clear()
                text_widget.clipboard_append(text_widget.get(tk.SEL_FIRST, tk.SEL_LAST))
        except Exception:
            pass

    def _paste():
        text = ""
        try:
            text = text_widget.clipboard_get()
        except Exception:
            try:
                from data.core.win_api import read_clipboard_text
                text = read_clipboard_text()
            except Exception:
                text = ""
        if text:
            try:
                if text_widget.tag_ranges("sel"):
                    text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except Exception:
                pass
            text_widget.insert(tk.INSERT, text)

    def _select_all():
        text_widget.tag_add(tk.SEL, "1.0", tk.END)
        text_widget.mark_set(tk.INSERT, "1.0")

    menu.add_command(label=t("menu_paste", "Вставить"), command=_paste)
    menu.add_command(label=t("menu_copy", "Копировать"), command=_copy)
    menu.add_command(label=t("menu_cut", "Вырезать"), command=_cut)
    menu.add_separator()
    menu.add_command(label=t("menu_select_all", "Выделить всё"), command=_select_all)

    text_widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def _on_key(e):
        if (e.state & 0x0004) or (e.state & 0x0001 and e.state & 0x0004):
            if e.keycode == 86 or e.keysym.lower() in ('v', 'cyrillic_em', 'm'):
                _paste()
                return "break"
            elif e.keycode == 67 or e.keysym.lower() in ('c', 'cyrillic_es', 's'):
                _copy()
                return "break"
            elif e.keycode == 88 or e.keysym.lower() in ('x', 'cyrillic_che'):
                _cut()
                return "break"
            elif e.keycode == 65 or e.keysym.lower() in ('a', 'cyrillic_ef'):
                _select_all()
                return "break"

    text_widget.bind("<KeyPress>", _on_key)

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def set_text(self, new_text):
        self.text = new_text

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() - 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        bg = theme.get_color("popup_bg")
        fg = theme.get_color("popup_fg")

        lbl = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background=bg, foreground=fg,
            relief=tk.SOLID, borderwidth=0,
            font=theme.font(-1), padx=6, pady=2
        )
        lbl.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
