# -*- coding: utf-8 -*-
# clean_project_comments.py
"""
Автономный скрипт очистки проекта от комментариев и docstrings.
Сохраняет пути файлов в первой строке для сохранения контекста.
Совместимость: Pure Python 3.8+ / Windows 7, 8, 10, 11 (0 pip-зависимостей)
"""

import os
import sys
import ast
import tokenize
import io

# Настройка кодировки консоли для Windows 7
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EXCLUDE_DIRS = {
    ".git", "__pycache__", "browser", "bin", "models", 
    ".idea", ".vscode", "venv", "env"
}

class DocstringFinder(ast.NodeVisitor):
    def __init__(self):
        # Список кортежей: (start_line, end_line, is_only_statement, col_offset)
        self.docstrings = []

    def _check_body(self, body):
        if not body:
            return
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                s_line = first.lineno
                e_line = getattr(first, "end_lineno", first.lineno)
                is_only = len(body) == 1
                col = first.col_offset
                self.docstrings.append((s_line, e_line, is_only, col))

    def visit_Module(self, node):
        self._check_body(node.body)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._check_body(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_body(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_body(node.body)
        self.generic_visit(node)

def get_base_project_dir():
    """Определяет корень проекта (ищет data или Services)."""
    current = os.path.abspath(os.path.dirname(__file__))
    if os.path.exists(os.path.join(current, "data")) or os.path.exists(os.path.join(current, "Services")):
        return current
    parent = os.path.dirname(current)
    if os.path.exists(os.path.join(parent, "data")) or os.path.exists(os.path.join(parent, "Services")):
        return parent
    return current

def clean_python_code(source, rel_path):
    # 1. Поиск диапазонов строк docstring через AST
    try:
        tree = ast.parse(source)
        finder = DocstringFinder()
        finder.visit(tree)
        docstring_ranges = finder.docstrings
    except Exception:
        docstring_ranges = []

    # 2. Поиск строк комментариев через токенизатор
    comment_positions = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        for tok in tokens:
            if tok[0] == tokenize.COMMENT:
                s_row, s_col = tok[2]
                e_row, e_col = tok[3]
                comment_positions.append((s_row, s_col, e_row, e_col))
    except Exception:
        pass

    raw_lines = source.splitlines()
    processed_lines = []

    # Создаем карту строк docstrings: номер строки -> действие
    doc_lines_map = {}
    for s_line, e_line, is_only, col in docstring_ranges:
        for l in range(s_line, e_line + 1):
            if l == s_line and is_only:
                doc_lines_map[l] = ("pass", col)
            else:
                doc_lines_map[l] = ("skip", col)

    # Карта строчных комментариев
    comment_map = {}
    for s_row, s_col, e_row, e_col in comment_positions:
        comment_map[s_row] = s_col

    for i, line in enumerate(raw_lines, start=1):
        # Если строка внутри docstring
        if i in doc_lines_map:
            action, col = doc_lines_map[i]
            if action == "pass":
                processed_lines.append(" " * col + "pass")
            continue

        # Если в строке есть комментарий #
        if i in comment_map:
            col = comment_map[i]
            code_part = line[:col].rstrip()
            if code_part:
                processed_lines.append(code_part)
            continue

        processed_lines.append(line.rstrip())

    # Сжатие множественных пустых строк
    compact = []
    blank_counter = 0
    for l in processed_lines:
        if not l.strip():
            blank_counter += 1
            if blank_counter <= 1:
                compact.append("")
        else:
            blank_counter = 0
            compact.append(l)

    while compact and not compact[0]:
        compact.pop(0)

    header = [
        "# -*- coding: utf-8 -*-",
        f"# {rel_path}"
    ]

    return "\n".join(header + compact) + "\n"

def clean_javascript_code(source, rel_path):
    lines = source.splitlines()
    result = []
    in_block = False

    for line in lines:
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            if "*/" not in s:
                in_block = True
            continue
        if s.startswith("//"):
            continue

        # Отрезаем комментарий в конце строки
        if "//" in line:
            idx = line.find("//")
            line = line[:idx]

        if line.strip():
            result.append(line.rstrip())
        else:
            if result and result[-1] != "":
                result.append("")

    while result and not result[0]:
        result.pop(0)

    header = [f"// {rel_path}"]
    return "\n".join(header + result) + "\n"

def main():
    root = get_base_project_dir()
    print("=" * 60)
    print("QTranslate AI Hub: Очистка комментариев и сжатие контекста")
    print(f"Целевая директория: {root}")
    print("=" * 60)

    processed_count = 0
    total_freed_bytes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".py", ".js"):
                continue

            if fname == "clean_project_comments.py":
                continue

            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root).replace("\\", "/")

            # Чтение
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                try:
                    with open(full_path, "r", encoding="cp1251") as f:
                        content = f.read()
                except Exception:
                    continue

            orig_size = len(content.encode("utf-8"))

            if ext == ".py":
                cleaned = clean_python_code(content, rel_path)
            else:
                cleaned = clean_javascript_code(content, rel_path)

            new_size = len(cleaned.encode("utf-8"))
            saved = orig_size - new_size

            # Запись при наличии экономии
            if saved > 0:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(cleaned)
                processed_count += 1
                total_freed_bytes += saved
                print(f"Очищен: {rel_path}  (-{saved} байт)")

    print("=" * 60)
    print("Результат работы:")
    print(f"Обработано файлов: {processed_count}")
    print(f"Сэкономлено байт: {total_freed_bytes} (~{total_freed_bytes // 4} токенов)")
    print("=" * 60)
    input("\nНажмите Enter для завершения...")

if __name__ == "__main__":
    main()