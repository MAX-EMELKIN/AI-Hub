# data/dictionary/glossary_engine.py
import os
import sys
import re
import threading


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", ".."))


SAMPLE_GLOSSARY = """# =============================================================================
# Пользовательский словарь терминов (Глоссарий)
# Формат: Оригинальное слово/фраза = Перевод
# Строки с решеткой # или // считаются комментариями
# =============================================================================
Sweetroll = Сладкий рулет
Lockpick = Отмычка
Power Armor = Силовая броня
Stealth Boy = Стелс-бой
Pip-Boy = Пип-бой
Stimpak = Стимулятор
RadAway = Антирадин
V.A.T.S. = ВАТС
Nuka-Cola = Ядер-Кола
"""


class GlossaryEngine:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.dict_dir = os.path.join(self.base_dir, "data", "dictionary")
        self.glossary_file = os.path.join(self.dict_dir, "glossary.txt")
        self.terms = {}
        self._lock = threading.Lock()
        self._ensure_file_exists()
        self.reload()

    def _ensure_file_exists(self):
        try:
            if not os.path.exists(self.dict_dir):
                os.makedirs(self.dict_dir, exist_ok=True)
            if not os.path.exists(self.glossary_file):
                with open(self.glossary_file, "w", encoding="utf-8") as f:
                    f.write(SAMPLE_GLOSSARY)
        except Exception:
            pass

    @staticmethod
    def parse_raw_text(raw_text):
        parsed = {}
        if not raw_text:
            return parsed

        sep_pattern = re.compile(r'\s*(?:=|->|➔|—|–|\t|;|\||:)\s*')
        lang_boundary_ltr = re.compile(
            r'^([A-Za-z0-9\s\'\-\.\(\)\/\[\]\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+?)\s{1,}([\u0400-\u04FF].*)$'
        )
        lang_boundary_rtl = re.compile(
            r'^([\u0400-\u04FF\s\'\-\.\(\)\/\[\]]+?)\s{1,}([A-Za-z0-9\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af].*)$'
        )

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            parts = sep_pattern.split(line, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                k = parts[0].strip()
                v = parts[1].strip()
                parsed[k] = v
                continue

            m1 = lang_boundary_ltr.match(line)
            if m1:
                k = m1.group(1).strip()
                v = m1.group(2).strip()
                if k and v:
                    parsed[k] = v
                    continue

            m2 = lang_boundary_rtl.match(line)
            if m2:
                k = m2.group(1).strip()
                v = m2.group(2).strip()
                if k and v:
                    parsed[k] = v
                    continue

        return parsed

    def reload(self):
        with self._lock:
            self.terms = {}
            if not os.path.exists(self.glossary_file):
                return
            raw_text = ""
            try:
                with open(self.glossary_file, "r", encoding="utf-8") as f:
                    raw_text = f.read()
            except Exception:
                try:
                    with open(self.glossary_file, "r", encoding="cp1251") as f:
                        raw_text = f.read()
                except Exception:
                    return

            self.terms = self.parse_raw_text(raw_text)

    def is_enabled(self):
        try:
            from data.core.config_manager import config
            return config.get_bool("DICTIONARY", "Enabled", True)
        except Exception:
            return True

    def inject_hints(self, source_text):
        if not self.is_enabled() or not self.terms or not source_text:
            return source_text, ""

        matched_count = 0
        annotated_text = source_text
        sorted_keys = sorted(self.terms.keys(), key=len, reverse=True)

        for term in sorted_keys:
            target_translation = self.terms[term]
            term_escaped = re.escape(term)
            if re.match(r'^[A-Za-z0-9\s\-_]+$', term):
                pattern = r'(?i)\b(' + term_escaped + r"(?:s|es|'s|’s|ed|ing)?)\b(?!\s*\[\[__GLOSS:)"
            else:
                pattern = r'(?i)\b(' + term_escaped + r')\b(?!\s*\[\[__GLOSS:)'

            def _replacer(m):
                nonlocal matched_count
                matched_count += 1
                orig_word = m.group(1)
                return f"{orig_word} [[__GLOSS:{target_translation}__]]"

            annotated_text = re.sub(pattern, _replacer, annotated_text)

        if matched_count == 0:
            return source_text, ""

        glossary_prompt_rule = (
            "ОБЯЗАТЕЛЬНОЕ ПРАВИЛО ГЛОССАРИЯ (ПОЛЬЗОВАТЕЛЬСКИЙ СЛОВАРЬ ТЕРМИНОВ):\n"
            "В исходном тексте некоторые термины размечены специальными подсказками вида [[__GLOSS:Нужный_Перевод__]].\n"
            "1. Точность терминологии: ты ОБЯЗАН использовать для слова именно тот перевод, который указан внутри метки [[__GLOSS:...__]], "
            "категорически запрещено заменять его синонимами или альтернативными вариантами! Это строгий отраслевой глоссарий.\n"
            "2. Грамматическая адаптация (склонение по падежам):\n"
            "   Слово внутри метки [[__GLOSS:...__]] приведено в базовой начальной форме (именительный падеж).\n"
            "   Ты ОБЯЗАН согласовать его род, число и падеж в контексте твоего перевода предложения!\n"
            "   Пример: если в тексте 'he found a magic apple [[__GLOSS:Сладкий рулет__]]', то слово 'рулет' должно стоять в винительном падеже, "
            "то есть переводи 'он нашел сладкий рулет', а не 'he has no magic apple [[__GLOSS:Сладкий рулет__]]' -> 'у него нет сладкого рулета'.\n"
            "3. Полная очистка: сами метки [[__GLOSS:...__]] НЕ ДОЛЖНЫ присутствовать в готовом тексте — удали их без следа!"
        )

        return annotated_text, glossary_prompt_rule

    def get_all_terms(self):
        with self._lock:
            return dict(self.terms)

    def save_all_terms(self, terms_dict):
        with self._lock:
            self.terms = dict(terms_dict)
            try:
                with open(self.glossary_file, "w", encoding="utf-8") as f:
                    f.write("# Пользовательский словарь терминов (Глоссарий)\n\n")
                    for k, v in sorted(self.terms.items(), key=lambda x: str(x[0]).lower()):
                        f.write(f"{k} = {v}\n")
                return True
            except Exception as e:
                print(f"[GlossaryEngine Error]: {e}")
                return False


glossary_engine = GlossaryEngine()