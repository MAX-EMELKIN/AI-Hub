# -*- coding: utf-8 -*-
"""
Модуль: data/gui/dialogs.py
Назначение: Компактный фасадный модуль графических диалогов Хаба.
            Реэкспортирует классы и виджеты из модульных файлов (dialog_helpers,
            wizard_dialog, ocr_dialog, preset_dialog, service_settings_dialog),
            обеспечивая 100% обратную совместимость со всеми модулями проекта.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64, 0 pip-зависимостей)
"""

from data.gui.dialog_helpers import (
    HelpPopup,
    ToolTip,
    attach_entry_context_menu,
    attach_text_context_menu
)

from data.gui.wizard_dialog import (
    AddServiceWizardDialog,
    WIZARD_HELP_FALLBACK
)

from data.gui.ocr_dialog import (
    OCRSettingsDialog
)

from data.gui.preset_dialog import (
    PresetEditorDialog
)

from data.gui.service_settings_dialog import (
    ServiceSettingsDialog,
    DOH_PRESET_KEYS,
    GEMINI_MODELS_LIST
)

__all__ = [
    "HelpPopup",
    "ToolTip",
    "attach_entry_context_menu",
    "attach_text_context_menu",
    "AddServiceWizardDialog",
    "WIZARD_HELP_FALLBACK",
    "OCRSettingsDialog",
    "PresetEditorDialog",
    "ServiceSettingsDialog",
    "DOH_PRESET_KEYS",
    "GEMINI_MODELS_LIST"
]