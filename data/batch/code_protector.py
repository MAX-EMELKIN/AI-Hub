# -*- coding: utf-8 -*-
"""
Модуль: data/batch/code_protector.py
Назначение: Экранирование и восстановление программного кода, игровых тегов, переменных и разметки.
Совместимость: Python 3.8+ / Windows 7, 8, 10, 11
"""

import re

class CodeProtector:
    """Модуль защиты переменных, тегов и кода от изменения нейросетью."""

    def __init__(self):
        # Регулярные выражения для поиска непереводимых сущностей
        self.patterns = [
            # 1. Многострочные блоки кода Markdown: ```...```
            r'```[\s\S]*?```',
            # 2. Инлайн-код Markdown: `...`
            r'`[^`\r\n]+`',
            # 3. Веб-ссылки и URL: https://... или http://...
            r'https?://[^\s<>"\)\]]+',
            # 4. Игровые теги и теги диалогов (Skyrim, Fallout, Unreal, Unity): <Alias=Player>, <Global=...>, </font>
            r'</?[A-Za-z0-9_]+(?:\s*=\s*[^>]+)?>',
            # 5. Спецификаторы формата строк: %s, %d, %1.2f, %02d, {0}, {name}, {$var}
            r'%[0-9]*\.?[0-9]*[sdifoxXb]',
            r'\{[0-9A-Za-z_$\.\-]+\}',
            r'\$[A-Za-z_][A-Za-z0-9_]*',
            # 6. Служебные спецсимволы экранирования: \n, \t, \r
            r'\\[nrt]'
        ]
        self.master_regex = re.compile('|'.join(f'({p})' for p in self.patterns))

    def mask(self, text):
        """
        Находит весь код и теги в тексте, заменяет их токенами [[__CODE_01__]].
        Возвращает: (masked_text, tokens_dict)
        """
        if not text:
            return text, {}

        tokens = {}
        token_counter = 1

        def _replacer(match):
            nonlocal token_counter
            matched_str = match.group(0)
            token_name = f"[[__CODE_{token_counter:03d}__]]"
            tokens[token_name] = matched_str
            token_counter += 1
            return token_name

        masked_text = self.master_regex.sub(_replacer, text)
        return masked_text, tokens

    def restore(self, translated_text, tokens):
        """
        Возвращает оригинальные теги и код на свои места в переведенном тексте.
        Устойчив к добавлению нейросетью случайных пробелов внутри скобок токена.
        """
        if not translated_text or not tokens:
            return translated_text

        restored_text = translated_text

        for token_name, original_val in tokens.items():
            # Извлекаем внутренний ID (например, CODE_001)
            raw_id = token_name.strip("[]")
            
            # Гибкий регекс: на случай если модель написала "[[ CODE_001 ]]" или "[ [__CODE_001__] ]"
            flexible_pattern = r'\[\s*\[\s*' + re.escape(raw_id) + r'\s*\]\s*\]'
            
            # Если токен найден через гибкий поиск
            if re.search(flexible_pattern, restored_text):
                restored_text = re.sub(flexible_pattern, lambda _: original_val, restored_text)
            else:
                # Прямая замена
                restored_text = restored_text.replace(token_name, original_val)

        return restored_text


# Глобальный экземпляр для вызова из любого модуля
code_protector = CodeProtector()