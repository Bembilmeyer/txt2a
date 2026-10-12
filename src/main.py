"""
Главный скрипт конвертации книг в аудиокниги
"""
import sys
from pathlib import Path
from typing import List

import yaml
from tqdm import tqdm

from audio_postprocess import (
    FFmpegNotFound,
    concatenate_wavs,
    encode_audiobook,
    find_ffmpeg,
    wav_duration_sec,
)
from silero_tts import SileroTTS
from text_extractor import clean_text, extract_chapters
from text_processor import Chunk, split_into_chunks

# Корень проекта — родитель папки src. Все пути из config.yaml считаются
# относительно него, поэтому скрипт можно запускать из любой директории.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SUPPORTED_FORMATS = ('.epub', '.txt', '.fb2')


def load_config(config_path: Path) -> dict:
    """Читает config.yaml"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def resolve_path(raw: str) -> Path:
    """Приводит путь из конфига к абсолютному относительно корня проекта"""
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_chunks(book_path: Path, config: dict) -> List[Chunk]:
    """Книга -> плоский список чанков с паузами на границах абзацев и глав"""
    processing = config['processing']
    chapters = extract_chapters(book_path)
    print(f"Глав найдено: {len(chapters)}")

    chunks: List[Chunk] = []

    for chapter_text in chapters:
        chapter_chunks = split_into_chunks(
            clean_text(chapter_text),
            max_chars=processing['chunk_size'],
            max_sentence_length=processing['max_sentence_length'],
            pause_between_paragraphs=processing['pause_between_paragraphs'],
        )
        if not chapter_chunks:
            continue

        # Пауза между главами перебивает паузу между абзацами на том же стыке
        chapter_chunks[-1].pause_after_ms = processing['pause_between_chapters']
        chunks.extend(chapter_chunks)

    return chunks


def synthesize_chunks(chunks: List[Chunk], tts: SileroTTS, temp_dir: Path):
    """Синтезирует чанки в WAV, возвращает файлы и паузы после них"""
    temp_dir.mkdir(parents=True, exist_ok=True)

    wav_files, pauses = [], []
    failed = 0

    for i, chunk in enumerate(tqdm(chunks, desc="Синтез", unit="чанк")):
        wav_path = temp_dir / f"chunk_{i:05d}.wav"

        # Готовый чанк не синтезируем заново: на книге в несколько тысяч
        # чанков это превращает прерванный запуск в продолжаемый.
        if wav_path.exists() and wav_path.stat().st_size > 44:
            ok = True
        else:
            ok = tts.synthesize(chunk.text, wav_path)

        if ok:
            wav_files.append(wav_path)
            pauses.append(chunk.pause_after_ms)
        else:
            failed += 1

    if failed:
        print(f"Не синтезировано чанков: {failed} из {len(chunks)}")

    return wav_files, pauses


def process_book(book_path: Path, config: dict, tts: SileroTTS):
    """Обрабатывает одну книгу"""
    print(f"\n=== Обработка: {book_path.name} ===")

    chunks = build_chunks(book_path, config)
    if not chunks:
        print("В книге не найдено текста для синтеза, пропускаю")
        return

    total_chars = sum(len(c.text) for c in chunks)
    print(f"Чанков: {len(chunks)}, символов: {total_chars}")

    temp_dir = resolve_path(config['paths']['temp_dir']) / book_path.stem
    wav_files, pauses = synthesize_chunks(chunks, tts, temp_dir)

    if not wav_files:
        print("Ни один чанк не синтезирован, итоговый файл не создан")
        return

    # Склейка в промежуточный WAV без потерь — кодируем уже целое
    merged_wav = temp_dir / '_merged.wav'
    concatenate_wavs(wav_files, merged_wav, pauses)

    duration = wav_duration_sec(merged_wav)
    print(f"Длительность: {duration / 3600:.2f} ч ({duration:.0f} с)")

    output_config = config['output']
    output_dir = resolve_path(config['paths']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)

    fmt = output_config['format'].lower()
    final_file = output_dir / f"{book_path.stem}.{fmt}"

    if fmt == 'wav':
        merged_wav.replace(final_file)
        print(f"Готово: {final_file}")
        return

    encode_audiobook(
        merged_wav,
        final_file,
        bitrate=output_config['bitrate'],
        normalize=output_config['normalize'],
        remove_silence=output_config['remove_silence'],
        speed=config['tts']['speed'],
        title=book_path.stem,
    )

    size_mb = final_file.stat().st_size / 1024 / 1024
    print(f"Готово: {final_file} ({size_mb:.1f} МБ)")


def main():
    # На Windows stdout берёт кодировку из консоли, и перенаправление вывода
    # в файл ломает русские сообщения. Просим UTF-8 явно.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    config = load_config(PROJECT_ROOT / 'config.yaml')

    books_dir = resolve_path(config['paths']['books_dir'])
    if not books_dir.is_dir():
        sys.exit(f"Папка с книгами не найдена: {books_dir}")

    books = sorted(
        b for b in books_dir.iterdir()
        if b.is_file() and b.suffix.lower() in SUPPORTED_FORMATS
    )

    if not books:
        sys.exit(f"В {books_dir} нет книг форматов {', '.join(SUPPORTED_FORMATS)}")

    # Проверяем ffmpeg до синтеза: обидно узнать о его отсутствии
    # через сорок минут работы, на этапе кодирования.
    if config['output']['format'].lower() != 'wav' and find_ffmpeg() is None:
        sys.exit(
            "ffmpeg не найден в PATH, а output.format требует кодирования.\n"
            "Установи ffmpeg (winget install Gyan.FFmpeg) и перезапусти терминал,\n"
            "либо поставь output.format: wav в config.yaml."
        )

    print(f"Книг к обработке: {len(books)}")

    # Модель весит 145 МБ и грузится небыстро — один экземпляр на все книги
    tts = SileroTTS(
        config=config,
        model_dir=resolve_path('models'),
    )

    for book in books:
        try:
            process_book(book, config, tts)
        except (ValueError, FFmpegNotFound, RuntimeError) as e:
            print(f"Ошибка при обработке {book.name}: {e}")


if __name__ == "__main__":
    main()
