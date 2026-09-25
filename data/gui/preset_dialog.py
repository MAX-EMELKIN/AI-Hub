# data/gui/preset_dialog.py
import tkinter as tk
from tkinter import messagebox
from data.core.config_manager import config
from data.core.i18n import t
from data.gui.dialog_helpers import attach_entry_context_menu, attach_text_context_menu, ToolTip
from data.gui.theme_manager import theme
from data.presets.preset_manager import preset_manager


class PresetEditorDialog(tk.Toplevel):
    def __init__(self, parent, service_id, preset_name="default", is_new=False, on_saved_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.service_id = service_id
        self.preset_name = preset_name
        self.is_new = is_new
        self.on_saved_callback = on_saved_callback
        bg_main = theme.get_color("bg_main")
        title_prefix = t("preset_create_title", "Создание пресета") if is_new else t("preset_edit_title", "Редактирование пресета")
        self.title(f"{title_prefix} — {service_id}")
        self.geometry("640x500")
        self.minsize(520, 380)
        self.configure(bg=bg_main)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        pw = self.parent.winfo_width() if self.parent else 600
        ph = self.parent.winfo_height() if self.parent else 400
        px = self.parent.winfo_rootx() if self.parent else 200
        py = self.parent.winfo_rooty() if self.parent else 150
        w, h = 640, 500
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        bg_main = theme.get_color("bg_main")
        fg_pri = theme.get_color("fg_primary")
        in_bg = theme.get_color("input_bg")
        in_fg = theme.get_color("input_fg")

        pad_frame = tk.Frame(self, bg=bg_main, padx=14, pady=12)
        pad_frame.pack(fill=tk.BOTH, expand=True)

        top_row = tk.Frame(pad_frame, bg=bg_main)
        top_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(top_row, text=t("preset_name_label", "Имя пресета:"), font=theme.font(0, "bold"), fg=fg_pri, bg=bg_main).pack(side=tk.LEFT, padx=(0, 8))
        self.name_entry = tk.Entry(top_row, font=theme.font(1), bg=in_bg, fg=in_fg, relief=tk.SOLID, bd=1)
        self.name_entry.insert(0, "" if self.is_new else self.preset_name)
        if not self.is_new and self.preset_name == "default":
            self.name_entry.config(state="disabled")
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        attach_entry_context_menu(self.name_entry)

        helper_row = tk.Frame(pad_frame, bg=bg_main)
        helper_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(helper_row, text=t("preset_tag_label", "Быстрая вставка тега:"), font=theme.font(-1), fg=theme.get_color("fg_muted"), bg=bg_main).pack(side=tk.LEFT, padx=(0, 6))
        btn_tag = tk.Button(
            helper_row, text=t("preset_btn_tag", "+ {TARGET_LANG}"), font=theme.font(-1, "bold"), relief=tk.FLAT,
            bg=theme.get_color("help_btn_bg"), fg=theme.get_color("help_btn_fg"), cursor="hand2", padx=6, pady=1,
            command=lambda: self.text_area.insert(tk.INSERT, "{TARGET_LANG}")
        )
        btn_tag.pack(side=tk.LEFT, padx=2)
        ToolTip(btn_tag, t("preset_tag_tooltip", "Вставить тег целевого языка перевода (например: русский, английский)"))

        btn_row = tk.Frame(pad_frame, bg=bg_main)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        if not self.is_new and self.preset_name != "default":
            tk.Button(
                btn_row, text=t("preset_btn_delete", "Удалить пресет"), font=theme.font(0), relief=tk.FLAT,
                bg="#ffebee", fg="#c62828", cursor="hand2", padx=10, pady=4,
                command=self._on_delete
            ).pack(side=tk.LEFT)

        tk.Button(
            btn_row, text=t("btn_cancel", "Отмена"), font=theme.font(0), relief=tk.FLAT,
            bg=theme.get_color("btn_bg"), fg=fg_pri, padx=14, pady=4, cursor="hand2",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Button(
            btn_row, text=t("preset_btn_save", "Сохранить"), font=theme.font(0, "bold"), relief=tk.FLAT,
            bg=theme.get_color("accent"), fg=theme.get_color("accent_text"),
            cursor="hand2", padx=16, pady=4, command=self._on_save
        ).pack(side=tk.RIGHT)

        text_frame = tk.Frame(pad_frame, relief=tk.SOLID, bd=1)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        self.text_area = tk.Text(text_frame, font=theme.font(1), bg=in_bg, fg=in_fg, wrap=tk.WORD, bd=0, padx=8, pady=8)
        sb = tk.Scrollbar(text_frame, command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attach_text_context_menu(self.text_area)

        initial_text = preset_manager.get_preset_text(self.service_id, self.preset_name)
        self.text_area.insert("1.0", initial_text)

    def _on_save(self):
        name = self.name_entry.get().strip()
        content = self.text_area.get("1.0", tk.END).strip()
        if not name:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("preset_warn_fill_name", "Пожалуйста, укажите название пресета."), parent=self)
            return
        if not content:
            messagebox.showwarning(t("btn_settings", "Внимание"), t("preset_warn_fill_content", "Промпт пресета не может быть пустым."), parent=self)
            return

        preset_manager.save_preset(self.service_id, name, content)
        config.set_active_preset(self.service_id, name)
        if self.on_saved_callback:
            self.on_saved_callback(name)
        messagebox.showinfo("OK", t("preset_saved_msg", "Пресет '{name}' успешно сохранен!", name=name), parent=self)
        self.destroy()

    def _on_delete(self):
        msg = t("preset_delete_confirm_msg", "Вы уверены, что хотите удалить пресет '{name}'?", name=self.preset_name)
        if messagebox.askyesno(t("confirm_delete_title", "Подтверждение удаления"), msg, parent=self):
            preset_manager.delete_preset(self.service_id, self.preset_name)
            config.set_active_preset(self.service_id, "default")
            if self.on_saved_callback:
                self.on_saved_callback("default")
            self.destroy()