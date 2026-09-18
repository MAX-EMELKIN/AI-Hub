# -*- coding: utf-8 -*-
# data/gui/dialogs.py
from data .gui .dialog_helpers import (
HelpPopup ,
ToolTip ,
attach_entry_context_menu ,
attach_text_context_menu
)

from data .gui .wizard_dialog import (
AddServiceWizardDialog ,
WIZARD_HELP_FALLBACK
)

from data .gui .ocr_dialog import (
OCRSettingsDialog
)

from data .gui .preset_dialog import (
PresetEditorDialog
)

from data .gui .service_settings_dialog import (
ServiceSettingsDialog ,
DOH_PRESET_KEYS ,
GEMINI_MODELS_LIST
)

__all__ =[
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
