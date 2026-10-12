"""
Обработка и сегментация текста для синтеза
"""
import re
from dataclasses import dataclass
from typing import List

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+')
_PARAGRAPH_SPLIT = re.compile(r'\n\s*\n+')
# Запасные точки разрыва для предложений, которые сами длиннее лимита
_SOFT_BREAK = re.compile(r'(?<=[,;:—])\s+')

# Чанк без букв и цифр синтезировать нечего — одни кавычки или звёздочки
_HAS_SPEECH = re.compile(r'[\w\d]', re.UNICODE)


@dataclass
class Chunk:
    """Фрагмент текста для синтеза и пауза после него"""
    text: str
    pause_after_ms: int = 0


def _hard_split(text: str, max_chars: int) -> List[str]:
    """Режет слишком длинное предложение по запятым, затем по словам"""
    if len(text) <= max_chars:
        return [text]

    parts = []
    for piece in _SOFT_BREAK.split(text):
        if len(piece) <= max_chars:
            parts.append(piece)
            continue

        # Последний рубеж: по словам, чтобы не разорвать слово посередине
        current = ""
        for word in piece.split():
            if current and len(current) + len(word) + 1 > max_chars:
                parts.append(current)
                current = word
            else:
                current = f"{current} {word}" if current else word
        if current:
            parts.append(current)

    return parts


def split_into_chunks(
    text: str,
    max_chars: int = 350,
    max_sentence_length: int = 400,
    pause_between_paragraphs: int = 0,
) -> List[Chunk]:
    """
    Разбивает текст на чанки, сохраняя границы абзацев.

    Абзацы обрабатываются по отдельности, поэтому чанк никогда не склеивает
    конец одного абзаца с началом другого — на этих стыках проставляется пауза.
    """
    chunks: List[Chunk] = []

    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = ' '.join(paragraph.split())
        if not paragraph or not _HAS_SPEECH.search(paragraph):
            continue

        sentences = []
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            if sentence.strip():
                sentences.extend(_hard_split(sentence.strip(), max_sentence_length))

        paragraph_chunks: List[str] = []
        current = ""

        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                paragraph_chunks.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}" if current else sentence

        if current:
            paragraph_chunks.append(current)

        if not paragraph_chunks:
            continue

        chunks.extend(Chunk(text=c) for c in paragraph_chunks)
        chunks[-1].pause_after_ms = pause_between_paragraphs

    return chunks
