"""
Извлечение текста из книг (EPUB, FB2, TXT)
"""
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re
from pathlib import Path


def extract_text_from_epub(file_path: Path) -> str:
    """Извлекает текст из EPUB"""
    book = epub.read_epub(str(file_path))
    chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(separator='\n')
            chapters.append(text)

    return '\n\n'.join(chapters)


def extract_text_from_txt(file_path: Path) -> str:
    """Извлекает текст из TXT"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_text(file_path: Path) -> str:
    """Универсальная функция извлечения текста"""
    suffix = file_path.suffix.lower()

    if suffix == '.epub':
        return extract_text_from_epub(file_path)
    elif suffix == '.txt':
        return extract_text_from_txt(file_path)
    elif suffix == '.fb2':
        # Простая обработка FB2 (можно улучшить)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'xml')
        return soup.get_text(separator='\n')
    else:
        raise ValueError(f"Неподдерживаемый формат: {suffix}")


def clean_text(text: str) -> str:
    """Базовая очистка текста"""
    # Удаляем лишние пробелы и переносы
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()