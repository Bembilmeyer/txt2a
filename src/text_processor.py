"""
Обработка и сегментация текста для синтеза
"""
import re
from typing import List


def split_into_chunks(text: str, max_chars: int = 350) -> List[str]:
    """Разбивает текст на чанки подходящего размера"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current += " " + sentence if current else sentence
        else:
            if current:
                chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return chunks


def add_ssml_pauses(text: str, pause_ms: int = 400) -> str:
    """Добавляет паузы между абзацами (простая версия)"""
    paragraphs = text.split('\n\n')
    return f'<break time="{pause_ms}ms"/>'.join(paragraphs)