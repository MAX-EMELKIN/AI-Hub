# -*- coding: utf-8 -*-
"""
Модуль: data/gui/tool_windows.py
Назначение: Фасад / реэкспорт окон инструментов для сохранения 100% обратной совместимости
            и избежания циклических импортов.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (x86 / x64)
"""

from data.gui.glossary_window import GlossaryWindow, GlossaryEnrichmentDialog, BatchGlossaryImportDialog
from data.gui.batch_window import BatchWindow
from data.gui.settings_window import SettingsWindow
from data.gui.chat_window import ChatWindow

__all__ = [
    "GlossaryWindow",
    "GlossaryEnrichmentDialog",
    "BatchGlossaryImportDialog",
    "BatchWindow",
    "SettingsWindow",
    "ChatWindow"
]