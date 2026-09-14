# -*- coding: utf-8 -*-
"""
Модуль: data/presets/preset_manager.py
Назначение: Управление изолированными пресетами промптов для каждого сервиса отдельно.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11
"""

import os
import sys

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))

DEFAULT_PRESETS_DATA = {
    "default": (
        "Сделай профессиональный перевод на {TARGET_LANG} с точной передачей стиля оригинала.\n"
        "ПРАВИЛА:\n"
        "1. Стиль и мимикрия: точно воспроизводи стиль, регистр и тональность источника.\n"
        "2. Терминология: устоявшиеся официальные термины пиши на целевом языке, уникальные бренды без перевода — в оригинале (без скобок с дублированием)."
    ),
    "games": (
        "Ты — профессиональный локализатор видеоигр. Сделай живой и атмосферный перевод на {TARGET_LANG}.\n"
        "ПРАВИЛА:\n"
        "1. Живая речь: переводи диалоги персонажей естественно. Если в оригинале есть игровой сленг, грубость, ругань или юмор — смело и сочно адаптируй их под колорит целевого языка.\n"
        "2. Игровой лор: сохраняй общепринятые игровые названия локаций, предметов и рас.\n"
        "3. Без цензуры и стерильности: сохраняй характер и интонацию говорящего персонажа."
    ),
    "academic": (
        "Сделай строгий технический/академический перевод на {TARGET_LANG}.\n"
        "ПРАВИЛА:\n"
        "1. Академический регистр: соблюдай нейтральный научный стиль. Никакого сленга, фамильярности или просторечий.\n"
        "2. Точность терминов: используй общепринятые государственные и отраслевые стандарты терминологии.\n"
        "3. Структурная строгость: точно передавай причинно-следственные связи и логические конструкции."
    ),
    "literary": (
        "Ты — профессиональный художественный переводчик и писатель. Переведи этот литературный текст на {TARGET_LANG}.\n"
        "ПРАВИЛА:\n"
        "1. Художественность: используй богатый словарный запас, выразительные метафоры и красивый литературный слог.\n"
        "2. Эмоциональность: передавай атмосферу сцены, напряжение и чувства персонажей.\n"
        "3. Избегай канцеляризмов и сухого подстрочника — текст должен читаться как качественная книга."
    ),
    "code": (
        "Сделай перевод текста для программистов и IT-специалистов на {TARGET_LANG}.\n"
        "ПРАВИЛА:\n"
        "1. Не переводи синтаксис языков программирования, имена функций, переменных (camelCase, snake_case), команды терминала и пути к файлам.\n"
        "2. Переводи только комментарии, описания, документацию и сообщения об ошибках.\n"
        "3. Терминологию разработки пиши общепринятым языком разработчиков."
    )
}

class PresetManager:
    """Менеджер изолированных пресетов для каждого сервиса."""

    def __init__(self):
        self.base_dir = get_base_dir()
        self.presets_root = os.path.join(self.base_dir, "data", "presets")
        os.makedirs(self.presets_root, exist_ok=True)

    def _get_service_dir(self, service_id):
        s_id = str(service_id).lower().strip().replace("/", "")
        s_dir = os.path.join(self.presets_root, s_id)
        os.makedirs(s_dir, exist_ok=True)
        return s_dir

    def ensure_service_presets(self, service_id):
        """Создает дефолтный набор пресетов для сервиса, если его папка пуста."""
        s_dir = self._get_service_dir(service_id)
        for name, text in DEFAULT_PRESETS_DATA.items():
            f_path = os.path.join(s_dir, f"{name}.txt")
            if not os.path.exists(f_path):
                try:
                    with open(f_path, "w", encoding="utf-8") as f:
                        f.write(text.strip())
                except Exception: pass

    def get_presets_for_service(self, service_id):
        """Возвращает список всех доступных пресетов для КОНКРЕТНОГО сервиса."""
        self.ensure_service_presets(service_id)
        s_dir = self._get_service_dir(service_id)
        
        presets = set()
        for item in os.listdir(s_dir):
            if item.lower().endswith(".txt"):
                presets.add(item[:-4])

        for base in DEFAULT_PRESETS_DATA.keys():
            presets.add(base)

        sorted_list = sorted([p for p in presets if p != "default"])
        return ["default"] + sorted_list

    def get_preset_text(self, service_id, preset_name):
        """Загружает текст пресета из изолированной папки сервиса."""
        s_dir = self._get_service_dir(service_id)
        p_path = os.path.join(s_dir, f"{preset_name}.txt")
        
        if os.path.exists(p_path):
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content: return content
            except Exception: pass

        # Fallback на базовый текст и сохранение в папку сервиса
        default_content = DEFAULT_PRESETS_DATA.get(preset_name, DEFAULT_PRESETS_DATA["default"])
        try:
            with open(p_path, "w", encoding="utf-8") as f:
                f.write(default_content.strip())
        except Exception: pass
        return default_content

    def save_preset(self, service_id, preset_name, content):
        """Сохраняет пресет СТРОГО в папку конкретного сервиса."""
        s_dir = self._get_service_dir(service_id)
        p_path = os.path.join(s_dir, f"{preset_name}.txt")
        try:
            with open(p_path, "w", encoding="utf-8") as f:
                f.write(content.strip())
            return True
        except Exception as e:
            print(f"[PresetManager Error]: Не удалось сохранить пресет '{preset_name}' для '{service_id}': {e}")
            return False

    def delete_preset(self, service_id, preset_name):
        """Удаляет пресет только у конкретного сервиса."""
        if preset_name == "default":
            return False

        s_dir = self._get_service_dir(service_id)
        p_path = os.path.join(s_dir, f"{preset_name}.txt")
        if os.path.exists(p_path):
            try:
                os.remove(p_path)
                return True
            except Exception: pass
        return False

    def _ensure_default_presets(self):
        """Инициализация базовых сервисов."""
        for s_id in ["google_ai", "deepseek_flash", "openai_120b", "tencent_hy3", "qwen_orca"]:
            self.ensure_service_presets(s_id)

preset_manager = PresetManager()