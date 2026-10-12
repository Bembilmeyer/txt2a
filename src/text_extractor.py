"""
Извлечение текста из книг (EPUB, FB2, TXT)
"""
import re
from pathlib import Path
from typing import List

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

# Кодировки по убыванию вероятности для русскоязычных книг
_ENCODINGS = ('utf-8-sig', 'utf-8', 'cp1251', 'koi8-r')


def _read_text_guess_encoding(file_path: Path) -> str:
    """Читает текстовый файл, подбирая кодировку"""
    raw = file_path.read_bytes()

    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Последний шанс: читаем с заменой нечитаемых байтов, чтобы книга
    # в неизвестной кодировке дала хоть что-то, а не исключение.
    print(f"  Кодировка {file_path.name} не распознана, читаю с потерями")
    return raw.decode('utf-8', errors='replace')


def extract_chapters_from_epub(file_path: Path) -> List[str]:
    """Извлекает главы из EPUB в порядке чтения"""
    book = epub.read_epub(str(file_path))

    documents = {
        item.get_id(): item
        for item in book.get_items()
        if item.get_type() == ebooklib.ITEM_DOCUMENT
        and not isinstance(item, epub.EpubNav)
    }

    # Порядок чтения задаётся spine, а не порядком файлов в архиве:
    # get_items() легко выдаёт главы вперемешку.
    ordered = [documents[idref] for idref, _ in book.spine if idref in documents]
    if not ordered:
        ordered = list(documents.values())

    chapters = []
    for item in ordered:
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()

        text = soup.get_text(separator='\n')
        if text.strip():
            chapters.append(text)

    return chapters


def extract_chapters_from_fb2(file_path: Path) -> List[str]:
    """Извлекает главы из FB2"""
    # Читаем байтами: у FB2 кодировка объявлена внутри XML-пролога,
    # и очень часто это windows-1251, а не UTF-8.
    soup = BeautifulSoup(file_path.read_bytes(), 'xml')

    for tag in soup(['binary', 'description']):
        tag.decompose()

    body = soup.find('body')
    if body is None:
        return [soup.get_text(separator='\n')]

    # Только секции верхнего уровня: вложенные попали бы в текст дважды
    sections = body.find_all('section', recursive=False)
    if not sections:
        return [body.get_text(separator='\n')]

    return [s.get_text(separator='\n') for s in sections if s.get_text().strip()]


def extract_chapters(file_path: Path) -> List[str]:
    """Универсальная функция: книга -> список глав"""
    suffix = file_path.suffix.lower()

    if suffix == '.epub':
        return extract_chapters_from_epub(file_path)
    elif suffix == '.fb2':
        return extract_chapters_from_fb2(file_path)
    elif suffix == '.txt':
        # В плоском тексте границы глав не размечены — считаем книгу одной главой
        return [_read_text_guess_encoding(file_path)]
    else:
        raise ValueError(f"Неподдерживаемый формат: {suffix}")


def extract_text(file_path: Path) -> str:
    """Книга одной строкой (главы разделены пустой строкой)"""
    return '\n\n'.join(extract_chapters(file_path))


def clean_text(text: str) -> str:
    """Базовая очистка текста"""
    # Неразрывные пробелы и мягкие переносы ломают и разбиение, и синтез
    text = text.replace('\xa0', ' ').replace('\xad', '')
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
